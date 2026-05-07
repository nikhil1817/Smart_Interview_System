import re
from typing import Dict

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


class NLIEvaluator:
    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-small"):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self.device = torch.device("cpu")
        self.contradiction_idx = 0
        self.neutral_idx = 1
        self.entailment_idx = 2

    def _ensure_loaded(self):
        if self.model is not None and self.tokenizer is not None:
            return

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()

        label2id = {k.lower(): v for k, v in (self.model.config.label2id or {}).items()}
        self.contradiction_idx = label2id.get("contradiction", 0)
        self.neutral_idx = label2id.get("neutral", 1)
        self.entailment_idx = label2id.get("entailment", 2)

    def _support_score(self, premise: str, hypothesis: str) -> float:
        self._ensure_loaded()

        encoded = self.tokenizer(
            premise,
            hypothesis,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        encoded = {k: v.to(self.device) for k, v in encoded.items()}

        with torch.no_grad():
            logits = self.model(**encoded).logits.squeeze(0)
            margin = float((logits[self.entailment_idx] - logits[self.contradiction_idx]).item())
            # Convert entailment-vs-contradiction margin into a smooth 0..1 score.
            score = float(torch.sigmoid(torch.tensor(margin * 1.5)).item())

        return max(0.0, min(1.0, score))

    def _contrastive_dimension_score(
        self,
        premise: str,
        positive_hypothesis: str,
        negative_hypothesis: str,
    ) -> float:
        pos_support = self._support_score(premise, positive_hypothesis)
        neg_support = self._support_score(premise, negative_hypothesis)

        # Center at 0.5 and spread based on model preference for positive over negative statement.
        score = 0.5 + 0.7 * (pos_support - neg_support)
        return max(0.0, min(1.0, score))

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-zA-Z][a-zA-Z0-9+/#.-]+", (text or "").lower())

    def _keyword_overlap(self, answer: str, question: str) -> float:
        answer_tokens = set(self._tokenize(answer))
        question_tokens = set(self._tokenize(question))
        if not answer_tokens or not question_tokens:
            return 0.0

        stop = {
            "the", "and", "for", "with", "that", "this", "have", "from", "your",
            "about", "what", "when", "where", "how", "why", "into", "then", "than",
            "were", "been", "their", "there", "will", "would", "could", "should",
            "a", "an", "to", "of", "in", "on", "at", "is", "are", "be", "it",
        }

        answer_tokens = {t for t in answer_tokens if t not in stop and len(t) > 2}
        question_tokens = {t for t in question_tokens if t not in stop and len(t) > 2}
        if not answer_tokens or not question_tokens:
            return 0.0

        overlap = len(answer_tokens.intersection(question_tokens))
        return overlap / max(1, min(len(answer_tokens), len(question_tokens)))

    def _specificity_signal(self, answer: str) -> float:
        lower = (answer or "").lower()
        word_count = len(self._tokenize(lower))

        technical_terms = [
            "latency", "throughput", "cache", "index", "retry", "jitter", "circuit",
            "idempotency", "rate", "limit", "scal", "tradeoff", "consistency", "availability",
            "queue", "monitor", "p95", "slo", "sla", "database", "api", "gateway",
        ]
        term_hits = sum(1 for term in technical_terms if term in lower)

        has_number = 1.0 if re.search(r"\d+%|\d+x|\$\d+|\b\d+\b", lower) else 0.0
        has_reasoning = 1.0 if re.search(r"because|therefore|tradeoff|decision|chose|due to|so that", lower) else 0.0

        return max(
            0.0,
            min(
                1.0,
                0.55 * min(1.0, term_hits / 7.0)
                + 0.2 * has_number
                + 0.15 * has_reasoning
                + 0.1 * min(1.0, word_count / 80.0),
            ),
        )

    def _has_uncertainty_language(self, answer: str) -> bool:
        return bool(re.search(r"don['’]?t know|not sure|no idea|maybe|i guess", answer or "", re.IGNORECASE))

    def evaluate(
        self,
        role_target: str,
        question_type: str,
        mode: str,
        current_question: str,
        candidate_answer: str,
    ) -> Dict[str, float]:
        if not candidate_answer.strip():
            return {
                "clarity": 0.0,
                "technical_depth": 0.0,
                "structure_star": 0.0,
                "relevance": 0.0,
                "communication": 0.0,
                "overall": 0.0,
                "confidence": 0.2,
            }

        premise = (
            f"Role: {role_target}\n"
            f"Question Type: {question_type}\n"
            f"Mode: {mode}\n"
            f"Question: {current_question}\n"
            f"Answer: {candidate_answer}"
        )

        clarity = self._contrastive_dimension_score(
            premise,
            "The answer is clear, structured, and easy to follow.",
            "The answer is confusing, disorganized, and hard to follow.",
        )
        technical_depth = self._contrastive_dimension_score(
            premise,
            "The answer shows strong technical depth with concrete implementation details.",
            "The answer lacks technical depth and concrete implementation details.",
        )
        structure_star = self._contrastive_dimension_score(
            premise,
            "The answer has clear structure with context, action, and outcome.",
            "The answer has no clear structure or outcome.",
        )
        relevance = self._contrastive_dimension_score(
            premise,
            "The answer directly addresses the exact question asked.",
            "The answer is mostly off-topic and does not address the question.",
        )
        communication = self._contrastive_dimension_score(
            premise,
            "The answer communicates decisions and tradeoffs precisely.",
            "The answer is vague and does not explain decisions or tradeoffs.",
        )

        question_overlap = self._keyword_overlap(candidate_answer, current_question)
        specificity = self._specificity_signal(candidate_answer)
        uncertainty = self._has_uncertainty_language(candidate_answer)
        word_count = len(self._tokenize(candidate_answer))

        # Ground dimensions with observable answer signals to prevent inflated scores on vague replies.
        clarity *= (0.6 + 0.4 * specificity)
        communication *= (0.55 + 0.45 * specificity)
        structure_star *= (0.65 + 0.35 * specificity)
        relevance = max(0.0, min(1.0, 0.65 * relevance + 0.35 * question_overlap))

        if uncertainty and word_count < 24:
            clarity = min(clarity, 0.4)
            communication = min(communication, 0.35)
            relevance = min(relevance, 0.35)

        if word_count < 10:
            clarity = min(clarity, 0.35)
            structure_star = min(structure_star, 0.25)

        # Weighted overall to reflect interview quality dimensions.
        overall = (
            0.22 * clarity
            + 0.24 * technical_depth
            + 0.16 * structure_star
            + 0.22 * relevance
            + 0.16 * communication
        )

        if uncertainty and specificity < 0.35:
            overall = max(0.0, overall - 0.16)
        if question_overlap < 0.08:
            overall = max(0.0, overall - 0.1)

        spread = max(clarity, technical_depth, structure_star, relevance, communication) - min(
            clarity, technical_depth, structure_star, relevance, communication
        )
        confidence = max(0.3, min(0.95, 0.55 + spread * 0.45))

        return {
            "clarity": round(clarity * 10, 2),
            "technical_depth": round(technical_depth * 10, 2),
            "structure_star": round(structure_star * 10, 2),
            "relevance": round(relevance * 10, 2),
            "communication": round(communication * 10, 2),
            "overall": round(overall * 10, 2),
            "confidence": round(confidence, 2),
        }
