class SkepticAgent:
    def __init__(self):
        self.name = "Skeptic"

    def ask_question(self, context, evaluation, resume=None):
        if evaluation["vagueness"] < 0.5:
            return "That sounds generic. What exactly did YOU do?"

        if evaluation["semantic"] < 0.4:
            return "I don’t think you understood the question. Try again."

        return "Are you sure that's the best approach? What are the trade-offs?"