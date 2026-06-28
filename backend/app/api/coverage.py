"""Knowledge coverage report API routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.core.auth import get_optional_user, get_user_id
from app.core.memory.coverage import coverage_engine

router = APIRouter(prefix="/api/v1/knowledge/coverage", tags=["coverage"])


class RefreshCoverageRequest(BaseModel):
    summary_id: str
    document_id: str
    model: str = "deepseek-chat"


@router.get("/{summary_id}")
async def get_coverage_report(
    summary_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Get coverage report for a knowledge summary."""
    user_id = get_user_id(current_user)
    report = await coverage_engine.calculate(summary_id, user_id)
    return report


@router.post("/refresh")
async def refresh_coverage(
    req: RefreshCoverageRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Refresh coverage: auto-generate missing questions and flashcards."""
    result = await coverage_engine.ensure_full_coverage(
        summary_id=req.summary_id,
        document_id=req.document_id,
        model=req.model,
    )
    return result
