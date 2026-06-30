"""Gamification API: streaks, achievements, focus sessions, study stats."""
from datetime import datetime, timedelta, timezone, date
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.gamification import LearningStreak, Achievement, FocusSession, ACHIEVEMENTS
from app.models import AnswerRecord, ReviewLog
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/gamification", tags=["gamification"])


# ── Helper ──

async def _get_or_create_today_streak(user_id: str, db: AsyncSession) -> LearningStreak:
    today = date.today()
    result = await db.execute(
        select(LearningStreak).where(
            LearningStreak.user_id == user_id,
            LearningStreak.streak_date == today,
        )
    )
    streak = result.scalar_one_or_none()
    if not streak:
        streak = LearningStreak(user_id=user_id, streak_date=today)
        db.add(streak)
        await db.flush()
    return streak


async def _check_achievements(user_id: str, db: AsyncSession) -> list[dict]:
    """Check and unlock any new achievements. Returns newly unlocked ones."""
    # Get current stats
    today = date.today()
    result = await db.execute(
        select(LearningStreak).where(LearningStreak.user_id == user_id)
        .order_by(LearningStreak.streak_date.desc())
    )
    all_streaks = result.scalars().all()

    total_questions = sum(s.questions_answered or 0 for s in all_streaks)
    total_cards = sum(s.cards_reviewed or 0 for s in all_streaks)
    total_docs = sum(s.documents_uploaded or 0 for s in all_streaks)
    total_focus_minutes = 0

    focus_result = await db.execute(
        select(func.coalesce(func.sum(FocusSession.duration_minutes), 0))
        .where(FocusSession.user_id == user_id, FocusSession.completed == True)
    )
    total_focus_minutes = focus_result.scalar() or 0

    focus_count_result = await db.execute(
        select(func.count(FocusSession.id))
        .where(FocusSession.user_id == user_id, FocusSession.completed == True)
    )
    focus_count = focus_count_result.scalar() or 0

    # Compute current streak
    current_streak = 0
    check_date = today
    streak_dates = {s.streak_date for s in all_streaks}
    while check_date in streak_dates:
        current_streak += 1
        check_date -= timedelta(days=1)

    # Check for perfect quiz
    perfect_result = await db.execute(
        select(func.count(AnswerRecord.id)).where(AnswerRecord.user_id == user_id, AnswerRecord.is_correct == True)
    )

    # Get existing achievements
    existing = await db.execute(
        select(Achievement.achievement_key).where(Achievement.user_id == user_id)
    )
    existing_keys = set(existing.scalars().all())

    # Check each achievement
    conditions = {
        "streak_3": current_streak >= 3,
        "streak_7": current_streak >= 7,
        "streak_30": current_streak >= 30,
        "cards_50": total_cards >= 50,
        "cards_200": total_cards >= 200,
        "questions_100": total_questions >= 100,
        "questions_500": total_questions >= 500,
        "docs_5": total_docs >= 5,
        "focus_10": focus_count >= 10,
        "focus_60": total_focus_minutes >= 60,
        "first_quiz": total_questions > 0,
    }

    newly_unlocked = []
    for ach in ACHIEVEMENTS:
        if ach["key"] in existing_keys:
            continue
        if conditions.get(ach["key"], False):
            record = Achievement(
                user_id=user_id,
                achievement_key=ach["key"],
                name=ach["name"],
                description=ach["desc"],
                icon=ach["icon"],
            )
            db.add(record)
            newly_unlocked.append(ach)

    if newly_unlocked:
        await db.flush()

    return newly_unlocked


# ── Endpoints ──

