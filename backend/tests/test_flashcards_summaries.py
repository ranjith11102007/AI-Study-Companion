"""Phase 5: flashcards + course summaries — real generation, no fabricated data."""
import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.ingestion.pipeline import process_material
from app.main import app
from app.models.user import User

PASSWORD = "secret123"


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


async def _upload_and_process(client: AsyncClient, headers: dict, course_id: int, filename: str, content: bytes):
    """Upload a file and synchronously process it so content_units are ready."""
    files = {"file": (filename, content, "text/plain")}
    up = await client.post(
        f"/api/courses/{course_id}/materials", files=files, headers=headers
    )
    assert up.status_code == 201, up.text
    material_id = up.json()["id"]
    await process_material(material_id)
    return material_id


# --------------------------------------------------------------------------- #
# Helpers for mocking the local model
# --------------------------------------------------------------------------- #
class MockChatProvider:
    def __init__(self, responses: dict[str, str]):
        self.responses = responses
        self.calls = []

    async def chat(self, messages, temperature=0.2, max_tokens=None, **kwargs):
        self.calls.append((messages, temperature, max_tokens, kwargs))
        key = messages[-1]["content"][:60] if messages else "default"
        return self.responses.get(key, self.responses.get("default", "Q: A || B || topic: C"))


def _mock_ollama_provider(monkeypatch, responses):
    mock = MockChatProvider(responses)
    monkeypatch.setattr("app.services.flashcards.get_chat_provider", lambda: mock)
    monkeypatch.setattr("app.services.summaries.get_chat_provider", lambda: mock)
    return mock


# --------------------------------------------------------------------------- #
# Flashcard generation tests
# --------------------------------------------------------------------------- #
async def test_generate_flashcards_requires_course_ownership():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h1 = await _make_user(client, f"fc-{uuid.uuid4().hex[:8]}@example.com")
        h2 = await _make_user(client, f"fc-{uuid.uuid4().hex[:8]}@example.com")
        try:
            (await client.post("/api/courses/", json={"title": "Math"}, headers=h1)).json()
            c2 = (await client.post("/api/courses/", json={"title": "Bio"}, headers=h2)).json()

            r = await client.post(
                "/api/flashcards/generate",
                json={"course_id": c2["id"], "count": 3},
                headers=h1,
            )
            assert r.status_code == 404
        finally:
            await _cleanup(h1["Authorization"].split(" ")[1])
            await _cleanup(h2["Authorization"].split(" ")[1])


async def test_generate_flashcards_400_on_empty_course():
    email = f"fc-empty-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            h = await _make_user(client, email)
            c = (await client.post("/api/courses/", json={"title": "Empty"}, headers=h)).json()
            r = await client.post(
                "/api/flashcards/generate",
                json={"course_id": c["id"], "count": 5},
                headers=h,
            )
            assert r.status_code == 400
            assert "no content" in r.json()["detail"].lower()
    finally:
        await _cleanup(email)


async def test_generate_flashcards_returns_cards_and_persists(monkeypatch):
    email = f"fc-gen-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    cards_text = "\n".join(
        f"Q: What is {i}? || A: Answer {i} || topic: Topic {i}" for i in range(1, 6)
    )
    _mock_ollama_provider(monkeypatch, {"default": cards_text})
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            h = await _make_user(client, email)
            c = (await client.post("/api/courses/", json={"title": "Physics"}, headers=h)).json()
            await _upload_and_process(client, h, c["id"], "notes.txt",
                b"Newton's laws. F=ma. Energy conserved. Gravity pulls. Mass attracts.")

            r = await client.post(
                "/api/flashcards/generate",
                json={"course_id": c["id"], "count": 4},
                headers=h,
            )
            assert r.status_code == 201, r.text
            cards = r.json()
            assert len(cards) >= 1
            assert all("front" in c and "back" in c for c in cards)
            assert all(c["course_id"] == c["id"] for c in cards)

            listed = await client.get(f"/api/flashcards?course_id={c['id']}", headers=h)
            assert listed.status_code == 200
            assert len(listed.json()) == len(cards)

            h2 = await _make_user(client, f"fc-{uuid.uuid4().hex[:8]}@example.com")
            assert (await client.get(f"/api/flashcards?course_id={c['id']}", headers=h2)).json() == []
    finally:
        await _cleanup(email)


