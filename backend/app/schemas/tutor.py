from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TutorAskRequest(BaseModel):
    course_id: int
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None


class Citation(BaseModel):
    content_unit_id: int
    material_id: int
    material_title: str
    material_type: str
    page_number: int | None = None
    slide_number: int | None = None
    start_timestamp: float | None = None
    end_timestamp: float | None = None
    excerpt: str
    score: float | None = None


class TutorAnswerResponse(BaseModel):
    conversation_id: int
    message_id: int
    answer: str
    evidence_status: str = Field(description="grounded | insufficient")
    citations: list[Citation] = Field(default_factory=list)
    sources_considered: int = 0


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    evidence_status: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationSummary(BaseModel):
    id: int
    course_id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetail(BaseModel):
    id: int
    course_id: int
    title: str
    messages: list[MessageOut] = Field(default_factory=list)
