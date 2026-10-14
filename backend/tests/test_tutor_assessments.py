"""Integration tests for retrieval, tutoring, citations, assessments and the
learner model. All model access is replaced with deterministic fakes so the
tests never require Ollama; PostgreSQL + pgvector are required (as elsewhere)."""

import json
import uuid

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.ingestion import pipeline
from app.main import app
from app.models.user import User
from app.services import assessments as assessment_service
from app.services import citations as citation_service
from app.services import learner as learner_service
from app.services import topics as topic_service
from app.services import tutor as tutor_service

PASSWORD = "secret123"
DIM = 768


class _FixedEmbedder:
    """Non-zero, identical vectors so every indexed chunk matches every query."""

    model = "test-embed"
    name = "test-embed"
    dimension = DIM

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (DIM - 1) for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        return [1.0] + [0.0] * (DIM - 1)


class _ScriptedChat:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    async def chat(self, messages, **_kwargs) -> str:
        self.calls += 1
        return self.text

    async def health(self) -> bool:
        return True


class _ExplodingChat:
    name = "exploding"

    async def chat(self, *_args, **_kwargs) -> str:
        raise AssertionError("the chat model must not be called here")

    async def health(self) -> bool:
        return True


class _StreamingChat:
    """Chat provider that yields its answer in pieces, like Ollama streaming."""

    name = "streaming"

    def __init__(self, pieces: list[str]) -> None:
        self.pieces = pieces

    async def stream_chat(self, _messages, **_kwargs):
        for piece in self.pieces:
            yield piece

    async def chat(self, *_args, **_kwargs) -> str:
        return "".join(self.pieces)

    async def health(self) -> bool:
        return True


class _BrokenEmbedder:
    name = "broken-embed"
    dimension = DIM

    async def embed(self, _texts):
        raise RuntimeError("ollama is not running")

    async def embed_query(self, _text):
        raise RuntimeError("ollama is not running")


@pytest.fixture
def fixed_embeddings(monkeypatch):
    monkeypatch.setattr(pipeline, "get_embedding_provider", _FixedEmbedder)


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


async def _user_id(email: str) -> int:
    async with SessionLocal() as db:
        return (
            await db.execute(select(User.id).where(User.email == email))
        ).scalar_one()


async def _indexed_course(client: AsyncClient, headers: dict, text: str) -> int:
    course = (
        await client.post("/api/courses/", json={"title": "Biology"}, headers=headers)
    ).json()
    response = await client.post(
        f"/api/courses/{course['id']}/materials",
        files={"file": ("notes.txt", text.encode("utf-8"), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    detail = (
        await client.get(
            f"/api/materials/{response.json()['id']}", headers=headers
        )
    ).json()
    assert detail["processing_status"] == "ready", detail
    return course["id"]


# --------------------------------------------------------------------------- #
# Tutor + citations
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_tutor_answers_with_real_citations(fixed_embeddings):
    email = f"tut-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course_id = await _indexed_course(
                client, headers, "Photosynthesis converts light energy into glucose."
            )
            user_id = await _user_id(email)

            chat = _ScriptedChat("Plants store light energy as glucose [1].\nSOURCES: 1")
            async with SessionLocal() as db:
                result = await tutor_service.answer_question(
                    db,
                    user_id=user_id,
                    course_id=course_id,
                    question="What do plants do with light energy?",
                    chat_provider=chat,
                    embedder=_FixedEmbedder(),
                )

            assert result["evidence_status"] == "grounded"
            assert result["sources_considered"] >= 1
            assert result["citations"], "grounded answers must carry citations"
            assert "SOURCES:" not in result["answer"]  # control line stripped
            citation = result["citations"][0]
            assert citation["material_title"] == "notes.txt"
            assert isinstance(citation["content_unit_id"], int)

            # The citation must resolve to real stored content for the owner.
            async with SessionLocal() as db:
                resolved = await citation_service.resolve_content_unit(
                    db, user_id=user_id, content_unit_id=citation["content_unit_id"]
                )
            assert "glucose" in resolved["content"].lower()
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_tutor_reports_insufficient_without_sources(fixed_embeddings):
    email = f"tut-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "Empty"}, headers=headers
                )
            ).json()
            user_id = await _user_id(email)

            async with SessionLocal() as db:
                result = await tutor_service.answer_question(
                    db,
                    user_id=user_id,
                    course_id=course["id"],
                    question="What is the meaning of life?",
                    chat_provider=_ExplodingChat(),
                    embedder=_FixedEmbedder(),
                )
            assert result["evidence_status"] == "insufficient"
            assert result["citations"] == []
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_citations_are_owner_scoped(fixed_embeddings):
    email_a = f"own-{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"own-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers_a = await _make_user(client, email_a)
            await _make_user(client, email_b)
            course_id = await _indexed_course(
                client, headers_a, "Cell respiration produces ATP."
            )
            user_a = await _user_id(email_a)
            user_b = await _user_id(email_b)

            async with SessionLocal() as db:
                chat = _ScriptedChat("ATP is produced [1].\nSOURCES: 1")
                result = await tutor_service.answer_question(
                    db,
                    user_id=user_a,
                    course_id=course_id,
                    question="What does respiration produce?",
                    chat_provider=chat,
                    embedder=_FixedEmbedder(),
                )
            unit_id = result["citations"][0]["content_unit_id"]

            async with SessionLocal() as db:
                with pytest.raises(HTTPException) as exc:
                    await citation_service.resolve_content_unit(
                        db, user_id=user_b, content_unit_id=unit_id
                    )
            assert exc.value.status_code == 404
    finally:
        await _cleanup(email_a)
        await _cleanup(email_b)


