"""Request/response schemas for optional global web search (Mode C)."""

from pydantic import BaseModel, Field


class WebSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=400)
    count: int | None = Field(default=None, ge=1, le=20)


class WebSource(BaseModel):
    """A single external source. ``source`` distinguishes a bare search-result
    snippet (``search_result``) from content actually fetched from the page
    (``page``), so the UI never implies a page was read when only its snippet
    was available."""

    title: str
    url: str
    domain: str
    snippet: str = ""
    source: str = "search_result"
    retrieved_at: str


class WebSearchResponse(BaseModel):
    query: str
    provider: str
    # "grounded"    — the local model answered from the retrieved snippets
    # "insufficient"— results were found but none supported an answer
    # "unavailable" — the local model could not be reached; results only
    evidence_status: str
    answer: str | None = None
    results: list[WebSource] = Field(default_factory=list)
    notice: str | None = None


class WebSearchStatus(BaseModel):
    configured: bool
    provider: str | None = None
