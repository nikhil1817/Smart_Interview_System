from fastapi import APIRouter
from pydantic import BaseModel
from controller.interview_controller import InterviewController

router = APIRouter()
controller = InterviewController()

class StartRequest(BaseModel):
    role: str
    mode: str = "standard"
    question_type: str = "Behavioral"
    interviewer: str | None = None
    resume_summary: str = ""
    resume_data: dict | None = None

class AnswerRequest(BaseModel):
    session_id: str
    answer: str

@router.post("/start-interview")
def start_interview(req: StartRequest):
    return controller.start_session(
        req.role,
        req.mode,
        req.question_type,
        req.interviewer,
        req.resume_summary,
        req.resume_data
    )

@router.post("/answer")
def answer(req: AnswerRequest):
    return controller.handle_answer(req.session_id, req.answer)

@router.get("/report/{session_id}")
def report(session_id: str):
    return controller.generate_report(session_id)