# --------------------------------------------------------------------------- #
# Streaming tutor (SSE)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_tutor_streams_tokens_then_persists(fixed_embeddings):
    email = f"str-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course_id = await _indexed_course(
                client, headers, "Photosynthesis converts light energy into glucose."
            )
            user_id = await _user_id(email)

            # Non-empty SOURCES line proves the control line is stripped.
            chat = _StreamingChat(
                ["Plants store ", "light energy as glucose [1].\nSOURCES: 1"]
            )
            async with SessionLocal() as db:
                events = [
                    event
                    async for event in tutor_service.stream_answer(
                        db,
                        user_id=user_id,
                        course_id=course_id,
                        question="What do plants do with light energy?",
                        chat_provider=chat,
                        embedder=_FixedEmbedder(),
                    )
                ]

            types = [event["type"] for event in events]
            assert types[0] == "status"
            assert "sources" in types
            assert "token" in types
            assert types[-1] == "done"

            tokens = "".join(e["text"] for e in events if e["type"] == "token")
            assert "glucose" in tokens.lower()

            done = events[-1]
            assert done["evidence_status"] == "grounded"
            assert done["sources_considered"] >= 1
            assert done["citations"]
            assert "SOURCES:" not in done["text"]  # control line stripped from final text
            assert done["conversation_id"] and done["message_id"]

            # The exchange must be persisted like the non-streaming path.
            async with SessionLocal() as db:
                _, messages = await tutor_service.get_conversation_messages(
                    db, user_id=await _user_id(email), conversation_id=done["conversation_id"]
                )
            assert [m.role for m in messages] == ["user", "assistant"]
            assert messages[-1].content == done["text"]
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_tutor_stream_reports_insufficient_without_sources(fixed_embeddings):
    email = f"str-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "Empty"}, headers=headers
                )
            ).json()
            user_id = await _user_id(email)

            async with SessionLocal() as db:
                events = [
                    e
                    async for e in tutor_service.stream_answer(
                        db,
                        user_id=user_id,
                        course_id=course["id"],
                        question="What is the meaning of life?",
                        chat_provider=_ExplodingChat(),
                        embedder=_FixedEmbedder(),
                    )
                ]
            types = [e["type"] for e in events]
            assert "token" not in types  # nothing indexed -> model not called
            assert events[-1]["type"] == "done"
            assert events[-1]["evidence_status"] == "insufficient"
            assert events[-1]["citations"] == []
            assert events[-1]["sources_considered"] == 0
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_tutor_stream_maps_provider_outage_to_error_event(fixed_embeddings):
    email = f"str-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course_id = await _indexed_course(
                client, headers, "Mitochondria produce ATP via respiration."
            )
            user_id = await _user_id(email)

            async with SessionLocal() as db:
                events = [
                    e
                    async for e in tutor_service.stream_answer(
                        db,
                        user_id=user_id,
                        course_id=course_id,
                        question="How is ATP produced?",
                        chat_provider=_ExplodingChat(),
                        embedder=_BrokenEmbedder(),
                    )
                ]
            assert events[0]["type"] == "status"
            assert events[-1]["type"] == "error"
            assert events[-1]["status"] == 503
            assert "unavailable" in events[-1]["message"].lower()
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_tutor_stream_endpoint_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/tutor/ask/stream",
            json={"course_id": 1, "question": "hi"},
            headers={"Accept": "text/event-stream"},
        )
    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# Assessments + grading + learner model
