"""initial schema: users, courses, learning_materials, content_units, topics, embeddings

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-08

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# Must stay in sync with EMBEDDING_DIMENSION
# (local embedding model: nomic-embed-text -> 768).
VECTOR_DIMENSION = 768


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_courses"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_courses_user_id_users", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_courses_user_id", "courses", ["user_id"])

    op.create_table(
        "learning_materials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("material_type", sa.String(length=20), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("processing_status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_learning_materials"),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"],
            name="fk_learning_materials_course_id_courses", ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_learning_materials_course_id", "learning_materials", ["course_id"]
    )

    op.create_table(
        "content_units",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("slide_number", sa.Integer(), nullable=True),
        sa.Column("start_timestamp", sa.Float(), nullable=True),
        sa.Column("end_timestamp", sa.Float(), nullable=True),
        sa.Column("metadata", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_units"),
        sa.ForeignKeyConstraint(
            ["material_id"], ["learning_materials.id"],
            name="fk_content_units_material_id_learning_materials", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"],
            name="fk_content_units_course_id_courses", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_content_units_material_id", "content_units", ["material_id"])
    op.create_index("ix_content_units_course_id", "content_units", ["course_id"])

    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_topic_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_topics"),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"],
            name="fk_topics_course_id_courses", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_topic_id"], ["topics.id"],
            name="fk_topics_parent_topic_id_topics", ondelete="SET NULL",
        ),
        sa.UniqueConstraint("course_id", "name", name="uq_topics_course_id"),
    )
    op.create_index("ix_topics_course_id", "topics", ["course_id"])
    op.create_index("ix_topics_parent_topic_id", "topics", ["parent_topic_id"])

    op.create_table(
        "content_unit_topics",
        sa.Column("content_unit_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint(
            "content_unit_id", "topic_id", name="pk_content_unit_topics"
        ),
        sa.ForeignKeyConstraint(
            ["content_unit_id"], ["content_units.id"],
            name="fk_content_unit_topics_content_unit_id_content_units",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["topics.id"],
            name="fk_content_unit_topics_topic_id_topics", ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_content_unit_topics_topic_id", "content_unit_topics", ["topic_id"]
    )

    op.create_table(
        "content_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_unit_id", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(VECTOR_DIMENSION), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_embeddings"),
        sa.ForeignKeyConstraint(
            ["content_unit_id"], ["content_units.id"],
            name="fk_content_embeddings_content_unit_id_content_units",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "content_unit_id", name="uq_content_embeddings_content_unit_id"
        ),
    )
    op.create_index(
        "ix_content_embeddings_embedding",
        "content_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_content_embeddings_embedding", table_name="content_embeddings")
    op.drop_table("content_embeddings")
    op.drop_index("ix_content_unit_topics_topic_id", table_name="content_unit_topics")
    op.drop_table("content_unit_topics")
    op.drop_index("ix_topics_parent_topic_id", table_name="topics")
    op.drop_index("ix_topics_course_id", table_name="topics")
    op.drop_table("topics")
    op.drop_index("ix_content_units_course_id", table_name="content_units")
    op.drop_index("ix_content_units_material_id", table_name="content_units")
    op.drop_table("content_units")
    op.drop_index("ix_learning_materials_course_id", table_name="learning_materials")
    op.drop_table("learning_materials")
    op.drop_index("ix_courses_user_id", table_name="courses")
    op.drop_table("courses")
    op.drop_table("users")
