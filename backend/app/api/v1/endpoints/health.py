from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import check_database
from app.schemas.health import DatabaseHealth, HealthResponse
from app.schemas.provider import ProvidersResponse
from app.services.providers import check_providers

router = APIRouter()
settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description="Reports API liveness and PostgreSQL connectivity.",
)
async def health() -> HealthResponse:
    database = await check_database()
    return HealthResponse(
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        status="ok" if database["status"] == "connected" else "degraded",
        timestamp=datetime.now(timezone.utc),
        database=DatabaseHealth(**database),
    )


@router.get(
    "/health/live",
    summary="Liveness probe",
    description="Always returns ok while the process is serving requests.",
)
async def live() -> dict:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc)}


@router.get(
    "/health/ready",
    response_model=ProvidersResponse,
    summary="Readiness probe",
    description=(
        "Reports whether PostgreSQL, pgvector, Ollama, OCR and storage are "
        "available. Degraded dependencies do not take the API offline."
    ),
)
async def ready() -> dict:
    return await check_providers()
