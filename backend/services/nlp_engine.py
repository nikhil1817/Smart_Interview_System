from sentence_transformers import SentenceTransformer, util
import numpy as np
import re

class NLPEngine:
    def __init__(self):
        # Temporarily disable model loading due to SSL/network issues
        # self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.model = None

        # Example "ideal answers" (expand later)
        self.reference_answers = {
            "challenge": "I faced a challenge where I had to optimize a slow system. I identified bottlenecks, implemented caching, and improved performance by 40 percent.",
            "teamwork": "I worked with a team to deliver a project by coordinating tasks, resolving conflicts, and ensuring deadlines were met."
        }

    def _tokenize(self, text):
        return re.findall(r"[a-zA-Z][a-zA-Z0-9+/#.-]+", (text or "").lower())

    def _keyword_overlap(self, answer, target):
        answer_tokens = set(self._tokenize(answer))
        target_tokens = set(self._tokenize(target))
        if not answer_tokens or not target_tokens:
            return 0.0

        stop = {
            "the", "and", "for", "with", "that", "this", "have", "from", "your",
            "about", "what", "when", "where", "how", "why", "into", "then", "than",
            "were", "been", "their", "there", "will", "would", "could", "should"
        }
        answer_tokens = {t for t in answer_tokens if t not in stop and len(t) > 2}
        target_tokens = {t for t in target_tokens if t not in stop and len(t) > 2}

        if not answer_tokens or not target_tokens:
            return 0.0

        overlap = len(answer_tokens.intersection(target_tokens))
        return overlap / max(1, min(len(answer_tokens), len(target_tokens)))

    # Semantic similarity with robust fallback.
    def semantic_score(self, user_answer, reference_text=""):
        if self.model is not None and reference_text:
            try:
                emb1 = self.model.encode(user_answer, convert_to_tensor=True)
                emb2 = self.model.encode(reference_text, convert_to_tensor=True)
                score = util.cos_sim(emb1, emb2).item()
                # Normalize cosine-like range into [0,1] defensively.
                return float(max(0.0, min(1.0, (score + 1.0) / 2.0 if score < 0 else score)))
            except Exception:
                pass

        # Fallback: lexical alignment + evidence density.
        overlap = self._keyword_overlap(user_answer, reference_text)
        answer_len = len(self._tokenize(user_answer))
        has_numbers = 1.0 if re.search(r"\d+%|\d+x|\$\d+|\b\d+\b", user_answer) else 0.0
        has_reasoning = 1.0 if re.search(r"because|therefore|tradeoff|due to|so that|impact", user_answer, re.IGNORECASE) else 0.0
        length_signal = min(1.0, answer_len / 80.0)

        return float(max(0.0, min(1.0, 0.45 * overlap + 0.25 * has_numbers + 0.2 * has_reasoning + 0.1 * length_signal)))

    # 🔹 Clarity score
    def clarity_score(self, text):
        sentences = re.split(r'[.!?]', text)
        lengths = [len(s.split()) for s in sentences if s.strip()]
        if not lengths:
            return 0.0

        avg_len = np.mean(lengths)
        sentence_count = len(lengths)
        punctuation_signal = 1.0 if re.search(r"[.!?]", text) else 0.0
        filler_hits = len(re.findall(r"\bum\b|\buh\b|\blike\b", text.lower()))
        filler_penalty = min(0.25, filler_hits * 0.05)

        if avg_len < 6:
            base = 0.35
        elif avg_len < 24:
            base = 0.82
        else:
            base = 0.62

        if sentence_count == 1 and avg_len > 35:
            base -= 0.12

        return float(max(0.0, min(1.0, base + 0.08 * punctuation_signal - filler_penalty)))

    # 🔹 Vagueness detection
    def vagueness_score(self, text):
        vague_words = ["something", "stuff", "things", "kind of", "basically", "etc", "whatever"]
        lower = text.lower()
        count = sum(1 for w in vague_words if w in lower)
        hedge = len(re.findall(r"maybe|probably|sort of|i guess", lower))
        penalty = 0.16 * count + 0.08 * hedge
        return float(max(0.0, min(1.0, 1.0 - penalty)))

    # 🔹 STAR detection (basic version)
    def star_score(self, text):
        text = text.lower()

        score = 0
        if "situation" in text or "when i" in text:
            score += 0.25
        if "task" in text or "my role" in text:
            score += 0.25
        if "action" in text or "i did" in text:
            score += 0.25
        if "result" in text or "%" in text or "improved" in text:
            score += 0.25

        if re.search(r"\b(first|then|after|finally)\b", text):
            score = min(1.0, score + 0.1)

        return float(score)

    def _technical_depth_score(self, text, question_type=""):
        technical_terms = [
            "latency", "throughput", "complexity", "cache", "index", "scal", "tradeoff",
            "consistency", "availability", "queue", "retry", "observability", "rollback",
            "api", "database", "model", "feature", "experiment", "metric"
        ]
        hits = sum(1 for term in technical_terms if term in text.lower())
        score = min(1.0, hits / 8.0)

        if (question_type or "").lower() == "behavioral":
            score = min(1.0, 0.7 * score + 0.3 * (1.0 if re.search(r"team|stakeholder|conflict|owner", text, re.IGNORECASE) else 0.2))

        return float(score)

    def _behavioral_signal_score(self, text):
        lower = (text or "").lower()
        ownership = 1.0 if re.search(r"\bi\b|\bmy\b|\bowned\b|\bled\b", lower) else 0.0
        impact = 1.0 if re.search(r"\d+%|\d+x|\$\d+|\bresult\b|\boutcome\b|\bimproved\b", lower) else 0.0
        conflict = 1.0 if re.search(r"stakeholder|conflict|tradeoff|alignment|risk", lower) else 0.0
        return float(min(1.0, 0.4 * ownership + 0.4 * impact + 0.2 * conflict))

    def _system_design_signal_score(self, text):
        lower = (text or "").lower()
        architecture = 1.0 if re.search(r"component|service|api|database|queue|cache", lower) else 0.0
        tradeoff = 1.0 if re.search(r"tradeoff|consistency|availability|latency|throughput", lower) else 0.0
        reliability = 1.0 if re.search(r"failure|retry|degrad|fallback|monitor|slo|sla", lower) else 0.0
        return float(min(1.0, 0.35 * architecture + 0.35 * tradeoff + 0.3 * reliability))

    def _algorithmic_signal_score(self, text):
        lower = (text or "").lower()
        complexity = 1.0 if re.search(r"o\([n\d\s\^+*log]+\)|complexity|runtime|space", lower) else 0.0
        ds = 1.0 if re.search(r"hash|heap|tree|graph|stack|queue|dp|dynamic programming", lower) else 0.0
        edge_case = 1.0 if re.search(r"edge case|corner case|test case", lower) else 0.0
        return float(min(1.0, 0.45 * complexity + 0.4 * ds + 0.15 * edge_case))

    def _question_type_weights(self, question_type):
        key = (question_type or "").strip().lower()
        if key == "behavioral":
            return {
                "semantic": 0.16,
                "clarity": 0.2,
                "vagueness": 0.14,
                "star": 0.3,
                "technical_depth": 0.08,
                "type_signal": 0.12,
            }
        if key == "system design":
            return {
                "semantic": 0.2,
                "clarity": 0.16,
                "vagueness": 0.14,
                "star": 0.08,
                "technical_depth": 0.26,
                "type_signal": 0.16,
            }
        if key == "leetcode/dsa":
            return {
                "semantic": 0.22,
                "clarity": 0.14,
                "vagueness": 0.12,
                "star": 0.06,
                "technical_depth": 0.24,
                "type_signal": 0.22,
            }
        # Technical / mixed default.
        return {
            "semantic": 0.22,
            "clarity": 0.18,
            "vagueness": 0.14,
            "star": 0.12,
            "technical_depth": 0.24,
            "type_signal": 0.10,
        }

    def _question_type_signal(self, answer, question_type):
        key = (question_type or "").strip().lower()
        if key == "behavioral":
            return self._behavioral_signal_score(answer)
        if key == "system design":
            return self._system_design_signal_score(answer)
        if key == "leetcode/dsa":
            return self._algorithmic_signal_score(answer)
        return min(1.0, 0.5 * self._technical_depth_score(answer, question_type) + 0.5 * self.clarity_score(answer))

    def _is_low_signal_answer(self, text):
        lower = (text or "").lower().strip()
        if not lower:
            return True

        direct_unknown_patterns = [
            r"^i\s+don['’]?t\s+know\.?$",
            r"^dont\s+know\.?$",
            r"^no\s+idea\.?$",
            r"^not\s+sure\.?$",
            r"^i\s+have\s+no\s+idea\.?$",
            r"^i\s+can['’]?t\s+answer\s+that\.?$",
        ]
        if any(re.match(p, lower) for p in direct_unknown_patterns):
            return True

        words = self._tokenize(lower)
        if len(words) <= 5 and re.search(r"don['’]?t know|no idea|not sure", lower):
            return True

        return False

    def _has_recovery_attempt(self, text):
        # Candidate admits uncertainty but still demonstrates reasoning/approach.
        return bool(re.search(
            r"i would|i\'d|approach|start by|first|then|tradeoff|assume|clarify|hypothesis|experiment|measure",
            text,
            re.IGNORECASE,
        ))

    # Final combined score.
    def evaluate(self, answer, current_question="", question_type="", mode=""):
        if not answer or len(answer.strip()) < 5:
            return {
                "score": 0,
                "details": "Empty or too short"
            }

        if self._is_low_signal_answer(answer):
            # Honest but low-information responses should score very low.
            return {
                "score": 0.8,
                "semantic": 0.02,
                "clarity": 0.35,
                "vagueness": 0.2,
                "star": 0.0,
                "technical_depth": 0.0,
                "relevance": 0.05,
                "low_signal": True,
            }

        semantic = self.semantic_score(answer, current_question)
        clarity = self.clarity_score(answer)
        vagueness = self.vagueness_score(answer)
        star = self.star_score(answer)
        technical_depth = self._technical_depth_score(answer, question_type)
        type_signal = self._question_type_signal(answer, question_type)
        evidence_signal = 1.0 if re.search(r"\d+%|\d+x|\$\d+|\b\d+\b", answer) else 0.0
        tradeoff_signal = 1.0 if re.search(r"tradeoff|because|therefore|decision|chose", answer, re.IGNORECASE) else 0.0

        # Relevance blends semantic alignment and low vagueness.
        relevance = max(0.0, min(1.0, 0.75 * semantic + 0.25 * vagueness))

        # Speed rounds reward concise but complete responses.
        if (mode or "").lower() == "speed_round":
            wc = len(self._tokenize(answer))
            if wc > 80:
                clarity = max(0.0, clarity - 0.1)
            elif wc >= 20:
                clarity = min(1.0, clarity + 0.05)

        weights = self._question_type_weights(question_type)
        base = (
            weights["semantic"] * semantic +
            weights["clarity"] * clarity +
            weights["vagueness"] * vagueness +
            weights["star"] * star +
            weights["technical_depth"] * technical_depth +
            weights["type_signal"] * type_signal
        )

        bonus = 0.08 * evidence_signal + 0.06 * tradeoff_signal
        final_score = (base + bonus) * 10

        # Penalize answers that barely connect to the question topic.
        question_overlap = self._keyword_overlap(answer, current_question)
        if current_question and question_overlap < 0.06:
            final_score = max(0.0, final_score - 1.0)
        if current_question and question_overlap < 0.03:
            final_score = max(0.0, final_score - 0.8)

        if re.search(r"don['’]?t know|not sure|no idea", answer, re.IGNORECASE):
            if self._has_recovery_attempt(answer):
                final_score = max(0.0, final_score - 1.2)
            else:
                final_score = max(0.0, final_score - 2.4)

        return {
            "score": round(final_score, 2),
            "semantic": semantic,
            "clarity": clarity,
            "vagueness": vagueness,
            "star": star,
            "technical_depth": technical_depth,
            "relevance": relevance,
            "type_signal": type_signal,
            "low_signal": False
        }