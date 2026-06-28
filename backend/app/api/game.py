"""Game generation API routes"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import GameProgress
from app.core.game import game_generator
from app.core.auth import get_optional_user, get_user_id, load_user_api_keys

router = APIRouter(prefix="/api/v1/generate", tags=["generate"])


class GameLevelRequest(BaseModel):
    knowledge_text: str
    game_type: str = "matching"
    count: int = 8
    model: str = "deepseek-chat"


class SaveProgressRequest(BaseModel):
    game_type: str
    level_id: str = ""
    best_score: int = 0
    stars: int = 0
    completed: bool = False


@router.post("/game-levels")
async def generate_game_levels(
    req: GameLevelRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Generate game level content via AI."""
    await load_user_api_keys(get_user_id(current_user), db)
    try:
        levels = await game_generator.generate_levels(
            req.knowledge_text, req.game_type, req.count, req.model
        )
        return {"pairs": levels if req.game_type in ("matching", "fix", "coding") else [],
                "levels": levels if req.game_type == "cloze_ladder" else [],
                "count": len(levels)}
    except Exception as e:
        raise HTTPException(500, f"Game generation failed: {str(e)}")


@router.post("/game-progress")
async def save_game_progress(
    req: SaveProgressRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Save game progress (best score, stars, completion)."""
    user_id = get_user_id(current_user)
    existing = await db.execute(
        select(GameProgress).where(
            GameProgress.user_id == user_id,
            GameProgress.game_type == req.game_type,
            GameProgress.level_id == req.level_id,
        )
    )
    progress = existing.scalar_one_or_none()

    if progress:
        progress.best_score = max(progress.best_score or 0, req.best_score)
        progress.stars = max(progress.stars or 0, req.stars)
        progress.completed = progress.completed or req.completed
    else:
        progress = GameProgress(
            user_id=user_id,
            game_type=req.game_type,
            level_id=req.level_id,
            best_score=req.best_score,
            stars=req.stars,
            completed=req.completed,
        )
        db.add(progress)

    await db.commit()
    return {"status": "saved", "best_score": progress.best_score, "stars": progress.stars, "completed": progress.completed}


@router.get("/game-progress")
async def get_game_progress(
    game_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Get game progress history."""
    user_id = get_user_id(current_user)
    query = select(GameProgress).where(GameProgress.user_id == user_id)
    if game_type:
        query = query.where(GameProgress.game_type == game_type)
    query = query.order_by(GameProgress.updated_at.desc())

    result = await db.execute(query)
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "game_type": r.game_type,
            "level_id": r.level_id,
            "best_score": r.best_score,
            "stars": r.stars,
            "completed": r.completed,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in records
    ]
