"""Very small in-process rate limiter (per client, per bucket).

Good enough to blunt accidental hammering of auth and LLM endpoints on a
single-process local deployment. It is deliberately not a distributed limiter.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_WINDOWS: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _client_key(request: Request) -> str:
    origin = request.headers.get("x-forwarded-for")
    if origin:
        return origin.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str, per_minute: int | None = None):
    async def dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        limit = per_minute or settings.llm_rate_limit_per_minute
        key = (bucket, _client_key(request))
        now = time.monotonic()
        window = _WINDOWS[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests — please slow down and try again shortly.",
            )
        window.append(now)

    return dependency
