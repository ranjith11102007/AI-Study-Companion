"""Study assignments: a real plan derived from mastery and owned by its user."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.assignment import Assignment
from app.models.course import Course
from app.models.learning_material import LearningMaterial
from app.services import materials as material_service
from app.services import learner as learner_service


async def list_assignments(db, *, user_id, course_id=None, status=None):
    stmt = (
        select(Assignment, Course.title)
        .join(Course, Course.id == Assignment.course_id)
        .where(Assignment.user_id == user_id)
    )
    if course_id is not None:
        stmt = stmt.where(Assignment.course_id == course_id)
    if status is not None:
        stmt = stmt.where(Assignment.status == status)
    stmt = stmt.order_by(Assignment.created_at.desc())
    rows = (await db.execute(stmt)).all()
    return rows  # list of (Assignment, course_title)


async def get_assignment(db, assignment_id, user_id):
    stmt = (
        select(Assignment, Course.title)
        .join(Course, Course.id == Assignment.course_id)
        .where(Assignment.id == assignment_id, Course.user_id == user_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise LookupError("assignment not found")
    return row  # (Assignment, course_title)


async def create_assignment(db, *, user_id, course_id, title, kind, topic, material_id,
                          due_at, notes, source_recommendation_id=None):
    await material_service.get_owned_course(db, course_id, user_id)
    if material_id is not None:
        mat_row = await db.execute(
            select(LearningMaterial.id).where(
                LearningMaterial.id == material_id,
                LearningMaterial.course_id == course_id,
            )
        )
        if mat_row.scalar_one_or_none() is None:
            raise LookupError("material not in this course")
    a = Assignment(
        user_id=user_id,
        course_id=course_id,
        title=title,
        kind=kind,
        topic=topic,
        material_id=material_id,
        status="todo",
        due_at=due_at,
        notes=notes,
        source_recommendation_id=source_recommendation_id,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    course = await db.get(Course, course_id)
    return a, (course.title if course else None)


async def generate_from_gaps(db, *, user_id, course_id, count, kind, days_out):
    await material_service.get_owned_course(db, course_id, user_id)
    weak = await learner_service.weak_topics(db, user_id=user_id, course_id=course_id)
    course = await db.get(Course, course_id)
    created: list[tuple[Assignment, str | None]] = []
    seen: set[str] = set()
    due = datetime.now(timezone.utc) + timedelta(days=max(1, int(days_out)))
    for row in weak:
        if len(created) >= count:
            break
        topic = getattr(row, "topic", None)
        if not topic or topic in seen:
            continue
        seen.add(topic)
        a = Assignment(
            user_id=user_id,
            course_id=course_id,
            title=f"Practice: {topic}",
            kind=kind,
            topic=topic,
            status="todo",
            due_at=due,
        )
        db.add(a)
        await db.flush()
        created.append((a, course.title if course else None))
    await db.commit()
    for a, _ in created:
        await db.refresh(a)
    return created


VALID_STATUSES = {"todo", "in_progress", "done", "skipped"}


async def update_assignment(db, assignment_id, user_id, data: dict):
    row = await get_assignment(db, assignment_id, user_id)
    a, course_title = row
    if "title" in data and data["title"] is not None:
        a.title = data["title"].strip()
    if "kind" in data and data["kind"] is not None:
        a.kind = data["kind"]
    if "topic" in data:
        a.topic = data["topic"]
    if "material_id" in data:
        a.material_id = data["material_id"]
    if "status" in data and data["status"] is not None:
        if data["status"] not in VALID_STATUSES:
            raise ValueError("unknown status")
        a.status = data["status"]
        if data["status"] == "done":
            a.completed_at = datetime.now(timezone.utc)
        elif data["status"] in ("todo", "in_progress"):
            a.completed_at = None
    if "due_at" in data:
        a.due_at = data["due_at"]
    if "notes" in data:
        a.notes = data["notes"]
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a, course_title


async def delete_assignment(db, assignment_id, user_id):
    a, _ = await get_assignment(db, assignment_id, user_id)
    await db.delete(a)
    await db.commit()
