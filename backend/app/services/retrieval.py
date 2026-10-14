"""Vector retrieval over a course's indexed content units.

Semantic similarity is used to *find* candidate passages; it is never treated
as proof that a passage factually supports an answer. Callers must still build
grounded output (see :mod:`app.services.tutor`).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ollama import get_embedding_provider
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.content_embedding import ContentEmbedding
from app.models.content_unit import ContentUnit
from app.models.learning_material import LearningMaterial

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class RetrievedChunk:
    content_unit_id: int
    material_id: int
    material_title: str
    material_type: str
    content: str
    page_number: int | None
    slide_number: int | None
    start_timestamp: float | None
    end_timestamp: float | None
    score: float  # cosine similarity in [0, 1] (1 = identical direction)

    def citation(self) -> dict:
        """A citation payload that only contains real, stored metadata."""
        return {
            "content_unit_id": self.content_unit_id,
            "material_id": self.material_id,
            "material_title": self.material_title,
            "material_type": self.material_type,
            "page_number": self.page_number,
            "slide_number": self.slide_number,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "excerpt": _excerpt(self.content, settings.tutor_excerpt_chars),
            "score": round(self.score, 4),
        }


def _excerpt(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


async def retrieve(
    db: AsyncSession,
    course_id: int,
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
    embedder=None,
) -> list[RetrievedChunk]:
    """Return the most relevant chunks for ``query`` within ``course_id``.

    ``embedder`` can be injected for tests; otherwise the configured local
    embedding provider is used.
    """
    query = (query or "").strip()
    if not query:
        return []

    top_k = top_k or settings.retrieval_top_k
    min_score = settings.retrieval_min_score if min_score is None else min_score

    # If the course has no indexed vectors at all, return no evidence without
    # touching the embedding model. This keeps an honest "insufficient" answer
    # from turning into a server error when the local model is not running.
    has_content = (
        await db.execute(
            select(ContentUnit.id)
            .join(ContentEmbedding, ContentEmbedding.content_unit_id == ContentUnit.id)
            .where(ContentUnit.course_id == course_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if has_content is None:
        return []

    provider = embedder or get_embedding_provider()
    try:
        vector = await provider.embed_query(query)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - map provider outages to a clear 503
        logger.error("Embedding provider failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The local embedding model is unavailable. Make sure Ollama is "
                "running and the embedding model is pulled."
            ),
        ) from exc

    distance = ContentEmbedding.embedding.cosine_distance(vector).label("distance")
    stmt = (
        select(
            ContentUnit.id,
            ContentUnit.material_id,
            ContentUnit.content,
            ContentUnit.page_number,
            ContentUnit.slide_number,
            ContentUnit.start_timestamp,
            ContentUnit.end_timestamp,
            LearningMaterial.original_filename,
            LearningMaterial.material_type,
            distance,
        )
        .join(ContentEmbedding, ContentEmbedding.content_unit_id == ContentUnit.id)
        .join(LearningMaterial, LearningMaterial.id == ContentUnit.material_id)
        .where(ContentUnit.course_id == course_id)
        .order_by(distance.asc())
        .limit(max(settings.retrieval_candidate_k, top_k))
    )

    rows = (await db.execute(stmt)).all()
    chunks: list[RetrievedChunk] = []
    for row in rows:
        score = 1.0 - float(row.distance)
        if score < min_score:
            continue
        chunks.append(
            RetrievedChunk(
                content_unit_id=row.id,
                material_id=row.material_id,
                material_title=row.original_filename,
                material_type=row.material_type,
                content=row.content,
                page_number=row.page_number,
                slide_number=row.slide_number,
                start_timestamp=row.start_timestamp,
                end_timestamp=row.end_timestamp,
                score=score,
            )
        )
        if len(chunks) >= top_k:
            break
    return chunks


def build_context(chunks: list[RetrievedChunk], max_chars: int | None = None) -> str:
    """Fence retrieved passages so the model treats them as evidence, not orders."""
    max_chars = max_chars or settings.tutor_max_context_chars
    parts: list[str] = []
    used = 0
    for index, chunk in enumerate(chunks, start=1):
        location = _location_label(chunk)
        body = chunk.content.strip()
        block = f'<source id="{index}" material="{chunk.material_title}" location="{location}">\n{body}\n</source>'
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)


def _location_label(chunk: RetrievedChunk) -> str:
    if chunk.page_number is not None:
        return f"page {chunk.page_number}"
    if chunk.slide_number is not None:
        return f"slide {chunk.slide_number}"
    if chunk.start_timestamp is not None:
        return f"t={chunk.start_timestamp:.1f}s"
    return "excerpt"
