"""user profile: display name, preferences, email verification marker

Revision ID: 0004_user_profile
Revises: 0003_material_error
Create Date: 2026-10-15

Additive, backward-compatible: adds three *nullable* columns to ``users``. No
existing column, constraint or row is altered. ``email_verified_at`` is added
here (rather than in the auth migration) so the profile endpoint can already
report verification state; the token tables arrive in a later migration.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_user_profile"
down_revision = "0003_material_error"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("display_name", sa.String(length=120), nullable=True)
    )
    op.add_column("users", sa.Column("preferences", JSONB(), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "preferences")
    op.drop_column("users", "display_name")
