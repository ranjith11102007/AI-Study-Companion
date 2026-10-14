
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("course_id", "name", name="uq_topics_course_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"),
        index=True,
    )

    def __repr__(self) -> str:
        return f"<Topic id={self.id} course_id={self.course_id} name={self.name!r}>"


class ContentUnitTopic(Base):
    __tablename__ = "content_unit_topics"

    content_unit_id: Mapped[int] = mapped_column(
        ForeignKey("content_units.id", ondelete="CASCADE"),
        primary_key=True,
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
