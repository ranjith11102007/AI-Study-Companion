"""Assessment engine: generation, verification, grading and feedback.

Question types are graded deterministically where possible:

* ``mcq``     — exact (normalised) option match.
* ``numeric`` — parsed and compared within a tolerance.
* ``short``   — rubric keyword-overlap, explicitly flagged as a heuristic and
  marked ``verified = False`` so it is never presented as machine-verified.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ollama import get_chat_provider
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.assessment import Assessment, Attempt, Question, Response
from app.models.content_unit import ContentUnit
from app.models.course import Course
from app.models.learning_material import LearningMaterial
from app.services import learner as learner_service

logger = get_logger(__name__)
settings = get_settings()

VALID_QTYPES = {"mcq", "short", "numeric"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
MIN_SHORT_OVERLAP = 0.4

GENERATION_PROMPT = """You write exam questions for a study app. Create {count} questions
strictly from the reference sources in the user message.

Return ONLY a JSON array. Do not add prose or markdown fences. Each element:
{{
  "qtype": "mcq" | "short" | "numeric",
  "difficulty": "{difficulty}",
  "topic": "short human-readable topic label",
  "concept": "the specific concept tested",
  "prompt": "the question text",
  "options": ["option A", "option B", "option C"],
  "correct_answer": "exact text of the correct option (mcq) OR the number (numeric) OR a model answer (short)",
  "rubric": "grading rubric with the key points",
  "explanation": "why the answer is correct, grounded in the sources",
  "sources": [1, 2]
}}

