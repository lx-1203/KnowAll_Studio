"""Answer Review API - 答题情况查看 & AI 知识点复习推荐"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from app.database import get_db
from app.core.auth import get_optional_user, get_user_id
from app.core.quiz.mastery_analyzer import mastery_analyzer

router = APIRouter(prefix="/api/v1/review", tags=["answer_review"])


class GenerateRecommendationsRequest(BaseModel):
    model: str = Field(default="deepseek-chat", description="LLM model for AI recommendations")


# ========== Mastery Analysis ==========

@router.get("/mastery")
async def get_mastery_analysis(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Get comprehensive knowledge point mastery analysis.

    Returns mastery scores for all knowledge points, classified as
    weak (<65%), moderate (65-85%), or strong (>85%).
    """
    user_id = get_user_id(current_user)
    result = await mastery_analyzer.analyze(user_id)
    return result


@router.get("/mastery/{kp_id}")
async def get_kp_mastery_detail(
    kp_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Get detailed mastery analysis for a single knowledge point."""
    user_id = get_user_id(current_user)
    result = await mastery_analyzer.analyze_single(kp_id, user_id)
    if result.get("mastery_score") is None:
        raise HTTPException(404, "No answer records found for this knowledge point")
    return result


# ========== Answer History ==========

@router.get("/history")
async def get_answer_history(
    kp_id: str | None = Query(None, description="Filter by knowledge point ID"),
    is_correct: bool | None = Query(None, description="Filter by correctness"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Get paginated answer history with question and knowledge point info."""
    user_id = get_user_id(current_user)
    result = await mastery_analyzer.get_answer_history(
        user_id=user_id,
        kp_id=kp_id,
        is_correct=is_correct,
        page=page,
        page_size=page_size,
    )
    return result


# ========== Overall Stats ==========

@router.get("/stats")
async def get_review_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Get overall answer statistics including 7-day trend and cognitive breakdown."""
    user_id = get_user_id(current_user)
    return await mastery_analyzer.get_overall_stats(user_id)


# ========== AI Review Recommendations ==========

@router.post("/recommend")
async def generate_review_recommendations(
    req: GenerateRecommendationsRequest = GenerateRecommendationsRequest(),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Generate AI-powered personalized review recommendations.

    Analyzes weak knowledge points and generates actionable review plans
    with suggested actions, time estimates, and resource recommendations.
    """
    user_id = get_user_id(current_user)
    result = await mastery_analyzer.generate_review_recommendations(
        user_id=user_id,
        model=req.model,
    )
    return result


# ========== Knowledge Point List for Review ==========

@router.get("/knowledge-points")
async def get_review_knowledge_points(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Get all knowledge points with their mastery status for review planning."""
    from app.models import KnowledgePointNode
    from app.database import async_session
    from sqlalchemy import select

    user_id = get_user_id(current_user)

    # Get mastery data
    analysis = await mastery_analyzer.analyze(user_id)
    mastery_map = analysis.get("mastery_map", {})

    # Get all knowledge point nodes
    async with async_session() as s:
        stmt = select(KnowledgePointNode).order_by(KnowledgePointNode.level, KnowledgePointNode.sequence)
        result = await s.execute(stmt)
        nodes = result.scalars().all()

        kp_list = []
        for node in nodes:
            mastery = mastery_map.get(node.id, {})
            kp_list.append({
                "id": node.id,
                "title": node.title,
                "level": node.level,
                "explanation": node.explanation or "",
                "mastery": mastery.get("mastery"),
                "accuracy": mastery.get("accuracy"),
                "total_attempts": mastery.get("total_attempts", 0),
                "error_count": mastery.get("error_count", 0),
                "trend": mastery.get("trend"),
                "has_data": node.id in mastery_map,
            })

        return {"total": len(kp_list), "items": kp_list}
