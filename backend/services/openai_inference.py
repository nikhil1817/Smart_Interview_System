import json
import os
import re
import time
from typing import Any, Dict, List
from pathlib import Path

from dotenv import load_dotenv

try:
    from openai import OpenAI
    from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError
except Exception:  # pragma: no cover - allow import-time absence until installed
    OpenAI = None  # type: ignore
    APIConnectionError = APIError = AuthenticationError = RateLimitError = Exception  # type: ignore


def _clamp(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = minimum
    return max(minimum, min(maximum, number))


class OpenAIAuthError(Exception):
    pass


class OpenAIRateLimitError(Exception):
    def __init__(self, message: str, retry_after_seconds: float | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class OpenAIConnectionError(Exception):
    pass


class OpenAITimeoutError(Exception):
    pass


class OpenAIRequestError(Exception):
    pass


class OpenAIInterviewService:
    """
    Drop-in replacement for GitHubModelsInterviewService, but using OpenAI API directly.

    Env variables (defaults in parentheses):
    - OPENAI_API_KEY: required to enable
    - OPENAI_QUESTION_MODEL (o4-mini)
    - OPENAI_EVAL_MODEL (o4-mini)
    - OPENAI_FEEDBACK_MODEL (o4-mini)
    - OPENAI_TIMEOUT_SECONDS (25)
    - OPENAI_MAX_RETRIES (1)
    - OPENAI_RETRY_BACKOFF_SECONDS (0.8)
    - OPENAI_CONTEXT_TURNS (6)
    - OPENAI_QUESTION_MAX_TOKENS (420)
    - OPENAI_EVAL_MAX_TOKENS (520)
    - OPENAI_FEEDBACK_MAX_TOKENS (420)
    """

    def __init__(self):
        self.api_key = ""
        self.question_model = ""
        self.evaluation_model = ""
        self.feedback_model = ""
        self.timeout_seconds = 25.0
        self.max_retries = 1
        self.retry_backoff_seconds = 0.8
        self.context_turns = 6
        self.question_max_tokens = 420
        self.evaluation_max_tokens = 520
        self.feedback_max_tokens = 420
        self.client = None
        self._refresh_settings_from_env()

    def _reload_dotenv_files(self) -> None:
        backend_dir = Path(__file__).resolve().parents[1]
        workspace_dir = backend_dir.parent
        load_dotenv(workspace_dir / ".env")
        load_dotenv(backend_dir / ".env", override=True)

    def _refresh_settings_from_env(self) -> None:
        self.api_key = (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_APIKEY") or "").strip()
        self.question_model = os.getenv("OPENAI_QUESTION_MODEL", "o4-mini")
        self.evaluation_model = os.getenv("OPENAI_EVAL_MODEL", "o4-mini")
        self.feedback_model = os.getenv("OPENAI_FEEDBACK_MODEL", "o4-mini")
        self.timeout_seconds = _clamp(os.getenv("OPENAI_TIMEOUT_SECONDS", "25"), 5, 120)
        self.max_retries = int(_clamp(os.getenv("OPENAI_MAX_RETRIES", "1"), 0, 6))
        self.retry_backoff_seconds = _clamp(os.getenv("OPENAI_RETRY_BACKOFF_SECONDS", "0.8"), 0.1, 5)
        self.context_turns = int(_clamp(os.getenv("OPENAI_CONTEXT_TURNS", "6"), 2, 12))
        self.question_max_tokens = int(_clamp(os.getenv("OPENAI_QUESTION_MAX_TOKENS", "420"), 120, 1200))
        self.evaluation_max_tokens = int(_clamp(os.getenv("OPENAI_EVAL_MAX_TOKENS", "520"), 180, 1600))
        self.feedback_max_tokens = int(_clamp(os.getenv("OPENAI_FEEDBACK_MAX_TOKENS", "420"), 120, 1400))

        if self.client is None and self.api_key and OpenAI is not None:
            # Instantiate lazily; requests set per-call timeout via client default
            self.client = OpenAI(api_key=self.api_key, timeout=float(self.timeout_seconds))
            return

        if self.client is not None:
            # Recreate client if timeout changed materially
            try:
                current_timeout = getattr(self.client, "_client", None)
                # If internal httpx client exists, we can’t easily introspect; recreate anyway if value shifts
                self.client = OpenAI(api_key=self.api_key, timeout=float(self.timeout_seconds))
            except Exception:
                self.client = OpenAI(api_key=self.api_key, timeout=float(self.timeout_seconds))

    def _ensure_ready(self) -> None:
        self._refresh_settings_from_env()
        if self.api_key and self.client is not None:
            return
        self._reload_dotenv_files()
        self._refresh_settings_from_env()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        cleaned = (text or "").strip()
        if not cleaned:
            raise ValueError("Empty model response")

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise ValueError("No JSON object found in model output")

        return json.loads(match.group(0))

    def _ask_json(self, model: str, system_prompt: str, user_prompt: str, max_tokens: int) -> Dict[str, Any]:
        self._ensure_ready()
        if not self.enabled or self.client is None or OpenAI is None:
            raise OpenAIAuthError("OpenAI API key is not configured")

        # We'll retry around common transient failures and 429s
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=int(max_tokens),
                )
                content = (resp.choices[0].message.content or "").strip()
                return self._extract_json(content)
            except RateLimitError as exc:
                print(f"[openai] RateLimitError: {exc}")
                last_error = exc
                if attempt >= self.max_retries:
                    raise OpenAIRateLimitError("OpenAI rate limited the request") from exc
                time.sleep(float(self.retry_backoff_seconds) * (2 ** attempt))
                continue
            except AuthenticationError as exc:
                print(f"[openai] AuthenticationError: {exc}")
                raise OpenAIAuthError("OpenAI authentication failed") from exc
            except APIConnectionError as exc:
                print(f"[openai] APIConnectionError: {exc}")
                last_error = exc
                if attempt >= self.max_retries:
                    raise OpenAIConnectionError("OpenAI connection failed") from exc
                time.sleep(float(self.retry_backoff_seconds) * (2 ** attempt))
                continue
            except APIError as exc:
                print(f"[openai] APIError: status={getattr(exc, 'status_code', None)} detail={exc}")
                last_error = exc
                # Retry 500-range errors
                if getattr(exc, "status_code", 500) >= 500 and attempt < self.max_retries:
                    time.sleep(float(self.retry_backoff_seconds) * (2 ** attempt))
                    continue
                raise OpenAIRequestError(f"OpenAI request failed: {exc}") from exc
            except Exception as exc:
                print(f"[openai] Unexpected error: {exc}")
                last_error = exc
                if attempt >= self.max_retries:
                    raise OpenAIRequestError("OpenAI request failed") from exc
                time.sleep(float(self.retry_backoff_seconds) * (2 ** attempt))
                continue

        if last_error is not None:
            raise last_error
        raise OpenAIRequestError("OpenAI request failed without response")

    def generate_question(
        self,
        role_target: str,
        question_type: str,
        mode: str,
        interviewer_persona: str,
        resume_summary: str,
        conversation_context: List[Dict[str, str]],
        candidate_answer: str,
        max_question_words: int,
    ) -> Dict[str, Any]:
        context_text = "\n".join(
            f"{turn.get('speaker', 'unknown')}: {turn.get('text', '')}" for turn in (conversation_context or [])[-self.context_turns:]
        )

        system_prompt = (
            "You are an expert senior interviewer. Output strictly valid JSON only. "
            "Generate exactly one high-quality question that is specific, non-generic, and diagnostic."
        )

        user_prompt = (
            "Return JSON with keys: question (string), question_source ('resume' or 'general').\n"
            f"role_target: {role_target}\n"
            f"question_type: {question_type}\n"
            f"mode: {mode}\n"
            f"interviewer_persona: {interviewer_persona}\n"
            f"resume_summary: {resume_summary or ''}\n"
            f"candidate_answer: {candidate_answer or ''}\n"
            f"max_question_words: {max_question_words}\n"
            "Rules:\n"
            "- Ask one probing question that tests reasoning depth, tradeoffs, or decision quality.\n"
            "- Avoid generic prompts like 'walk me through' unless grounded in specific context.\n"
            "- If resume_summary has substance, prefer resume-grounded question_source='resume'.\n"
            "- For stress mode, challenge assumptions with a realistic constraint.\n"
            "- For speed_round mode, keep it sharp and <= 18 words.\n"
            "- Do not repeat prior assistant questions from conversation_context.\n"
            "- Keep wording natural and interviewer-like, not template-like.\n"
            "conversation_context:\n"
            f"{context_text}"
        )

        data = self._ask_json(
            model=self.question_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=self.question_max_tokens,
        )

        question = (data.get("question") or "").strip()
        source = (data.get("question_source") or "general").strip().lower()

        if not question:
            raise ValueError("OpenAI question generation returned empty question")

        words = question.split()
        if len(words) > max_question_words:
            question = " ".join(words[:max_question_words]).rstrip(".,;:!?") + "?"

        if source not in {"resume", "general"}:
            source = "general"

        return {
            "question": question,
            "question_source": source,
        }

    def evaluate_answer(
        self,
        role_target: str,
        question_type: str,
        mode: str,
        current_question: str,
        candidate_answer: str,
        conversation_context: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        context_text = "\n".join(
            f"{turn.get('speaker', 'unknown')}: {turn.get('text', '')}" for turn in (conversation_context or [])[-self.context_turns:]
        )

        system_prompt = "You are a strict senior interviewer evaluating answer quality. Return JSON only."

        user_prompt = (
            "Return JSON with keys: clarity, technical_depth, structure_star, relevance, communication, overall, "
            "confidence, low_signal, uncertainty_flags.\n"
            "Score fields must be numbers from 0 to 10. confidence must be 0 to 1. "
            "uncertainty_flags must be a string array.\n"
            "Scoring anchors:\n"
            "- 0-2: off-topic, incorrect, or empty signal\n"
            "- 3-4: partial relevance with major gaps\n"
            "- 5-6: acceptable baseline but missing depth or structure\n"
            "- 7-8: strong, specific, technically grounded\n"
            "- 9-10: exceptional depth, precision, and tradeoff clarity\n"
            "Set low_signal=true when answer is vague, too short, or mostly generic.\n"
            "Add uncertainty_flags like: ['too_generic','missing_tradeoffs','no_metrics','partial_relevance'] when applicable.\n"
            f"role_target: {role_target}\n"
            f"question_type: {question_type}\n"
            f"mode: {mode}\n"
            f"current_question: {current_question}\n"
            f"candidate_answer: {candidate_answer}\n"
            "conversation_context:\n"
            f"{context_text}"
        )

        data = self._ask_json(
            model=self.evaluation_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=self.evaluation_max_tokens,
        )

        return {
            "clarity": round(_clamp(data.get("clarity", 0), 0, 10), 2),
            "technical_depth": round(_clamp(data.get("technical_depth", 0), 0, 10), 2),
            "structure_star": round(_clamp(data.get("structure_star", 0), 0, 10), 2),
            "relevance": round(_clamp(data.get("relevance", 0), 0, 10), 2),
            "communication": round(_clamp(data.get("communication", 0), 0, 10), 2),
            "overall": round(_clamp(data.get("overall", 0), 0, 10), 2),
            "confidence": round(_clamp(data.get("confidence", 0.6), 0, 1), 2),
            "low_signal": bool(data.get("low_signal", False)),
            "uncertainty_flags": [str(flag) for flag in (data.get("uncertainty_flags") or [])][:5],
        }

    def generate_feedback(
        self,
        role_target: str,
        question_type: str,
        current_question: str,
        candidate_answer: str,
        scores: Dict[str, float],
    ) -> Dict[str, Any]:
        system_prompt = "You are an interview coach. Return concise, practical, actionable coaching in JSON only."

        user_prompt = (
            "Return JSON with keys: feedback (string), improvement_actions (array of 3 concise strings).\n"
            f"role_target: {role_target}\n"
            f"question_type: {question_type}\n"
            f"current_question: {current_question}\n"
            f"candidate_answer: {candidate_answer}\n"
            f"scores: {json.dumps(scores)}"
        )

        data = self._ask_json(
            model=self.feedback_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=self.feedback_max_tokens,
        )

        feedback = str(data.get("feedback") or "").strip()
        actions = [str(item).strip() for item in (data.get("improvement_actions") or []) if str(item).strip()]

        if not feedback:
            raise ValueError("OpenAI feedback generation returned empty feedback")

        while len(actions) < 3:
            actions.append("Answer directly, justify one tradeoff, and include one measurable outcome.")

        return {
            "feedback": feedback[:900],
            "improvement_actions": actions[:3],
        }

