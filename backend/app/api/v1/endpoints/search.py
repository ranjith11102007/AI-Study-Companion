"""Optional global web search (Mode C) endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.models.user import User
from app.schemas.websearch import (
    WebSearchRequest,
    WebSearchResponse,
    WebSearchStatus,
)
from app.services import websearch as websearch_service

router = APIRouter()


@router.get("/search/status", response_model=WebSearchStatus)
async def search_status(current_user: User = Depends(get_current_user)):
    """Report whether global web search is configured (no secrets exposed)."""
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "configured": websearch_service.is_configured(),
        "provider": (settings.search_provider or "").strip().lower() or None,
    }


@router.post(
    "/search/web",
    response_model=WebSearchResponse,
    dependencies=[Depends(rate_limit("websearch", per_minute=20))],
)
async def web_search(
    payload: WebSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """Search the open web and answer with the local model + cited sources."""
    return await websearch_service.web_search(payload.query, count=payload.count)
