"""Learner model: per-topic mastery (Bayesian Knowledge Tracing) + recommendations.

Mastery is updated *only* from graded assessment responses. Parameters are
documented in ``docs/learner-model.md`` and are configurable; they are priors,
not values calibrated to an individual student.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

settings = get_settings()

MIN_EVIDENCE_FOR_WEAK = 2
STALE_AFTER_DAYS = 7


def bkt_update(
    p_known: float,
    correct: bool,
    *,
    p_learn: float | None = None,
    p_guess: float | None = None,
    p_slip: float | None = None,
) -> float:
    """One Bayesian Knowledge Tracing update step.

    Returns the posterior probability that the student has learned the topic
    after observing ``correct``, then applies the learning-transition rate.
    """
    p_learn = settings.bkt_learn_rate if p_learn is None else p_learn
    p_guess = settings.bkt_guess if p_guess is None else p_guess
    p_slip = settings.bkt_slip if p_slip is None else p_slip

    if correct:
        num = p_known * (1.0 - p_slip)
        den = num + (1.0 - p_known) * p_guess
    else:
        num = p_known * p_slip
        den = num + (1.0 - p_known) * (1.0 - p_guess)

    p_observed = num / den if den > 0 else p_known
    return p_observed + (1.0 - p_observed) * p_learn


async def record_evidence(
    db: AsyncSession,
    *,
    user_id: int,
    course_id: int,
    topic: str,
    correct: bool,
) -> None:
    from app.models.learner import TopicMastery

    topic = (topic or "General").strip()[:120] or "General"
    row = (
        await db.execute(
            select(TopicMastery).where(
                TopicMastery.user_id == user_id,
                TopicMastery.course_id == course_id,
                TopicMastery.topic == topic,
            )
        )
    ).scalar_one_or_none()

    if row is None:
        row = TopicMastery(
            user_id=user_id,
            course_id=course_id,
            topic=topic,
            mastery=settings.bkt_prior_learned,
            evidence_count=0,
            correct_count=0,
        )
        db.add(row)

    row.mastery = bkt_update(row.mastery, correct)
    row.evidence_count += 1
    row.correct_count = (row.correct_count or 0) + (1 if correct else 0)
    row.last_practiced_at = datetime.now(timezone.utc)
    await db.flush()


async def list_mastery(db: AsyncSession, *, user_id: int, course_id: int) -> list:
    from app.models.learner import TopicMastery

    rows = await db.execute(
        select(TopicMastery)
        .where(TopicMastery.user_id == user_id, TopicMastery.course_id == course_id)
        .order_by(TopicMastery.mastery.asc(), TopicMastery.topic.asc())
    )
    return list(rows.scalars().all())


async def weak_topics(db: AsyncSession, *, user_id: int, course_id: int) -> list:
    """Topics with enough evidence to be considered genuinely weak.

    An untested topic (no evidence) is deliberately excluded.
    """
    from app.models.learner import TopicMastery

    rows = await db.execute(
        select(TopicMastery)
        .where(
            TopicMastery.user_id == user_id,
            TopicMastery.course_id == course_id,
            TopicMastery.evidence_count >= MIN_EVIDENCE_FOR_WEAK,
            TopicMastery.mastery < settings.bkt_mastery_threshold,
        )
        .order_by(TopicMastery.mastery.asc())
    )
    return list(rows.scalars().all())


async def _course_topics(db: AsyncSession, *, user_id: int, course_id: int) -> set[str]:
    """Topics ever seen in this course's assessments for this user."""
    from app.models.assessment import Assessment, Question

    rows = await db.execute(
        select(Question.topic)
        .join(Assessment, Assessment.id == Question.assessment_id)
        .where(Assessment.user_id == user_id, Assessment.course_id == course_id)
        .distinct()
    )
    return {t for (t,) in rows.all() if t}


