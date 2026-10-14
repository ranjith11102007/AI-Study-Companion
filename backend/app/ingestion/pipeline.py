"""Ingestion pipeline: file -> content units -> embeddings -> ready/failed.

Runs in a background task with its own database session. Any failure marks the
material as ``failed`` and is logged server-side; it never crashes the API.

Failures are reported *per stage* so the server log (and the stored
``processing_error``) says where indexing stopped: reading the stored file,
extracting text, chunking, generating embeddings, persisting vectors, or the
final commit.
"""

import asyncio
from enum import Enum
from pathlib import Path

import httpx
from sqlalchemy import delete

from app.ai import EmbeddingProvider, get_embedding_provider
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
# The provider's own error body goes to the server log, never to the browser;
# cap it so an unexpected response cannot flood the log.
_MAX_DETAIL_LENGTH = 600


class Stage(str, Enum):
    """Diagnostic phase of one indexing attempt.

    ``FILE_VALIDATION`` / ``FILE_STORAGE`` also run in the upload endpoint,
    where they surface as an immediate HTTP 4xx. ``FILE_VALIDATION`` is reused
    here for the stored-file check before extraction.
    """

    FILE_VALIDATION = "FILE_VALIDATION"
    FILE_STORAGE = "FILE_STORAGE"
    TEXT_EXTRACTION = "TEXT_EXTRACTION"
    TEXT_CHUNKING = "TEXT_CHUNKING"
    EMBEDDING_GENERATION = "EMBEDDING_GENERATION"
    VECTOR_STORAGE = "VECTOR_STORAGE"
    DATABASE_UPDATE = "DATABASE_UPDATE"


def _error_detail(exc: Exception) -> str:
    """Concrete server-side context for a failure (never sent to clients)."""
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        body = " ".join((exc.response.text or "").split())
        return f"HTTP {exc.response.status_code}: {body}"[:_MAX_DETAIL_LENGTH]
    return f"{type(exc).__name__}: {exc}"[:_MAX_DETAIL_LENGTH]


def _user_safe_error(exc: Exception, stage: Stage) -> str:
    """Map an ingestion exception to a short, user-safe reason (no stack)."""
    if isinstance(exc, IngestionError):
        return str(exc)[:_MAX_ERROR_LENGTH]

    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        status = exc.response.status_code
        body = (exc.response.text or "").lower()
        if status == 429:
            return (
                "The embedding provider is rate-limiting requests (HTTP 429). "
                "Wait a moment, then choose “Retry indexing”."
            )
        if status in (401, 403):
            return (
                f"The embedding provider rejected the API key (HTTP {status}). "
                "Check OPENAI_API_KEY, then retry."
            )
        if status == 400 and "at most 100" in body:
            return (
                "The embedding provider accepts at most 100 passages per "
                "request. Reduce EMBEDDING_BATCH_SIZE, then retry."
            )
        if status == 400 and "dimension" in body:
            return (
                "Embedding dimension mismatch. Set EMBEDDING_DIMENSION to the "
                "embedding model's size, then retry."
            )
        if status >= 500:
            return (
                f"The embedding provider is temporarily unavailable "
                f"(HTTP {status}). Try again shortly."
            )
        return (
            f"The embedding provider rejected the request (HTTP {status}). "
            "See the server log for details."
        )

    probe = f"{type(exc).__name__} {exc}".lower()
    if any(token in probe for token in ("connect", "11434", "ollama")):
        return (
            "The local embedding model (Ollama) is not reachable. "
            "Start Ollama, then choose “Retry indexing”."
        )
    if any(
        token in probe
        for token in (
            "byte sequence",
            "encoding",
            "utf8",
            "utf-8",
            "surrogate",
            "character",
        )
    ):
        return (
            "The source contained characters that could not be stored. "
            "Try re-uploading the file."
        )
    if "dimension" in probe:
        return (
            "The embedding vector size does not match the stored vectors. "
            "Check EMBEDDING_DIMENSION, then retry."
        )
    return f"Indexing failed at {stage.value} — see the server log for details."


async def _embed_all(
    provider: EmbeddingProvider, texts: list[str]
) -> list[list[float]]:
    """Embed ``texts`` in provider-sized batches, preserving input order.

    One document can yield more passages than a single embedding request
    accepts. Gemini's OpenAI-compatible endpoint, for example, answers with
    ``HTTP 400 * BatchEmbedContentsRequest.requests: at most 100 requests can
    be in one batch`` as soon as a call carries more than 100 inputs. Batching
    here keeps every provider within its own limit and is a no-op for small
    documents.
    """
    batch_size = max(int(settings.embedding_batch_size), 1)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        vectors.extend(await _embed_batch(provider, batch))
    return vectors


