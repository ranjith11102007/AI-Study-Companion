"""Brave Search API provider (documented free tier, one API key).

Endpoint: ``GET https://api.search.brave.com/res/v1/web/search``
Auth:     header ``X-Subscription-Token: <key>``
Docs:     https://api-dashboard.search.brave.com/app/documentation

Free-tier limits (as documented by Brave) are modest — roughly 1 request/second
and a monthly query allowance. Results are the provider's own snippets; the page
is not fetched here, so every result is reported as ``search_result``.
"""

from __future__ import annotations

import httpx

from app.core.logging import get_logger
from app.search.base import SearchProvider, WebResult

logger = get_logger(__name__)

BRAVE_WEB_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


def parse_brave_response(data: dict) -> list[WebResult]:
    """Turn a Brave web-search payload into :class:`WebResult` objects.

    Pure and defensive: missing/odd fields are skipped rather than guessed.
    """
    results: list[WebResult] = []
    web = data.get("web") if isinstance(data, dict) else None
    raw_items = (web or {}).get("results") or []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        if not url:
            continue
        results.append(
            WebResult(
                title=(item.get("title") or url).strip(),
                url=url,
                snippet=(item.get("description") or "").strip(),
                age=item.get("age"),
                extra_snippets=list(item.get("extra_snippets") or []),
            )
        )
    return results


class BraveSearchProvider(SearchProvider):
    """Brave Search API client. ``transport`` is injectable for tests."""

    name = "brave"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self._transport = transport

    async def search(self, query: str, *, count: int = 5) -> list[WebResult]:
        query = (query or "").strip()
        if not query:
            return []
        params = {
            "q": query,
            # Brave accepts count 1..20 and offset 0..9.
            "count": max(1, min(int(count), 20)),
            "safesearch": "moderate",
        }
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        async with httpx.AsyncClient(
            timeout=self.timeout, transport=self.transport
        ) as client:
            response = await client.get(
                BRAVE_WEB_ENDPOINT, params=params, headers=headers
            )
        response.raise_for_status()
        return parse_brave_response(response.json())

    @property
    def transport(self) -> httpx.AsyncBaseTransport | None:
        return self._transport
