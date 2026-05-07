import uuid

class SessionManager:
    def __init__(self):
        self.sessions = {}

    def create_session(
        self,
        role,
        mode="standard",
        question_type="Behavioral",
        interviewer=None,
        resume_summary="",
        resume_data=None,
        panel_members=None,
        current_state="START",
        question_count=0,
        max_questions=5,
        current_question="",
        current_interviewer="",
        panel_index=0,
    ):
        session_id = str(uuid.uuid4())

        self.sessions[session_id] = {
            "role": role,
            "mode": mode,
            "question_type": question_type,
            "interviewer": interviewer,
            "resume_summary": resume_summary,
            "resume": resume_data,
            "panel_members": panel_members or [],
            "turn_index": 0,
            "current_agent": "hr",
            "history": [],
            "current_state": current_state,
            "question_count": question_count,
            "max_questions": max_questions,
            "current_question": current_question,
            "current_interviewer": current_interviewer,
            "panel_index": panel_index,
        }

        return session_id

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def add_interaction(self, session_id, interaction):
        self.sessions[session_id]["history"].append(interaction)
        self.sessions[session_id]["turn_index"] += 1
        
    def attach_resume(self, session_id, resume_data):
        self.sessions[session_id]["resume"] = resume_data
        self.sessions[session_id]["resume_summary"] = resume_data.get("summary", "")

    def update_session(self, session_id, **kwargs):
        if session_id not in self.sessions:
            return
        self.sessions[session_id].update(kwargs)