"""Citation resolution: turn a stored content unit id into real source detail.

Every citation shown in the UI resolves through here, so it is guaranteed to
reference a database record the requesting user actually owns.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_unit import ContentUnit
from app.models.course import Course
from app.models.learning_material import LearningMaterial


def location_label(
    page_number: int | None,
    slide_number: int | None,
    start_timestamp: float | None,
) -> str:
    if page_number is not None:
        return f"page {page_number}"
    if slide_number is not None:
        return f"slide {slide_number}"
    if start_timestamp is not None:
        return f"t={start_timestamp:.1f}s"
    return "excerpt"


async def resolve_content_unit(
    db: AsyncSession, *, user_id: int, content_unit_id: int
) -> dict:
    row = (
        await db.execute(
            select(ContentUnit, LearningMaterial)
            .join(LearningMaterial, LearningMaterial.id == ContentUnit.material_id)
            .join(Course, Course.id == ContentUnit.course_id)
            .where(ContentUnit.id == content_unit_id, Course.user_id == user_id)
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    unit, material = row
    return {
        "content_unit_id": unit.id,
        "course_id": unit.course_id,
        "material_id": material.id,
        "material_title": material.original_filename,
        "material_type": material.material_type,
        "content_type": unit.content_type,
        "title": unit.title,
        "content": unit.content,
        "page_number": unit.page_number,
        "slide_number": unit.slide_number,
        "start_timestamp": unit.start_timestamp,
        "end_timestamp": unit.end_timestamp,
        "location": location_label(
            unit.page_number, unit.slide_number, unit.start_timestamp
        ),
    }
