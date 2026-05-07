import uuid
import os
from fastapi import APIRouter
from fastapi import HTTPException

from agents.evaluator_agent import EvaluatorAgent
from modeling.inference_models import (
    EvaluateAnswerRequest,
    EvaluateAnswerResponse,
    GenerateFeedbackRequest,
    GenerateFeedbackResponse,
    GenerateQuestionRequest,
    GenerateQuestionResponse,
    ScoreObject,
)
from services.interview_blueprint import get_interviewer_profile
from services.interview_blueprint import get_panel_members
from services.llm_coach import LLMCoach
from services.nlp_engine import NLPEngine
from services.nli_evaluator import NLIEvaluator
from services.openai_inference import OpenAIInterviewService
from services.question_generator import QuestionGenerator

router = APIRouter(prefix="/v1/model", tags=["model-inference"])

evaluator = EvaluatorAgent()
qgen = QuestionGenerator()
coach = LLMCoach()
nli_evaluator = NLIEvaluator()
nlp_evaluator = NLPEngine()
openai_inference = OpenAIInterviewService()
ALLOW_RULE_BASED_FALLBACK = os.getenv("ALLOW_RULE_BASED_FALLBACK", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


@router.get("/health")
def model_health():
    return {
        "ok": True,
        "openai": {
            "enabled": openai_inference.enabled,
            "question_model": openai_inference.question_model,
            "evaluation_model": openai_inference.evaluation_model,
            "feedback_model": openai_inference.feedback_model,
        },
        "env_sources": ["/.env", "/backend/.env"],
    }


def _blend_scores(primary: float, secondary: float, primary_weight: float = 0.55) -> float:
    return (primary_weight * primary) + ((1.0 - primary_weight) * secondary)


def _hybrid_evaluate_answer(
    role_target: str,
    question_type: str,
    mode: str,
    current_question: str,
    candidate_answer: str,
) -> dict:
    nli = nli_evaluator.evaluate(
        role_target=role_target,
        question_type=question_type,
        mode=mode,
        current_question=current_question,
        candidate_answer=candidate_answer,
    )

    rubric = nlp_evaluator.evaluate(
        answer=candidate_answer,
        current_question=current_question,
        question_type=question_type,
        mode=mode,
    )

    nli_clarity = float(nli.get("clarity", 0.0))
    nli_technical = float(nli.get("technical_depth", 0.0))
    nli_structure = float(nli.get("structure_star", 0.0))
    nli_relevance = float(nli.get("relevance", 0.0))
    nli_communication = float(nli.get("communication", 0.0))
    nli_overall = float(nli.get("overall", 0.0))

    rb_clarity = float(rubric.get("clarity", 0.0)) * 10.0
    rb_technical = float(rubric.get("technical_depth", 0.0)) * 10.0
    rb_structure = float(rubric.get("star", 0.0)) * 10.0
    rb_relevance = float(rubric.get("relevance", 0.0)) * 10.0
    rb_specificity = float(rubric.get("vagueness", 0.0)) * 10.0
    rb_communication = max(0.0, min(10.0, (0.6 * rb_clarity) + (0.4 * rb_specificity)))
    rb_overall = float(rubric.get("score", 0.0))

    clarity = _blend_scores(rb_clarity, nli_clarity)
    technical_depth = _blend_scores(rb_technical, nli_technical)
    structure_star = _blend_scores(rb_structure, nli_structure)
    relevance = _blend_scores(rb_relevance, nli_relevance)
    communication = _blend_scores(rb_communication, nli_communication)
    overall = _blend_scores(rb_overall, nli_overall)

    low_signal = bool(rubric.get("low_signal", False))
    word_count = len((candidate_answer or "").split())
    if word_count < 7:
        low_signal = True

    if low_signal:
        overall = min(overall, 3.0)
        technical_depth = min(technical_depth, 3.0)
        structure_star = min(structure_star, 3.0)

    spread = max(clarity, technical_depth, structure_star, relevance, communication) - min(
        clarity, technical_depth, structure_star, relevance, communication
    )
    base_conf = float(nli.get("confidence", 0.55))
    confidence = max(0.2, min(0.95, 0.45 + 0.35 * base_conf + 0.2 * (spread / 10.0)))
    if low_signal:
        confidence = max(0.2, confidence - 0.18)

    return {
        "clarity": round(max(0.0, min(10.0, clarity)), 2),
        "technical_depth": round(max(0.0, min(10.0, technical_depth)), 2),
        "structure_star": round(max(0.0, min(10.0, structure_star)), 2),
        "relevance": round(max(0.0, min(10.0, relevance)), 2),
        "communication": round(max(0.0, min(10.0, communication)), 2),
        "overall": round(max(0.0, min(10.0, overall)), 2),
        "confidence": round(confidence, 2),
        "low_signal": low_signal,
    }


def _trace_id() -> str:
    return str(uuid.uuid4())


def _provider_reason(error: Exception) -> str:
    name = error.__class__.__name__.lower()
    if "authentication" in name or "auth" in name:
        return "openai_auth_error"
    if "rate" in name:
        return "openai_rate_limited"
    if "timeout" in name:
        return "openai_timeout"
    if "connection" in name:
        return "openai_connection_error"
    return "openai_request_failed"


def _infer_intent(question_type: str, mode: str) -> str:
    question_type_key = (question_type or "").lower()
    mode_key = (mode or "").lower()

    if mode_key == "stress":
        return "challenge_assumptions"
    if mode_key == "speed_round":
        return "rapid_signal_check"
    if question_type_key == "system design":
        return "probe_tradeoff"
    if question_type_key == "behavioral":
        return "probe_ownership"
    if question_type_key == "technical":
        return "probe_problem_solving"
    return "probe_depth"


def _expected_signals(question_type: str, mode: str) -> list[str]:
    base = ["specific examples", "clear reasoning"]
    question_type_key = (question_type or "").lower()
    mode_key = (mode or "").lower()

    if question_type_key == "system design":
        base.extend(["tradeoff analysis", "failure mode awareness"])
    elif question_type_key == "leetcode/dsa":
        base.extend(["complexity reasoning", "data structure selection"])
    elif question_type_key == "behavioral":
        base.extend(["situation-task-action-result", "measurable impact"])

    if mode_key == "stress":
        base.append("defense under pushback")
    if mode_key == "speed_round":
        base.append("concise delivery")

    return base


def _last_assistant_question(context) -> str:
    for turn in reversed(context):
        if turn.speaker == "assistant":
            return turn.text
    return ""


def _classify_answer_quality(eval_result: dict) -> str:
    if eval_result.get("low_signal"):
        return "low"
    score = float(eval_result.get("score", 0.0))
    if score < 3.5:
        return "low"
    if score < 6.5:
        return "medium"
    return "high"


def _low_signal_recovery_question(role_target: str, question_type: str, turn_index: int = 0) -> str:
    qtype = (question_type or "").lower()
    if qtype == "system design":
        options = [
            "No worries. Start simple: define the core components, one key tradeoff, and how you would measure success for the design.",
            "Let us simplify it. Name the main components first, then one failure scenario and your mitigation.",
            "Start with a basic version of the design, then tell me what you would scale first and why.",
        ]
        return options[turn_index % len(options)]
    if qtype == "technical":
        options = [
            "No problem. Walk me through your approach step by step: assumptions, first action, and how you would validate correctness.",
            "Take it one step at a time: what assumptions would you make, what would you implement first, and how would you test it?",
            "Let us break it down. What is your initial strategy, one tradeoff, and one metric to confirm it works?",
        ]
        return options[turn_index % len(options)]
    if qtype == "behavioral":
        options = [
            "That's okay. Pick a smaller real example and explain Situation, your Action, and one measurable Result.",
            "Use a concise STAR format: context, your action, and the impact in numbers.",
            "Choose one concrete incident, describe your decision, and what changed because of it.",
        ]
        return options[turn_index % len(options)]

    options = [
        f"That's okay. For this {role_target} interview, give me a first-pass approach, one decision you would make, and why.",
        f"No stress. For this {role_target} scenario, outline your first step, main tradeoff, and success metric.",
        f"Start simple for this {role_target} prompt: approach, key decision, and how you would validate outcomes.",
    ]
    return options[turn_index % len(options)]


def _clarify_question(base_question: str) -> str:
    return f"{base_question} Be specific about what you did, why you chose it, and what changed afterward."


def _deepen_question(base_question: str, question_type: str) -> str:
    qtype = (question_type or "").lower()
    if qtype == "system design":
        return f"{base_question} Also cover one failure mode, mitigation strategy, and scaling bottleneck."
    if qtype == "technical":
        return f"{base_question} Include complexity, tradeoffs, and what you would optimize next."
    if qtype == "behavioral":
        return f"{base_question} Add the toughest tradeoff you faced and how you measured impact."
    return f"{base_question} Add one tradeoff and one metric that proves your decision was effective."


def _count_resume_questions(history: list[dict]) -> int:
    return sum(1 for item in history if item.get("source") == "resume")


def _resume_pivot_question(resume_data: dict, question_type: str) -> str | None:
    if not resume_data:
        return None
    achievements = resume_data.get("achievements") or []
    projects = resume_data.get("projects") or []
    skills = resume_data.get("skills") or []

    if achievements:
        return (
            f"From your background, you mentioned '{achievements[0]}'. "
            "What was your exact contribution, and what tradeoff did you personally make?"
        )
    if projects:
        return (
            f"From your background, in '{projects[0]}', what hard decision did you own end-to-end?"
        )
    if skills:
        qtype = (question_type or "").lower()
        if qtype == "technical":
            return f"From your background, describe a technically hard problem you solved using {skills[0]} and why your approach worked."
        return f"From your background, what is the most impactful outcome you delivered using {skills[0]}?"
    return None


@router.post("/generate-question", response_model=GenerateQuestionResponse)
def generate_question(req: GenerateQuestionRequest):
    provider_error_reason = None
    profile = get_interviewer_profile(req.interviewer_persona)
    mode_key = (req.mode or "").lower()
    panel_members = get_panel_members(req.interviewer_persona) if mode_key == "panel" else []

    if panel_members:
        speaker_idx = sum(1 for t in req.conversation_context if t.speaker == "user") % len(panel_members)
        speaker = panel_members[speaker_idx]
        persona = {
            "name": speaker.get("name", profile.get("name", req.interviewer_persona)),
            "role": speaker.get("role", "Panelist"),
            "style": speaker.get("style", profile.get("style", "structured")),
            "focus": speaker.get("focus", "structured assessment"),
        }
    else:
        persona = {
            "name": profile.get("name", req.interviewer_persona),
            "role": profile.get("role", "Interviewer"),
            "style": profile.get("style", "structured"),
            "focus": profile.get("followup", "clear and specific reasoning"),
        }

    history = [
        {
            "next_question": turn.text,
            "source": "resume" if qgen.is_resume_question(turn.text) else "general"
        }
        for turn in req.conversation_context
        if turn.speaker == "assistant"
    ]

    resume_data = req.resume_data
    if not resume_data and req.resume_summary:
        resume_data = {
            "raw_text": req.resume_summary,
            "summary": req.resume_summary
        }

    fallback = (
        "Can you walk me through your approach and the tradeoffs you considered?"
    )

    if openai_inference.enabled:
        try:
            openai_question = openai_inference.generate_question(
                role_target=req.role_target,
                question_type=req.question_type,
                mode=req.mode,
                interviewer_persona=req.interviewer_persona,
                resume_summary=req.resume_summary,
                conversation_context=[turn.model_dump() for turn in req.conversation_context],
                candidate_answer=req.candidate_answer,
                max_question_words=req.constraints.max_question_words,
            )

            question = openai_question["question"]
            question_source = openai_question.get("question_source") or "general"

            return GenerateQuestionResponse(
                question=question,
                intent=_infer_intent(req.question_type, req.mode),
                difficulty=req.constraints.difficulty,
                persona_style=profile.get("style", "structured"),
                expected_signals=_expected_signals(req.question_type, req.mode),
                question_source=question_source,
                provider="openai",
                persona=persona,
                panel_members=panel_members,
                trace_id=_trace_id(),
            )
        except Exception as exc:
            provider_error_reason = _provider_reason(exc)

    if not ALLOW_RULE_BASED_FALLBACK:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "llm_generation_unavailable",
                "message": "LLM question generation is unavailable.",
                "provider": "openai",
                "provider_reason": provider_error_reason or "openai_disabled",
            },
        )

    if req.candidate_answer.strip():
        base_question = qgen.generate_followup(
            req.role_target,
            req.question_type,
            resume_data,
            history,
            fallback,
            req.mode,
        )

        previous_question = _last_assistant_question(req.conversation_context)
        try:
            hybrid_scores = _hybrid_evaluate_answer(
                role_target=req.role_target,
                question_type=req.question_type,
                mode=req.mode,
                current_question=previous_question,
                candidate_answer=req.candidate_answer,
            )
            eval_result = {
                "score": float(hybrid_scores.get("overall", 0.0)),
                "clarity": float(hybrid_scores.get("clarity", 0.0)) / 10.0,
                "technical_depth": float(hybrid_scores.get("technical_depth", 0.0)) / 10.0,
                "structure_star": float(hybrid_scores.get("structure_star", 0.0)) / 10.0,
                "relevance": float(hybrid_scores.get("relevance", 0.0)) / 10.0,
                "communication": float(hybrid_scores.get("communication", 0.0)) / 10.0,
                "low_signal": bool(hybrid_scores.get("low_signal", False)),
            }
        except Exception:
            eval_result = evaluator.evaluate(
                req.candidate_answer,
                current_question=previous_question,
                question_type=req.question_type,
                mode=req.mode,
                role_target=req.role_target,
                interviewer_persona=req.interviewer_persona,
                resume_summary=req.resume_summary,
                conversation_context=[turn.model_dump() for turn in req.conversation_context],
            )
        quality = _classify_answer_quality(eval_result)

        if quality == "low":
            question = _low_signal_recovery_question(req.role_target, req.question_type, len(history))
        elif quality == "high":
            resume_count = _count_resume_questions(history)
            if resume_data and resume_count < 1 and len(history) >= 1:
                question = _resume_pivot_question(resume_data, req.question_type) or _deepen_question(base_question, req.question_type)
            else:
                question = _deepen_question(base_question, req.question_type)
        else:
            question = _clarify_question(base_question)
    else:
        question = qgen.generate_opening(req.role_target, req.question_type, resume_data, req.mode)

    max_words = req.constraints.max_question_words
    words = question.split()
    if len(words) > max_words:
        question = " ".join(words[:max_words]).rstrip(".,;:!?") + "?"

    question_source = "resume" if qgen.is_resume_question(question) else "general"

    return GenerateQuestionResponse(
        question=question,
        intent=_infer_intent(req.question_type, req.mode),
        difficulty=req.constraints.difficulty,
        persona_style=profile.get("style", "structured"),
        expected_signals=_expected_signals(req.question_type, req.mode),
        question_source=question_source,
        provider="fallback",
        provider_reason=provider_error_reason,
        persona=persona,
        panel_members=panel_members,
        trace_id=_trace_id(),
    )


