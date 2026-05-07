import random
import re
from services.interview_blueprint import get_role_questions


SPECIALIZED_ROLE_QUESTIONS = {
    "swe": {
        "technical": [
            "Describe a production bug you debugged end-to-end. How did you isolate root cause?",
            "How do you decide between shipping quickly and hardening reliability for a backend change?",
        ],
        "system design": [
            "Design an internal notifications service: where do you enforce idempotency and retries?",
            "How would you redesign a high-latency API under 10x traffic growth?",
        ],
    },
    "frontend engineer": {
        "technical": [
            "Explain a UI performance bottleneck you fixed and how you verified the improvement.",
            "How do you structure state boundaries to prevent unnecessary rerenders in complex screens?",
        ],
        "system design": [
            "Design a design-system architecture that scales across multiple product teams.",
            "How would you handle SSR, caching, and hydration tradeoffs for a content-heavy app?",
        ],
    },
    "backend engineer": {
        "technical": [
            "Walk me through a data consistency issue you handled in a distributed service.",
            "How do you choose between synchronous APIs and event-driven workflows for a feature?",
        ],
        "system design": [
            "Design a rate-limited API gateway with observability and graceful degradation.",
            "How would you evolve a monolith into services without breaking reliability?",
        ],
    },
    "ml engineer": {
        "technical": [
            "Describe how you productionized a model and monitored drift over time.",
            "How do you debug model quality regressions after a new training run?",
        ],
        "system design": [
            "Design an inference platform with latency SLOs and fallback policies.",
            "How would you build a feature store strategy for online/offline parity?",
        ],
    },
    "data scientist": {
        "technical": [
            "Tell me about an experiment that changed a product decision. What was your causal reasoning?",
            "How do you handle missing data and leakage risks in a modeling workflow?",
        ],
        "behavioral": [
            "Describe a time your analysis conflicted with stakeholder intuition. How did you align the team?",
            "How do you communicate uncertainty without losing decision momentum?",
        ],
    },
    "product manager": {
        "behavioral": [
            "Tell me about a roadmap tradeoff where both options were high-impact. How did you decide?",
            "Describe a launch that underperformed. What did you change next and why?",
        ],
        "system design": [
            "How would you design a metrics framework for a new user-onboarding funnel?",
            "What system constraints would you prioritize before scaling a new product surface?",
        ],
    },
    "devops": {
        "technical": [
            "Describe an incident response where you reduced time-to-recovery materially.",
            "How do you choose alert thresholds that reduce noise but catch critical failures?",
        ],
        "system design": [
            "Design a CI/CD pipeline with rollback safety for high-frequency deployments.",
            "How would you architect multi-region failover for a customer-facing service?",
        ],
    },
    "engineering manager": {
        "behavioral": [
            "Tell me about a low-performing team dynamic you turned around. What actions worked?",
            "How do you balance short-term delivery pressure with long-term engineering quality?",
        ],
        "mixed": [
            "Describe a cross-functional decision where you had to balance technical debt and business urgency.",
            "How do you coach senior engineers through ambiguous architecture decisions?",
        ],
    },
}


