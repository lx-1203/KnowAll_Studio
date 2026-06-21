"""Game generation API routes"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.game import game_generator

router = APIRouter(prefix="/api/v1/generate", tags=["generate"])


class GameLevelRequest(BaseModel):
    knowledge_text: str
    game_type: str = "matching"
    count: int = 8
    model: str = "deepseek-chat"


@router.post("/game-levels")
async def generate_game_levels(req: GameLevelRequest):
    """Generate game level content via AI."""
    try:
        levels = await game_generator.generate_levels(
            req.knowledge_text, req.game_type, req.count, req.model
        )
        return {"pairs": levels if req.game_type == "matching" else [],
                "levels": levels if req.game_type == "cloze_ladder" else [],
                "count": len(levels)}
    except Exception as e:
        raise HTTPException(500, f"Game generation failed: {str(e)}")
