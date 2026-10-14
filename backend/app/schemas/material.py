from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MaterialResponse(BaseModel):
    id: int
    course_id: int
    filename: str
    original_filename: str
    material_type: str
    processing_status: str
    processing_error: str | None = None
    content_unit_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
