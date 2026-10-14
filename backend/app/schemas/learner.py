from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MasteryOut(BaseModel):
    topic: str
    mastery: float
    evidence_count: int
    correct_count: int
    last_practiced_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RecommendationOut(BaseModel):
    id: int
    kind: str
    topic: str | None = None
    reason: str
    priority: float
    material_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MasteryOverview(BaseModel):
    course_id: int
    topics: list[MasteryOut]
    weak_topics: list[MasteryOut]
    strong_topics: list[MasteryOut]
    untested_topics: list[str]
