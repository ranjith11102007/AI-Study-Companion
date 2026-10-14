"""Course topic extraction (heuristic) and knowledge-graph editable links.

Topic suggestions are a transparent frequency heuristic over the course's
indexed text; they are presented as *candidates* that a student can accept,
rename or delete, never as verified facts.
"""

from __future__ import annotations

import re
from collections import Counter

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_unit import ContentUnit
from app.models.course import Course
from app.models.topic import ContentUnitTopic, Topic

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "you",
    "are", "was", "were", "have", "has", "had", "not", "but", "can", "will",
    "which", "their", "there", "these", "those", "then", "than", "they", "them",
    "their", "when", "where", "what", "when", "will", "would", "should", "could",
    "also", "such", "more", "most", "some", "such", "than", "then", "then",
    "about", "above", "after", "again", "also", "because", "been", "before",
    "being", "between", "both", "each", "each", "each", "each", "each", "other",
    "other", "such", "over", "such", "than", "then", "these", "they", "this",
    "those", "through", "under", "using", "very", "what", "when", "where",
    "which", "while", "who", "will", "with", "would", "used", "used", "used",
}


async def _owned_course(db: AsyncSession, course_id: int, user_id: int) -> Course:
    course = (
        await db.execute(
            select(Course).where(Course.id == course_id, Course.user_id == user_id)
        )
    ).scalar_one_or_none()
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )
    return course


async def list_topics(db: AsyncSession, *, user_id: int, course_id: int) -> list[dict]:
    await _owned_course(db, user_id=user_id, course_id=course_id)
    counts = dict(
        (
            await db.execute(
                select(ContentUnitTopic.topic_id, func.count())
                .join(Topic, Topic.id == ContentUnitTopic.topic_id)
                .where(Topic.course_id == course_id)
                .group_by(ContentUnitTopic.topic_id)
            )
        ).all()
    )
    rows = await db.execute(
        select(Topic).where(Topic.course_id == course_id).order_by(Topic.name.asc())
    )
    topics = list(rows.scalars().all())
    names = {t.id: t.name for t in topics}
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "parent_id": t.parent_topic_id,
            "prerequisite_of": t.parent_topic_id,
            "parent_name": names.get(t.parent_topic_id),
            "source_count": counts.get(t.id, 0),
        }
        for t in topics
    ]


async def create_topic(
    db: AsyncSession,
    *,
    user_id: int,
    course_id: int,
    name: str,
    description: str | None = None,
    parent_id: int | None = None,
) -> Topic:
    await _owned_course(db, user_id=user_id, course_id=course_id)
    name = (name or "").strip()[:120]
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Topic name is required."
        )
    if parent_id is not None:
        parent = await db.get(Topic, parent_id)
        if parent is None or parent.course_id != course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent topic must belong to the same course.",
            )
    topic = Topic(
        course_id=course_id,
        name=name,
        description=(description or "").strip() or None,
        parent_topic_id=parent_id,
    )
    db.add(topic)
    try:
        await db.commit()
    except Exception as exc:  # noqa: BLE001 - unique constraint on (course, name)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A topic with that name already exists in this course.",
        ) from exc
    await db.refresh(topic)
    return topic


async def delete_topic(db: AsyncSession, *, user_id: int, course_id: int, topic_id: int):
    await _owned_course(db, user_id=user_id, course_id=course_id)
    topic = await db.get(Topic, topic_id)
    if topic is None or topic.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )
    await db.delete(topic)
    await db.commit()


async def _walk_ancestors(db: AsyncSession, topic: Topic) -> list[int]:
    chain: list[int] = []
    current = topic
    seen = set()
    while current is not None and current.parent_topic_id is not None:
        if current.parent_topic_id in seen:
            break
        seen.add(current.parent_topic_id)
        chain.append(current.parent_topic_id)
        current = await db.get(Topic, current.parent_topic_id)
    return chain


async def set_prerequisite(
    db: AsyncSession,
    *,
    user_id: int,
    course_id: int,
    topic_id: int,
    prerequisite_id: int | None,
) -> Topic:
    await _owned_course(db, user_id=user_id, course_id=course_id)
    topic = await db.get(Topic, topic_id)
    if topic is None or topic.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    if prerequisite_id is not None:
        prereq = await db.get(Topic, prerequisite_id)
        if prereq is None or prereq.course_id != course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prerequisite must belong to the same course.",
            )
        if prerequisite_id == topic_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A topic cannot be its own prerequisite.",
            )
        # Reject cycles: the topic must not appear in the prereq's ancestor chain.
        if topic_id in await _walk_ancestors(db, prereq):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That link would create a prerequisite cycle.",
            )

    topic.parent_topic_id = prerequisite_id
    await db.commit()
    await db.refresh(topic)
    return topic


async def attach_source(
    db: AsyncSession, *, user_id: int, course_id: int, topic_id: int, content_unit_id: int
) -> None:
    await _owned_course(db, user_id=user_id, course_id=course_id)
    topic = await db.get(Topic, topic_id)
    unit = await db.get(ContentUnit, content_unit_id)
    if topic is None or topic.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )
    if unit is None or unit.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
        )
    existing = await db.get(ContentUnitTopic, (content_unit_id, topic_id))
    if existing is None:
        db.add(ContentUnitTopic(content_unit_id=content_unit_id, topic_id=topic_id))
        await db.commit()


# --------------------------------------------------------------------------- #
# Heuristic suggestions
# --------------------------------------------------------------------------- #
_CAP_PHRASE = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})\b")


def heuristic_candidates(texts: list[str], limit: int = 12) -> list[str]:
    """Rank candidate topic phrases by document frequency (transparent heuristic)."""
    counter: Counter[str] = Counter()
    for text in texts:
        seen: set[str] = set()
        for match in _CAP_PHRASE.findall(text or ""):
            phrase = match.strip()
            low = phrase.lower()
            if low in STOPWORDS or len(low) < 4:
                continue
            seen.add(phrase)
        for phrase in seen:
            counter[phrase] += 1
    ranked = [phrase for phrase, freq in counter.most_common() if freq >= 2]
    if not ranked:
        ranked = [phrase for phrase, _ in counter.most_common()]
    return ranked[:limit]


async def suggest_topics(
    db: AsyncSession, *, user_id: int, course_id: int, limit: int = 12
) -> list[dict]:
    await _owned_course(db, user_id=user_id, course_id=course_id)
    rows = await db.execute(
        select(ContentUnit.content, ContentUnit.title)
        .where(ContentUnit.course_id == course_id)
        .limit(200)
    )
    texts = [f"{title or ''}\n{content or ''}" for content, title in rows.all()]

    existing = {
        name.lower()
        for (name,) in (
            await db.execute(select(Topic.name).where(Topic.course_id == course_id))
        ).all()
    }
    suggestions = []
    for phrase in heuristic_candidates(texts, limit=limit * 2):
        if phrase.lower() in existing:
            continue
        suggestions.append({"name": phrase, "source": "heuristic"})
        if len(suggestions) >= limit:
            break
    return suggestions
