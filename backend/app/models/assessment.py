"""Assessment engine: assessments, questions, attempts and per-question responses."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
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


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="generating", nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer)
    generation_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Assessment id={self.id} status={self.status!r}>"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # mcq | short | numeric
    qtype: Mapped[str] = mapped_column(String(16), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    topic: Mapped[str] = mapped_column(String(120), default="General", nullable=False)
    concept: Mapped[str | None] = mapped_column(String(200))
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list | None] = mapped_column(JSONB)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    rubric: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    source_unit_ids: Mapped[list | None] = mapped_column(JSONB)
    verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    verification_notes: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Question id={self.id} qtype={self.qtype!r}>"


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default="in_progress", nullable=False
    )
    score: Mapped[float | None] = mapped_column(Float)
    max_score: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Attempt id={self.id} status={self.status!r}>"


class Response(Base):
    __tablename__ = "assessment_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("attempts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    # None = not auto-gradable (flagged for review)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[float | None] = mapped_column(Float)
    feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Response id={self.id} attempt_id={self.attempt_id}>"
