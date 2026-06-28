"""Memory feedback API routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from app.database import get_db
from app.core.auth import get_optional_user, get_user_id
from app.core.memory.feedback_loop import feedback_engine

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


class FeedbackScanRequest(BaseModel):
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class CompleteReviewRequest(BaseModel):
    queue_id: str


@router.post("/feedback/scan")
async def scan_feedback(
    req: FeedbackScanRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Scan all knowledge points and push weak ones to review queue."""
    user_id = get_user_id(current_user)
    result = await feedback_engine.scan(
        user_id=user_id,
        threshold=req.threshold,
    )
    return result


@router.get("/review-queue")
async def get_review_queue(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Get current user's review queue sorted by priority."""
    user_id = get_user_id(current_user)
    items = await feedback_engine.get_review_queue(user_id=user_id, limit=limit)
    return {"total": len(items), "items": items}


@router.post("/review-queue/complete")
async def complete_review_item(
    req: CompleteReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Mark a review queue item as completed."""
    success = await feedback_engine.mark_completed(req.queue_id)
    if not success:
        raise HTTPException(404, "Review queue item not found")
    return {"queue_id": req.queue_id, "completed": True}


@router.get("/stats")
async def get_memory_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Get memory/learning statistics for current user."""
    user_id = get_user_id(current_user)
    return await feedback_engine.get_memory_stats(user_id)


@router.post("/flashcards/{card_id}/record")
async def record_flashcard_result(
    card_id: str,
    is_correct: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Record a flashcard review result for feedback tracking."""
    await feedback_engine.record_answer_result(card_id, is_correct)
    return {"card_id": card_id, "is_correct": is_correct, "recorded": True}