async def _latest_material_id(db: AsyncSession, *, course_id: int) -> int | None:
    from app.models.learning_material import LearningMaterial

    return (
        await db.execute(
            select(func.max(LearningMaterial.id)).where(
                LearningMaterial.course_id == course_id
            )
        )
    ).scalar_one_or_none()


async def generate_recommendations(
    db: AsyncSession, *, user_id: int, course_id: int
) -> list:
    """Rebuild this student's recommendations from real learner state."""
    from app.models.learner import Recommendation

    await db.execute(
        delete(Recommendation).where(
            Recommendation.user_id == user_id, Recommendation.course_id == course_id
        )
    )

    material_id = await _latest_material_id(db, course_id=course_id)
    now = datetime.now(timezone.utc)

    mastery_rows = await list_mastery(db, user_id=user_id, course_id=course_id)
    by_topic = {row.topic: row for row in mastery_rows}

    created: list[Recommendation] = []

    for row in mastery_rows:
        if row.evidence_count >= MIN_EVIDENCE_FOR_WEAK and (
            row.mastery < settings.bkt_mastery_threshold
        ):
            gap = settings.bkt_mastery_threshold - row.mastery
            priority = round(min(1.0, gap) * (1.0 + 0.1 * row.evidence_count), 4)
            created.append(
                Recommendation(
                    user_id=user_id,
                    course_id=course_id,
                    kind="weak_topic",
                    topic=row.topic,
                    reason=(
                        f"Mastery for “{row.topic}” is "
                        f"{row.mastery * 100:.0f}% across {row.evidence_count} "
                        "graded answers — below the target. Review and re-practice it."
                    ),
                    priority=priority,
                    material_id=material_id,
                )
            )
        elif row.evidence_count and row.last_practiced_at is not None:
            last = row.last_practiced_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if now - last > timedelta(days=STALE_AFTER_DAYS):
                created.append(
                    Recommendation(
                        user_id=user_id,
                        course_id=course_id,
                        kind="revision",
                        topic=row.topic,
                        reason=(
                            f"You last practised “{row.topic}” "
                            f"{(now - last).days} days ago. A short revision will "
                            "help retention."
                        ),
                        priority=0.4,
                        material_id=material_id,
                    )
                )

    for topic in sorted(await _course_topics(db, user_id=user_id, course_id=course_id)):
        if topic not in by_topic:
            created.append(
                Recommendation(
                    user_id=user_id,
                    course_id=course_id,
                    kind="diagnostic",
                    topic=topic,
                    reason=(
                        f"You've been assessed on “{topic}” but have no graded "
                        "evidence yet. Take a short quiz to establish your level."
                    ),
                    priority=0.5,
                    material_id=material_id,
                )
            )

    created.sort(key=lambda r: r.priority, reverse=True)
    for item in created:
        db.add(item)
    await db.commit()
    return created


async def strong_topics(db: AsyncSession, *, user_id: int, course_id: int) -> list:
    from app.models.learner import TopicMastery

    rows = await db.execute(
        select(TopicMastery)
        .where(
            TopicMastery.user_id == user_id,
            TopicMastery.course_id == course_id,
            TopicMastery.evidence_count >= MIN_EVIDENCE_FOR_WEAK,
            TopicMastery.mastery >= settings.bkt_mastery_threshold,
        )
        .order_by(TopicMastery.mastery.desc())
    )
    return list(rows.scalars().all())


def already_tested(topic: str, mastery_rows: list) -> bool:
    """Utility: whether a topic already has any recorded evidence."""
    return any(
        getattr(row, "topic", None) == topic and getattr(row, "evidence_count", 0) > 0
        for row in mastery_rows
    )


async def untested_topics(db: AsyncSession, *, user_id: int, course_id: int) -> list[str]:
    topics = await _course_topics(db, user_id=user_id, course_id=course_id)
    rows = await list_mastery(db, user_id=user_id, course_id=course_id)
    tested = {r.topic for r in rows if r.evidence_count > 0}
    return sorted(topics - tested)