@router.post("/evaluate-answer", response_model=EvaluateAnswerResponse)
def evaluate_answer(req: EvaluateAnswerRequest):
    provider_error_reason = None
    if openai_inference.enabled:
        try:
            result = openai_inference.evaluate_answer(
                role_target=req.role_target,
                question_type=req.question_type,
                mode=req.mode,
                current_question=req.current_question,
                candidate_answer=req.candidate_answer,
                conversation_context=[turn.model_dump() for turn in req.conversation_context],
            )

            return EvaluateAnswerResponse(
                scores=ScoreObject(
                    clarity=result["clarity"],
                    technical_depth=result["technical_depth"],
                    structure_star=result["structure_star"],
                    relevance=result["relevance"],
                    communication=result["communication"],
                    overall=result["overall"],
                ),
                confidence=float(result.get("confidence", 0.6)),
                uncertainty_flags=result.get("uncertainty_flags", []),
                provider="openai",
                provider_reason=None,
                trace_id=_trace_id(),
            )
        except Exception as exc:
            provider_error_reason = _provider_reason(exc)

    if not ALLOW_RULE_BASED_FALLBACK:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "llm_evaluation_unavailable",
                "message": "LLM answer evaluation is unavailable.",
                "provider": "openai",
                "provider_reason": provider_error_reason or "openai_disabled",
            },
        )

    try:
        result = _hybrid_evaluate_answer(
            role_target=req.role_target,
            question_type=req.question_type,
            mode=req.mode,
            current_question=req.current_question,
            candidate_answer=req.candidate_answer,
        )

        clarity = float(result.get("clarity", 0.0))
        technical_depth = float(result.get("technical_depth", 0.0))
        structure_star = float(result.get("structure_star", 0.0))
        relevance = float(result.get("relevance", 0.0))
        communication = float(result.get("communication", 0.0))
        overall = float(result.get("overall", 0.0))
        model_confidence = float(result.get("confidence", 0.65))
    except Exception:
        # Fallback for reliability if model generation fails.
        result = evaluator.evaluate(
            req.candidate_answer,
            current_question=req.current_question,
            question_type=req.question_type,
            mode=req.mode,
            role_target=req.role_target,
            conversation_context=[turn.model_dump() for turn in req.conversation_context],
        )
        clarity = float(result.get("clarity", 0.0) * 10)
        technical_depth = float(result.get("technical_depth", 0.0) * 10)
        structure_star = float(result.get("structure_star", 0.0) * 10)
        relevance = float(result.get("relevance", 0.0) * 10)
        communication = float(result.get("communication", ((result.get("clarity", 0.0) + result.get("relevance", 0.0)) / 2)) * 10)
        overall = float(result.get("score", 0.0))
        model_confidence = 0.55

    word_count = len(req.candidate_answer.split())
    confidence = model_confidence
    uncertainty_flags = []

    if word_count < 12:
        uncertainty_flags.append("answer_too_short")
        confidence -= 0.2
    if overall < 2:
        uncertainty_flags.append("insufficient_answer")
        confidence -= 0.2
    if overall < 3:
        uncertainty_flags.append("very_low_signal")
        confidence -= 0.1
    if req.mode == "speed_round":
        confidence -= 0.05

    confidence = float(max(0.1, min(0.95, confidence)))

    return EvaluateAnswerResponse(
        scores=ScoreObject(
            clarity=round(max(0, min(10, clarity)), 2),
            technical_depth=round(max(0, min(10, technical_depth)), 2),
            structure_star=round(max(0, min(10, structure_star)), 2),
            relevance=round(max(0, min(10, relevance)), 2),
            communication=round(max(0, min(10, communication)), 2),
            overall=round(max(0, min(10, overall)), 2),
        ),
        confidence=confidence,
        uncertainty_flags=uncertainty_flags,
        provider="fallback",
        provider_reason=provider_error_reason,
        trace_id=_trace_id(),
    )


