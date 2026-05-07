import json
import re
from typing import Any, Dict, List

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


class LLMCoach:
    def __init__(self, model_name: str = "google/flan-t5-small"):
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.device = torch.device("cpu")

    def _ensure_loaded(self) -> None:
        if self.model is not None and self.tokenizer is not None:
            return

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()

    def _generate_text(self, prompt: str, max_new_tokens: int = 220) -> str:
        self._ensure_loaded()
        encoded = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=768,
        )
        encoded = {k: v.to(self.device) for k, v in encoded.items()}

        with torch.no_grad():
            out = self.model.generate(
                **encoded,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                num_beams=4,
                length_penalty=1.0,
            )

        return self.tokenizer.decode(out[0], skip_special_tokens=True).strip()

    def _extract_json(self, text: str) -> Dict[str, Any] | None:
        if not text:
            return None

    def _extract_score_vector(self, text: str) -> List[float] | None:
        if not text:
            return None

        # Preferred format: 6 values separated by | characters.
        if "|" in text:
            raw = [p.strip() for p in text.split("|")]
            values = []
            for part in raw:
                match = re.search(r"-?\d+(?:\.\d+)?", part)
                if match:
                    values.append(float(match.group(0)))
            if len(values) >= 6:
                return values[:6]

        # Fallback: first 6 numeric tokens in output.
        values = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", text)]
        if len(values) >= 6:
            return values[:6]

        return None
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def evaluate_answer(
        self,
        role_target: str,
        question_type: str,
        mode: str,
        current_question: str,
        candidate_answer: str,
        conversation_context: List[Dict[str, str]] | None = None,
    ) -> Dict[str, Any]:
        context = "\n".join([f"{t.get('speaker', 'user')}: {t.get('text', '')}" for t in (conversation_context or [])[-4:]])
        prompt = (
            "You are an expert interview evaluator. Score the answer with precision. "
            "Return ONLY 6 numbers in this exact order separated by '|': "
            "clarity|technical_depth|structure_star|relevance|communication|overall. "
            "Each number must be from 0 to 10. No extra text.\n"
            f"Role: {role_target}\n"
            f"QuestionType: {question_type}\n"
            f"Mode: {mode}\n"
            f"CurrentQuestion: {current_question}\n"
            f"ConversationContext:\n{context}\n"
            f"CandidateAnswer: {candidate_answer}\n"
            "Scores:"
        )

        raw = self._generate_text(prompt, max_new_tokens=48)
        values = self._extract_score_vector(raw)
        if not values:
            raise ValueError(f"Could not parse evaluation scores: {raw}")

        def clamp_score(v: Any) -> float:
            try:
                return float(max(0.0, min(10.0, float(v))))
            except Exception:
                return 0.0

        by_label = {
            "clarity": clamp_score(values[0]),
            "technical_depth": clamp_score(values[1]),
            "structure_star": clamp_score(values[2]),
            "relevance": clamp_score(values[3]),
            "communication": clamp_score(values[4]),
            "overall": clamp_score(values[5]),
        }

        # Confidence estimate from score spread and overall magnitude.
        spread = max(by_label.values()) - min(by_label.values())
        confidence = max(0.2, min(0.95, 0.45 + (by_label["overall"] / 20.0) + (spread / 40.0)))

        return {
            "clarity": by_label["clarity"],
            "technical_depth": by_label["technical_depth"],
            "structure_star": by_label["structure_star"],
            "relevance": by_label["relevance"],
            "communication": by_label["communication"],
            "overall": by_label["overall"],
            "confidence": confidence,
            "reasons": "Model-based scoring from interview context and answer quality.",
        }

    def generate_feedback(
        self,
        role_target: str,
        question_type: str,
        current_question: str,
        candidate_answer: str,
        scores: Dict[str, float],
    ) -> Dict[str, Any]:
        prompt = (
            "You are an interview coach. Return output exactly in this format:\n"
            "FEEDBACK: <2-4 concise sentences>\n"
            "ACTION1: <specific action>\n"
            "ACTION2: <specific action>\n"
            "ACTION3: <specific action>\n"
            f"Role: {role_target}\n"
            f"QuestionType: {question_type}\n"
            f"CurrentQuestion: {current_question}\n"
            f"CandidateAnswer: {candidate_answer}\n"
            f"Scores: {json.dumps(scores)}\n"
            "Output:"
        )

        raw = self._generate_text(prompt, max_new_tokens=220)
        feedback_match = re.search(r"FEEDBACK\s*:\s*(.*)", raw, re.IGNORECASE)
        feedback = feedback_match.group(1).strip() if feedback_match else ""

        actions = []
        for i in range(1, 4):
            m = re.search(rf"ACTION{i}\s*:\s*(.*)", raw, re.IGNORECASE)
            if m:
                actions.append(m.group(1).strip())

        actions = [str(a)[:180] for a in actions[:3] if a]

        while len(actions) < 3:
            actions.append("Answer directly, justify one tradeoff, and include one measurable outcome.")

        return {
            "feedback": feedback[:600] if feedback else "Your answer can be stronger with tighter structure and clearer evidence.",
            "improvement_actions": actions,
        }
