"""Flashcard + course summary schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


class GenerateFlashcardsRequest(BaseModel):
    course_id: int
    count: int = Field(default=8, ge=1, le=30)
    kind: str = Field(default="practice", max_length=24)


class FlashcardResponse(BaseModel):
    id: int
    course_id: int
    course_title: str | None = None
    front: str
    back: str
    topic: str | None = None
    source_unit_id: int | None = None
    interval_days: int
    ease: float
    correct_count: int
    wrong_count: int
    next_review_at: datetime | None = None
    last_reviewed_at: datetime | None = None
    created_at: datetime


class ReviewRequest(BaseModel):
    correct: bool


class CourseSummaryResponse(BaseModel):
    course_id: int
    course_title: str | None = None
    title: str
    body: str
    source_unit_count: int
    model: str
    generated_at: datetime
    cached: bool = False
