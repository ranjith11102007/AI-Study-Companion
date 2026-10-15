"""Optional global web search (Mode C).

The provider is selected by configuration and is *disabled by default* — a
local-first deployment never reaches the internet unless the operator opts in
by setting ``SEARCH_PROVIDER`` and a key.
"""

from app.core.config import get_settings
from app.search.base import SOURCE_PAGE, SOURCE_SNIPPET, SearchProvider, WebResult
from app.search.brave import BraveSearchProvider, parse_brave_response

__all__ = [
    "SOURCE_PAGE",
    "SOURCE_SNIPPET",
    "BraveSearchProvider",
    "SearchProvider",
    "WebResult",
    "get_search_provider",
    "parse_brave_response",
]


def get_search_provider() -> SearchProvider | None:
    """Return the configured provider, or ``None`` when search is disabled.

    Returning ``None`` (rather than raising) keeps the health/status endpoint
    and the UI able to report "not configured" honestly.
    """
    settings = get_settings()
    name = (settings.search_provider or "").strip().lower()
    if name == "brave" and settings.brave_search_api_key.strip():
        return BraveSearchProvider(
            settings.brave_search_api_key,
            timeout=settings.search_timeout_seconds,
        )
    return None
