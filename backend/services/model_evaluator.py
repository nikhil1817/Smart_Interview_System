import os
from typing import Any, Dict, List

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


LABELS = [
    "clarity",
    "technical_depth",
    "structure_star",
    "relevance",
    "communication",
    "overall",
]


class ModelEvaluator:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.device = torch.device("cpu")
        configured = os.getenv("EVALUATOR_MODEL_PATH")
        if configured:
            self.model_path = configured
        else:
            artifacts_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modeling", "artifacts"))
            v2 = os.path.join(artifacts_root, "evaluator_v2")
            v1 = os.path.join(artifacts_root, "evaluator_v1")
            self.model_path = v2 if os.path.exists(v2) else v1

    def _build_input(
        self,
        answer: str,
        current_question: str = "",
        question_type: str = "",
        mode: str = "",
        role_target: str = "",
        interviewer_persona: str = "",
        resume_summary: str = "",
        conversation_context: List[Dict[str, str]] | None = None,
    ) -> str:
        context_lines = []
        for turn in (conversation_context or [])[-4:]:
            speaker = turn.get("speaker", "unknown")
            text = turn.get("text", "")
            context_lines.append(f"{speaker}: {text}")

        context_text = "\n".join(context_lines)
        return (
            f"Role: {role_target}\n"
            f"QuestionType: {question_type}\n"
            f"Mode: {mode}\n"
            f"Interviewer: {interviewer_persona}\n"
            f"ResumeSummary: {resume_summary}\n"
            f"ConversationContext:\n{context_text}\n"
            f"CurrentQuestion: {current_question}\n"
            f"CandidateAnswer: {answer}"
        )

    def _ensure_loaded(self) -> None:
        if self.model is not None and self.tokenizer is not None:
            return

        model_dir = os.path.abspath(self.model_path)
        if not os.path.exists(model_dir):
            raise FileNotFoundError(f"Evaluator model path not found: {model_dir}")

        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir)
        self.model.to(self.device)
        self.model.eval()

    def evaluate(
        self,
        answer: str,
        current_question: str = "",
        question_type: str = "",
        mode: str = "",
        role_target: str = "",
        interviewer_persona: str = "",
        resume_summary: str = "",
        conversation_context: List[Dict[str, str]] | None = None,
    ) -> Dict[str, Any]:
        if not answer or len(answer.strip()) < 2:
            return {
                "score": 0.0,
                "clarity": 0.0,
                "technical_depth": 0.0,
                "structure_star": 0.0,
                "relevance": 0.0,
                "communication": 0.0,
                "low_signal": True,
            }

        self._ensure_loaded()

        prompt = self._build_input(
            answer=answer,
            current_question=current_question,
            question_type=question_type,
            mode=mode,
            role_target=role_target,
            interviewer_persona=interviewer_persona,
            resume_summary=resume_summary,
            conversation_context=conversation_context,
        )

        with torch.no_grad():
            encoded = self.tokenizer(
                prompt,
                truncation=True,
                padding=True,
                max_length=512,
                return_tensors="pt",
            )
            encoded = {k: v.to(self.device) for k, v in encoded.items()}
            logits = self.model(**encoded).logits.squeeze(0).detach().cpu().tolist()

        if not isinstance(logits, list):
            logits = [float(logits)]

        # Trained labels are on a 0-10 scale. Clamp for stability.
        by_label = {}
        for i, label in enumerate(LABELS):
            value = float(logits[i]) if i < len(logits) else 0.0
            by_label[label] = max(0.0, min(10.0, value))

        return {
            "score": by_label["overall"],
            "clarity": by_label["clarity"] / 10.0,
            "technical_depth": by_label["technical_depth"] / 10.0,
            "structure_star": by_label["structure_star"] / 10.0,
            "relevance": by_label["relevance"] / 10.0,
            "communication": by_label["communication"] / 10.0,
            "low_signal": by_label["overall"] < 1.2,
            "raw_scores": by_label,
        }