# --------------------------------------------------------------------------- #
def _generation_payload() -> str:
    return json.dumps(
        [
            {
                "qtype": "mcq",
                "difficulty": "easy",
                "topic": "Photosynthesis",
                "concept": "inputs",
                "prompt": "What does photosynthesis convert light into?",
                "options": ["Glucose", "Heat", "Sound"],
                "correct_answer": "Glucose",
                "explanation": "Light energy is stored as glucose.",
                "sources": [1],
            },
            {
                "qtype": "numeric",
                "difficulty": "medium",
                "topic": "Photosynthesis",
                "prompt": "How many carbon atoms are in one glucose molecule?",
                "correct_answer": "6",
                "explanation": "Glucose has six carbons.",
                "sources": [1],
            },
            {
                "qtype": "short",
                "difficulty": "hard",
                "topic": "Respiration",
                "prompt": "Explain how respiration releases energy.",
                "correct_answer": "Glucose is broken down with oxygen to release energy.",
                "rubric": "glucose oxygen energy",
                "explanation": "Glucose is oxidised.",
                "sources": [1],
            },
            {
                # Invalid: correct option is not among the options.
                "qtype": "mcq",
                "difficulty": "easy",
                "topic": "Bad",
                "prompt": "Broken question?",
                "options": ["A", "B"],
                "correct_answer": "Z",
                "explanation": "invalid",
                "sources": [1],
            },
        ]
    )


@pytest.mark.asyncio
async def test_assessment_generation_grading_and_mastery(fixed_embeddings):
    email = f"asm-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course_id = await _indexed_course(
                client, headers, "Photosynthesis converts light into glucose (6 carbons)."
            )
            user_id = await _user_id(email)

            async with SessionLocal() as db:
                assessment = await assessment_service.generate_assessment(
                    db,
                    user_id=user_id,
                    course_id=course_id,
                    title="Quiz 1",
                    question_count=5,
                    chat_provider=_ScriptedChat(_generation_payload()),
                )

            assert assessment.status == "ready"
            # The invalid MCQ is rejected; the duplicate is not generated.
            assert assessment.question_count == 3, assessment.generation_notes

            async with SessionLocal() as db:
                questions = await assessment_service.list_questions(db, assessment.id)
                by_type = {q.qtype: q for q in questions}
                assert set(by_type) == {"mcq", "numeric", "short"}
                assert by_type["short"].verified is False
                assert by_type["mcq"].verified is True
                assert by_type["mcq"].source_unit_ids

                attempt = await assessment_service.start_attempt(
                    db, user_id=user_id, assessment_id=assessment.id
                )
                assert attempt["status"] == "in_progress"
                assert all(
                    "correct_answer" not in q for q in attempt["questions"]
                ), "answer keys must not leak while an attempt is in progress"

                summary = await assessment_service.submit_attempt(
                    db,
                    user_id=user_id,
                    attempt_id=attempt["attempt_id"],
                    answers=[
                        {"question_id": by_type["mcq"].id, "answer": "Glucose"},
                        {"question_id": by_type["numeric"].id, "answer": "6"},
                        {
                            "question_id": by_type["short"].id,
                            "answer": "Light energy is stored as glucose by photosynthesis.",
                        },
                    ],
                )
            assert summary["status"] == "graded"
            assert summary["max_score"] == 3
            # MCQ + numeric are graded exactly (full marks); the short answer is
            # partial credit from the documented keyword-overlap heuristic.
            assert 2.0 <= summary["score"] < 3.0
            assert summary["topics"]["Photosynthesis"]["correct"] == 2

            async with SessionLocal() as db:
                detail = await assessment_service.get_attempt_detail(
                    db, user_id=user_id, attempt_id=attempt["attempt_id"]
                )
            short = next(q for q in detail["questions"] if q["qtype"] == "short")
            assert "heuristic" in (short["feedback"] or "").lower()
            assert short["verified"] is False

            # Duplicate submission is rejected.
            async with SessionLocal() as db:
                with pytest.raises(HTTPException) as exc:
                    await assessment_service.submit_attempt(
                        db,
                        user_id=user_id,
                        attempt_id=attempt["attempt_id"],
                        answers=[],
                    )
            assert exc.value.status_code == 409

            # Learner model now has evidence + recommendations.
            async with SessionLocal() as db:
                mastery = await learner_service.list_mastery(
                    db, user_id=user_id, course_id=course_id
                )
                topics = {m.topic for m in mastery}
                assert "Photosynthesis" in topics
                recs = await learner_service.generate_recommendations(
                    db, user_id=user_id, course_id=course_id
                )
                assert isinstance(recs, list)
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_weak_topic_requires_repeated_evidence(fixed_embeddings):
    email = f"wk-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course_id = await _indexed_course(
                client, headers, "Mitosis produces two identical daughter cells."
            )
            user_id = await _user_id(email)

            async with SessionLocal() as db:
                # A single wrong answer is not enough to declare a topic weak.
                await learner_service.record_evidence(
                    db, user_id=user_id, course_id=course_id, topic="Mitosis", correct=False
                )
                await db.commit()
                weak = await learner_service.weak_topics(
                    db, user_id=user_id, course_id=course_id
                )
                assert weak == []

                await learner_service.record_evidence(
                    db, user_id=user_id, course_id=course_id, topic="Mitosis", correct=False
                )
                await db.commit()
                weak = await learner_service.weak_topics(
                    db, user_id=user_id, course_id=course_id
                )
                assert [w.topic for w in weak] == ["Mitosis"]
    finally:
        await _cleanup(email)