@router.get("/dashboard")
async def gamification_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's gamification dashboard: streaks, achievements, stats."""
    user_id = current_user.id
    today = date.today()

    # Current streak
    all_streaks_result = await db.execute(
        select(LearningStreak.streak_date).where(LearningStreak.user_id == user_id)
        .order_by(LearningStreak.streak_date.desc())
    )
    streak_dates = [row[0] for row in all_streaks_result.all()]

    current_streak = 0
    check_date = today
    for d in streak_dates:
        if d == check_date:
            current_streak += 1
            check_date -= timedelta(days=1)
        elif d < check_date:
            break

    longest_streak = 0
    temp = 0
    prev = None
    for d in sorted(streak_dates):
        if prev is None:
            temp = 1
        elif d == prev + timedelta(days=1):
            temp += 1
        else:
            longest_streak = max(longest_streak, temp)
            temp = 1
        prev = d
    longest_streak = max(longest_streak, temp)

    # Today's minutes
    today_streak = await db.execute(
        select(LearningStreak).where(
            LearningStreak.user_id == user_id,
            LearningStreak.streak_date == today,
        )
    )
    ts = today_streak.scalar_one_or_none()
    today_minutes = ts.study_minutes if ts else 0

    # All achievements
    ach_result = await db.execute(
        select(Achievement).where(Achievement.user_id == user_id).order_by(Achievement.unlocked_at.desc())
    )
    achievements = [
        {"key": a.achievement_key, "name": a.name, "description": a.description,
         "icon": a.icon, "unlocked_at": a.unlocked_at.isoformat() if a.unlocked_at else None}
        for a in ach_result.scalars().all()
    ]

    # Weekly chart data
    week_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        day_result = await db.execute(
            select(LearningStreak).where(
                LearningStreak.user_id == user_id,
                LearningStreak.streak_date == d,
            )
        )
        day_streak = day_result.scalar_one_or_none()
        week_data.append({
            "date": d.isoformat(),
            "minutes": day_streak.study_minutes if day_streak else 0,
            "questions": day_streak.questions_answered if day_streak else 0,
            "cards": day_streak.cards_reviewed if day_streak else 0,
        })

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "today_minutes": today_minutes,
        "achievements": achievements,
        "total_achievements": len(achievements),
        "max_achievements": len(ACHIEVEMENTS),
        "week_data": week_data,
    }


class RecordActivityRequest(BaseModel):
    activity_type: str  # quiz / flashcard / document / focus
    count: int = 1
    duration_minutes: int = 0


@router.post("/record-activity")
async def record_activity(
    req: RecordActivityRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record a learning activity (called internally by quiz/flashcard/document endpoints)."""
    user_id = current_user.id
    streak = await _get_or_create_today_streak(user_id, db)

    if req.activity_type == "quiz":
        streak.questions_answered += req.count
    elif req.activity_type == "flashcard":
        streak.cards_reviewed += req.count
    elif req.activity_type == "document":
        streak.documents_uploaded += req.count
    elif req.activity_type == "focus":
        pass  # handled by focus session endpoint

    if req.duration_minutes > 0:
        streak.study_minutes += req.duration_minutes

    await db.commit()

    # Check achievements
    new_achievements = await _check_achievements(user_id, db)
    if new_achievements:
        await db.commit()

    return {
        "streak_updated": True,
        "minutes_today": streak.study_minutes,
        "new_achievements": new_achievements,
    }


class FocusSessionRequest(BaseModel):
    duration_minutes: int
    session_type: str = "study"
    tags: list[str] = []


@router.post("/focus/start")
async def start_focus_session(
    req: FocusSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start and complete a focus session."""
    session = FocusSession(
        user_id=current_user.id,
        duration_minutes=req.duration_minutes,
        session_type=req.session_type,
        tags=req.tags,
        ended_at=datetime.now(timezone.utc),
    )
    db.add(session)

    # Also record to streak
    streak = await _get_or_create_today_streak(current_user.id, db)
    streak.study_minutes += req.duration_minutes

    await db.commit()

    # Check achievements
    new_achievements = await _check_achievements(current_user.id, db)
    if new_achievements:
        await db.commit()

    return {
        "session_id": session.id,
        "duration_minutes": req.duration_minutes,
        "total_focus_today": streak.study_minutes,
        "new_achievements": new_achievements,
    }


@router.get("/focus/history")
async def focus_history(
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent focus sessions."""
    result = await db.execute(
        select(FocusSession).where(FocusSession.user_id == current_user.id)
        .order_by(FocusSession.started_at.desc()).limit(limit)
    )
    sessions = result.scalars().all()
    return {
        "total": len(sessions),
        "sessions": [
            {
                "id": s.id,
                "duration_minutes": s.duration_minutes,
                "session_type": s.session_type,
                "completed": s.completed,
                "started_at": s.started_at.isoformat() if s.started_at else None,
            }
            for s in sessions
        ],
    }
