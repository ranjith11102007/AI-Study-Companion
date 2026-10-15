"""Study assignments: a plan built from mastery gaps, owned per user."""


from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentGenerateRequest,
    AssignmentResponse,
    AssignmentUpdate,
)
from app.services import assignments as assignment_service
from app.services import materials as material_service

router = APIRouter()


def _serialize(row) -> dict:
    assignment, course_title = row
    return {
        "id": assignment.id,
        "course_id": assignment.course_id,
        "course_title": course_title,
        "title": assignment.title,
        "kind": assignment.kind,
        "topic": assignment.topic,
        "material_id": assignment.material_id,
        "status": assignment.status,
        "due_at": assignment.due_at,
        "notes": assignment.notes,
        "created_at": assignment.created_at,
        "completed_at": assignment.completed_at,
    }


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Assignment not found.")


@router.get("/", response_model=list[AssignmentResponse])
async def list_assignments(
    course_id: int | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if course_id is not None:
        await material_service.get_owned_course(db, course_id, current_user.id)
    rows = await assignment_service.list_assignments(
        db, user_id=current_user.id, course_id=course_id, status=status
    )
    return [_serialize(r) for r in rows]


@router.post("/", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    payload: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        assignment, course_title = await assignment_service.create_assignment(
            db,
            user_id=current_user.id,
            course_id=payload.course_id,
            title=payload.title,
            kind=payload.kind,
            topic=payload.topic,
            material_id=payload.material_id,
            due_at=payload.due_at,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "id": assignment.id,
        "course_id": assignment.course_id,
        "course_title": course_title,
        "title": assignment.title,
        "kind": assignment.kind,
        "topic": assignment.topic,
        "material_id": assignment.material_id,
        "status": assignment.status,
        "due_at": assignment.due_at,
        "notes": assignment.notes,
        "created_at": assignment.created_at,
        "completed_at": assignment.completed_at,
    }


@router.post(
    "/generate",
    response_model=list[AssignmentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def generate_assignments(
    payload: AssignmentGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        rows = await assignment_service.generate_from_gaps(
            db,
            user_id=current_user.id,
            course_id=payload.course_id,
            count=payload.count,
            kind=payload.kind,
            days_out=payload.days_out,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return [_serialize(r) for r in rows]


@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        row = await assignment_service.get_assignment(db, assignment_id, current_user.id)
    except LookupError:
        raise _not_found()
    return _serialize(row)


@router.patch("/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = payload.model_dump(exclude_unset=True)
    # due_at: a null on a "clear" intent is honoured; otherwise unchanged.
    # Remap "preferences"-style nulls are not needed here; kept as-is.
    try:
        row = await assignment_service.update_assignment(
            db, assignment_id, current_user.id, data
        )
    except LookupError:
        raise _not_found()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serialize(row)


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await assignment_service.delete_assignment(
            db, assignment_id, current_user.id
        )
    except LookupError:
        raise _not_found()
    return None
