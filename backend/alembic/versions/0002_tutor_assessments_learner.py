"""tutor conversations, assessments, learner model and evaluation runs

Revision ID: 0002_learning_features
Revises: 1cc7c09069a1
Create Date: 2026-10-13

Additive, backward-compatible migration: only new tables and indexes. No
existing table or column is dropped or altered.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_learning_features"
down_revision = "1cc7c09069a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Tutor conversations -------------------------------------------------
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"],
            name="fk_conversations_course_id_courses", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_conversations_user_id_users", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_conversations_course_id", "conversations", ["course_id"])
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("evidence_status", sa.String(length=20), nullable=True),
        sa.Column("citations", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"],
            name="fk_messages_conversation_id_conversations", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("time_limit_minutes", sa.Integer(), nullable=True),
        sa.Column("generation_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assessments"),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"],
            name="fk_assessments_course_id_courses", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_assessments_user_id_users", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_assessments_course_id", "assessments", ["course_id"])
    op.create_index("ix_assessments_user_id", "assessments", ["user_id"])

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("qtype", sa.String(length=16), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("concept", sa.String(length=200), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("correct_answer", sa.Text(), nullable=False),
        sa.Column("rubric", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("source_unit_ids", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_questions"),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["assessments.id"],
            name="fk_questions_assessment_id_assessments", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_questions_assessment_id", "questions", ["assessment_id"])
    op.create_index("ix_questions_fingerprint", "questions", ["fingerprint"])

    op.create_table(
        "attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("max_score", sa.Float(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_attempts"),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["assessments.id"],
            name="fk_attempts_assessment_id_assessments", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_attempts_user_id_users", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_attempts_assessment_id", "attempts", ["assessment_id"])
    op.create_index("ix_attempts_user_id", "attempts", ["user_id"])

    op.create_table(
        "assessment_responses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assessment_responses"),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["attempts.id"],
            name="fk_assessment_responses_attempt_id_attempts", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"],
            name="fk_assessment_responses_question_id_questions", ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_assessment_responses_attempt_id", "assessment_responses", ["attempt_id"]
    )
    op.create_index(
        "ix_assessment_responses_question_id", "assessment_responses", ["question_id"]
    )

    op.create_table(
        "topic_mastery",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("mastery", sa.Float(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("last_practiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_topic_mastery"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_topic_mastery_user_id_users", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"],
            name="fk_topic_mastery_course_id_courses", ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id", "course_id", "topic", name="uq_topic_mastery_scope"
        ),
    )
    op.create_index("ix_topic_mastery_user_id", "topic_mastery", ["user_id"])
    op.create_index("ix_topic_mastery_course_id", "topic_mastery", ["course_id"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("priority", sa.Float(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recommendations"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_recommendations_user_id_users", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"],
            name="fk_recommendations_course_id_courses", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["material_id"], ["learning_materials.id"],
            name="fk_recommendations_material_id_learning_materials",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_recommendations_user_id", "recommendations", ["user_id"])
    op.create_index("ix_recommendations_course_id", "recommendations", ["course_id"])

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("metrics", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("results", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evaluation_runs"),
    )


def downgrade() -> None:
    op.drop_table("evaluation_runs")
    op.drop_index("ix_recommendations_course_id", table_name="recommendations")
    op.drop_index("ix_recommendations_user_id", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index("ix_topic_mastery_course_id", table_name="topic_mastery")
    op.drop_index("ix_topic_mastery_user_id", table_name="topic_mastery")
    op.drop_table("topic_mastery")
    op.drop_index(
        "ix_assessment_responses_question_id", table_name="assessment_responses"
    )
    op.drop_index(
        "ix_assessment_responses_attempt_id", table_name="assessment_responses"
    )
    op.drop_table("assessment_responses")
    op.drop_index("ix_attempts_user_id", table_name="attempts")
    op.drop_index("ix_attempts_assessment_id", table_name="attempts")
    op.drop_table("attempts")
    op.drop_index("ix_questions_fingerprint", table_name="questions")
    op.drop_index("ix_questions_assessment_id", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_assessments_user_id", table_name="assessments")
    op.drop_index("ix_assessments_course_id", table_name="assessments")
    op.drop_table("assessments")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_index("ix_conversations_course_id", table_name="conversations")
    op.drop_table("conversations")
