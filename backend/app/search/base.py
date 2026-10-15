"""Pluggable web-search provider interface (Mode C: Global Web Search).

Global search is deliberately isolated from course retrieval. A provider only
ever returns *web* results; nothing here merges external pages into a
course-grounded answer. Each result records whether it is a bare search-result
snippet or text actually fetched from the page, so the UI can be honest about
what was verified.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlsplit

# A result the provider returned but whose page we did not fetch.
SOURCE_SNIPPET = "search_result"
# A result whose full page we retrieved and extracted text from.
SOURCE_PAGE = "page"


@dataclass
class WebResult:
    """One external web result.

    ``snippet`` is the provider's own description. ``content`` is only set when
    the page itself was fetched (:data:`SOURCE_PAGE`); callers must not present
    a snippet as if the full page had been read.
    """

    title: str
    url: str
    snippet: str = ""
    age: str | None = None
    extra_snippets: list[str] = field(default_factory=list)
    source: str = SOURCE_SNIPPET
    content: str | None = None

    @property
    def domain(self) -> str:
        host = urlsplit(self.url).netloc.lower()
        return host[4:] if host.startswith("www.") else host

    def as_citation(self, retrieved_at: str | None = None) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "domain": self.domain,
            "snippet": self.snippet,
            "source": self.source,
            "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        }


class SearchProvider(ABC):
    """A source of web results. Implementations must not fabricate results."""

    name: str = "provider"

    @abstractmethod
    async def search(self, query: str, *, count: int = 5) -> list[WebResult]:
        """Return up to ``count`` results for ``query`` (may return fewer)."""
        raise NotImplementedError
