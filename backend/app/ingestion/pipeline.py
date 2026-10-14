"""Ingestion pipeline: file -> content units -> embeddings -> ready/failed.

Runs in a background task with its own database session. Any failure marks the
material as ``failed`` and is logged server-side; it never crashes the API.
"""

from pathlib import Path

from sqlalchemy import delete

from app.ai import get_embedding_provider
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.ingestion.chunking import sanitize_text
from app.ingestion.extractors import IngestionError, extract_units
from app.models.content_embedding import ContentEmbedding
from app.models.content_unit import ContentUnit
from app.models.learning_material import LearningMaterial

logger = get_logger(__name__)
settings = get_settings()

_MAX_ERROR_LENGTH = 400


def _user_safe_error(exc: Exception) -> str:
    """Map an ingestion exception to a short, user-safe reason (no stack)."""
    if isinstance(exc, IngestionError):
        message = str(exc)
    else:
        probe = f"{type(exc).__name__} {exc}".lower()
        if any(token in probe for token in ("connect", "11434", "ollama")):
            message = (
                "The local embedding model (Ollama) is not reachable. "
                "Start Ollama, then choose “Retry indexing”."
            )
        elif any(
            token in probe
            for token in ("byte sequence", "encoding", "utf8", "character")
        ):
            message = (
                "The source contained characters that could not be stored. "
                "Try re-uploading the file."
            )
        else:
            message = "Indexing failed — see the server log for details."
    return message[:_MAX_ERROR_LENGTH]



async def process_material(material_id: int) -> None:
    async with SessionLocal() as db:
        material = await db.get(LearningMaterial, material_id)
        if material is None:
            logger.warning("process_material: material %s not found", material_id)
            return

        material.processing_status = "processing"
        material.processing_error = None
        await db.commit()

        try:
            # Re-processing must be idempotent: drop any previously indexed
            # chunks (embeddings cascade via FK) before inserting the fresh set.
            await db.execute(
                delete(ContentUnit).where(ContentUnit.material_id == material_id)
            )
            await db.flush()

            path = Path(material.file_path)
            if not path.exists():
                raise IngestionError("Stored file is missing on disk.")

            units = extract_units(path, material.material_type)
            content_units: list[ContentUnit] = []
            for unit in units:
                content = sanitize_text(unit.content).strip()
                if not content:
                    continue
                content_unit = ContentUnit(
                    material_id=material.id,
                    course_id=material.course_id,
                    content_type=material.material_type,
                    title=sanitize_text(unit.title) or None,
                    content=content,
                    page_number=unit.page_number,
                    slide_number=unit.slide_number,
                    metadata_=unit.metadata or None,
                )
                db.add(content_unit)
                content_units.append(content_unit)
            if not content_units:
                raise IngestionError("Nothing was extracted from this file.")
            await db.flush()

            provider = get_embedding_provider()
            model_name = getattr(provider, "model", settings.ollama_embed_model)
            vectors = await provider.embed([cu.content for cu in content_units])
            if len(vectors) != len(content_units):
                raise IngestionError("Embedding count did not match content units.")

            for content_unit, vector in zip(content_units, vectors):
                db.add(
                    ContentEmbedding(
                        content_unit_id=content_unit.id,
                        embedding=vector,
                        model=model_name,
                    )
                )

            material.processing_status = "ready"
            material.processing_error = None
            await db.commit()
            logger.info(
                "Material %s indexed (%s units)", material.id, len(content_units)
            )
        except Exception as exc:  # noqa: BLE001 - background task must not raise
            await db.rollback()
            logger.error("Material %s ingestion failed: %s", material_id, exc)
            failed = await db.get(LearningMaterial, material_id)
            if failed is not None:
                failed.processing_status = "failed"
                failed.processing_error = _user_safe_error(exc)
                await db.commit()
