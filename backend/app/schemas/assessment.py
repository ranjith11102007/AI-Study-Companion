from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssessmentCreate(BaseModel):
    course_id: int
    title: str = Field(default="Practice assessment", max_length=200)
    question_count: int = Field(default=5, ge=1, le=20)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    time_limit_minutes: int | None = Field(default=None, ge=1, le=240)


class AssessmentSummary(BaseModel):
    id: int
    course_id: int
    title: str
    difficulty: str
    status: str
    question_count: int
    time_limit_minutes: int | None = None
    generation_notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublicQuestion(BaseModel):
    id: int
    qtype: str
    difficulty: str
    topic: str
    concept: str | None = None
    prompt: str
    options: list[str] | None = None


class AttemptStartResponse(BaseModel):
    attempt_id: int
    assessment_id: int
    status: str
    questions: list[PublicQuestion]


class AnswerSubmission(BaseModel):
    question_id: int
    answer: str = ""


class AttemptSubmitRequest(BaseModel):
    answers: list[AnswerSubmission] = Field(default_factory=list)


class AttemptSummary(BaseModel):
    attempt_id: int
    assessment_id: int
    status: str
    score: float | None = None
    max_score: float | None = None
    percent: float = 0.0
    topics: dict = Field(default_factory=dict)


class GradedQuestion(PublicQuestion):
    correct_answer: str
    explanation: str
    rubric: str | None = None
    source_unit_ids: list[int] | None = None
    verified: bool
    verification_notes: str | None = None
    answer: str = ""
    is_correct: bool | None = None
    score: float | None = None
    feedback: str | None = None


class AttemptDetail(BaseModel):
    attempt_id: int
    assessment_id: int
    status: str
    score: float | None = None
    max_score: float | None = None
    percent: float = 0.0
    questions: list[GradedQuestion] = Field(default_factory=list)
