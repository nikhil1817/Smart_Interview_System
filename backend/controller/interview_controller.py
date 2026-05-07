import random
from enum import Enum
from fastapi import HTTPException
from services.session_manager import SessionManager
from services.question_generator import QuestionGenerator
from services.interview_blueprint import (
    default_interviewer_for_mode,
    get_interviewer_profile,
    get_panel_members,
)
from agents.technical_agent import TechnicalAgent
from agents.hr_agent import HRAgent
from agents.skeptic_agent import SkepticAgent
from agents.evaluator_agent import EvaluatorAgent


class InterviewState(str, Enum):
    START = "START"
    ROLE_SELECTED = "ROLE_SELECTED"
    RESUME_PROCESSED = "RESUME_PROCESSED"
    QUESTION_ASKED = "QUESTION_ASKED"
    ANSWER_RECEIVED = "ANSWER_RECEIVED"
    ANSWER_EVALUATED = "ANSWER_EVALUATED"
    FOLLOW_UP = "FOLLOW_UP"
    INTERVIEW_COMPLETE = "INTERVIEW_COMPLETE"


def transition_state(current_state: str, event: str) -> str:
    state_key = InterviewState(current_state)
    transitions = {
        InterviewState.START: {
            "select_role": InterviewState.ROLE_SELECTED,
        },
        InterviewState.ROLE_SELECTED: {
            "process_resume": InterviewState.RESUME_PROCESSED,
        },
        InterviewState.RESUME_PROCESSED: {
            "ask_question": InterviewState.QUESTION_ASKED,
        },
        InterviewState.QUESTION_ASKED: {
            "submit_answer": InterviewState.ANSWER_RECEIVED,
        },
        InterviewState.ANSWER_RECEIVED: {
            "evaluate_answer": InterviewState.ANSWER_EVALUATED,
        },
        InterviewState.ANSWER_EVALUATED: {
            "follow_up": InterviewState.FOLLOW_UP,
            "next_question": InterviewState.QUESTION_ASKED,
            "end_interview": InterviewState.INTERVIEW_COMPLETE,
        },
        InterviewState.FOLLOW_UP: {
            "submit_answer": InterviewState.ANSWER_RECEIVED,
            "end_interview": InterviewState.INTERVIEW_COMPLETE,
        },
        InterviewState.INTERVIEW_COMPLETE: {},
    }

    next_state = transitions.get(state_key, {}).get(event)
    if next_state is None:
        raise ValueError(f"Invalid transition: {current_state} --({event})-> ?")
    return next_state.value

