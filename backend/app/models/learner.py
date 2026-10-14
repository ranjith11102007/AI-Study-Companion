"""Persistent learner model and generated study recommendations."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TopicMastery(Base):
    """Per-student, per-topic mastery estimate (Bayesian Knowledge Tracing).

    ``mastery`` is the probability the student has learned the topic; it is
    updated only from real, graded assessment responses. ``evidence_count``
    records how many graded answers back the estimate so an untested topic is
    never confused with a demonstrated weak one.
    """

    __tablename__ = "topic_mastery"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", "topic", name="uq_topic_mastery_scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    mastery: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<TopicMastery topic={self.topic!r} mastery={self.mastery:.2f}>"


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("learning_materials.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Recommendation id={self.id} kind={self.kind!r}>"


class EvaluationRun(Base):
    """A reproducibility record for the retrieval/evaluation harness."""

    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="running", nullable=False)
    metrics: Mapped[dict | None] = mapped_column(JSONB)
    results: Mapped[dict | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<EvaluationRun id={self.id} dataset={self.dataset!r}>"
