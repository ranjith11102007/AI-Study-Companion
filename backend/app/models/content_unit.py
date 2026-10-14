from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContentUnit(Base):
    """A source-preserving chunk of learning content.

    page_number / slide_number / start_timestamp / end_timestamp keep the
    original source location so answers can cite pages, slides or video
    timestamps later on.
    """

    __tablename__ = "content_units"

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("learning_materials.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    slide_number: Mapped[int | None] = mapped_column(Integer)
    start_timestamp: Mapped[float | None] = mapped_column(Float)
    end_timestamp: Mapped[float | None] = mapped_column(Float)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ContentUnit id={self.id} material_id={self.material_id} content_type={self.content_type!r}>"
