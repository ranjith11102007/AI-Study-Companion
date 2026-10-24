"""flashcards and course summaries (Phase 5)

Revision ID: 0007_flashcards
Revises: 0006_auth_security
Create Date: 2026-10-15

Additive, backward-compatible: two new tables. Cards carry a simple spaced
review state (next review date + interval) so the UI can schedule reviews
without inventing analytics; summaries are cached per (course, user).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007_flashcards"
down_revision = "0006_auth_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flashcards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("front", sa.Text(), nullable=False),
        sa.Column("back", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=True),
        sa.Column("source_unit_id", sa.Integer(), sa.ForeignKey("content_units.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ease", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wrong_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id", name="pk_flashcards"),
    )
    op.create_index("ix_flashcards_user_id", "flashcards", ["user_id"])
    op.create_index("ix_flashcards_course_id", "flashcards", ["course_id"])

    op.create_table(
        "course_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_unit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model", sa.String(length=80), nullable=False, server_default="local"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_course_summaries"),
        sa.UniqueConstraint("user_id", "course_id", name="uq_course_summary_user_course"),
    )
    op.create_index("ix_course_summaries_user_id", "course_summaries", ["user_id"])
    op.create_index("ix_course_summaries_course_id", "course_summaries", ["course_id"])


def downgrade() -> None:
    op.drop_index("ix_course_summaries_course_id", table_name="course_summaries")
    op.drop_index("ix_course_summaries_user_id", table_name="course_summaries")
    op.drop_table("course_summaries")
    op.drop_index("ix_flashcards_course_id", table_name="flashcards")
    op.drop_index("ix_flashcards_user_id", table_name="flashcards")
    op.drop_table("flashcards")
