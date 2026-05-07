from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    speaker: Literal["assistant", "user"]
    text: str = Field(min_length=1)


class ScoreObject(BaseModel):
    clarity: float = Field(ge=0, le=10)
    technical_depth: float = Field(ge=0, le=10)
    structure_star: float = Field(ge=0, le=10)
    relevance: float = Field(ge=0, le=10)
    communication: float = Field(ge=0, le=10)
    overall: float = Field(ge=0, le=10)


class GenerateQuestionConstraints(BaseModel):
    max_question_words: int = Field(default=35, ge=10, le=80)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class GenerateQuestionRequest(BaseModel):
    session_id: str
    role_target: str
    question_type: str
    mode: str
    interviewer_persona: str
    resume_summary: str = ""
    resume_data: Optional[dict] = None
    conversation_context: List[ConversationTurn] = []
    candidate_answer: str = ""
    constraints: GenerateQuestionConstraints = GenerateQuestionConstraints()


class GenerateQuestionResponse(BaseModel):
    question: str
    intent: str
    difficulty: Literal["easy", "medium", "hard"]
    persona_style: str
    expected_signals: List[str]
    question_source: Literal["resume", "general"] = "general"
    provider: Literal["openai", "github_models", "fallback"] = "fallback"
    provider_reason: Optional[str] = None
    persona: Optional[dict] = None
    panel_members: List[dict] = []
    trace_id: str


class EvaluateAnswerRequest(BaseModel):
    session_id: str
    role_target: str
    question_type: str
    mode: str
    current_question: str
    candidate_answer: str
    conversation_context: List[ConversationTurn] = []


class EvaluateAnswerResponse(BaseModel):
    scores: ScoreObject
    confidence: float = Field(ge=0, le=1)
    uncertainty_flags: List[str] = []
    provider: Literal["openai", "github_models", "fallback"] = "fallback"
    provider_reason: Optional[str] = None
    trace_id: str


class GenerateFeedbackRequest(BaseModel):
    session_id: str
    current_question: str
    candidate_answer: str
    scores: ScoreObject
    role_target: str
    question_type: str


class GenerateFeedbackResponse(BaseModel):
    feedback: str
    improvement_actions: List[str]
    provider: Literal["openai", "github_models", "fallback"] = "fallback"
    provider_reason: Optional[str] = None
    trace_id: str


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None


class ErrorResponse(BaseModel):
    error: ErrorPayload
    trace_id: str
