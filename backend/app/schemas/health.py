from datetime import datetime

from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    status: str = Field(description="connected | unavailable")
    latency_ms: float | None = Field(default=None, description="Round-trip time in ms")
    detail: str | None = Field(default=None, description="Error message when down")


class HealthResponse(BaseModel):
    service: str
    version: str
    environment: str
    status: str = Field(description="ok | degraded")
    timestamp: datetime
    database: DatabaseHealth