# --------------------------------------------------------------------------- #
# Review / spaced-repetition
# --------------------------------------------------------------------------- #
async def test_review_card_updates_interval_and_ease(monkeypatch):
    email = f"fc-review-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    _mock_ollama_provider(monkeypatch, {"default": "Q: X || A: Y || topic: Z"})
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            h = await _make_user(client, email)
            c = (await client.post("/api/courses/", json={"title": "Chem"}, headers=h)).json()
            await _upload_and_process(client, h, c["id"], "chem.txt", b"H2O is water. Atoms bond. Hydrogen and oxygen form molecules.")

            gen = await client.post(
                "/api/flashcards/generate", json={"course_id": c["id"], "count": 1}, headers=h
            )
            card = gen.json()[0]
            cid = card["id"]
            assert card["interval_days"] == 1
            assert card["ease"] == 2.5

            r1 = await client.patch(
                f"/api/flashcards/{cid}", json={"correct": True}, headers=h
            )
            assert r1.status_code == 200
            assert r1.json()["interval_days"] >= 2
            assert r1.json()["ease"] >= 2.5
            assert r1.json()["correct_count"] == 1

            r2 = await client.patch(
                f"/api/flashcards/{cid}", json={"correct": False}, headers=h
            )
            assert r2.status_code == 200
            assert r2.json()["interval_days"] == 1
            assert r2.json()["ease"] < 2.5
            assert r2.json()["wrong_count"] == 1
    finally:
        await _cleanup(email)


async def test_review_card_owner_only():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h1 = await _make_user(client, f"fc-o1-{uuid.uuid4().hex[:8]}@example.com")
        h2 = await _make_user(client, f"fc-o2-{uuid.uuid4().hex[:8]}@example.com")
        try:
            c = (await client.post("/api/courses/", json={"title": "Owner"}, headers=h1)).json()
            await _upload_and_process(client, h1, c["id"], "o.txt", b"test content for owner")
            gen = await client.post(
                "/api/flashcards/generate", json={"course_id": c["id"], "count": 1}, headers=h1
            )
            cid = gen.json()[0]["id"]

            r = await client.patch(
                f"/api/flashcards/{cid}", json={"correct": True}, headers=h2
            )
            assert r.status_code == 404
        finally:
            await _cleanup(h1["Authorization"].split(" ")[1])
            await _cleanup(h2["Authorization"].split(" ")[1])


# --------------------------------------------------------------------------- #
# Course summary
# --------------------------------------------------------------------------- #
async def test_summary_400_on_empty_course():
    email = f"sum-empty-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            h = await _make_user(client, email)
            c = (await client.post("/api/courses/", json={"title": "NoContent"}, headers=h)).json()
            r = await client.get(f"/api/summaries/{c['id']}", headers=h)
            assert r.status_code == 400
            assert "no content" in r.json()["detail"].lower()
    finally:
        await _cleanup(email)


async def test_summary_generates_and_caches(monkeypatch):
    email = f"sum-gen-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    summary_json = '{"title": "Unit 1: Basics", "body": "Summary text with key points."}'
    _mock_ollama_provider(monkeypatch, {"default": summary_json})
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            h = await _make_user(client, email)
            c = (await client.post("/api/courses/", json={"title": "HasContent"}, headers=h)).json()
            await _upload_and_process(client, h, c["id"], "s.txt", b"Study material. Topic A. Topic B. Details. More content here for summarization.")

            r1 = await client.get(f"/api/summaries/{c['id']}", headers=h)
            assert r1.status_code == 200
            d1 = r1.json()
            assert d1["cached"] is False
            assert "title" in d1 and "body" in d1

            r2 = await client.get(f"/api/summaries/{c['id']}", headers=h)
            assert r2.status_code == 200
            d2 = r2.json()
            assert d2["cached"] is True
            assert d2["title"] == d1["title"]
    finally:
        await _cleanup(email)


async def test_summary_owner_only():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h1 = await _make_user(client, f"sum-o1-{uuid.uuid4().hex[:8]}@example.com")
        h2 = await _make_user(client, f"sum-o2-{uuid.uuid4().hex[:8]}@example.com")
        try:
            c = (await client.post("/api/courses/", json={"title": "Owned"}, headers=h1)).json()
            r = await client.get(f"/api/summaries/{c['id']}", headers=h2)
            assert r.status_code == 404
        finally:
            await _cleanup(h1["Authorization"].split(" ")[1])
            await _cleanup(h2["Authorization"].split(" ")[1])