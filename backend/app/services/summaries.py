"""Course summary generation + cache service."""
from __future__ import annotations

import json

from datetime import datetime, timezone

from sqlalchemy import select

from app.ai.ollama import get_chat_provider
from app.models.content_unit import ContentUnit
from app.models.course import Course
from app.models.flashcard import CourseSummary
from app.services.materials import get_owned_course


def _now():
    return datetime.now(timezone.utc)


async def get_or_generate_summary(db, user_id, course_id, force=False):
    await get_owned_course(db, course_id, user_id)

    existing = (await db.execute(
        select(CourseSummary).where(CourseSummary.user_id == user_id, CourseSummary.course_id == course_id)
    )).scalar_one_or_none()
    if existing and not force:
        course = await db.get(Course, course_id)
        return {
            "course_id": course_id,
            "course_title": course.title if course else None,
            "title": existing.title,
            "body": existing.body,
            "source_unit_count": existing.source_unit_count,
            "model": existing.model,
            "generated_at": existing.generated_at,
            "cached": True,
        }

    units = (await db.execute(
        select(ContentUnit).where(ContentUnit.course_id == course_id).order_by(ContentUnit.id)
    )).scalars().all()
    chosen = []
    chars = 0
    for u in units:
        t = (u.content or "").strip()
        if not t:
            continue
        if chars + len(t) > 8000:
            remain = 8000 - chars
            if remain < 200:
                break
            t = t[:remain]
        chosen.append(t)
        chars += len(t)
        if chars >= 8000:
            break
    if not chosen:
        raise ValueError("no_content")
    context = "\n\n".join(chosen)

    messages = [
        {"role": "system", "content": (
            "You are a study assistant. Summarise the course text into 3-5 short "
            "paragraphs and 5-8 bullet \"Key points\". Cover only what the text "
            "says. Do not invent facts. Return a JSON object with keys "
            "'title' (one short phrase) and 'body' (the full summary text)."
        )},
        {"role": "user", "content": f"COURSE TEXT:\n{context}"},
    ]
    provider = get_chat_provider()
    try:
        raw = await provider.chat(messages, temperature=0.2, max_tokens=1200)
    except Exception:
        raise ValueError("model_unavailable")

    title = "Course summary"
    body = raw or "No summary produced."
    parsed = None
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            parsed = json.loads(raw[start:end + 1])
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        title = (parsed.get("title") or title)[:200]
        body = str(parsed.get("body") or body)

    course = await db.get(Course, course_id)
    if existing:
        existing.title = title
        existing.body = body
        existing.source_unit_count = len(chosen)
        existing.model = "local"
        existing.generated_at = _now()
        summary = existing
    else:
        summary = CourseSummary(
            user_id=user_id,
            course_id=course_id,
            title=title,
            body=body,
            source_unit_count=len(chosen),
            model="local",
        )
        db.add(summary)
    await db.commit()
    await db.refresh(summary)
    return {
        "course_id": course_id,
        "course_title": course.title if course else None,
        "title": summary.title,
        "body": summary.body,
        "source_unit_count": summary.source_unit_count,
        "model": summary.model,
        "generated_at": summary.generated_at,
        "cached": False,
    }
