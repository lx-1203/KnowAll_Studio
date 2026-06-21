"""Dashboard / Stats API - learning analytics"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import (
    Document, KnowledgeTree, QuestionBank, AnswerRecord, ErrorLog,
    Flashcard, ReviewLog, ReviewSchedule, Deck, APICallLog,
)

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    """Get overall learning statistics."""
    # Document count
    doc_result = await db.execute(select(func.count(Document.id)))
    doc_count = doc_result.scalar() or 0

    # Question bank
    q_result = await db.execute(select(func.count(QuestionBank.id)))
    question_count = q_result.scalar() or 0

    # Answer records
    a_result = await db.execute(select(func.count(AnswerRecord.id)))
    answer_count = a_result.scalar() or 0

    # Correct answers
    c_result = await db.execute(
        select(func.count(AnswerRecord.id)).where(AnswerRecord.is_correct == True)
    )
    correct_count = c_result.scalar() or 0

    # Error count
    e_result = await db.execute(select(func.count(ErrorLog.id)))
    error_count = e_result.scalar() or 0

    # Flashcard counts
    card_result = await db.execute(select(func.count(Flashcard.id)))
    card_total = card_result.scalar() or 0

    # Reviews today
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).replace(tzinfo=None).date()
    rev_result = await db.execute(
        select(func.count(ReviewLog.id)).where(func.date(ReviewLog.review_at) == today)
    )
    reviews_today = rev_result.scalar() or 0

    # Due cards
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    due_result = await db.execute(
        select(func.count(ReviewSchedule.id)).where(
            (ReviewSchedule.state == "new") |
            ((ReviewSchedule.next_review_at != None) & (ReviewSchedule.next_review_at <= now))
        )
    )
    due_count = due_result.scalar() or 0

    # Token usage
    token_result = await db.execute(
        select(
            func.coalesce(func.sum(APICallLog.tokens_input), 0),
            func.coalesce(func.sum(APICallLog.tokens_output), 0),
            func.coalesce(func.sum(APICallLog.cost_estimate), 0),
        )
    )
    tok_in, tok_out, cost = token_result.one()

    return {
        "documents": doc_count,
        "questions": question_count,
        "answers_submitted": answer_count,
        "correct_rate": round(correct_count / max(answer_count, 1) * 100, 1),
        "errors": error_count,
        "cards_total": card_total,
        "cards_due": due_count,
        "reviews_today": reviews_today,
        "token_usage": {"input": tok_in, "output": tok_out, "total": (tok_in or 0) + (tok_out or 0)},
        "cost_estimate": round(cost or 0, 4),
    }


@router.get("/daily")
async def daily_stats(days: int = 7, db: AsyncSession = Depends(get_db)):
    """Get daily activity breakdown for the last N days."""
    from datetime import datetime, timedelta, timezone

    results = []
    for i in range(days):
        day = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=i)).date()
        next_day = day + timedelta(days=1)

        # Reviews on this day
        rev_count = await db.execute(
            select(func.count(ReviewLog.id)).where(
                func.date(ReviewLog.review_at) == day
            )
        )
        # Answers on this day
        ans_count = await db.execute(
            select(func.count(AnswerRecord.id)).where(
                func.date(AnswerRecord.answered_at) == day
            )
        )
        correct = await db.execute(
            select(func.count(AnswerRecord.id)).where(
                func.date(AnswerRecord.answered_at) == day,
                AnswerRecord.is_correct == True,
            )
        )
        # API calls on this day
        api_count = await db.execute(
            select(func.count(APICallLog.id)).where(
                func.date(APICallLog.created_at) == day
            )
        )

        results.append({
            "date": day.isoformat(),
            "reviews": rev_count.scalar() or 0,
            "answers": ans_count.scalar() or 0,
            "correct": correct.scalar() or 0,
            "api_calls": api_count.scalar() or 0,
        })

    return {"days": results}


@router.get("/topics")
async def topic_stats(db: AsyncSession = Depends(get_db)):
    """Get statistics grouped by question tags (topics)."""
    questions_result = await db.execute(select(QuestionBank))
    all_qs = questions_result.scalars().all()

    # Aggregate by first tag
    topic_map: dict[str, dict] = {}
    for q in all_qs:
        tag = q.tags[0] if q.tags else "未分类"
        if tag not in topic_map:
            topic_map[tag] = {"topic": tag, "total": 0, "errors": 0}
        topic_map[tag]["total"] += 1

    # Get error stats per topic
    error_result = await db.execute(
        select(ErrorLog, QuestionBank)
        .join(QuestionBank, ErrorLog.question_id == QuestionBank.id)
    )
    for err, q in error_result.all():
        tag = q.tags[0] if q.tags else "未分类"
        if tag not in topic_map:
            topic_map[tag] = {"topic": tag, "total": 1, "errors": 0}
        topic_map[tag]["errors"] += err.error_count

    return {"topics": list(topic_map.values())}
