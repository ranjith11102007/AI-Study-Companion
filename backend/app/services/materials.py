"""Learning-material service: file storage + ownership-scoped lookups."""

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.ingestion.extractors import IngestionError, detect_material_type
from app.models.content_unit import ContentUnit
from app.models.course import Course
from app.models.learning_material import LearningMaterial

settings = get_settings()

MAX_FILENAME_LENGTH = 255


async def get_owned_course(
    db: AsyncSession, course_id: int, user_id: int
) -> Course:
    result = await db.execute(
        select(Course).filter(Course.id == course_id, Course.user_id == user_id)
    )
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )
    return course


def _safe_original_name(filename: str | None) -> str:
    name = (filename or "upload").strip().replace("\\", "/").rsplit("/", 1)[-1]
    return name[:MAX_FILENAME_LENGTH] or "upload"


def validate_material(filename: str | None) -> tuple[str, str]:
    """Return ``(original_filename, material_type)`` or raise a 400."""
    original = _safe_original_name(filename)
    try:
        material_type = detect_material_type(original)
    except IngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    extension = original.rsplit(".", 1)[-1].lower()
    if extension not in settings.allowed_extension_set():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension: .{extension}",
        )
    return original, material_type


async def save_upload(course_id: int, upload: UploadFile, extension: str) -> Path:
    """Persist the upload under data/uploads/<course_id>/ and return the path."""
    target_dir = settings.upload_dir / str(course_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.{extension}"
    target = target_dir / stored_name

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    size = 0
    try:
        with target.open("wb") as buffer:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds the {settings.max_upload_size_mb} MB limit.",
                    )
                buffer.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    if size == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty."
        )
    return target


async def list_materials(db: AsyncSession, course_id: int) -> list[LearningMaterial]:
    result = await db.execute(
        select(LearningMaterial)
        .filter(LearningMaterial.course_id == course_id)
        .order_by(LearningMaterial.created_at.desc(), LearningMaterial.id.desc())
    )
    return list(result.scalars().all())


async def count_units(db: AsyncSession, material_id: int) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(ContentUnit)
        .filter(ContentUnit.material_id == material_id)
    )
    return int(result.scalar_one())


async def get_material(
    db: AsyncSession, material_id: int, user_id: int
) -> LearningMaterial:
    result = await db.execute(
        select(LearningMaterial)
        .join(Course, Course.id == LearningMaterial.course_id)
        .filter(LearningMaterial.id == material_id, Course.user_id == user_id)
    )
    material = result.scalar_one_or_none()
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Material not found"
        )
    return material
