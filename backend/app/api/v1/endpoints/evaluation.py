from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.provider import EvaluationResponse, EvaluateRequest, ProvidersResponse
from app.services import evaluation as evaluation_service
from app.services import providers as provider_service

router = APIRouter()


@router.get("/providers/status", response_model=ProvidersResponse)
async def providers_status():
    return await provider_service.check_providers()


@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    dependencies=[Depends(get_current_user)],
)
async def run_evaluation(
    payload: EvaluateRequest,
    db: AsyncSession = Depends(get_db),
):
    result = evaluation_service.run_evaluation(dataset_name=payload.dataset)
    if payload.store:
        _persist(db, result)
        await db.commit()
    return {
        "dataset": result.dataset,
        "metrics": result.metrics,
        "per_question": result.per_question,
    }


@router.get(
    "/evaluate/latest",
    response_model=EvaluationResponse,
)
async def latest_evaluation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select

    from app.models.learner import EvaluationRun

    row = (
        await db.execute(
            select(EvaluationRun).order_by(EvaluationRun.id.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        result = evaluation_service.run_evaluation()
        return {
            "dataset": result.dataset,
            "metrics": result.metrics,
            "per_question": result.per_question,
        }
    return {
        "dataset": row.dataset,
        "metrics": row.metrics or {},
        "per_question": (row.results or {}).get("per_question", []),
    }


def _persist(db: AsyncSession, result) -> None:
    from app.models.learner import EvaluationRun

    db.add(
        EvaluationRun(
            dataset=result.dataset,
            status="completed",
            metrics=result.metrics,
            results={"per_question": result.per_question},
        )
    )