@router.post("/generate-feedback", response_model=GenerateFeedbackResponse)
def generate_feedback(req: GenerateFeedbackRequest):
    scores = req.scores
    qtype = (req.question_type or "").lower()
    provider_error_reason = None

    if openai_inference.enabled:
        try:
            model_feedback = openai_inference.generate_feedback(
                role_target=req.role_target,
                question_type=req.question_type,
                current_question=req.current_question,
                candidate_answer=req.candidate_answer,
                scores={
                    "clarity": float(scores.clarity),
                    "technical_depth": float(scores.technical_depth),
                    "structure_star": float(scores.structure_star),
                    "relevance": float(scores.relevance),
                    "communication": float(scores.communication),
                    "overall": float(scores.overall),
                },
            )
            return GenerateFeedbackResponse(
                feedback=model_feedback["feedback"],
                improvement_actions=model_feedback["improvement_actions"],
                provider="openai",
                provider_reason=None,
                trace_id=_trace_id(),
            )
        except Exception as exc:
            provider_error_reason = _provider_reason(exc)

    if not ALLOW_RULE_BASED_FALLBACK:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "llm_feedback_unavailable",
                "message": "LLM feedback generation is unavailable.",
                "provider": "openai",
                "provider_reason": provider_error_reason or "openai_disabled",
            },
        )

    try:
        model_feedback = coach.generate_feedback(
            role_target=req.role_target,
            question_type=req.question_type,
            current_question=req.current_question,
            candidate_answer=req.candidate_answer,
            scores={
                "clarity": float(scores.clarity),
                "technical_depth": float(scores.technical_depth),
                "structure_star": float(scores.structure_star),
                "relevance": float(scores.relevance),
                "communication": float(scores.communication),
                "overall": float(scores.overall),
            },
        )
        return GenerateFeedbackResponse(
            feedback=model_feedback["feedback"],
            improvement_actions=model_feedback["improvement_actions"],
            provider="fallback",
            provider_reason=provider_error_reason,
            trace_id=_trace_id(),
        )
    except Exception:
        pass

    if scores.overall < 2.0 or (scores.relevance < 2.5 and scores.technical_depth < 2.5):
        return GenerateFeedbackResponse(
            feedback=(
                "You did not answer the question directly. That is okay, but the interviewer needs to see your reasoning. "
                "If you are unsure, state your assumptions, propose a first step, and explain one tradeoff."
            ),
            improvement_actions=[
                "Start with: 'My first assumption is ...'",
                "Give one concrete approach and why you chose it",
                "End with one metric you would track to validate success",
            ],
            provider="fallback",
            provider_reason=provider_error_reason,
            trace_id=_trace_id(),
        )

    metric_map = {
        "clarity": float(scores.clarity),
        "technical_depth": float(scores.technical_depth),
        "structure_star": float(scores.structure_star),
        "relevance": float(scores.relevance),
        "communication": float(scores.communication),
    }
    weakest = sorted(metric_map.items(), key=lambda kv: kv[1])[:2]
    weakest_keys = [k for k, _ in weakest]

    coaching_lines = {
        "clarity": "Your answer needs a cleaner structure and shorter, high-signal sentences.",
        "technical_depth": "You need more concrete technical details, not just high-level intent.",
        "structure_star": "Your story structure is weak; organize with clear sequence and ownership.",
        "relevance": "Parts of your answer drifted from the exact question asked.",
        "communication": "Delivery felt imprecise; tighten wording and remove filler language.",
    }

    action_map = {
        "clarity": "Use a 3-part format: decision -> reason -> result.",
        "technical_depth": "Name one implementation detail (component, algorithm, API, or data model) and why it matters.",
        "structure_star": "Use STAR explicitly: Situation, Task, Action, Result.",
        "relevance": "Echo the key phrase from the question in your first sentence, then answer only that scope.",
        "communication": "Keep each sentence under ~20 words and remove vague terms.",
    }

    qtype_template = {
        "behavioral": "Template: 'Situation was __. My task was __. I did __. Result was __ (metric).'",
        "system design": "Template: 'I propose __ architecture. Key tradeoff: __ vs __. Failure mode: __. Metric: __.'",
        "technical": "Template: 'Approach: __. Complexity/tradeoff: __. Validation: __.'",
        "leetcode/dsa": "Template: 'Data structure: __. Complexity: __. Edge case: __.'",
    }

    strengths = []
    if scores.technical_depth >= 7:
        strengths.append("strong technical reasoning")
    if scores.relevance >= 7:
        strengths.append("good focus on the prompt")
    if scores.clarity >= 7:
        strengths.append("clear delivery")

    if not strengths:
        strengths_text = "You have a workable baseline"
    else:
        strengths_text = f"You showed {', '.join(strengths[:2])}"

    weakest_text = " and ".join([k.replace("_", " ") for k in weakest_keys])
    lead = f"{strengths_text}, but the biggest gaps were {weakest_text}."

    focused_lines = [coaching_lines[k] for k in weakest_keys]
    feedback = " ".join([lead] + focused_lines)

    actions = [action_map[k] for k in weakest_keys]

    if qtype in qtype_template:
        actions.append(qtype_template[qtype])
    else:
        actions.append("Template: 'Decision -> reasoning -> tradeoff -> measurable outcome.'")

    if scores.overall >= 7.5:
        actions[0] = "Push depth: include one alternative you rejected and why."

    return GenerateFeedbackResponse(
        feedback=feedback,
        improvement_actions=actions,
        provider="fallback",
        provider_reason=provider_error_reason,
        trace_id=_trace_id(),
    )
