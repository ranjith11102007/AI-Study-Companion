from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.provider import CitationResolved
from app.services import citations as citation_service

router = APIRouter()


@router.get("/citations/{content_unit_id}", response_model=CitationResolved)
async def resolve_citation(
    content_unit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await citation_service.resolve_content_unit(
        db, user_id=current_user.id, content_unit_id=content_unit_id
    )
