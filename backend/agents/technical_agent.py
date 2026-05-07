class TechnicalAgent:
    def __init__(self):
        self.name = "Technical Interviewer"

    def ask_question(self, context, evaluation, resume=None):
        if resume and resume.get("skills"):
            skill = resume["skills"][0]
            return f"You listed {skill}. Can you explain a challenge you faced using it?"

        if evaluation["semantic"] < 0.5:
            return "Can you clarify your approach?"

        return "How would you optimize your solution?"