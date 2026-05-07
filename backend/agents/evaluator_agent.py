from services.model_evaluator import ModelEvaluator

class EvaluatorAgent:
    def __init__(self):
        self.model_evaluator = ModelEvaluator()

    def evaluate(
        self,
        answer: str,
        current_question: str = "",
        question_type: str = "",
        mode: str = "",
        role_target: str = "",
        interviewer_persona: str = "",
        resume_summary: str = "",
        conversation_context: list[dict] | None = None,
    ):
        return self.model_evaluator.evaluate(
            answer,
            current_question=current_question,
            question_type=question_type,
            mode=mode,
            role_target=role_target,
            interviewer_persona=interviewer_persona,
            resume_summary=resume_summary,
            conversation_context=conversation_context,
        )