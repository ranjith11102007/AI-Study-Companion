"""Profile and study-history schemas.

Nothing here is synthesised: every field is read from a real row. ``HistoryEvent``
carries a ``kind`` and an ``href`` so the UI can deep-link straight to the real
object (a conversation, an attempt, a course) rather than a decorative feed.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    id: int
    name: str
    email: str
    display_name: str | None = None
    preferences: dict | None = None
    # True only if the address was actually confirmed (email_verified_at set).
    email_verified: bool = False
    created_at: datetime


class UserProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    display_name: str | None = Field(default=None, max_length=120)
    preferences: dict | None = None


class HistoryEvent(BaseModel):
    # kind: tutor | assessment | upload | mastery
    kind: str
    id: str
    title: str
    detail: str | None = None
    course_id: int | None = None
    course_title: str | None = None
    status: str | None = None
    score: float | None = None
    max_score: float | None = None
    href: str | None = None
    at: datetime


class HistoryResponse(BaseModel):
    events: list[HistoryEvent] = Field(default_factory=list)
    total: int = 0
    has_more: bool = False
    kinds: list[str] = Field(default_factory=list)
