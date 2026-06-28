"""Game Quiz API — serves quiz questions for the game module."""
import json
import random
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import QuestionBank
from app.core.auth import get_optional_user

router = APIRouter(prefix="/api/v1/game", tags=["game"])

# Path to local quiz bank
QUIZ_BANK_DIR = Path(__file__).resolve().parent.parent / "data" / "quiz_bank"


def _load_local_bank(difficulty: str) -> list[dict]:
    """Load questions from local JSON bank."""
    file_path = QUIZ_BANK_DIR / f"default_{difficulty}.json"
    if not file_path.exists():
        return []
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


@router.get("/quiz")
async def get_game_questions(
    difficulty: str = Query("easy", description="Question difficulty: easy, medium, hard"),
    count: int = Query(5, ge=1, le=20, description="Number of questions to fetch"),
    source: str = Query("local", description="Source: local or db"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """
    Fetch game quiz questions.

    Supports two sources:
    - `local`: Read from bundled JSON files (fast, no DB needed).
    - `db`: Query from the QuestionBank table (requires pre-generated questions).
    """
    if difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(400, "difficulty must be easy, medium, or hard")

    questions: list[dict] = []

    if source == "db":
        # Query from database QuestionBank
        result = await db.execute(
            select(QuestionBank)
            .where(QuestionBank.difficulty_score >= _difficulty_min(difficulty))
            .where(QuestionBank.difficulty_score <= _difficulty_max(difficulty))
            .where(QuestionBank.question_type.in_(["single_choice", "multi_choice", "true_false"]))
            .order_by(func.random())
            .limit(count)
        )
        rows = result.scalars().all()
        for q in rows:
            questions.append({
                "id": q.id,
                "question_type": q.question_type,
                "difficulty": difficulty,
                "question_text": q.question_text,
                "options": q.options if isinstance(q.options, list) else [],
                "answer": q.correct_answer,
                "analysis": q.analysis or "",
            })
    else:
        # Load from local JSON
        pool = _load_local_bank(difficulty)
        if pool:
            random.shuffle(pool)
            selected = pool[:count]
            questions = selected
        else:
            # Fallback: try other difficulties
            for fallback_diff in ("medium", "easy", "hard"):
                if fallback_diff == difficulty:
                    continue
                pool = _load_local_bank(fallback_diff)
                if pool:
                    random.shuffle(pool)
                    questions = pool[:count]
                    break

    if not questions:
        raise HTTPException(404, f"No questions available for difficulty={difficulty}")

    return {"questions": questions, "total": len(questions)}


@router.get("/quiz/local")
async def get_local_quiz_info():
    """Get info about available local quiz banks."""
    info = {}
    for difficulty in ("easy", "medium", "hard"):
        pool = _load_local_bank(difficulty)
        info[difficulty] = {
            "count": len(pool),
            "available": len(pool) > 0,
        }
    return {"banks": info}


def _difficulty_min(diff: str) -> float:
    """Map difficulty label to minimum difficulty_score."""
    return {"easy": 0.0, "medium": 0.36, "hard": 0.66}.get(diff, 0.0)


def _difficulty_max(diff: str) -> float:
    """Map difficulty label to maximum difficulty_score."""
    return {"easy": 0.35, "medium": 0.65, "hard": 1.0}.get(diff, 1.0)
