"""Local provider / dependency health checks (no secrets ever returned)."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal, check_database

logger = get_logger(__name__)
settings = get_settings()


async def _ollama_status() -> dict:
    base = settings.ollama_base_url.rstrip("/")
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=settings.provider_health_timeout_seconds
        ) as client:
            response = await client.get(f"{base}/api/tags")
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # noqa: BLE001 - health check must never raise
        logger.info("Ollama health check failed: %s", exc)
        return {
            "name": "ollama",
            "status": "unavailable",
            "latency_ms": None,
            "detail": "Ollama server not reachable at the configured URL.",
            "models": [],
        }

    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]

    def has(model: str) -> bool:
        return any(name == model or name.startswith(f"{model}:") for name in models)

    missing = [
        model
        for model in (settings.ollama_chat_model, settings.ollama_embed_model)
        if not has(model)
    ]

    return {
        "name": "ollama",
        "status": "ok" if not missing else "degraded",
        "latency_ms": latency_ms,
        "chat_model": settings.ollama_chat_model,
        "embed_model": settings.ollama_embed_model,
        "detail": (
            "Local chat and embedding models are available."
            if not missing
            else "Missing local model(s): " + ", ".join(missing)
        ),
        "models": models,
    }


def _using_openai_provider() -> bool:
    from app.ai.openai_compat import OPENAI_ALIASES

    return (
        settings.chat_provider.strip().lower() in OPENAI_ALIASES
        or settings.embedding_provider.strip().lower() in OPENAI_ALIASES
    )


async def _openai_status() -> dict:
    """Status of the configured OpenAI-compatible AI endpoint (never raises)."""
    base = settings.openai_base_url.rstrip("/")
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=settings.provider_health_timeout_seconds
        ) as client:
            response = await client.get(
                f"{base}/models",
                headers=(
                    {"Authorization": f"Bearer {settings.openai_api_key}"}
                    if settings.openai_api_key
                    else {}
                ),
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # noqa: BLE001 - health check must never raise
        logger.info("OpenAI-compatible provider check failed: %s", exc)
        return {
            "name": "openai",
            "status": "unavailable",
            "latency_ms": None,
            "detail": "The configured OpenAI-compatible AI endpoint is unreachable.",
            "models": [],
        }

    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    return {
        "name": "openai",
        "status": "ok",
        "latency_ms": latency_ms,
        "chat_model": settings.openai_chat_model,
        "embed_model": settings.openai_embed_model,
        "detail": "OpenAI-compatible AI endpoint reachable.",
        "models": models,
    }


def check_ocr() -> dict:
    from app.ingestion.extractors import ocr_available

    available = ocr_available()
    return {
        "name": "ocr",
        "status": "ok" if available else "unavailable",
        "detail": (
            "Tesseract OCR available for image ingestion."
            if available
            else "Tesseract not found — image OCR ingestion is disabled."
        ),
    }


def check_office() -> dict:
    """Report whether PowerPoint (.pptx) ingestion is available."""
    try:
        import pptx  # noqa: F401
    except ImportError:
        return {
            "name": "office",
            "status": "unavailable",
            "detail": "python-pptx is not installed — .pptx ingestion is disabled.",
        }
    return {
        "name": "office",
        "status": "ok",
        "detail": "PowerPoint (.pptx) ingestion available.",
    }


def check_storage() -> dict:
    try:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.upload_dir / ".health-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return {"name": "storage", "status": "ok", "detail": "Upload directory writable."}
    except Exception as exc:  # noqa: BLE001
        logger.info("Storage check failed: %s", exc)
        return {
            "name": "storage",
            "status": "unavailable",
            "detail": "Upload directory is not writable.",
        }


async def _pgvector_status() -> dict:
    try:
        async with SessionLocal() as db:
            result = await db.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
            version = result.scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001
        logger.info("pgvector check failed: %s", exc)
        return {
            "name": "pgvector",
            "status": "unavailable",
            "detail": "Could not query the database for the vector extension.",
        }
    if version is None:
        return {
            "name": "pgvector",
            "status": "unavailable",
            "detail": "The 'vector' extension is not installed in this database.",
        }
    return {
        "name": "pgvector",
        "status": "ok",
        "detail": f"pgvector {version} available.",
        "dimension": settings.embedding_dimension,
    }


async def check_providers() -> dict:
    """Aggregate the status of every local dependency. Never raises."""
    database = await check_database()
    db_ok = database["status"] == "connected"
    providers = [
        {
            "name": "database",
            "status": "ok" if db_ok else "unavailable",
            "detail": database.get("detail") or "PostgreSQL reachable.",
        },
        await _pgvector_status(),
        await (_openai_status() if _using_openai_provider() else _ollama_status()),
        check_ocr(),
        check_office(),
        check_storage(),
    ]

    degraded = [p["name"] for p in providers if p["status"] != "ok"]
    return {
        "status": "ok" if not degraded else "degraded",
        "timestamp": datetime.now(timezone.utc),
        "degraded": degraded,
        "providers": providers,
    }
