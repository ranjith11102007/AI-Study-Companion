import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db():
    """FastAPI dependency that yields a scoped async session."""
    async with SessionLocal() as session:
        yield session


async def check_database(target_engine=None) -> dict[str, Any]:
    """Lightweight connectivity probe used by the health endpoint.

    Never raises: returns a status dict so the API stays available even when
    PostgreSQL is not running yet. Raw driver errors are logged server-side
    only; API responses receive a safe, generic summary.
    """
    probe_engine = target_engine if target_engine is not None else engine
    started = time.perf_counter()
    try:
        async with probe_engine.connect() as connection:
            await connection.execute(
                text("SELECT 1"),
            )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {"status": "connected", "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001 - health probe must not crash
        logger.warning("Database health check failed: %s", exc)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "status": "unavailable",
            "latency_ms": latency_ms,
            "detail": "database unreachable - see server logs for details",
        }
