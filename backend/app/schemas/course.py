from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class CourseBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None

class CourseCreate(CourseBase):
    pass

class CourseUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None

class CourseResponse(CourseBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
