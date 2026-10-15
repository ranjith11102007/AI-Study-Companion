from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.ingestion.pipeline import process_material
from app.models.learning_material import LearningMaterial
from app.models.user import User
from app.schemas.material import MaterialResponse
from app.services import materials as material_service

router = APIRouter()

# Served inline so a browser (or a PDF.js `fetch`) can display the original
# file. Unknown extensions fall back to a safe binary type.
_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


async def _serialize(db: AsyncSession, material: LearningMaterial) -> dict:
    return {
        "id": material.id,
        "course_id": material.course_id,
        "filename": material.filename,
        "original_filename": material.original_filename,
        "material_type": material.material_type,
        "processing_status": material.processing_status,
        "processing_error": material.processing_error,
        "content_unit_count": await material_service.count_units(db, material.id),
        "created_at": material.created_at,
    }


@router.post(
    "/courses/{course_id}/materials",
    response_model=MaterialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_material(
    course_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await material_service.get_owned_course(db, course_id, current_user.id)
    original, material_type = material_service.validate_material(file.filename)
    extension = original.rsplit(".", 1)[-1].lower()
    stored_path = await material_service.save_upload(course_id, file, extension)

    material = LearningMaterial(
        course_id=course_id,
        filename=stored_path.name,
        original_filename=original,
        material_type=material_type,
        file_path=str(stored_path),
        processing_status="pending",
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)

    background_tasks.add_task(process_material, material.id)
    return await _serialize(db, material)


@router.get("/courses/{course_id}/materials", response_model=list[MaterialResponse])
async def list_course_materials(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await material_service.get_owned_course(db, course_id, current_user.id)
    items = await material_service.list_materials(db, course_id)
    return [await _serialize(db, material) for material in items]


@router.get("/materials/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    material = await material_service.get_material(db, material_id, current_user.id)
    return await _serialize(db, material)


@router.get("/materials/{material_id}/file")
async def get_material_file(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the stored original file to its owner.

    Ownership is enforced by :func:`material_service.get_material` (a 404 for
    anything the caller does not own, so the endpoint never leaks existence).
    The on-disk path itself is never disclosed to the client.
    """
    material = await material_service.get_material(db, material_id, current_user.id)
    stored_path = Path(material.file_path)
    if not stored_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The stored file is no longer available. Upload it again.",
        )
    extension = stored_path.suffix.lstrip(".").lower()
    media_type = _MEDIA_TYPES.get(extension, "application/octet-stream")
    return FileResponse(
        stored_path,
        media_type=media_type,
        filename=material.original_filename,
        content_disposition_type="inline",
    )


@router.post("/materials/{material_id}/reprocess", response_model=MaterialResponse)
async def reprocess_material(
    material_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run extraction/indexing for an existing material (e.g. after a failure)."""
    material = await material_service.get_material(db, material_id, current_user.id)
    if not Path(material.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The stored file is missing on disk — upload it again.",
        )
    material.processing_status = "pending"
    material.processing_error = None
    await db.commit()
    await db.refresh(material)

    background_tasks.add_task(process_material, material.id)
    return await _serialize(db, material)


@router.delete("/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    material = await material_service.get_material(db, material_id, current_user.id)
    stored_path = Path(material.file_path)
    await db.delete(material)
    await db.commit()
    stored_path.unlink(missing_ok=True)
    return None
