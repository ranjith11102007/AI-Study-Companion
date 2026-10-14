from datetime import datetime

from pydantic import BaseModel


class ProviderStatus(BaseModel):
    name: str
    status: str
    detail: str | None = None


class ProvidersResponse(BaseModel):
    status: str
    timestamp: datetime
    degraded: list[str] = []
    providers: list[dict]


class CitationResolved(BaseModel):
    content_unit_id: int
    course_id: int
    material_id: int
    material_title: str
    material_type: str
    content_type: str
    title: str | None = None
    content: str
    page_number: int | None = None
    slide_number: int | None = None
    start_timestamp: float | None = None
    end_timestamp: float | None = None
    location: str


class EvaluateRequest(BaseModel):
    dataset: str | None = None
    store: bool = True


class EvaluationResponse(BaseModel):
    dataset: str
    metrics: dict
    per_question: list[dict]
