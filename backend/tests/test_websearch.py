"""Web search (Mode C) + authenticated material file endpoint.

The provider and the local chat model are both mocked here, so these tests need
neither internet access nor a running Ollama. One thin API integration test
exercises the real FastAPI stack (including auth and ownership).
"""

import uuid

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.ingestion import pipeline
from app.main import app
from app.models.user import User
from app.search.base import SOURCE_SNIPPET, WebResult
from app.search.brave import BraveSearchProvider, parse_brave_response
from app.services import websearch as websearch_service

PASSWORD = "secret123"

BRAVE_SAMPLE = {
    "web": {
        "results": [
            {
                "title": "Photosynthesis - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Photosynthesis",
                "description": "Photosynthesis converts light energy into glucose.",
                "age": "2 days ago",
                "extra_snippets": ["Chlorophyll absorbs light."],
            },
            {
                "title": "Duplicate",
                "url": "https://en.wikipedia.org/wiki/Photosynthesis",
                "description": "duplicate url",
            },
            {"title": "No URL here", "description": "skip me"},
            {
                "title": "Khan Academy: Calvin cycle",
                "url": "https://www.khanacademy.org/science/calvin-cycle",
                "description": "The Calvin cycle fixes carbon into sugar.",
            },
        ]
    }
}


class _FakeProvider:
    name = "fake"

    def __init__(self, results):
        self._results = results

    async def search(self, query, *, count=5):
        return list(self._results)[:count]


class _BoomProvider:
    name = "fake"

    async def search(self, query, *, count=5):
        raise RuntimeError("boom")


class _FakeChat:
    def __init__(self, text="Answer [1].\nSOURCES: 1", fail=False):
        self._text = text
        self._fail = fail

    async def chat(self, messages, **kwargs):
        if self._fail:
            raise httpx.ConnectError("ollama down")
        return self._text


# --------------------------------------------------------------------------- #
# Parsing + ranking (pure)                                                     #
# --------------------------------------------------------------------------- #
def test_parse_brave_response_keeps_only_usable_results():
    results = parse_brave_response(BRAVE_SAMPLE)
    # URL-less entry dropped; duplicate URLs are kept here (ranked later).
    assert len(results) == 3
    assert results[0].title == "Photosynthesis - Wikipedia"
    assert results[0].source == SOURCE_SNIPPET
    assert results[0].age == "2 days ago"
    assert results[0].extra_snippets == ["Chlorophyll absorbs light."]


def test_parse_brave_response_tolerates_garbage():
    assert parse_brave_response({}) == []
    assert parse_brave_response({"web": None}) == []
    assert parse_brave_response({"web": {"results": [None, 42]}}) == []


def test_webresult_domain_and_citation():
    result = WebResult(title="T", url="https://www.example.com/a/b", snippet="s")
    assert result.domain == "example.com"
    citation = result.as_citation("2026-01-01T00:00:00+00:00")
    assert citation["domain"] == "example.com"
    assert citation["source"] == SOURCE_SNIPPET
    assert citation["retrieved_at"] == "2026-01-01T00:00:00+00:00"


def test_rank_dedupes_and_boosts_query_overlap():
    results = [
        WebResult(title="Unrelated", url="https://a.example/x", snippet="nothing"),
        WebResult(title="Calvin cycle", url="https://b.example/y", snippet="carbon fixation"),
        WebResult(title="Dup", url="https://a.example/x", snippet="dup"),
    ]
    ranked = websearch_service._rank_results("calvin cycle", results, 5)
    assert [r.url for r in ranked] == ["https://b.example/y", "https://a.example/x"]


def test_rank_drops_non_http_urls():
    results = [
        WebResult(title="js", url="javascript:alert(1)"),
        WebResult(title="ok", url="https://ok.example/"),
    ]
    ranked = websearch_service._rank_results("x", results, 5)
    assert [r.url for r in ranked] == ["https://ok.example/"]


# --------------------------------------------------------------------------- #
# Brave provider (mocked transport, no network)                                #
# --------------------------------------------------------------------------- #
async def test_brave_provider_parses_response_and_sends_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["token"] = request.headers.get("X-Subscription-Token")
        return httpx.Response(200, json=BRAVE_SAMPLE)

    provider = BraveSearchProvider("test-key", transport=httpx.MockTransport(handler))
    results = await provider.search("photosynthesis", count=10)
    assert seen["token"] == "test-key"
    assert "count=10" in seen["url"]
    assert results[0].title == "Photosynthesis - Wikipedia"


