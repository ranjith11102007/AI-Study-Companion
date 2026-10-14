import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.ratelimit import rate_limit
from app.db.session import SessionLocal, get_db
from app.models.course import Course
from app.models.user import User
from app.schemas.tutor import (
    ConversationDetail,
    ConversationSummary,
    MessageOut,
    TutorAnswerResponse,
    TutorAskRequest,
)
from app.services import tutor as tutor_service

router = APIRouter()
settings = get_settings()


@router.post(
    "/tutor/ask",
    response_model=TutorAnswerResponse,
    dependencies=[Depends(rate_limit("tutor"))],
    summary="Ask the source-grounded tutor a question",
)
async def ask(
    payload: TutorAskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await tutor_service.answer_question(
        db,
        user_id=current_user.id,
        course_id=payload.course_id,
        question=payload.question,
        conversation_id=payload.conversation_id,
    )
    return result


@router.post(
    "/tutor/ask/stream",
    dependencies=[Depends(rate_limit("tutor"))],
    summary="Stream a source-grounded tutor answer (server-sent events)",
)
async def ask_stream(
    payload: TutorAskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream a tutor answer as SSE so the UI can show live progress.

    Ownership is verified up front so an invalid course returns a normal 404.
    The generator then runs on its own session so it stays valid for the whole
    streamed response.
    """
    user_id = current_user.id
    owned = (
        await db.execute(
            select(Course.id).where(
                Course.id == payload.course_id, Course.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if owned is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    async def event_stream():
        async with SessionLocal() as session:
            async for event in tutor_service.stream_answer(
                session,
                user_id=user_id,
                course_id=payload.course_id,
                question=payload.question,
                conversation_id=payload.conversation_id,
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tutor/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    course_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await tutor_service.list_conversations(
        db, user_id=current_user.id, course_id=course_id
    )
    return list(rows)


@router.get("/tutor/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation, messages = await tutor_service.get_conversation_messages(
        db, user_id=current_user.id, conversation_id=conversation_id
    )
    return ConversationDetail(
        id=conversation.id,
        course_id=conversation.course_id,
        title=conversation.title,
        messages=[MessageOut.model_validate(m) for m in messages],
    )


@router.delete(
    "/tutor/conversations/{conversation_id}",
    status_code=204,
)
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await tutor_service.delete_conversation(
        db, user_id=current_user.id, conversation_id=conversation_id
    )
    return None
