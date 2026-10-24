"""Flashcard generation + spaced-review service.

Cards are generated from the user's own indexed course content by the local\nmodel. A line format `Q: ... || A: ... || topic: ...` is parsed; we never\ninvent content without a source chunk.\n"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.ai.ollama import get_chat_provider
from app.models.content_unit import ContentUnit
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.services.materials import get_owned_course

LOCAL = "ollama"
CARD_REGEX = re.compile(
    r"^\s*Q:\s*(.+?)\s*\|\|\s*A:\s*(.+?)(?:\s*\|\|\s*topic:\s*(.+))?\s*$",
    re.IGNORECASE | re.DOTALL,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _owned_course(db, course_id, user_id):
    return await get_owned_course(db, course_id, user_id)


async def _course_title(db, course_id):
    c = await db.get(Course, course_id)
    return c.title if c else None


async def _gather_content(db, course_id, max_chars=6000):
    rows = (
        await db.execute(
            select(ContentUnit).where(ContentUnit.course_id == course_id).order_by(ContentUnit.id)
        )
    ).scalars().all()
    chosen = []
    chars = 0
    for u in rows:
        text = (u.content or "").strip()
        if not text:
            continue
        # prefer substantive units
        if chars + len(text) > max_chars:
            remain = max_chars - chars
            if remain < 200:
                break
            text = text[:remain]
        chosen.append((u, text))
        chars += len(text)
        if chars >= max_chars:
            break
    return chosen


async def generate_from_course(db, user_id, course_id, count=8):
    await _owned_course(db, course_id, user_id)
    units = await _gather_content(db, course_id)
    if not units:
        raise ValueError("no_content")

    context = "\n\n".join(f"[{u.id}] {t}" for u, t in units)
    style_instructions = (
        "You are a study-assistant for one student. "
        "Generate exactly " + str(min(count, 20)) + " flashcards from the course text below. "
        "Return ONE card per line with this exact format and nothing else: "
        "Q: <short question> || A: <concise answer, 1-2 sentences> || topic: <topic name>. "
        "Every card must be grounded in the provided text; do not invent facts. "
        "Avoid duplicate questions."
    )
    messages = [
        {"role": "system", "content": style_instructions},
        {"role": "user", "content": f"COURSE TEXT:\n{context}"},
    ]
    provider = get_chat_provider()
    try:
        raw = await provider.chat(messages, temperature=0.3, max_tokens=2048)
    except Exception:
        raise ValueError("model_unavailable")

    cards = []
    for line in (raw or "").splitlines():
        m = CARD_REGEX.match(line.strip())
        if not m:
            continue
        front = m.group(1).strip()
        back = m.group(2).strip()
        topic = (m.group(3) or "").strip() or None
        if not front or not back:
            continue
        cards.append((front, back, topic))

    # Dedupe by front.
    seen = set()
    uniq = []
    for f, b, t in cards:
        key = f.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append((f, b, t))

    if not uniq:
        raise ValueError("bad_model_output")

    # Assign source_unit_id naively: map by order to units (rough grounding).
    now = _now()
    limit_n = min(count, len(uniq))
    inserted = []
    for i, (front, back, topic) in enumerate(uniq[:limit_n]):
        suid = units[min(i, len(units) - 1)][0].id
        row = Flashcard(
            user_id=user_id,
            course_id=course_id,
            front=front,
            back=back,
            topic=topic,
            source_unit_id=suid,
            next_review_at=now,
        )
        db.add(row)
        await db.flush()
        inserted.append(row)
    await db.commit()
    for r in inserted:
        await db.refresh(r)
    title = await _course_title(db, course_id)
    return [(r, title) for r in inserted]


async def list_flashcards(db, user_id, course_id, due_only=False):
    rows = (await db.execute(
        select(Flashcard, Course.title).join(Course, Course.id == Flashcard.course_id).where(
            Flashcard.user_id == user_id, Flashcard.course_id == course_id
        )
    )).all()
    now = _now()
    out = []
    for card, title in rows:
        if due_only and card.next_review_at and card.next_review_at > now:
            continue
        out.append((card, title))
    out.sort(key=lambda x: (x[0].next_review_at or x[0].created_at))
    return out


async def review_card(db, user_id, card_id, correct):
    row = (await db.execute(
        select(Flashcard, Course.title).join(Course, Course.id == Flashcard.course_id).where(
            Flashcard.id == card_id, Flashcard.user_id == user_id
        )
    )).first()
    if row is None:
        raise LookupError("not_found")
    card, title = row
    now = _now()
    card.last_reviewed_at = now
    if correct:
        card.correct_count += 1
        card.interval_days = min(30, max(1, card.interval_days * 2))
        card.ease = min(2.5, card.ease + 0.1)
    else:
        card.wrong_count += 1
        card.interval_days = 1
        card.ease = max(1.3, card.ease - 0.2)
    card.next_review_at = now + timedelta(days=card.interval_days)
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card, title


async def delete_card(db, user_id, card_id):
    row = (await db.execute(
        select(Flashcard).where(Flashcard.id == card_id, Flashcard.user_id == user_id)
    )).scalar_one_or_none()
    if row is None:
        raise LookupError("not_found")
    await db.delete(row)
    await db.commit()
