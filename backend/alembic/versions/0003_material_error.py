"""learning material processing error

Revision ID: 0003_material_error
Revises: 0002_learning_features
Create Date: 2026-10-13

Additive, backward-compatible: adds a nullable ``processing_error`` column so a
failed ingestion can explain *why* it failed to the user.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_material_error"
down_revision = "0002_learning_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "learning_materials",
        sa.Column("processing_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("learning_materials", "processing_error")
