"""Integration tests for material upload, indexing and per-user isolation."""

import uuid

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.ingestion import pipeline
from app.main import app
from app.models.user import User

PASSWORD = "secret123"


class _FakeEmbeddingProvider:
    """Deterministic embeddings so tests never depend on a running Ollama."""

    model = "test-embed"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 768 for _ in texts]


class _BatchLimitedEmbeddingProvider:
    """Reproduces the hosted Gemini ``/v1beta/openai/embeddings`` behaviour.

    When a single request carries more than 100 inputs, Gemini answers
    ``HTTP 400 * BatchEmbedContentsRequest.requests: at most 100 requests can
    be in one batch``. That is exactly what used to leave a 41-page PDF stuck
    at "failed, 0 chunks" while a small file indexed fine.
    """

    model = "stub-batch-limited-100"
    batch_sizes: list[int] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        type(self).batch_sizes.append(len(texts))
        if len(texts) > 100:
            request = httpx.Request(
                "POST", "https://gemini.test/v1beta/openai/embeddings"
            )
            response = httpx.Response(
                400,
                request=request,
                text=(
                    "* BatchEmbedContentsRequest.requests: "
                    "at most 100 requests can be in one batch\n"
                ),
            )
            raise httpx.HTTPStatusError(
                "Client error '400 Bad Request'", request=request, response=response
            )
        return [[0.0] * 768 for _ in texts]


class _RejectingEmbeddingProvider:
    """Always fails, to prove failures are reported accurately and retryably."""

    model = "stub-rejecting"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        request = httpx.Request(
            "POST", "https://gemini.test/v1beta/openai/embeddings"
        )
        response = httpx.Response(429, request=request, text="quota exceeded")
        raise httpx.HTTPStatusError(
            "Client error '429 Too Many Requests'", request=request, response=response
        )


@pytest.fixture
def fake_embeddings(monkeypatch):
    monkeypatch.setattr(pipeline, "get_embedding_provider", _FakeEmbeddingProvider)


async def _make_user(client: AsyncClient, email: str) -> dict:
    await client.post(
        "/api/auth/signup",
        json={"name": "Test", "email": email, "password": PASSWORD},
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


@pytest.mark.asyncio
async def test_upload_text_material_is_extracted_and_indexed(fake_embeddings):
    email = f"mat-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "Biology"}, headers=headers
                )
            ).json()

            response = await client.post(
                f"/api/courses/{course['id']}/materials",
                files={
                    "file": (
                        "notes.txt",
                        b"Photosynthesis converts light into chemical energy.",
                        "text/plain",
                    )
                },
                headers=headers,
            )
            assert response.status_code == 201, response.text
            material = response.json()
            assert material["material_type"] == "text"
            assert material["original_filename"] == "notes.txt"
            assert material["processing_status"] == "pending"

            listing = (
                await client.get(
                    f"/api/courses/{course['id']}/materials", headers=headers
                )
            ).json()
            assert len(listing) == 1

            detail = (
                await client.get(f"/api/materials/{material['id']}", headers=headers)
            ).json()
            assert detail["processing_status"] == "ready"
            assert detail["content_unit_count"] == 1
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_and_empty_files():
    email = f"mat-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "Chem"}, headers=headers
                )
            ).json()
            url = f"/api/courses/{course['id']}/materials"

            bad_ext = await client.post(
                url,
                files={"file": ("deck.docx", b"PK\x03\x04", "application/octet-stream")},
                headers=headers,
            )
            assert bad_ext.status_code == 400

            empty = await client.post(
                url,
                files={"file": ("empty.txt", b"", "text/plain")},
                headers=headers,
            )
            assert empty.status_code == 400
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_upload_pptx_material_is_extracted_and_indexed(fake_embeddings):
    from io import BytesIO

    from pptx import Presentation
    from pptx.util import Inches

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = "Cell Biology"
    textbox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(1))
    textbox.text_frame.text = "Mitochondria produce ATP for the cell."
    buffer = BytesIO()
    presentation.save(buffer)

    email = f"mat-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "Bio slides"}, headers=headers
                )
            ).json()

            response = await client.post(
                f"/api/courses/{course['id']}/materials",
                files={
                    "file": (
                        "cells.pptx",
                        buffer.getvalue(),
                        "application/vnd.openxmlformats-officedocument."
                        "presentationml.presentation",
                    )
                },
                headers=headers,
            )
            assert response.status_code == 201, response.text
            material = response.json()
            assert material["material_type"] == "pptx"

            detail = (
                await client.get(f"/api/materials/{material['id']}", headers=headers)
            ).json()
            assert detail["processing_status"] == "ready", detail
            assert detail["content_unit_count"] >= 1
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_upload_enforces_size_limit(monkeypatch):
    from app.services import materials as material_service

    monkeypatch.setattr(material_service.settings, "max_upload_size_mb", 0)

    email = f"mat-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "Phys"}, headers=headers
                )
            ).json()
            response = await client.post(
                f"/api/courses/{course['id']}/materials",
                files={"file": ("big.txt", b"x" * 64, "text/plain")},
                headers=headers,
            )
            assert response.status_code == 413
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_material_access_is_owner_scoped(fake_embeddings):
    email_a = f"mat-{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"mat-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers_a = await _make_user(client, email_a)
            headers_b = await _make_user(client, email_b)

            course = (
                await client.post(
                    "/api/courses/", json={"title": "Private"}, headers=headers_a
                )
            ).json()
            material = (
                await client.post(
                    f"/api/courses/{course['id']}/materials",
                    files={"file": ("secret.txt", b"private notes", "text/plain")},
                    headers=headers_a,
                )
            ).json()

            other_material = await client.get(
                f"/api/materials/{material['id']}", headers=headers_b
            )
            assert other_material.status_code == 404

            other_listing = await client.get(
                f"/api/courses/{course['id']}/materials", headers=headers_b
            )
            assert other_listing.status_code == 404

            other_upload = await client.post(
                f"/api/courses/{course['id']}/materials",
                files={"file": ("x.txt", b"nope", "text/plain")},
                headers=headers_b,
            )
            assert other_upload.status_code == 404
    finally:
        await _cleanup(email_a)
        await _cleanup(email_b)


