from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentSummary,
    AttemptStartResponse,
    AttemptSubmitRequest,
    AttemptSummary,
)
from app.services import assessments as assessment_service

router = APIRouter()


@router.post(
    "/assessments",
    response_model=AssessmentSummary,
    status_code=201,
    dependencies=[Depends(rate_limit("assessments"))],
    summary="Generate a verified assessment from indexed course material",
)
async def create_assessment(
    payload: AssessmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await assessment_service.generate_assessment(
        db,
        user_id=current_user.id,
        course_id=payload.course_id,
        title=payload.title,
        question_count=payload.question_count,
        difficulty=payload.difficulty,
        time_limit_minutes=payload.time_limit_minutes,
    )


@router.get("/assessments", response_model=list[AssessmentSummary])
async def list_assessments(
    course_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await assessment_service.list_assessments(
        db, user_id=current_user.id, course_id=course_id
    )


@router.get("/assessments/{assessment_id}", response_model=AssessmentSummary)
async def get_assessment(
    assessment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await assessment_service.get_assessment(
        db, user_id=current_user.id, assessment_id=assessment_id
    )


@router.delete("/assessments/{assessment_id}", status_code=204)
async def delete_assessment(
    assessment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await assessment_service.delete_assessment(
        db, user_id=current_user.id, assessment_id=assessment_id
    )
    return None


@router.post(
    "/assessments/{assessment_id}/attempts",
    response_model=AttemptStartResponse,
    status_code=201,
)
async def start_attempt(
    assessment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = await assessment_service.start_attempt(
        db, user_id=current_user.id, assessment_id=assessment_id
    )
    return attempt


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptSummary)
async def submit_attempt(
    attempt_id: int,
    payload: AttemptSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await assessment_service.submit_attempt(
        db,
        user_id=current_user.id,
        attempt_id=attempt_id,
        answers=[item.model_dump() for item in payload.answers],
    )


@router.get("/attempts/{attempt_id}")
async def get_attempt(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await assessment_service.get_attempt_detail(
        db, user_id=current_user.id, attempt_id=attempt_id
    )
