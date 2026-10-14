import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import check_database
from app.main import app

settings = get_settings()

EXPECTED_TABLES = {
    "users",
    "courses",
    "learning_materials",
    "content_units",
    "topics",
    "content_unit_topics",
    "content_embeddings",
}


@pytest.mark.asyncio
async def test_check_database_never_leaks_driver_errors() -> None:
    unreachable = create_async_engine(
        "postgresql+asyncpg://nobody:secret@127.0.0.1:59999/no_such_db",
        connect_args={"timeout": 1},
    )
    try:
        result = await check_database(target_engine=unreachable)
    finally:
        await unreachable.dispose()

    assert result["status"] == "unavailable"
    detail = result["detail"]
    assert detail == "database unreachable - see server logs for details"
    assert "asyncpg" not in detail
    assert "secret" not in detail
    assert "59999" not in detail
    assert "Traceback" not in detail


@pytest.mark.asyncio
async def test_health_endpoint_database_detail_is_sanitized() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    db = payload["database"]
    assert db["status"] in {"connected", "unavailable"}
    if db["status"] == "unavailable":
        assert db["detail"] == "database unreachable - see server logs for details"
        assert payload["status"] == "degraded"
    else:
        assert payload["status"] == "ok"


def test_expected_tables_are_registered() -> None:
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables))


def test_embedding_vector_dimension_matches_settings() -> None:
    from pgvector.sqlalchemy import Vector

    table = Base.metadata.tables["content_embeddings"]
    embedding_type = table.c.embedding.type
    assert isinstance(embedding_type, Vector)
    assert embedding_type.dim == settings.embedding_dimension == 768


def test_users_email_unique() -> None:
    users = Base.metadata.tables["users"]
    assert any(c.name == "uq_users_email" for c in users.constraints)


def test_topics_unique_and_hierarchy_columns() -> None:
    topics = Base.metadata.tables["topics"]
    assert any(
        c.name == "uq_topics_course_id"
        and {col.name for col in c.columns} == {"course_id", "name"}
        for c in topics.constraints
    )
    assert "description" in topics.c
    assert "parent_topic_id" in topics.c
    parent_fk = next(
        fk for fk in topics.foreign_keys if fk.parent.name == "parent_topic_id"
    )
    assert parent_fk.target_fullname == "topics.id"
    assert parent_fk.ondelete == "SET NULL"


def test_content_units_preserve_source_information() -> None:
    units = Base.metadata.tables["content_units"]
    for column in ("page_number", "slide_number", "start_timestamp", "end_timestamp"):
        assert column in units.c
        assert units.c[column].nullable is True
    assert "metadata" in units.c
    assert "content_type" in units.c
    assert "course_id" in units.c


def test_learning_material_upload_fields() -> None:
    materials = Base.metadata.tables["learning_materials"]
    for column in (
        "filename",
        "original_filename",
        "material_type",
        "file_path",
        "processing_status",
    ):
        assert column in materials.c


def test_embeddings_one_per_content_unit() -> None:
    embeddings = Base.metadata.tables["content_embeddings"]
    assert any(
        c.name == "uq_content_embeddings_content_unit_id" for c in embeddings.constraints
    )


def test_foreign_keys_cascade() -> None:
    courses = Base.metadata.tables["courses"]
    fk = next(c for c in courses.foreign_keys if c.parent.name == "user_id")
    assert fk.ondelete == "CASCADE"

    materials = Base.metadata.tables["learning_materials"]
    fk = next(c for c in materials.foreign_keys if c.parent.name == "course_id")
    assert fk.ondelete == "CASCADE"

    units = Base.metadata.tables["content_units"]
    fk = next(c for c in units.foreign_keys if c.parent.name == "material_id")
    assert fk.ondelete == "CASCADE"


def test_migration_file_exists() -> None:
    from pathlib import Path

    versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    files = [p.name for p in versions.glob("*.py")]
    assert "0001_initial_schema.py" in files


def test_database_url_normalization() -> None:
    from app.core.config import normalize_database_url

    local = "postgresql+asyncpg://studymate:studymate@127.0.0.1:5432/studymate"
    assert normalize_database_url(local) == local

    supabase_pooler = normalize_database_url(
        "postgresql://postgres.abcdefgh:pw@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
    )
    assert supabase_pooler.startswith("postgresql+asyncpg://")
    assert "ssl=require" in supabase_pooler
    assert "sslmode" not in supabase_pooler

    supabase_direct = normalize_database_url(
        "postgresql://postgres:pw@db.abcdefgh.supabase.co:5432/postgres"
    )
    assert "ssl=require" in supabase_direct

    neon = normalize_database_url(
        "postgresql://u:p@ep-cool-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    )
    assert "ssl=require" in neon
    assert "channel_binding" not in neon

