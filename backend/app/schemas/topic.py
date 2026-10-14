from pydantic import BaseModel, Field


class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    parent_id: int | None = None


class TopicOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    parent_id: int | None = None
    parent_name: str | None = None
    source_count: int = 0


class TopicSuggestion(BaseModel):
    name: str
    source: str = "heuristic"


class PrerequisiteUpdate(BaseModel):
    prerequisite_id: int | None = None


class AttachSourceRequest(BaseModel):
    content_unit_id: int
