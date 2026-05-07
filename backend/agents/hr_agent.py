class HRAgent:
    def __init__(self):
        self.name = "HR Interviewer"

    def ask_question(self, context, evaluation, resume=None):
        if evaluation["star"] < 0.5:
            return "Can you structure your answer using Situation, Task, Action, and Result?"

        if evaluation["vagueness"] < 0.6:
            return "Can you be more specific about your contributions?"

        return "What did you learn from this experience?"