class QuestionGenerator:
    RESUME_MIN_QUESTIONS = 1
    RESUME_WINDOW = 5

    def generate_opening(self, role="SWE", question_type="Behavioral", resume_data=None, mode="standard"):
        # Start with a role/question-type prompt unless resume signal is exceptionally strong.
        if self._should_use_resume_opening(resume_data):
            resume_question = self._resume_question(resume_data, opening=True)
            if resume_question:
                return self._apply_mode_style(resume_question, mode)

        questions = self._role_question_pool(role, question_type, mode)
        chosen = random.choice(questions) if questions else "Tell me about yourself."
        return self._apply_mode_style(chosen, mode)

    def generate_followup(self, role, question_type, resume_data, history, fallback_question, mode="standard"):
        if len(history) >= 4:
            return self._apply_mode_style("Before we wrap, what is one decision you would revisit and why?", mode)

        should_push_resume = self._needs_resume_quota(history, resume_data)
        if should_push_resume:
            resume_question = self._resume_question(
                resume_data,
                opening=False,
                history=history,
                force=True
            )
            if resume_question:
                return self._apply_mode_style(resume_question, mode)

        # If quota is met, only occasionally pivot to resume context.
        if resume_data and random.random() < 0.28:
            resume_question = self._resume_question(resume_data, opening=False, history=history, force=False)
            if resume_question:
                return self._apply_mode_style(resume_question, mode)

        role_questions = self._role_question_pool(role, question_type, mode)
        used_questions = {item.get("next_question", "") for item in history}
        available_questions = [question for question in role_questions if question not in used_questions]

        if available_questions:
            return self._apply_mode_style(random.choice(available_questions), mode)

        return self._apply_mode_style(fallback_question, mode)

    def _resume_question(self, resume_data, opening=False, history=None, force=False):
        if not resume_data:
            return None

        history = history or []
        skills = resume_data.get("skills", [])
        projects = resume_data.get("projects", [])
        achievements = resume_data.get("achievements", [])
        experience = resume_data.get("experience", [])
        keywords = resume_data.get("keywords", [])
        asked_text = self._history_text(history)

        if opening and achievements:
            return f"From your background, tell me about a project where you achieved '{achievements[0]}'. What was your direct contribution?"

        if opening and skills:
            return f"From your background, walk me through a challenging problem you solved using {skills[0]}."

        if (not opening) and achievements:
            for item in achievements:
                if item.lower() not in asked_text:
                    return f"You mentioned '{item}'. How did you measure success, and what tradeoff did you make?"

        if (not opening) and projects:
            for project in projects:
                if project.lower() not in asked_text:
                    return f"From your background, tell me about this project: {project}"

        if (not opening) and experience:
            for exp in experience:
                if exp.lower() not in asked_text:
                    return f"In the role '{exp}', what was the hardest decision you owned end-to-end?"

        if (not opening) and skills:
            for skill in skills:
                if skill.lower() not in asked_text:
                    return f"How did you build real depth in {skill} rather than just surface familiarity?"

        if (not opening) and keywords:
            for keyword in keywords:
                if keyword.lower() not in asked_text:
                    return f"Give me a concrete example where you improved {keyword} and what changed after your work."

        if force and resume_data.get("raw_text"):
            return (
                "From your background, pick one impactful project and walk me through your exact contribution, "
                "decision process, and measurable result."
            )

        return None

    def _history_text(self, history):
        values = []
        for item in history:
            text = (item.get("next_question") or "").strip()
            if text:
                values.append(text.lower())
        return " \n ".join(values)

    def _count_resume_questions(self, history):
        count = 0
        for item in history:
            next_question = (item.get("next_question") or "").strip().lower()
            source = (item.get("source") or "").strip().lower()
            if source == "resume" or self._looks_resume_question(next_question):
                count += 1
        return count

    def is_resume_question(self, question_text):
        return self._looks_resume_question(question_text or "")

    def _looks_resume_question(self, question_text):
        if not question_text:
            return False
        return bool(re.search(r"\byou mentioned\b|\bfrom your background\b|\byour project\b|\bin the role\b", question_text, re.IGNORECASE))

    def _needs_resume_quota(self, history, resume_data):
        if not resume_data:
            return False

        has_resume_signal = any([
            resume_data.get("skills"),
            resume_data.get("projects"),
            resume_data.get("experience"),
            resume_data.get("achievements"),
            resume_data.get("raw_text")
        ])
        if not has_resume_signal:
            return False

        asked_resume = self._count_resume_questions(history)
        return len(history) < self.RESUME_WINDOW and asked_resume < self.RESUME_MIN_QUESTIONS

    def _normalize_question_type(self, question_type):
        return (question_type or "behavioral").strip().lower()

    def _normalize_role(self, role):
        return (role or "swe").strip().lower()

    def _normalize_mode(self, mode):
        return (mode or "standard").strip().lower()

    def _role_question_pool(self, role, question_type, mode):
        role_key = self._normalize_role(role)
        qtype_key = self._normalize_question_type(question_type)
        base = list(get_role_questions(role, question_type))

        role_specific = SPECIALIZED_ROLE_QUESTIONS.get(role_key, {})
        specialized = list(role_specific.get(qtype_key, []))

        if qtype_key == "mixed":
            # Mixed mode pulls from behavioral + technical to feel realistic.
            specialized.extend(role_specific.get("behavioral", [])[:1])
            specialized.extend(role_specific.get("technical", [])[:1])

        # Favor specialized prompts first while keeping blueprint prompts as backup.
        if specialized:
            return specialized + base
        return base

    def _apply_mode_style(self, question, mode):
        mode_key = self._normalize_mode(mode)
        q = (question or "").strip()

        if mode_key == "stress":
            if not re.search(r"prove|defend|justify|specific|exactly", q, re.IGNORECASE):
                return f"Defend your reasoning with specifics: {q}"
            return q

        if mode_key == "speed_round":
            # Keep it concise and sharp for rapid-fire flow.
            words = q.split()
            if len(words) > 18:
                q = " ".join(words[:18]).rstrip(".,;:!?") + "?"
            return f"Quick: {q}"

        if mode_key == "panel":
            if not re.search(r"stakeholder|tradeoff|team|impact", q, re.IGNORECASE):
                return f"From your perspective and team impact, {q[0].lower() + q[1:] if len(q) > 1 else q}"
            return q

        return q

    def _should_use_resume_opening(self, resume_data):
        if not resume_data:
            return False

        signal_count = 0
        for key in ["achievements", "projects", "experience", "skills"]:
            if resume_data.get(key):
                signal_count += 1

        # Use resume as opener only for rich resumes and not every time.
        return signal_count >= 3 and random.random() < 0.35