async def test_brave_provider_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    provider = BraveSearchProvider("k", transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        await provider.search("q")


async def test_brave_provider_empty_query_returns_nothing():
    provider = BraveSearchProvider("k")
    assert await provider.search("   ") == []


# --------------------------------------------------------------------------- #
# Service behaviour                                                            #
# --------------------------------------------------------------------------- #
async def test_web_search_grounded_answer_with_citations():
    provider = _FakeProvider(parse_brave_response(BRAVE_SAMPLE))
    out = await websearch_service.web_search(
        "photosynthesis", provider=provider, chat_provider=_FakeChat()
    )
    assert out["evidence_status"] == "grounded"
    results = out["results"]
    assert [r["url"] for r in results] == [
        "https://en.wikipedia.org/wiki/Photosynthesis",
        "https://www.khanacademy.org/science/calvin-cycle",
    ]
    assert results[0]["domain"] == "en.wikipedia.org"
    assert out["answer"] == "Answer [1].\nSOURCES: 1"


async def test_web_search_no_results_is_insufficient():
    out = await websearch_service.web_search(
        "obscure query", provider=_FakeProvider([]), chat_provider=_FakeChat()
    )
    assert out["evidence_status"] == "insufficient"
    assert out["results"] == []
    assert out["answer"] is None


async def test_web_search_model_failure_keeps_results_and_is_honest():
    out = await websearch_service.web_search(
        "photosynthesis",
        provider=_FakeProvider(parse_brave_response(BRAVE_SAMPLE)),
        chat_provider=_FakeChat(fail=True),
    )
    assert out["evidence_status"] == "unavailable"
    assert out["answer"] is None
    assert len(out["results"]) == 2  # real results are still returned
    assert "unavailable" in out["notice"]


async def test_web_search_provider_error_raises_502():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await websearch_service.web_search("x", provider=_BoomProvider())
    assert exc.value.status_code == 502


async def test_web_search_empty_query_raises_422():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await websearch_service.web_search("   ")
    assert exc.value.status_code == 422


async def test_web_search_unconfigured_raises_503(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(websearch_service, "get_search_provider", lambda: None)
    with pytest.raises(HTTPException) as exc:
        await websearch_service.web_search("anything")
    assert exc.value.status_code == 503


# --------------------------------------------------------------------------- #
# API integration (real FastAPI stack + DB, mocked external boundaries)        #
# --------------------------------------------------------------------------- #
class _FakeEmbeddingProvider:
    model = "test-embed"

    async def embed(self, texts):
        return [[0.0] * 768 for _ in texts]


@pytest.fixture
def fake_embeddings(monkeypatch):
    monkeypatch.setattr(pipeline, "get_embedding_provider", _FakeEmbeddingProvider)


async def _make_user(client: AsyncClient, email: str) -> dict:
    await client.post(
        "/api/auth/signup", json={"name": "T", "email": email, "password": PASSWORD}
    )
    token = (
        await client.post(
            "/api/auth/signin", json={"email": email, "password": PASSWORD}
        )
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _cleanup(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(delete(User).filter(User.email == email))
        await db.commit()


async def test_material_file_endpoint_is_owner_scoped(fake_embeddings):
    owner = f"file-{uuid.uuid4().hex[:8]}@example.com"
    other = f"file-{uuid.uuid4().hex[:8]}@example.com"
    body = b"Photosynthesis converts light into chemical energy."
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, owner)
            other_headers = await _make_user(client, other)
            course = await client.post(
                "/api/courses/", json={"title": "Bio"}, headers=headers
            )
            course_id = course.json()["id"]
            uploaded = await client.post(
                f"/api/courses/{course_id}/materials",
                files={"file": ("notes.txt", body, "text/plain")},
                headers=headers,
            )
            assert uploaded.status_code == 201, uploaded.text
            material_id = uploaded.json()["id"]

            resp = await client.get(
                f"/api/materials/{material_id}/file", headers=headers
            )
            assert resp.status_code == 200
            assert resp.content == body
            assert resp.headers["content-type"].startswith("text/plain")

            # A different user must not be able to read the file (404, no leak).
            denied = await client.get(
                f"/api/materials/{material_id}/file", headers=other_headers
            )
            assert denied.status_code == 404
    finally:
        await _cleanup(owner)
        await _cleanup(other)


async def test_search_endpoint_reports_unconfigured(monkeypatch):
    email = f"search-{uuid.uuid4().hex[:8]}@example.com"
    monkeypatch.setattr(websearch_service, "get_search_provider", lambda: None)
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            status_resp = await client.get("/api/search/status", headers=headers)
            assert status_resp.status_code == 200
            assert status_resp.json()["configured"] is False

            resp = await client.post(
                "/api/search/web", json={"query": "anything"}, headers=headers
            )
            assert resp.status_code == 503
    finally:
        await _cleanup(email)


async def test_search_endpoint_returns_cited_results(monkeypatch):
    email = f"search-{uuid.uuid4().hex[:8]}@example.com"
    monkeypatch.setattr(
        websearch_service,
        "get_search_provider",
        lambda: _FakeProvider(parse_brave_response(BRAVE_SAMPLE)),
    )
    monkeypatch.setattr(websearch_service, "get_chat_provider", lambda: _FakeChat())
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            resp = await client.post(
                "/api/search/web", json={"query": "photosynthesis"}, headers=headers
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["evidence_status"] == "grounded"
            assert data["provider"] == "fake"
            assert len(data["results"]) == 2
            assert data["results"][0]["url"].startswith("https://")
    finally:
        await _cleanup(email)
