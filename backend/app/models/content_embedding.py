from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.db.base import Base


class ContentEmbedding(Base):
    """One embedding vector per content unit.

    The vector dimension must match EMBEDDING_DIMENSION
    (nomic-embed-text -> 768 by default) and the migration that
    created the column.
    """

    __tablename__ = "content_embeddings"
    __table_args__ = (
        Index(
            "ix_content_embeddings_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    content_unit_id: Mapped[int] = mapped_column(
        ForeignKey("content_units.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    embedding: Mapped[list[float]] = mapped_column(
        Vector(get_settings().embedding_dimension), nullable=False
    )
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ContentEmbedding id={self.id} content_unit_id={self.content_unit_id} model={self.model!r}>"
