from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.learner import Recommendation
from app.models.user import User
from app.schemas.learner import MasteryOverview, RecommendationOut
from app.services import learner as learner_service
from app.services import materials as material_service

router = APIRouter()


@router.get("/courses/{course_id}/mastery", response_model=MasteryOverview)
async def get_mastery(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await material_service.get_owned_course(db, course_id, current_user.id)
    return {
        "course_id": course_id,
        "topics": await learner_service.list_mastery(
            db, user_id=current_user.id, course_id=course_id
        ),
        "weak_topics": await learner_service.weak_topics(
            db, user_id=current_user.id, course_id=course_id
        ),
        "strong_topics": await learner_service.strong_topics(
            db, user_id=current_user.id, course_id=course_id
        ),
        "untested_topics": await learner_service.untested_topics(
            db, user_id=current_user.id, course_id=course_id
        ),
    }


@router.get(
    "/courses/{course_id}/recommendations",
    response_model=list[RecommendationOut],
)
async def get_recommendations(
    course_id: int,
    refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await material_service.get_owned_course(db, course_id, current_user.id)
    if refresh:
        return await learner_service.generate_recommendations(
            db, user_id=current_user.id, course_id=course_id
        )
    result = await db.execute(
        select(Recommendation)
        .where(
            Recommendation.user_id == current_user.id,
            Recommendation.course_id == course_id,
        )
        .order_by(Recommendation.priority.desc(), Recommendation.id.desc())
    )
    return list(result.scalars().all())
