"""Dashboard / Stats API - learning analytics"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Date
from app.database import get_db
from app.models import (
    Document, KnowledgeTree, QuestionBank, AnswerRecord, ErrorLog,
    Flashcard, ReviewLog, ReviewSchedule, Deck, APICallLog,
)

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


def _date_filter(col, target_date):
    """Cross-database date comparison: cast both sides to Date."""
    return cast(col, Date) == target_date


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    """Get overall learning statistics."""
    doc_result = await db.execute(select(func.count(Document.id)))
    doc_count = doc_result.scalar() or 0

    q_result = await db.execute(select(func.count(QuestionBank.id)))
    question_count = q_result.scalar() or 0

    a_result = await db.execute(select(func.count(AnswerRecord.id)))
    answer_count = a_result.scalar() or 0

    c_result = await db.execute(
        select(func.count(AnswerRecord.id)).where(AnswerRecord.is_correct == True)
    )
    correct_count = c_result.scalar() or 0

    e_result = await db.execute(select(func.count(ErrorLog.id)))
    error_count = e_result.scalar() or 0

    card_result = await db.execute(select(func.count(Flashcard.id)))
    card_total = card_result.scalar() or 0

    # Reviews today (cross-DB compatible)
    today = datetime.now(timezone.utc).replace(tzinfo=None).date()
    rev_result = await db.execute(
        select(func.count(ReviewLog.id)).where(_date_filter(ReviewLog.review_at, today))
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
    """Get daily activity breakdown for the last N days (optimized with single queries)."""
    today = datetime.now(timezone.utc).replace(tzinfo=None).date()

    # Build date range
    dates = [(today - timedelta(days=i)) for i in range(days)]
    min_date = dates[-1]
    max_date = today + timedelta(days=1)

    # Single query for reviews per day
    rev_query = await db.execute(
        select(cast(ReviewLog.review_at, Date), func.count(ReviewLog.id))
        .where(cast(ReviewLog.review_at, Date) >= min_date)
        .group_by(cast(ReviewLog.review_at, Date))
    )
    reviews_by_date = {str(row[0]): row[1] for row in rev_query.all()}

    # Single query for answers per day
    ans_query = await db.execute(
        select(cast(AnswerRecord.answered_at, Date), func.count(AnswerRecord.id))
        .where(cast(AnswerRecord.answered_at, Date) >= min_date)
        .group_by(cast(AnswerRecord.answered_at, Date))
    )
    answers_by_date = {str(row[0]): row[1] for row in ans_query.all()}

    # Single query for correct answers per day
    corr_query = await db.execute(
        select(cast(AnswerRecord.answered_at, Date), func.count(AnswerRecord.id))
        .where(cast(AnswerRecord.answered_at, Date) >= min_date, AnswerRecord.is_correct == True)
        .group_by(cast(AnswerRecord.answered_at, Date))
    )
    correct_by_date = {str(row[0]): row[1] for row in corr_query.all()}

    # Single query for API calls per day
    api_query = await db.execute(
        select(cast(APICallLog.created_at, Date), func.count(APICallLog.id))
        .where(cast(APICallLog.created_at, Date) >= min_date)
        .group_by(cast(APICallLog.created_at, Date))
    )
    api_by_date = {str(row[0]): row[1] for row in api_query.all()}

    results = []
    for day in dates:
        day_str = day.isoformat()
        results.append({
            "date": day_str,
            "reviews": reviews_by_date.get(day_str, 0),
            "answers": answers_by_date.get(day_str, 0),
            "correct": correct_by_date.get(day_str, 0),
            "api_calls": api_by_date.get(day_str, 0),
        })

    return {"days": results}


@router.get("/topics")
async def topic_stats(db: AsyncSession = Depends(get_db)):
    """Get statistics grouped by question tags (topics)."""
    questions_result = await db.execute(select(QuestionBank))
    all_qs = questions_result.scalars().all()

    topic_map: dict[str, dict] = {}
    for q in all_qs:
        tag = q.tags[0] if q.tags else "未分类"
        if tag not in topic_map:
            topic_map[tag] = {"topic": tag, "total": 0, "errors": 0}
        topic_map[tag]["total"] += 1

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