class InterviewController:
    def __init__(self):
        self.tech = TechnicalAgent()
        self.hr = HRAgent()
        self.skeptic = SkepticAgent()
        self.evaluator = EvaluatorAgent()
        self.qgen = QuestionGenerator()
        self.sessions = SessionManager()
        self.panel_fsa_personas = [
            {
                "name": "Friendly HR",
                "role": "HR",
                "style": "empathetic, warm, supportive",
                "focus": "culture-fit and communication",
                "lead": "Let's begin with a people perspective.",
                "agent": "hr",
            },
            {
                "name": "Strict Interviewer",
                "role": "Hiring Manager",
                "style": "direct, demanding, standards-focused",
                "focus": "ownership and accountability",
                "lead": "Be precise and concrete.",
                "agent": "skeptic",
            },
            {
                "name": "Deep Technical Expert",
                "role": "Senior Engineer",
                "style": "technical, rigorous, system-level",
                "focus": "architecture and tradeoffs",
                "lead": "Let's go deeper technically.",
                "agent": "technical",
            },
            {
                "name": "Interrupting Skeptic",
                "role": "Panel Skeptic",
                "style": "skeptical, interruptive, challenge-oriented",
                "focus": "assumption stress-testing",
                "lead": "I'll challenge that assumption.",
                "agent": "skeptic",
            },
        ]

    def start_session(
        self,
        role,
        mode="standard",
        question_type="Behavioral",
        interviewer=None,
        resume_summary="",
        resume_data=None
    ):
        current_state = InterviewState.START.value
        current_state = transition_state(current_state, "select_role")

        normalized_mode = self.normalize_mode(mode)
        interviewer_name = interviewer or default_interviewer_for_mode(normalized_mode)
        current_state = transition_state(current_state, "process_resume")

        panel_members = [
            {
                "name": persona["name"],
                "role": persona["role"],
                "style": persona["style"],
                "focus": persona["focus"],
                "agent": persona["agent"],
            }
            for persona in self.panel_fsa_personas
        ] if normalized_mode == "panel" else []

        opening_interviewer = "Friendly HR" if normalized_mode == "panel" else interviewer_name
        opening_panel_index = 0 if normalized_mode == "panel" else -1

        session_id = self.sessions.create_session(
            role,
            normalized_mode,
            question_type,
            opening_interviewer,
            resume_summary,
            resume_data,
            panel_members,
            current_state=current_state,
            question_count=0,
            max_questions=5,
            current_question="",
            current_interviewer=opening_interviewer,
            panel_index=opening_panel_index,
        )

        session = self.sessions.get_session(session_id)
        resume = session.get("resume")
        if normalized_mode == "panel":
            speaker = self.panel_persona_by_index(session.get("panel_index", 0))
        else:
            speaker = self.resolve_opening_speaker(session)

        if resume:
            opener = self.qgen.generate_opening(role, question_type, resume, normalized_mode)
        else:
            opener = self.default_opening(role, question_type)

        first_question = self.decorate_opening(normalized_mode, opener, role, interviewer_name, speaker)
        question_source = "resume" if self.qgen.is_resume_question(first_question) else "general"
        current_state = transition_state(current_state, "ask_question")

        self.sessions.update_session(
            session_id,
            current_question=first_question,
            current_state=current_state,
            question_count=1,
            current_interviewer=speaker["display_name"],
        )

        return {
            "session_id": session_id,
            "question": first_question,
            "question_source": question_source,
            "agent": speaker["display_name"],
            "persona": speaker,
            "panel_members": session.get("panel_members", []),
            "mode": normalized_mode,
            "role": role,
            "question_type": question_type,
            "current_state": current_state,
        }

    def handle_answer(self, session_id, user_answer):
        session = self.sessions.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")

        current_state = session.get("current_state", InterviewState.START.value)
        if current_state not in {InterviewState.QUESTION_ASKED.value, InterviewState.FOLLOW_UP.value}:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid state for answer submission: {current_state}",
            )

        try:
            current_state = transition_state(current_state, "submit_answer")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"FSA Error: {str(exc)}") from exc

        mode = session.get("mode", "standard")
        question_type = session.get("question_type", "Behavioral")

        evaluation = self.evaluator.evaluate(user_answer)
        agent_eval = self.normalize_agent_evaluation(evaluation)

        try:
            current_state = transition_state(current_state, "evaluate_answer")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"FSA Error: {str(exc)}") from exc

        if session.get("question_count", 0) >= session.get("max_questions", 5):
            try:
                current_state = transition_state(current_state, "end_interview")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"FSA Error: {str(exc)}") from exc

            speaker = {
                "name": "System",
                "role": "System",
                "style": "closing",
                "focus": "interview completion",
                "lead": "",
                "agent": "system",
                "display_name": "System",
            }
            question = "Interview complete. Thank you for participating."
            question_source = "general"
            session["current_state"] = current_state
            session["current_interviewer"] = speaker["display_name"]
            session["current_question"] = question

            self.sessions.add_interaction(session_id, {
                "agent": speaker["display_name"],
                "speaker": speaker,
                "answer": user_answer,
                "evaluation": evaluation,
                "next_question": question,
                "source": question_source,
                "state": current_state,
            })

            return {
                "agent": speaker["display_name"],
                "question": question,
                "question_source": question_source,
                "evaluation": evaluation,
                "persona": speaker,
                "panel_members": session.get("panel_members", []),
                "current_state": current_state,
            }

        if mode == "panel":
            next_index = self.next_panel_speaker(user_answer, session.get("panel_index", 0))
            session["panel_index"] = next_index
            speaker = self.panel_persona_by_index(next_index)
            agent = self.agent_from_name(speaker.get("agent"))
            try:
                current_state = transition_state(current_state, "follow_up")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"FSA Error: {str(exc)}") from exc
        else:
            agent = self.choose_agent(mode, session, agent_eval)
            speaker = self.resolve_speaker(session, agent)
            try:
                current_state = transition_state(current_state, "next_question")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"FSA Error: {str(exc)}") from exc

        resume = session.get("resume")
        question = self.next_question(mode, session, agent, speaker, user_answer, agent_eval, resume, question_type)
        question_source = "resume" if self.qgen.is_resume_question(question) else "general"
        session["current_state"] = current_state
        session["current_question"] = question
        session["current_interviewer"] = speaker["display_name"]
        session["question_count"] = int(session.get("question_count", 0)) + 1

        # Save interaction
        self.sessions.add_interaction(session_id, {
            "agent": speaker["display_name"],
            "speaker": speaker,
            "answer": user_answer,
            "evaluation": evaluation,
            "next_question": question,
            "source": question_source,
            "state": current_state,
        })

        return {
            "agent": speaker["display_name"],
            "question": question,
            "question_source": question_source,
            "evaluation": evaluation,
            "persona": speaker,
            "panel_members": session.get("panel_members", []),
            "current_state": current_state,
        }

    def normalize_agent_evaluation(self, evaluation):
        clarity = float(evaluation.get("clarity", 0.0))
        relevance = float(evaluation.get("relevance", 0.0))
        structure = float(evaluation.get("structure_star", evaluation.get("star", 0.0)))

        # Model evaluator returns normalized [0,1] for most fields in this controller path.
        clarity_norm = clarity if clarity <= 1.0 else clarity / 10.0
        relevance_norm = relevance if relevance <= 1.0 else relevance / 10.0
        structure_norm = structure if structure <= 1.0 else structure / 10.0

        semantic = float(evaluation.get("semantic", relevance_norm))
        semantic_norm = semantic if semantic <= 1.0 else semantic / 10.0

        vagueness = float(evaluation.get("vagueness", max(0.0, min(1.0, 1.0 - clarity_norm))))

        merged = dict(evaluation)
        merged.update(
            {
                "clarity": max(0.0, min(1.0, clarity_norm)),
                "relevance": max(0.0, min(1.0, relevance_norm)),
                "star": max(0.0, min(1.0, structure_norm)),
                "structure_star": max(0.0, min(1.0, structure_norm)),
                "semantic": max(0.0, min(1.0, semantic_norm)),
                "vagueness": max(0.0, min(1.0, vagueness)),
            }
        )
        return merged

    def panel_persona_by_index(self, index):
        persona = self.panel_fsa_personas[index % len(self.panel_fsa_personas)]
        return {
            "name": persona["name"],
            "role": persona["role"],
            "style": persona["style"],
            "focus": persona["focus"],
            "lead": persona["lead"],
            "agent": persona["agent"],
            "display_name": persona["name"],
        }

    def next_panel_speaker(self, answer, current_index):
        _ = answer
        return (int(current_index) + 1) % len(self.panel_fsa_personas)

    def agent_from_name(self, name):
        key = (name or "").strip().lower()
        if key in {"hr", "friendly_hr"}:
            return self.hr
        if key in {"skeptic", "strict", "interrupting_skeptic"}:
            return self.skeptic
        if key in {"technical", "tech", "deep_technical_expert"}:
            return self.tech
        return self.hr

    def normalize_mode(self, mode):
        return (mode or "standard").strip().lower().replace(" ", "_")

    def opening_agent(self, mode):
        if mode == "stress":
            return self.skeptic
        if mode == "speed_round":
            return self.tech
        return self.hr

    def default_opening(self, role, question_type):
        return (
            f"For this {question_type} interview for the {role} role, "
            "tell me about the experience that best prepares you for it."
        )

    def decorate_opening(self, mode, opener, role, interviewer, speaker):
        if mode == "panel":
            return f"{speaker['name']} joining for the panel interview for the {role} role. {opener}"
        if mode == "stress":
            return f"{speaker['lead']} This will be a tough interview. {opener}"
        if mode == "speed_round":
            return f"{speaker['lead']} Speed round starts now. {opener}"
        if interviewer:
            return f"{speaker['name']} here. {speaker['lead']} {opener}"
        return opener

    def resolve_opening_speaker(self, session):
        mode = session.get("mode", "standard")

        if mode == "panel":
            return self.resolve_panel_speaker(session, self.hr)

        return self.resolve_single_speaker(session, self.opening_agent(mode))

    def resolve_speaker(self, session, agent):
        if session.get("mode") == "panel":
            return self.resolve_panel_speaker(session, agent)

        return self.resolve_single_speaker(session, agent)

    def resolve_single_speaker(self, session, agent):
        profile = get_interviewer_profile(session.get("interviewer"))
        return {
            "name": profile["name"],
            "role": profile["role"],
            "style": profile["style"],
            "focus": profile["followup"],
            "lead": profile["lead"],
            "agent": agent.name,
            "display_name": profile["name"]
        }

    def resolve_panel_speaker(self, session, agent):
        members = session.get("panel_members", [])

        if not members:
            return {
                "name": agent.name,
                "role": "Panelist",
                "style": "panel",
                "focus": "structured assessment",
                "lead": "Let's continue.",
                "agent": agent.name,
                "display_name": agent.name
            }

        matching_members = [member for member in members if member.get("agent") == agent.name]
        candidates = matching_members or members
        member = candidates[session.get("turn_index", 0) % len(candidates)]

        return {
            "name": member["name"],
            "role": member["role"],
            "style": member["style"],
            "focus": member["focus"],
            "lead": f"From a {member['focus']} angle,",
            "agent": agent.name,
            "display_name": f"{member['name']} · {member['role']}"
        }

    def choose_agent(self, mode, session, evaluation):
        if mode == "panel":
            return self.panel_logic(session, evaluation)
        if mode == "stress":
            return self.stress_logic(session, evaluation)
        if mode == "speed_round":
            return self.speed_round_logic(session, evaluation)
        return self.standard_logic(evaluation)

    def standard_logic(self, evaluation):
        """Standard mode: Simple progression based on answer quality"""
        if evaluation["vagueness"] < 0.5:
            return self.skeptic
        elif evaluation["star"] < 0.5:
            return self.hr
        else:
            return self.tech

    def panel_logic(self, session, evaluation):
        """Panel mode: Simulates realistic panel interview with interruptions"""
        history = session["history"]

        # First question always HR
        if len(history) == 0:
            return self.hr

        # Random interruptions to feel more natural
        if random.random() < 0.3:
            return self.skeptic

        # If vague → skeptic interrupts
        if evaluation["vagueness"] < 0.5:
            return self.skeptic

        # If weak structure → HR
        if evaluation["star"] < 0.5:
            return self.hr

        # Otherwise technical deep dive
        return self.tech

    def stress_logic(self, session, evaluation):
        if evaluation["vagueness"] < 0.7 or evaluation["clarity"] < 0.6:
            return self.skeptic
        if len(session["history"]) % 2 == 0:
            return self.skeptic
        return self.tech

    def speed_round_logic(self, session, evaluation):
        history_length = len(session["history"])

        if history_length % 3 == 0:
            return self.tech
        if evaluation["star"] < 0.5:
            return self.hr
        return self.skeptic

    def next_question(self, mode, session, agent, speaker, user_answer, evaluation, resume, question_type):
        history = session.get("history", [])
        fallback_question = agent.ask_question(user_answer, evaluation, resume)

        base_question = self.qgen.generate_followup(
            session["role"],
            question_type,
            resume,
            history,
            fallback_question,
            mode
        )

        if speaker.get("focus") and mode != "speed_round":
            base_question = f"{speaker['lead']} {base_question}"

        if mode == "panel":
            return base_question
        if mode == "stress":
            challenge = random.choice([
                "That's still too soft.",
                "I want specifics, not generalities.",
                "Convince me you made the right call."
            ])
            return f"{challenge} {base_question}"
        if mode == "speed_round":
            return f"Quick answer only: {base_question}"

        return base_question

    def generate_report(self, session_id):
        session = self.sessions.get_session(session_id)
        history = session["history"]

        scores = [h["evaluation"]["score"] for h in history]

        avg_score = sum(scores) / len(scores) if scores else 0

        weak_areas = []
        if any(h["evaluation"]["vagueness"] < 0.5 for h in history):
            weak_areas.append("Vagueness")
        if any(h["evaluation"]["star"] < 0.5 for h in history):
            weak_areas.append("Behavioral structure")

        return {
            "average_score": round(avg_score, 2),
            "total_questions": len(history),
            "mode": session.get("mode", "standard"),
            "role": session.get("role"),
            "question_type": session.get("question_type"),
            "interviewer": session.get("interviewer"),
            "current_state": session.get("current_state"),
            "weak_areas": weak_areas,
            "summary": "Needs improvement in clarity and structure."
        }
    