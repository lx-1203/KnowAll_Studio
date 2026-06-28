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
    since: str | None = None  # ISO datetime — incremental scan


class CompleteReviewRequest(BaseModel):
    queue_id: str


@router.post("/feedback/scan")
async def scan_feedback(
    req: FeedbackScanRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Scan all knowledge points and push weak ones to review queue.

    Use `since` parameter for incremental scanning (only records after the given time).
    """
    user_id = get_user_id(current_user)
    result = await feedback_engine.scan(
        user_id=user_id,
        threshold=req.threshold,
        since=req.since,
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


# ── Decay Detection & Related Cards ─────────────────────────────


@router.post("/feedback/detect-decay")
async def detect_memory_decay(
    lookback_reviews: int = 5,
    decay_threshold: int = 2,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Detect cards whose recent ratings are trending downward (memory decay).

    Args:
        lookback_reviews: Number of recent reviews to examine per card
        decay_threshold: Minimum count of low ratings (AGAIN/HARD) to flag as decay
    """
    user_id = get_user_id(current_user)
    decaying = await feedback_engine.detect_decay(
        user_id=user_id,
        lookback_reviews=lookback_reviews,
        decay_threshold=decay_threshold,
    )
    return {"decay_count": len(decaying), "decaying_cards": decaying}


@router.get("/flashcards/{card_id}/related")
async def get_related_flashcards(
    card_id: str,
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Get cards related to this one (same knowledge point or deck)."""
    related = await feedback_engine.get_related_cards(card_id, limit)
    return {"card_id": card_id, "related_count": len(related), "cards": related}
