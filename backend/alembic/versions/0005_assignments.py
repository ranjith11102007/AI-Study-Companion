"""study assignments (study-plan items derived from mastery gaps)

Revision ID: 0005_assignments
Revises: 0004_user_profile
Create Date: 2026-10-15

Additive, backward-compatible: one new ``assignments`` table. Status/owner
scoping and optional linkage back to a ``recommendations`` row so the study
plan is transparent about why it was suggested.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_assignments"
down_revision = "0004_user_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "course_id", sa.Integer(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False, server_default="practice"),
        sa.Column("topic", sa.String(length=120), nullable=True),
        sa.Column(
            "material_id", sa.Integer(),
            sa.ForeignKey("learning_materials.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_recommendation_id", sa.Integer(),
            sa.ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="todo"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_assignments"),
    )
    op.create_index("ix_assignments_user_id", "assignments", ["user_id"])
    op.create_index("ix_assignments_course_id", "assignments", ["course_id"])
    op.create_index("ix_assignments_status", "assignments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_assignments_status", table_name="assignments")
    op.drop_index("ix_assignments_course_id", table_name="assignments")
    op.drop_index("ix_assignments_user_id", table_name="assignments")
    op.drop_table("assignments")
