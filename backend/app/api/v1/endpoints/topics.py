from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.topic import (
    AttachSourceRequest,
    PrerequisiteUpdate,
    TopicCreate,
    TopicOut,
    TopicSuggestion,
)
from app.services import topics as topic_service

router = APIRouter()


@router.get("/courses/{course_id}/topics", response_model=list[TopicOut])
async def list_topics(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await topic_service.list_topics(
        db, user_id=current_user.id, course_id=course_id
    )


@router.get(
    "/courses/{course_id}/topics/suggestions",
    response_model=list[TopicSuggestion],
)
async def suggest_topics(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await topic_service.suggest_topics(
        db, user_id=current_user.id, course_id=course_id
    )


@router.post("/courses/{course_id}/topics", response_model=TopicOut, status_code=201)
async def create_topic(
    course_id: int,
    payload: TopicCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    topic = await topic_service.create_topic(
        db,
        user_id=current_user.id,
        course_id=course_id,
        name=payload.name,
        description=payload.description,
        parent_id=payload.parent_id,
    )
    return {
        "id": topic.id,
        "name": topic.name,
        "description": topic.description,
        "parent_id": topic.parent_id,
        "parent_name": None,
        "source_count": 0,
    }


@router.delete("/courses/{course_id}/topics/{topic_id}", status_code=204)
async def delete_topic(
    course_id: int,
    topic_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await topic_service.delete_topic(
        db, user_id=current_user.id, course_id=course_id, topic_id=topic_id
    )
    return None


@router.post(
    "/courses/{course_id}/topics/{topic_id}/prerequisite",
    response_model=TopicOut,
)
async def set_prerequisite(
    course_id: int,
    topic_id: int,
    payload: PrerequisiteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    topic = await topic_service.set_prerequisite(
        db,
        user_id=current_user.id,
        course_id=course_id,
        topic_id=topic_id,
        prerequisite_id=payload.prerequisite_id,
    )
    return {
        "id": topic.id,
        "name": topic.name,
        "description": topic.description,
        "parent_id": topic.parent_id,
        "parent_name": None,
        "source_count": 0,
    }


@router.post(
    "/courses/{course_id}/topics/{topic_id}/sources",
    status_code=204,
)
async def attach_source(
    course_id: int,
    topic_id: int,
    payload: AttachSourceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await topic_service.attach_source(
        db,
        user_id=current_user.id,
        course_id=course_id,
        topic_id=topic_id,
        content_unit_id=payload.content_unit_id,
    )
    return None