# --------------------------------------------------------------------------- #
# Topics / prerequisites
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_topic_prerequisite_cycle_is_rejected():
    email = f"top-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)
            course = (
                await client.post(
                    "/api/courses/", json={"title": "Maths"}, headers=headers
                )
            ).json()
            user_id = await _user_id(email)

            async with SessionLocal() as db:
                a = await topic_service.create_topic(
                    db, user_id=user_id, course_id=course["id"], name="Algebra"
                )
                b = await topic_service.create_topic(
                    db, user_id=user_id, course_id=course["id"], name="Calculus"
                )
                await topic_service.set_prerequisite(
                    db,
                    user_id=user_id,
                    course_id=course["id"],
                    topic_id=b.id,
                    prerequisite_id=a.id,
                )
                with pytest.raises(HTTPException) as exc:
                    await topic_service.set_prerequisite(
                        db,
                        user_id=user_id,
                        course_id=course["id"],
                        topic_id=a.id,
                        prerequisite_id=b.id,
                    )
                assert exc.value.status_code == 400 or exc.value.status_code == 409
    finally:
        await _cleanup(email)


# --------------------------------------------------------------------------- #
# Providers + evaluation endpoints
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_providers_status_is_public_and_lists_dependencies():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/providers/status")
    assert response.status_code == 200
    body = response.json()
    names = {p["name"] for p in body["providers"]}
    assert {"database", "pgvector", "ollama", "ocr", "storage"} <= names
    assert body["status"] in {"ok", "degraded"}
    # Every provider entry carries an explicit status, never a fabricated value.
    assert all(p.get("status") for p in body["providers"])


@pytest.mark.asyncio
async def test_evaluation_endpoint_runs_and_persists(fixed_embeddings):
    email = f"eval-{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _make_user(client, email)

            unauth = await client.post("/api/evaluate", json={"store": False})
            assert unauth.status_code == 401

            run = await client.post(
                "/api/evaluate", json={"dataset": None, "store": True}, headers=headers
            )
            assert run.status_code == 200, run.text
            body = run.json()
            assert body["metrics"]["retrieval_hit_at_k"] == 1.0
            assert body["metrics"]["unsupported_detection"] == 1.0
            assert body["per_question"]

            latest = await client.get("/api/evaluate/latest", headers=headers)
            assert latest.status_code == 200
            assert latest.json()["dataset"] == body["dataset"]
    finally:
        await _cleanup(email)