# Transient provider answers worth another attempt: rate limiting and the
# usual "try again" server statuses.
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
_RETRY_FACTOR = 3
_MAX_RETRY_DELAY_SECONDS = 60.0


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        return exc.response.status_code in _RETRYABLE_STATUS
    return isinstance(exc, httpx.TimeoutException)


async def _embed_batch(
    provider: EmbeddingProvider, texts: list[str]
) -> list[list[float]]:
    """Embed one batch, retrying rate limits / transient failures.

    A minute-budgeted free tier (Gemini: ~100 requests/minute) answers 429 for
    the second half of a large document; without a retry that document could
    never be indexed. Waits grow 3x per attempt and are capped so the retry
    still lands inside the provider's window.
    """
    attempts = max(int(settings.embedding_max_attempts), 1)
    base = max(float(settings.embedding_retry_base_seconds), 0.0)

    for attempt in range(1, attempts + 1):
        try:
            return await provider.embed(texts)
        except Exception as exc:  # noqa: BLE001 - re-raised unless retryable
            if attempt >= attempts or not _is_retryable(exc):
                raise
            delay = min(base * _RETRY_FACTOR ** (attempt - 1), _MAX_RETRY_DELAY_SECONDS)
            logger.warning(
                "Embedding request failed (%s); retrying in %.1fs (%d/%s)",
                type(exc).__name__,
                delay,
                attempt,
                attempts,
            )
            if delay:
                await asyncio.sleep(delay)

    raise AssertionError("unreachable")  # pragma: no cover


async def process_material(material_id: int) -> None:
    stage = Stage.FILE_VALIDATION
    async with SessionLocal() as db:
        material = await db.get(LearningMaterial, material_id)
        if material is None:
            logger.warning("process_material: material %s not found", material_id)
            return

        material.processing_status = "processing"
        material.processing_error = None
        await db.commit()

        try:
            stage = Stage.FILE_VALIDATION
            path = Path(material.file_path)
            if not path.exists():
                raise IngestionError(
                    "The stored file is missing on disk — upload it again."
                )

            # Re-processing must be idempotent: drop any previously indexed
            # chunks (embeddings cascade via FK) before inserting the fresh set.
            await db.execute(
                delete(ContentUnit).where(ContentUnit.material_id == material_id)
            )
            await db.flush()

            stage = Stage.TEXT_EXTRACTION
            units = extract_units(path, material.material_type)

            stage = Stage.TEXT_CHUNKING
            content_units: list[ContentUnit] = []
            for unit in units:
                content = sanitize_text(unit.content).strip()
                if not content:
                    continue
                content_units.append(
                    ContentUnit(
                        material_id=material.id,
                        course_id=material.course_id,
                        content_type=material.material_type,
                        content=content,
                        title=sanitize_text(unit.title) or None,
                        page_number=unit.page_number,
                        slide_number=unit.slide_number,
                        metadata_=unit.metadata or None,
                    )
                )
            if not content_units:
                raise IngestionError("No readable text was found in this file.")
            db.add_all(content_units)
            await db.flush()

            stage = Stage.EMBEDDING_GENERATION
            provider = get_embedding_provider()
            vectors = await _embed_all(
                provider, [cu.content for cu in content_units]
            )
            if len(vectors) != len(content_units):
                raise IngestionError("Embedding count did not match content units.")

            stage = Stage.VECTOR_STORAGE
            model_name = getattr(provider, "model", settings.ollama_embed_model)
            for content_unit, vector in zip(content_units, vectors):
                db.add(
                    ContentEmbedding(
                        content_unit_id=content_unit.id,
                        embedding=vector,
                        model=model_name,
                    )
                )

            stage = Stage.DATABASE_UPDATE
            material.processing_status = "ready"
            material.processing_error = None
            await db.commit()
            logger.info(
                "Material %s indexed (%s units)", material.id, len(content_units)
            )
        except Exception as exc:  # noqa: BLE001 - background task must not raise
            await db.rollback()
            logger.exception(
                "Material %s ingestion failed [stage=%s type=%s]: %s | detail: %s",
                material_id,
                stage.value,
                type(exc).__name__,
                exc,
                _error_detail(exc),
            )
            failed = await db.get(LearningMaterial, material_id)
            if failed is not None:
                failed.processing_status = "failed"
                failed.processing_error = _user_safe_error(exc, stage)
                await db.commit()
