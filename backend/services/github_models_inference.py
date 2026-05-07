import json
import os
import re
import time
from typing import Any, Dict, List
from pathlib import Path

import httpx
from dotenv import load_dotenv


def _clamp(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = minimum
    return max(minimum, min(maximum, number))


class GitHubModelsAuthError(Exception):
    pass


class GitHubModelsRateLimitError(Exception):
    def __init__(self, message: str, retry_after_seconds: float | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class GitHubModelsConnectionError(Exception):
    pass


class GitHubModelsTimeoutError(Exception):
    pass


class GitHubModelsRequestError(Exception):
    pass


class GitHubModelsInterviewService:
    def __init__(self):
        self.api_key = ""
        self.base_url = ""
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
        self.api_key = (os.getenv("GITHUB_MODELS_API_KEY") or "").strip()
        self.base_url = (os.getenv("GITHUB_MODELS_BASE_URL") or "https://models.github.ai/inference").rstrip("/")
        self.question_model = os.getenv("GITHUB_QUESTION_MODEL", "openai/o4-mini")
        self.evaluation_model = os.getenv("GITHUB_EVAL_MODEL", "openai/o4-mini")
        self.feedback_model = os.getenv("GITHUB_FEEDBACK_MODEL", "openai/o4-mini")
        self.timeout_seconds = _clamp(os.getenv("GITHUB_MODELS_TIMEOUT_SECONDS", "25"), 5, 120)
        self.max_retries = int(_clamp(os.getenv("GITHUB_MODELS_MAX_RETRIES", "1"), 0, 6))
        self.retry_backoff_seconds = _clamp(os.getenv("GITHUB_MODELS_RETRY_BACKOFF_SECONDS", "0.8"), 0.1, 5)
        self.context_turns = int(_clamp(os.getenv("GITHUB_MODELS_CONTEXT_TURNS", "6"), 2, 12))
        self.question_max_tokens = int(_clamp(os.getenv("GITHUB_QUESTION_MAX_TOKENS", "420"), 120, 1200))
        self.evaluation_max_tokens = int(_clamp(os.getenv("GITHUB_EVAL_MAX_TOKENS", "520"), 180, 1600))
        self.feedback_max_tokens = int(_clamp(os.getenv("GITHUB_FEEDBACK_MAX_TOKENS", "420"), 120, 1400))

        if self.client is None:
            self.client = httpx.Client(timeout=float(self.timeout_seconds))
            return

        current_timeout = getattr(self.client.timeout, "connect", None)
        expected_timeout = float(self.timeout_seconds)
        if current_timeout is None or abs(float(current_timeout) - expected_timeout) > 1e-6:
            self.client.close()
            self.client = httpx.Client(timeout=expected_timeout)

    def _ensure_ready(self) -> None:
        self._refresh_settings_from_env()
        if self.api_key:
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

    def _ask_json(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> Dict[str, Any]:
        self._ensure_ready()
        if not self.enabled:
            raise GitHubModelsAuthError("GitHub Models API key is not configured")

        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "max_completion_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        response = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.post(endpoint, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                if attempt >= self.max_retries:
                    raise GitHubModelsTimeoutError("GitHub Models request timed out") from exc
                time.sleep(float(self.retry_backoff_seconds) * (2 ** attempt))
                continue
            except httpx.ConnectError as exc:
                if attempt >= self.max_retries:
                    raise GitHubModelsConnectionError("GitHub Models connection failed") from exc
                time.sleep(float(self.retry_backoff_seconds) * (2 ** attempt))
                continue
            except httpx.RequestError as exc:
                if attempt >= self.max_retries:
                    raise GitHubModelsRequestError("GitHub Models request failed") from exc
                time.sleep(float(self.retry_backoff_seconds) * (2 ** attempt))
                continue

            if response.status_code in (401, 403):
                raise GitHubModelsAuthError("GitHub Models authentication failed")

            if response.status_code == 429:
                retry_after_raw = response.headers.get("retry-after")
                retry_after_seconds = None
                if retry_after_raw is not None:
                    try:
                        retry_after_seconds = max(0.0, float(retry_after_raw))
                    except Exception:
                        retry_after_seconds = None
                message = "GitHub Models rate limited the request"
                if retry_after_seconds is not None:
                    message = f"{message} (retry after {int(retry_after_seconds)}s)"
                raise GitHubModelsRateLimitError(message, retry_after_seconds=retry_after_seconds)

            if response.status_code >= 400:
                response_text = (response.text or "").strip()
                if len(response_text) > 500:
                    response_text = response_text[:500] + "..."
                raise GitHubModelsRequestError(
                    f"GitHub Models returned status {response.status_code}: {response_text}"
                )

            break

        if response is None:
            raise GitHubModelsRequestError("GitHub Models request failed without response")

        body = response.json()
        message = body.get("choices", [{}])[0].get("message", {})
        content = message.get("content", "")

        if isinstance(content, list):
            content = "".join(
                str(item.get("text", "")) if isinstance(item, dict) else str(item)
                for item in content
            )

        return self._extract_json(content or "")

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
            raise ValueError("GitHub Models question generation returned empty question")

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
            raise ValueError("GitHub Models feedback generation returned empty feedback")

        while len(actions) < 3:
            actions.append("Answer directly, justify one tradeoff, and include one measurable outcome.")

        return {
            "feedback": feedback[:900],
            "improvement_actions": actions[:3],
        }
