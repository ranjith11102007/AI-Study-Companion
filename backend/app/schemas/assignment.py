"""Assignment / study-plan schemas. State and ownership are always server-derived."""

from datetime import datetime

from pydantic import BaseModel, Field
from typing import Literal


Status = Literal["todo", "in_progress", "done", "skipped"]
Kind = Literal["practice", "review", "reflection"]


class AssignmentCreate(BaseModel):
    course_id: int
    title: str = Field(min_length=1, max_length=200)
    kind: Kind = "practice"
    topic: str | None = Field(default=None, max_length=120)
    material_id: int | None = None
    due_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=800)


class AssignmentGenerateRequest(BaseModel):
    course_id: int
    # How many assignments to create (one per weak topic, capped to what exists).
    count: int = Field(default=3, ge=1, le=20)
    kind: Kind = "practice"
    days_out: int = Field(default=7, ge=1, le=60)


class AssignmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Kind | None = None
    topic: str | None = None
    material_id: int | None = None
    status: Status | None = None
    due_at: datetime | None = None
    notes: str | None = None


class AssignmentResponse(BaseModel):
    id: int
    course_id: int
    course_title: str | None = None
    title: str
    kind: str
    topic: str | None = None
    material_id: int | None = None
    status: str
    due_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
