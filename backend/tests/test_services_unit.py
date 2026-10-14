"""Unit tests for pure logic (no database, network or model downloads)."""

import pytest

from app.models.assessment import Question
from app.ingestion import chunking
from app.services import evaluation, learner, retrieval, topics
from app.services.assessments import (
    _extract_json_array,
    _validate_question,
    fingerprint,
    grade_question,
    parse_number,
)


def test_chunking_respects_size_and_overlap():
    text = "sentence. " * 400
    chunks = chunking.chunk_text(text, size=200, overlap=40)
    assert len(chunks) > 1
    assert all(len(c) <= 260 for c in chunks)


def test_bkt_update_increases_on_correct_and_decreases_on_wrong():
    up = learner.bkt_update(0.3, True)
    down = learner.bkt_update(0.3, False)
    assert up > 0.3
    assert down < up
    assert 0.0 <= down <= 1.0


def test_parse_number_handles_floats_fractions_and_garbage():
    assert parse_number("42") == 42.0
    assert parse_number("0.5") == 0.5
    assert abs(parse_number("1/4") - 0.25) < 1e-9
    assert parse_number("banana") is None


def test_extract_json_array_handles_fences_and_prose():
    assert _extract_json_array('[{"a": 1}]') == [{"a": 1}]
    assert _extract_json_array('```json\n[{"b": 2}]\n```') == [{"b": 2}]
    assert _extract_json_array("no json here") == []


def test_fingerprint_is_stable_and_option_order_independent():
    a = fingerprint("mcq", "What is X?", ["A", "B"])
    b = fingerprint("mcq", "what is   x?", ["B", "A"])
    assert a == b
    assert a != fingerprint("short", "What is X?", None)


def test_validate_question_accepts_and_rejects_correctly():
    good_mcq = {
        "qtype": "mcq",
        "prompt": "Which gas do plants release?",
        "options": ["Oxygen", "Nitrogen", "Helium"],
        "correct_answer": "oxygen",
        "explanation": "Photosynthesis releases oxygen.",
        "topic": "Photosynthesis",
        "sources": [1],
    }
    valid, _ = _validate_question(good_mcq, [101])
    assert valid is not None
    assert valid["correct_answer"] == "Oxygen"
    assert valid["source_unit_ids"] == [101]
    assert valid["verified"] is True

    bad_key = dict(good_mcq, correct_answer="Argon")
    rejected, reason = _validate_question(bad_key, [101])
    assert rejected is None
    assert "option" in reason.lower() or "among" in reason.lower()

    short = {
        "qtype": "short",
        "prompt": "Explain photosynthesis.",
        "correct_answer": "Plants convert light to glucose.",
        "rubric": "light, glucose, oxygen",
        "explanation": "See source.",
        "sources": [1],
    }
    valid_short, _ = _validate_question(short, [101])
    assert valid_short is not None
    assert valid_short["verified"] is False


def _q(**kwargs) -> Question:
    base = dict(
        qtype="mcq",
        prompt="p",
        explanation="e",
        topic="t",
        difficulty="medium",
        correct_answer="B",
        options=["A", "B", "C"],
        fingerprint="f",
        verified=True,
    )
    base.update(kwargs)
    return Question(**base)


def test_grade_mcq_and_numeric_deterministically():
    correct, score, _ = grade_question(_q(), "b")
    assert correct is True and score == 1.0

    wrong, score, _ = grade_question(_q(), "A")
    assert wrong is False and score == 0.0

    numeric = _q(qtype="numeric", correct_answer="9.8", options=None)
    ok, score, _ = grade_question(numeric, "9.80")
    assert ok is True and score == 1.0
    bad, _, _ = grade_question(numeric, "5")
    assert bad is False


def test_grade_short_uses_documented_overlap_heuristic():
    short = _q(
        qtype="short",
        correct_answer="light energy converted to chemical energy in glucose",
        rubric="light chemical glucose",
        options=None,
    )
    correct, score, feedback = grade_question(
        short, "Light energy is converted into chemical energy stored as glucose."
    )
    assert correct is True
    assert score > 0
    assert "heuristic" in feedback.lower()


def test_build_context_fences_sources_and_respects_budget():
    chunks = [
        retrieval.RetrievedChunk(
            content_unit_id=i,
            material_id=1,
            material_title="notes.txt",
            material_type="text",
            content="Body " * 20,
            page_number=i,
            slide_number=None,
            start_timestamp=None,
            end_timestamp=None,
            score=0.9,
        )
        for i in (1, 2, 3)
    ]
    context = retrieval.build_context(chunks, max_chars=400)
    assert "<source" in context
    assert "</source>" in context
    assert len(context) <= 400


def test_run_evaluation_metrics_are_in_range():
    result = evaluation.run_evaluation()
    assert set(result.metrics) >= {
        "retrieval_hit_at_k",
        "context_precision",
        "context_recall",
        "citation_correctness",
        "unsupported_detection",
    }
    for key, value in result.metrics.items():
        assert 0.0 <= float(value) <= 1.0 or key.startswith("learner_")


def test_unsupported_questions_are_not_retrieved_as_support():
    dataset = evaluation.load_dataset()
    unsupported = [q for q in dataset["questions"] if not q.get("answerable", True)]
    assert unsupported, "dataset must contain unsupported questions"
    result = evaluation.run_evaluation()
    assert result.metrics["unsupported_detection"] == 1.0


def test_simulate_profiles_mastery_tracks_accuracy():
    profiles = evaluation.simulate_profiles({"low": 0.0, "high": 1.0}, steps=6)
    low = next(p for p in profiles if p["profile"] == "low")
    high = next(p for p in profiles if p["profile"] == "high")
    assert high["mastery_end"] > low["mastery_end"]


def test_learner_simulation_is_reproducible():
    first = evaluation.run_learner_simulation()
    second = evaluation.run_learner_simulation()
    assert first == second
    assert len(first) == 3


def test_topic_heuristic_candidates_rank_by_frequency():
    texts = [
        "Newton First Law applies. Newton Second Law applies.",
        "Newton First Law again. Kinetic Energy is useful.",
    ]
    candidates = topics.heuristic_candidates(texts)
    assert any("Newton" in c for c in candidates)


@pytest.mark.asyncio
async def test_provider_health_aggregates_statuses(monkeypatch):
    """`check_database` reports "connected"; the aggregate must treat that as
    healthy and only flag genuinely degraded dependencies."""
    from app.services import providers

    async def fake_db():
        return {"status": "connected", "latency_ms": 1.0}

    async def fake_pgvector():
        return {"name": "pgvector", "status": "unavailable", "detail": "missing"}

    async def fake_ollama():
        return {"name": "ollama", "status": "ok", "detail": "local"}

    monkeypatch.setattr(providers, "check_database", fake_db)
    monkeypatch.setattr(providers, "_pgvector_status", fake_pgvector)
    monkeypatch.setattr(providers, "_ollama_status", fake_ollama)
    monkeypatch.setattr(
        providers, "check_ocr", lambda: {"name": "ocr", "status": "ok", "detail": ""}
    )
    monkeypatch.setattr(
        providers,
        "check_office",
        lambda: {"name": "office", "status": "ok", "detail": ""},
    )
    monkeypatch.setattr(
        providers,
        "check_storage",
        lambda: {"name": "storage", "status": "ok", "detail": ""},
    )

    result = await providers.check_providers()
    assert result["status"] == "degraded"
    assert result["degraded"] == ["pgvector"]
    database = next(p for p in result["providers"] if p["name"] == "database")
    assert database["status"] == "ok"
