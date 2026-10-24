"""Flashcards + course summaries endpoints (Phase 5)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.flashcard import (
    CourseSummaryResponse,
    FlashcardResponse,
    GenerateFlashcardsRequest,
    ReviewRequest,
)
from app.services import flashcards as flashcard_service
from app.services import summaries as summary_service

router = APIRouter()


@router.post("/flashcards/generate", response_model=list[FlashcardResponse], status_code=status.HTTP_201_CREATED)
async def generate_flashcards(
    payload: GenerateFlashcardsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        rows = await flashcard_service.generate_from_course(
            db, current_user.id, payload.course_id, count=payload.count
        )
    except ValueError as exc:
        if str(exc) == "no_content":
            raise HTTPException(status_code=400, detail="No content indexed for this course yet. Upload materials first.")
        if str(exc) == "model_unavailable":
            raise HTTPException(status_code=503, detail="The local model is unavailable. Make sure Ollama is running.")
        if str(exc) == "bad_model_output":
            raise HTTPException(status_code=502, detail="The model did not produce usable cards. Try again.")
        raise HTTPException(status_code=500, detail="Could not generate flashcards.")
    title_cache = {}
    result = []
    for card, course_title in rows:
        title_cache[card.course_id] = course_title
        result.append({
            "id": card.id,
            "course_id": card.course_id,
            "course_title": course_title,
            "front": card.front,
            "back": card.back,
            "topic": card.topic,
            "source_unit_id": card.source_unit_id,
            "interval_days": card.interval_days,
            "ease": card.ease,
            "correct_count": card.correct_count,
            "wrong_count": card.wrong_count,
            "next_review_at": card.next_review_at,
            "last_reviewed_at": card.last_reviewed_at,
            "created_at": card.created_at,
        })
    return result


@router.get("/flashcards", response_model=list[FlashcardResponse])
async def list_flashcards(
    course_id: int = Query(...),
    due_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await flashcard_service.list_flashcards(db, current_user.id, course_id, due_only=due_only)
    return [
        {
            "id": c.id,
            "course_id": c.course_id,
            "course_title": title,
            "front": c.front,
            "back": c.back,
            "topic": c.topic,
            "source_unit_id": c.source_unit_id,
            "interval_days": c.interval_days,
            "ease": c.ease,
            "correct_count": c.correct_count,
            "wrong_count": c.wrong_count,
            "next_review_at": c.next_review_at,
            "last_reviewed_at": c.last_reviewed_at,
            "created_at": c.created_at,
        }
        for c, title in rows
    ]


@router.patch("/flashcards/{card_id}", response_model=FlashcardResponse)
async def review_card(
    card_id: int,
    payload: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        card, title = await flashcard_service.review_card(db, current_user.id, card_id, payload.correct)
    except LookupError:
        raise HTTPException(status_code=404, detail="Flashcard not found.")
    return {
        "id": card.id,
        "course_id": card.course_id,
        "course_title": title,
        "front": card.front,
        "back": card.back,
        "topic": card.topic,
        "source_unit_id": card.source_unit_id,
        "interval_days": card.interval_days,
        "ease": card.ease,
        "correct_count": card.correct_count,
        "wrong_count": card.wrong_count,
        "next_review_at": card.next_review_at,
        "last_reviewed_at": card.last_reviewed_at,
        "created_at": card.created_at,
    }


@router.delete("/flashcards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flashcard(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await flashcard_service.delete_card(db, current_user.id, card_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Flashcard not found.")
    return None


@router.get("/summaries/{course_id}", response_model=CourseSummaryResponse)
async def course_summary(
    course_id: int,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = await summary_service.get_or_generate_summary(db, current_user.id, course_id, force=force)
    except ValueError as exc:
        if str(exc) == "no_content":
            raise HTTPException(status_code=400, detail="No content indexed for this course yet. Upload materials first.")
        if str(exc) == "model_unavailable":
            raise HTTPException(status_code=503, detail="The local model is unavailable. Make sure Ollama is running.")
        raise HTTPException(status_code=500, detail="Could not generate the summary.")
    return data
