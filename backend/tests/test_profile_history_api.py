"""Profile (/api/users/me) and study history (/api/history).

Real FastAPI stack + DB. Only the external embedding boundary is faked (an
upload would otherwise need a running Ollama); everything else — ownership,
persistence, pagination — is exercised for real.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.ingestion import pipeline
from app.main import app
from app.models.user import User

PASSWORD = "secret123"


class _FakeEmbeddingProvider:
    model = "test-embed"

    async def embed(self, texts):
        return [[0.0] * 768 for _ in texts]


@pytest.fixture
def fake_embeddings(monkeypatch):
    monkeypatch.setattr(pipeline, "get_embedding_provider", _FakeEmbeddingProvider)


async def _make_user(client: AsyncClient, email: str) -> dict:
    await client.post(
        "/api/auth/signup", json={"name": "Prof", "email": email, "password": PASSWORD}
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


async def _upload(client, headers, course_id, name="notes.txt", body=b"hello world"):
    resp = await client.post(
        f"/api/courses/{course_id}/materials",
        files={"file": (name, body, "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# Profile                                                                      #
# --------------------------------------------------------------------------- #
async def test_profile_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/users/me")
    assert resp.status_code == 401


async def test_profile_reflects_real_account_and_persists_updates():
    email = f"me-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)

            me = await client.get("/api/users/me", headers=headers)
            assert me.status_code == 200
            body = me.json()
            assert body["email"] == email
            assert body["name"] == "Prof"
            # Never claimed as verified until it actually is.
            assert body["email_verified"] is False
            assert body["preferences"] == {}

            updated = await client.patch(
                "/api/users/me",
                json={"display_name": "Ranjith", "preferences": {"reduceMotion": True}},
                headers=headers,
            )
            assert updated.status_code == 200
            assert updated.json()["display_name"] == "Ranjith"
            assert updated.json()["preferences"]["reduceMotion"] is True

            # A later partial update must not wipe the earlier preference.
            await client.patch(
                "/api/users/me",
                json={"preferences": {"defaultCourseId": 7}},
                headers=headers,
            )
            again = (await client.get("/api/users/me", headers=headers)).json()
            assert again["preferences"]["reduceMotion"] is True
            assert again["preferences"]["defaultCourseId"] == 7
            assert again["display_name"] == "Ranjith"
    finally:
        await _cleanup(email)


async def test_profile_email_is_not_changeable_here():
    email = f"me-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            # `email` is not part of the update schema; extra keys are ignored.
            resp = await client.patch(
                "/api/users/me", json={"email": "other@example.com"}, headers=headers
            )
            assert resp.status_code == 200
            assert resp.json()["email"] == email
    finally:
        await _cleanup(email)


async def test_clear_display_name_with_blank():
    email = f"me-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            await client.patch(
                "/api/users/me", json={"display_name": "Temp"}, headers=headers
            )
            resp = await client.patch(
                "/api/users/me", json={"display_name": "   "}, headers=headers
            )
            assert resp.status_code == 200
            assert resp.json()["display_name"] is None
    finally:
        await _cleanup(email)


# --------------------------------------------------------------------------- #
# History                                                                      #
# --------------------------------------------------------------------------- #
async def test_history_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/history")
        assert resp.status_code == 401


async def test_history_contains_real_upload_and_is_owner_scoped(fake_embeddings):
    owner = f"hist-{uuid.uuid4().hex[:8]}@example.com"
    other = f"hist-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, owner)
            other_headers = await _make_user(client, other)

            course = (
                await client.post(
                    "/api/courses/", json={"title": "Biology"}, headers=headers
                )
            ).json()
            await client.post(
                f"/api/courses/{course['id']}/materials",
                files={"file": ("notes.txt", b"hello", "text/plain")},
                headers=headers,
            )

            other_course = (
                await client.post(
                    "/api/courses/", json={"title": "Chemistry"}, headers=other_headers
                )
            ).json()
            await client.post(
                f"/api/courses/{other_course['id']}/materials",
                files={"file": ("secret.txt", b"nope", "text/plain")},
                headers=other_headers,
            )

            resp = await client.get("/api/history", headers=headers)
            assert resp.status_code == 200, resp.text
            data = resp.json()
            uploads = events_of(data, "upload")
            upload_titles = [e["title"] for e in uploads]
            # Our own upload is present; the other user's upload is never shown.
            assert upload_titles == ["notes.txt"]
            assert [e["course_title"] for e in uploads] == ["Biology"]
            assert data["total"] == 1
            assert "upload" in data["kinds"]
    finally:
        await _cleanup(owner)
        await _cleanup(other)


def events_of(payload: dict, kind: str) -> list[dict]:
    return [e for e in payload["events"] if e["kind"] == kind]


async def test_history_kind_filter_and_pagination(fake_embeddings):
    email = f"hist-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "Physics"}, headers=headers
                )
            ).json()
            for name in ("one.txt", "two.txt", "three.txt"):
                await client.post(
                    f"/api/courses/{course['id']}/materials",
                    files={"file": (name, b"x", "text/plain")},
                    headers=headers,
                )

            uploads = await client.get(
                "/api/history?kind=upload", headers=headers
            )
            assert uploads.status_code == 200
            payload = uploads.json()
            assert payload["total"] == 3
            assert all(e["kind"] == "upload" for e in payload["events"])

            first = await client.get(
                "/api/history?kind=upload&limit=2&offset=0", headers=headers
            )
            second = await client.get(
                "/api/history?kind=upload&limit=2&offset=2", headers=headers
            )
            assert first.json()["has_more"] is True
            assert len(first.json()["events"]) == 2
            assert second.json()["has_more"] is False
            assert len(second.json()["events"]) == 1

            bad = await client.get("/api/history?kind=nope", headers=headers)
            assert bad.status_code == 422
    finally:
        await _cleanup(email)


async def test_history_course_filter_requires_ownership(fake_embeddings):
    owner = f"hist-{uuid.uuid4().hex[:8]}@example.com"
    other = f"hist-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, owner)
            other_headers = await _make_user(client, other)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "Mine"}, headers=headers
                )
            ).json()

            mine = await client.get(
                f"/api/history?course_id={course['id']}", headers=headers
            )
            assert mine.status_code == 200
            assert mine.json()["total"] == 0

            denied = await client.get(
                f"/api/history?course_id={course['id']}", headers=other_headers
            )
            assert denied.status_code == 404
    finally:
        await _cleanup(owner)
        await _cleanup(other)
