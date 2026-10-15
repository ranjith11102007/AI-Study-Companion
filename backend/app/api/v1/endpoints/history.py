"""Study history endpoint: a real activity feed derived from existing rows.

See ``app/services/history.py`` — no new table, no synthesised events.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import HistoryResponse
from app.services import materials as material_service
from app.services.history import build_history

router = APIRouter()


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    kind: Literal["tutor", "assessment", "upload", "mastery"] | None = None,
    course_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """One page of the user's own history, newest first.

    ``kind`` narrows the feed to one event type; ``course_id`` limits it to a
    single course, which the caller must own (otherwise 404).
    """
    if course_id is not None:
        await material_service.get_owned_course(db, course_id, current_user.id)

    return await build_history(
        db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        kind=kind,
        course_id=course_id,
    )
