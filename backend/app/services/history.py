"""Study history: a real activity feed derived from existing rows.

There is deliberately **no new table** here. Every event is a real row from
conversations, assessments/attempts, learning materials or topic mastery, and
each one carries a deep link back to the actual object. Nothing is synthesised
and no streak/score is invented.

Scoping:

* ``conversations`` and ``attempts`` and ``topic_mastery`` carry ``user_id``.
* ``learning_materials`` does not, so its rows are reached through the owning
  ``courses.user_id`` join — a user can never see another user's uploads.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment, Attempt
from app.models.conversation import Conversation
from app.models.course import Course
from app.models.learning_material import LearningMaterial
from app.models.learner import TopicMastery

ALL_KINDS = ("tutor", "assessment", "upload", "mastery")
# Bound how much we pull before merging/sorting so a huge account cannot make
# one page request scan everything.
_MAX_FETCH = 200


def _sort_key(event: dict) -> datetime:
    """Normalise to an aware datetime so aware/naive rows can be compared."""
    dt = event["at"]
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _count_scalar(db: AsyncSession, stmt) -> int:
    return int((await db.execute(stmt)).scalar_one() or 0)


async def _count_tutor(db: AsyncSession, user_id: int, course_id: int | None) -> int:
    stmt = select(func.count()).select_from(Conversation).where(
        Conversation.user_id == user_id
    )
    if course_id is not None:
        stmt = stmt.where(Conversation.course_id == course_id)
    return await _count_scalar(db, stmt)


async def _count_assessment(db: AsyncSession, user_id: int, course_id: int | None) -> int:
    stmt = (
        select(func.count())
        .select_from(Attempt)
        .join(Assessment, Assessment.id == Attempt.assessment_id)
        .where(Attempt.user_id == user_id)
    )
    if course_id is not None:
        stmt = stmt.where(Assessment.course_id == course_id)
    return await _count_scalar(db, stmt)


async def _count_upload(db: AsyncSession, user_id: int, course_id: int | None) -> int:
    stmt = (
        select(func.count())
        .select_from(LearningMaterial)
        .join(Course, Course.id == LearningMaterial.course_id)
        .where(Course.user_id == user_id)
    )
    if course_id is not None:
        stmt = stmt.where(LearningMaterial.course_id == course_id)
    return await _count_scalar(db, stmt)


async def _count_mastery(db: AsyncSession, user_id: int, course_id: int | None) -> int:
    stmt = (
        select(func.count())
        .select_from(TopicMastery)
        .where(
            TopicMastery.user_id == user_id,
            TopicMastery.last_practiced_at.is_not(None),
        )
    )
    if course_id is not None:
        stmt = stmt.where(TopicMastery.course_id == course_id)
    return await _count_scalar(db, stmt)


async def _tutor_events(db, user_id, course_id, fetch) -> list[dict]:
    stmt = (
        select(
            Conversation.id,
            Conversation.title,
            Conversation.course_id,
            Conversation.updated_at,
            Course.title,
        )
        .join(Course, Course.id == Conversation.course_id)
        .where(Conversation.user_id == user_id)
    )
    if course_id is not None:
        stmt = stmt.where(Conversation.course_id == course_id)
    rows = (
        await db.execute(stmt.order_by(Conversation.updated_at.desc()).limit(fetch))
    ).all()
    return [
        {
            "kind": "tutor",
            "id": f"tutor-{row[0]}",
            "title": row[1],
            "detail": "Tutor conversation",
            "course_id": row[2],
            "course_title": row[4],
            "status": None,
            "score": None,
            "max_score": None,
            "href": f"tutor.html?conversation={row[0]}",
            "at": row[3],
        }
        for row in rows
    ]


async def _assessment_events(db, user_id, course_id, fetch) -> list[dict]:
    stmt = (
        select(
            Attempt.id,
            Attempt.status,
            Attempt.score,
            Attempt.max_score,
            Attempt.started_at,
            Attempt.submitted_at,
            Assessment.title,
            Assessment.course_id,
            Course.title,
        )
        .join(Assessment, Assessment.id == Attempt.assessment_id)
        .join(Course, Course.id == Assessment.course_id)
        .where(Attempt.user_id == user_id)
    )
    if course_id is not None:
        stmt = stmt.where(Assessment.course_id == course_id)
    rows = (
        await db.execute(
            stmt.order_by(
                func.coalesce(Attempt.submitted_at, Attempt.started_at).desc()
            ).limit(fetch)
        )
    ).all()

    events: list[dict] = []
    for row in rows:
        at = row[5] or row[4]
        if at is None:
            continue
        events.append(
            {
                "kind": "assessment",
                "id": f"assessment-{row[0]}",
                "title": row[6],
                "detail": "Submitted attempt" if row[5] else "Attempt in progress",
                "course_id": row[7],
                "course_title": row[8],
                "status": row[1],
                "score": row[2],
                "max_score": row[3],
                "href": f"results.html?attempt={row[0]}",
                "at": at,
            }
        )
    return events


async def _upload_events(db, user_id, course_id, fetch) -> list[dict]:
    stmt = (
        select(
            LearningMaterial.id,
            LearningMaterial.original_filename,
            LearningMaterial.processing_status,
            LearningMaterial.created_at,
            LearningMaterial.course_id,
            Course.title,
        )
        .join(Course, Course.id == LearningMaterial.course_id)
        .where(Course.user_id == user_id)
    )
    if course_id is not None:
        stmt = stmt.where(LearningMaterial.course_id == course_id)
    rows = (
        await db.execute(
            stmt.order_by(LearningMaterial.created_at.desc()).limit(fetch)
        )
    ).all()
    return [
        {
            "kind": "upload",
            "id": f"upload-{row[0]}",
            "title": row[1],
            "detail": "Material uploaded",
            "course_id": row[4],
            "course_title": row[5],
            "status": row[2],
            "score": None,
            "max_score": None,
            "href": f"course.html?id={row[4]}",
            "at": row[3],
        }
        for row in rows
    ]


async def _mastery_events(db, user_id, course_id, fetch) -> list[dict]:
    stmt = (
        select(
            TopicMastery.id,
            TopicMastery.topic,
            TopicMastery.mastery,
            TopicMastery.evidence_count,
            TopicMastery.last_practiced_at,
            TopicMastery.course_id,
            Course.title,
        )
        .join(Course, Course.id == TopicMastery.course_id)
        .where(
            TopicMastery.user_id == user_id,
            TopicMastery.last_practiced_at.is_not(None),
        )
    )
    if course_id is not None:
        stmt = stmt.where(TopicMastery.course_id == course_id)
    rows = (
        await db.execute(
            stmt.order_by(TopicMastery.last_practiced_at.desc()).limit(fetch)
        )
    ).all()
    return [
        {
            "kind": "mastery",
            "id": f"mastery-{row[0]}",
            "title": row[1],
            "detail": (
                "Mastery " + str(round(row[2] * 100)) + "% from "
                + str(row[3]) + " graded answer(s)"
            ),
            "course_id": row[5],
            "course_title": row[6],
            "status": None,
            "score": row[2],
            "max_score": 1.0,
            "href": "progress.html",
            "at": row[4],
        }
        for row in rows
    ]


_BUILDERS = {
    "tutor": _tutor_events,
    "assessment": _assessment_events,
    "upload": _upload_events,
    "mastery": _mastery_events,
}

_COUNTERS = {
    "tutor": _count_tutor,
    "assessment": _count_assessment,
    "upload": _count_upload,
    "mastery": _count_mastery,
}


async def build_history(
    db: AsyncSession,
    *,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    kind: str | None = None,
    course_id: int | None = None,
) -> dict:
    """Return one page of the user's real study history, newest first."""
    kinds = [kind] if kind in _BUILDERS else list(ALL_KINDS)
    fetch = min(offset + limit + 1, _MAX_FETCH)

    events: list[dict] = []
    for name in kinds:
        events.extend(await _BUILDERS[name](db, user_id, course_id, fetch))

    events.sort(key=_sort_key, reverse=True)
    total = 0
    for name in kinds:
        total += await _COUNTERS[name](db, user_id, course_id)

    page = events[offset : offset + limit]
    return {
        "events": page,
        "total": total,
        "has_more": total > offset + len(page),
        "kinds": list(ALL_KINDS),
    }