Rules:
- Every question must be fully answerable from the sources. Never invent facts.
- mcq must have exactly one correct option and it must be one of the options.
- numeric correct_answer must be a bare number.
- Prefer a mix of mcq and short. Use numeric only when the sources state a quantity.
"""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _extract_json_array(text: str) -> list:
    text = (text or "").strip()
    if not text:
        return []
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _normalize(value: str) -> str:
    value = (value or "").lower().strip()
    value = re.sub(r"[^\w\s/.\-]", "", value)
    return re.sub(r"\s+", " ", value)


def _keywords(text: str) -> set[str]:
    return {
        tok
        for tok in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(tok) > 3
    }


def parse_number(value: str) -> float | None:
    value = (value or "").strip().replace(",", "")
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    frac = re.fullmatch(r"(-?\d+)\s*/\s*(\d+)", value)
    if frac and float(frac.group(2)) != 0:
        return float(frac.group(1)) / float(frac.group(2))
    return None


def fingerprint(qtype: str, prompt: str, options: list | None) -> str:
    raw = (
        qtype
        + "|"
        + _normalize(prompt)
        + "|"
        + "|".join(sorted(_normalize(o) for o in (options or [])))
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _gather_sources(
    db: AsyncSession, course_id: int, max_chars: int
) -> tuple[str, list[int]]:
    rows = (
        await db.execute(
            select(ContentUnit, LearningMaterial.original_filename)
            .join(LearningMaterial, LearningMaterial.id == ContentUnit.material_id)
            .where(ContentUnit.course_id == course_id)
            .order_by(ContentUnit.id.asc())
            .limit(40)
        )
    ).all()

    parts: list[str] = []
    ids: list[int] = []
    used = 0
    for unit, material_title in rows:
        if unit.page_number is not None:
            location = f"page {unit.page_number}"
        elif unit.slide_number is not None:
            location = f"slide {unit.slide_number}"
        else:
            location = "excerpt"
        block = (
            f'<source id="{len(ids) + 1}" material="{material_title}" '
            f'location="{location}">\n{unit.content.strip()}\n</source>'
        )
        if used + len(block) > max_chars:
            break
        parts.append(block)
        ids.append(unit.id)
        used += len(block)
    return "\n\n".join(parts), ids


def _validate_question(raw: dict, source_ids: list[int]) -> tuple[dict | None, str]:
    if not isinstance(raw, dict):
        return None, "not an object"

    qtype = str(raw.get("qtype", "")).lower().strip()
    if qtype not in VALID_QTYPES:
        return None, f"unsupported qtype {qtype!r}"

    prompt = str(raw.get("prompt", "")).strip()
    correct = str(raw.get("correct_answer", "")).strip()
    explanation = str(raw.get("explanation", "")).strip()
    if not prompt or not correct or not explanation:
        return None, "missing prompt/correct_answer/explanation"

    difficulty = str(raw.get("difficulty", "medium")).lower().strip()
    if difficulty not in VALID_DIFFICULTIES:
        difficulty = "medium"

    options = raw.get("options")
    verified = True
    notes = ""

    if qtype == "mcq":
        if not isinstance(options, list):
            return None, "mcq needs an options list"
        options = [str(o).strip() for o in options if str(o).strip()]
        if not 2 <= len(options) <= 6:
            return None, "mcq needs 2-6 options"
        normalized = [_normalize(o) for o in options]
        if len(set(normalized)) != len(normalized):
            return None, "duplicate mcq options"
        if _normalize(correct) not in normalized:
            return None, "correct option not among options"
        correct = options[normalized.index(_normalize(correct))]
        notes = "MCQ option set validated; answer key matches exactly one option."
    else:
        options = None
        if qtype == "numeric":
            if parse_number(correct) is None:
                return None, "numeric answer is not a number"
            notes = (
                "Numeric answer parsed; graded within "
                f"{settings.assessment_numeric_tolerance:.0%} tolerance."
            )
        elif qtype == "short":
            if not str(raw.get("rubric", "")).strip():
                return None, "short answer requires a rubric"
            verified = False
            notes = (
                "Short answer: not machine-verified. Auto-grading uses rubric "
                "keyword overlap (heuristic) — review recommended."
            )

    source_refs = raw.get("sources") or raw.get("source_unit_ids") or []
    resolved: list[int] = []
    if isinstance(source_refs, list):
        for ref in source_refs:
            if isinstance(ref, int) and 1 <= ref <= len(source_ids):
                resolved.append(source_ids[ref - 1])
    if not resolved and source_ids:
        resolved = [source_ids[0]]
        notes = (notes + " Defaulted to the first source.").strip()
    if not resolved:
        return None, "no resolvable source reference"

    return (
        {
            "qtype": qtype,
            "difficulty": difficulty,
            "topic": (str(raw.get("topic", "General")).strip() or "General")[:120],
            "concept": (str(raw.get("concept", "")).strip() or None),
            "prompt": prompt,
            "options": options,
            "correct_answer": correct,
            "rubric": (str(raw.get("rubric", "")).strip() or None),
            "explanation": explanation,
            "source_unit_ids": resolved,
            "verified": verified,
            "verification_notes": notes or None,
            "fingerprint": fingerprint(qtype, prompt, options),
        },
        "",
    )


async def _existing_fingerprints(db: AsyncSession, course_id: int) -> set[str]:
    rows = await db.execute(
        select(Question.fingerprint)
        .join(Assessment, Assessment.id == Question.assessment_id)
        .where(Assessment.course_id == course_id)
    )
    return {fp for (fp,) in rows.all()}


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
async def generate_assessment(
    db: AsyncSession,
    *,
    user_id: int,
    course_id: int,
    title: str,
    question_count: int,
    difficulty: str = "medium",
    time_limit_minutes: int | None = None,
    chat_provider=None,
) -> Assessment:
    course = (
        await db.execute(
            select(Course).where(Course.id == course_id, Course.user_id == user_id)
        )
    ).scalar_one_or_none()
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    question_count = max(1, min(question_count, settings.assessment_max_questions))
    if difficulty not in VALID_DIFFICULTIES:
        difficulty = "medium"

    context, source_ids = await _gather_sources(
        db, course_id, settings.tutor_max_context_chars
    )
    if not context:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No indexed content for this course. Upload and index material first.",
        )

    provider = chat_provider or get_chat_provider()
    try:
        raw = await provider.chat(
            [
                {
                    "role": "system",
                    "content": GENERATION_PROMPT.format(
                        count=question_count, difficulty=difficulty
                    ),
                },
                {
                    "role": "user",
                    "content": f"Course: {course.title}\n\nReference sources:\n{context}",
                },
            ],
            temperature=settings.tutor_temperature,
            max_tokens=settings.tutor_max_tokens,
        )
    except Exception as exc:  # noqa: BLE001 - surface a clear, actionable error
        logger.error("Assessment generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The local AI model is unavailable. Make sure Ollama is running "
                "and the configured chat model is pulled."
            ),
        ) from exc

    parsed = _extract_json_array(raw)
    existing = await _existing_fingerprints(db, course_id)
    seen = set(existing)
    validated: list[dict] = []
    rejected: list[str] = []

    for candidate in parsed:
        question, error = _validate_question(candidate, source_ids)
        if question is None:
            rejected.append(error)
            continue
        if question["fingerprint"] in seen:
            rejected.append("duplicate of an existing question")
            continue
        seen.add(question["fingerprint"])
        validated.append(question)
        if len(validated) >= question_count:
            break

    if not validated:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "The model did not produce any verifiable questions. Try again, "
                "or add more indexed material for this course."
            ),
        )

    assessment = Assessment(
        course_id=course_id,
        user_id=user_id,
        title=(title or "Practice assessment").strip()[:200],
        difficulty=difficulty,
        status="ready",
        question_count=len(validated),
        time_limit_minutes=time_limit_minutes,
        generation_notes=(
            f"Generated {len(validated)} verified questions from "
            f"{len(source_ids)} source chunks "
            f"({len(rejected)} candidate(s) rejected)."
        ),
    )
    db.add(assessment)
    await db.flush()

    for q in validated:
        db.add(Question(assessment_id=assessment.id, **q))
    await db.commit()
    await db.refresh(assessment)
    return assessment


# --------------------------------------------------------------------------- #
# Read / delete
# --------------------------------------------------------------------------- #
async def get_owned_assessment(
    db: AsyncSession, *, user_id: int, assessment_id: int
) -> Assessment:
    assessment = (
        await db.execute(
            select(Assessment).where(
                Assessment.id == assessment_id, Assessment.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )
    return assessment


async def list_assessments(
    db: AsyncSession, *, user_id: int, course_id: int
) -> list[Assessment]:
    rows = await db.execute(
        select(Assessment)
        .where(Assessment.user_id == user_id, Assessment.course_id == course_id)
        .order_by(Assessment.created_at.desc(), Assessment.id.desc())
    )
    return list(rows.scalars().all())


async def list_questions(db: AsyncSession, assessment_id: int) -> list[Question]:
    rows = await db.execute(
        select(Question)
        .where(Question.assessment_id == assessment_id)
        .order_by(Question.id.asc())
    )
    return list(rows.scalars().all())


async def delete_assessment(
    db: AsyncSession, *, user_id: int, assessment_id: int
) -> None:
    assessment = await get_assessment(db, user_id=user_id, assessment_id=assessment_id)
    await db.delete(assessment)
    await db.commit()


async def get_assessment(db: AsyncSession, *, user_id: int, assessment_id: int):
    return await get_owned_assessment(
        db, user_id=user_id, assessment_id=assessment_id
    )


def public_question(question: Question) -> dict:
    """Question shape used while an attempt is still in progress (no answer key)."""
    return {
        "id": question.id,
        "qtype": question.qtype,
        "difficulty": question.difficulty,
        "topic": question.topic,
        "concept": question.concept,
        "prompt": question.prompt,
        "options": question.options,
    }


# --------------------------------------------------------------------------- #
# Grading
# --------------------------------------------------------------------------- #
def grade_question(question: Question, answer: str) -> tuple[bool | None, float, str]:
    answer = (answer or "").strip()

    if question.qtype == "mcq":
        correct = _normalize(answer) == _normalize(question.correct_answer)
        feedback = (
            "Correct." if correct else f"Incorrect. Correct answer: {question.correct_answer}"
        )
        return correct, 1.0 if correct else 0.0, feedback

    if question.qtype == "numeric":
        given = parse_number(answer)
        expected = parse_number(question.correct_answer)
        if given is None or expected is None:
            return None, 0.0, "Answer was not a valid number."
        tol = max(abs(expected) * settings.assessment_numeric_tolerance, 1e-6)
        correct = abs(given - expected) <= tol
        feedback = (
            "Correct."
            if correct
            else f"Incorrect. Expected {question.correct_answer} (±{tol:g})."
        )
        return correct, 1.0 if correct else 0.0, feedback

    # short answer — transparent keyword-overlap heuristic
    reference = " ".join(filter(None, [question.correct_answer, question.rubric]))
    ref_tokens = _keywords(reference)
    if not ref_tokens:
        return None, 0.0, "No rubric keywords available; manual review required."
    overlap = len(ref_tokens & _keywords(answer)) / len(ref_tokens)
    correct = overlap >= MIN_SHORT_OVERLAP
    feedback = (
        f"Auto-graded by keyword overlap ({overlap:.0%} of rubric points matched). "
        "This is a heuristic — review the rubric for full credit."
    )
    return correct, round(overlap, 3), feedback


async def start_attempt(
    db: AsyncSession, *, user_id: int, assessment_id: int
) -> dict:
    assessment = await get_owned_assessment(
        db, user_id=user_id, assessment_id=assessment_id
    )
    questions = await list_questions(db, assessment.id)
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This assessment has no questions.",
        )
    attempt = Attempt(
        assessment_id=assessment.id, user_id=user_id, status="in_progress"
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return {
        "attempt_id": attempt.id,
        "assessment_id": assessment.id,
        "status": attempt.status,
        "questions": [public_question(q) for q in questions],
    }


async def submit_attempt(
    db: AsyncSession,
    *,
    user_id: int,
    attempt_id: int,
    answers: list[dict],
) -> dict:
    attempt = (
        await db.execute(
            select(Attempt).where(
                Attempt.id == attempt_id, Attempt.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found"
        )
    if attempt.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This attempt has already been submitted.",
        )

    questions = {q.id: q for q in await list_questions(db, attempt.assessment_id)}
    course_id = await _assessment_course(db, attempt.assessment_id)
    answers_by_id = {
        int(item.get("question_id")): str(item.get("answer", ""))
        for item in answers
        if item.get("question_id") is not None
    }

    score = 0.0
    max_score = float(len(questions))
    topic_stats: dict[str, dict] = {}

    for qid, question in questions.items():
        answer = answers_by_id.get(qid, "")
        is_correct, points, feedback = grade_question(question, answer)
        score += points
        db.add(
            Response(
                attempt_id=attempt.id,
                question_id=qid,
                answer=answer,
                is_correct=is_correct,
                score=points,
                feedback=feedback,
            )
        )
        stats = topic_stats.setdefault(question.topic, {"correct": 0, "total": 0})
        stats["total"] += 1
        if is_correct:
            stats["correct"] += 1
        if is_correct is not None:
            await learner_service.record_evidence(
                db,
                user_id=user_id,
                course_id=course_id,
                topic=question.topic,
                correct=bool(is_correct),
            )

    attempt.status = "graded"
    attempt.score = round(score, 3)
    attempt.max_score = max_score
    attempt.submitted_at = datetime.now(timezone.utc)
    await db.flush()

    await learner_service.generate_recommendations(
        db, user_id=user_id, course_id=course_id
    )
    await db.commit()

    return {
        "attempt_id": attempt.id,
        "assessment_id": attempt.assessment_id,
        "status": attempt.status,
        "score": attempt.score,
        "max_score": attempt.max_score,
        "percent": round((score / max_score * 100) if max_score else 0.0, 1),
        "topics": topic_stats,
    }


async def _assessment_course(db: AsyncSession, assessment_id: int) -> int:
    assessment = await db.get(Assessment, assessment_id)
    return assessment.course_id if assessment else 0


async def get_attempt_detail(
    db: AsyncSession, *, user_id: int, attempt_id: int
) -> dict:
    attempt = (
        await db.execute(
            select(Attempt).where(
                Attempt.id == attempt_id, Attempt.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found"
        )

    questions = {q.id: q for q in await list_questions(db, attempt.assessment_id)}
    rows = await db.execute(
        select(Response).where(Response.attempt_id == attempt.id)
    )
    responses = {r.question_id: r for r in rows.scalars().all()}

    if attempt.status == "in_progress":
        return {
            "attempt_id": attempt.id,
            "assessment_id": attempt.assessment_id,
            "status": attempt.status,
            "questions": [public_question(q) for q in questions.values()],
        }

    items = []
    for qid, question in questions.items():
        response = responses.get(qid)
        items.append(
            {
                **public_question(question),
                "correct_answer": question.correct_answer,
                "explanation": question.explanation,
                "rubric": question.rubric,
                "source_unit_ids": question.source_unit_ids,
                "verified": question.verified,
                "verification_notes": question.verification_notes,
                "answer": response.answer if response else "",
                "is_correct": response.is_correct if response else None,
                "score": response.score if response else None,
                "feedback": response.feedback if response else None,
            }
        )

    return {
        "attempt_id": attempt.id,
        "assessment_id": attempt.assessment_id,
        "status": attempt.status,
        "score": attempt.score,
        "max_score": attempt.max_score,
        "percent": round(
            (attempt.score / attempt.max_score * 100)
            if attempt.score is not None and attempt.max_score
            else 0.0,
            1,
        ),
        "questions": items,
    }