@pytest.mark.asyncio
async def test_upload_text_with_nul_bytes_is_indexed(fake_embeddings):
    """Regression: NUL bytes in extracted text used to fail the whole upload."""
    email = f"mat-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "OS Notes"}, headers=headers
                )
            ).json()
            response = await client.post(
                f"/api/courses/{course['id']}/materials",
                files={
                    "file": (
                        "os.txt",
                        b"Operating\x00 System Concepts\x00",
                        "text/plain",
                    )
                },
                headers=headers,
            )
            assert response.status_code == 201, response.text
            material = response.json()

            detail = (
                await client.get(f"/api/materials/{material['id']}", headers=headers)
            ).json()
            assert detail["processing_status"] == "ready", detail
            assert detail["content_unit_count"] == 1
            assert not detail.get("processing_error")
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_reprocess_material_reindexes(fake_embeddings):
    email = f"mat-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "Reprocess"}, headers=headers
                )
            ).json()
            material = (
                await client.post(
                    f"/api/courses/{course['id']}/materials",
                    files={
                        "file": (
                            "notes.txt",
                            b"Cells are the unit of life.",
                            "text/plain",
                        )
                    },
                    headers=headers,
                )
            ).json()

            again = await client.post(
                f"/api/materials/{material['id']}/reprocess", headers=headers
            )
            assert again.status_code == 200, again.text

            detail = (
                await client.get(f"/api/materials/{material['id']}", headers=headers)
            ).json()
            assert detail["processing_status"] == "ready", detail
            assert detail["content_unit_count"] == 1
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_reprocess_is_owner_scoped(fake_embeddings):
    email_a = f"mat-{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"mat-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers_a = await _make_user(client, email_a)
            headers_b = await _make_user(client, email_b)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "Mine"}, headers=headers_a
                )
            ).json()
            material = (
                await client.post(
                    f"/api/courses/{course['id']}/materials",
                    files={"file": ("a.txt", b"hello", "text/plain")},
                    headers=headers_a,
                )
            ).json()

            forbidden = await client.post(
                f"/api/materials/{material['id']}/reprocess", headers=headers_b
            )
            assert forbidden.status_code == 404
    finally:
        await _cleanup(email_a)
        await _cleanup(email_b)


@pytest.mark.asyncio
async def test_upload_with_more_than_100_chunks_is_batched(monkeypatch):
    """Regression: one embedding request per document broke on >100 chunks.

    A 41-page text PDF produced 106 chunks, which Gemini's OpenAI-compatible
    endpoint rejects outright. The document must still index (in batches)
    rather than being marked failed.
    """
    monkeypatch.setattr(
        pipeline, "get_embedding_provider", _BatchLimitedEmbeddingProvider
    )
    _BatchLimitedEmbeddingProvider.batch_sizes = []

    paragraph = "word " * 120  # ~600 chars -> one chunk per paragraph
    body = ("\n\n".join(paragraph for _ in range(200))).encode("utf-8")
    assert len(body) > 100_000

    email = f"mat-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "COA Unit 3"}, headers=headers
                )
            ).json()

            response = await client.post(
                f"/api/courses/{course['id']}/materials",
                files={"file": ("coa-unit-3.txt", body, "text/plain")},
                headers=headers,
            )
            assert response.status_code == 201, response.text
            material = response.json()

            detail = (
                await client.get(f"/api/materials/{material['id']}", headers=headers)
            ).json()
            assert detail["processing_status"] == "ready", detail
            assert detail["content_unit_count"] > 100
            assert not detail["processing_error"]

            sizes = _BatchLimitedEmbeddingProvider.batch_sizes
            assert sizes, "the embedding provider was never called"
            assert max(sizes) <= 100
            assert sum(sizes) == detail["content_unit_count"]
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_failed_indexing_reports_the_cause_and_retries_cleanly(monkeypatch):
    """A failed attempt stores an actionable reason and can be retried."""
    monkeypatch.setattr(pipeline, "get_embedding_provider", _RejectingEmbeddingProvider)

    email = f"mat-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "OS Notes"}, headers=headers
                )
            ).json()

            response = await client.post(
                f"/api/courses/{course['id']}/materials",
                files={
                    "file": (
                        "os.txt",
                        b"Operating System Concepts: a process is a program.",
                        "text/plain",
                    )
                },
                headers=headers,
            )
            assert response.status_code == 201, response.text
            material = response.json()

            failed = (
                await client.get(f"/api/materials/{material['id']}", headers=headers)
            ).json()
            assert failed["processing_status"] == "failed"
            assert failed["content_unit_count"] == 0
            assert "429" in failed["processing_error"]
            assert "Traceback" not in failed["processing_error"]

            # The operator fixes the provider; the user clicks Retry.
            monkeypatch.setattr(
                pipeline, "get_embedding_provider", _FakeEmbeddingProvider
            )
            retry = await client.post(
                f"/api/materials/{material['id']}/reprocess", headers=headers
            )
            assert retry.status_code == 200, retry.text

            recovered = (
                await client.get(f"/api/materials/{material['id']}", headers=headers)
            ).json()
            assert recovered["processing_status"] == "ready", recovered
            assert recovered["content_unit_count"] == 1
            assert not recovered["processing_error"]
    finally:
        await _cleanup(email)
