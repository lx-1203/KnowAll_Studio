"""Language vocabulary API routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from app.database import get_db
from app.models import LanguageVocabulary
from app.core.auth import get_optional_user, get_user_id, load_user_api_keys

router = APIRouter(prefix="/api/v1/language", tags=["language"])


class GenerateVocabularyRequest(BaseModel):
    document_id: str
    summary_id: str
    language_type: str = "auto"


class MarkMasteredRequest(BaseModel):
    mastered: bool = True


@router.post("/vocabulary/generate")
async def generate_vocabulary(
    req: GenerateVocabularyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Generate vocabulary list from document using LanguageAgent."""
    await load_user_api_keys(get_user_id(current_user), db)

    from app.core.agents.language_agent import LanguageAgent

    agent = LanguageAgent()
    result = await agent.run(
        summary_id=req.summary_id,
        document_id=req.document_id,
        language_type=req.language_type,
    )
    if result.status == "error":
        raise HTTPException(500, result.error or "Vocabulary generation failed")
    return result


@router.get("/vocabulary")
async def list_vocabulary(
    document_id: str | None = None,
    summary_id: str | None = None,
    difficulty: str | None = None,
    part_of_speech: str | None = None,
    mastered: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """List vocabulary items with filtering."""
    query = select(LanguageVocabulary)

    if document_id:
        query = query.where(LanguageVocabulary.document_id == document_id)
    if difficulty:
        query = query.where(LanguageVocabulary.difficulty == difficulty)
    if part_of_speech:
        query = query.where(LanguageVocabulary.part_of_speech == part_of_speech)
    if mastered is not None:
        query = query.where(LanguageVocabulary.mastered == mastered)

    # Get total
    from sqlalchemy import func
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get items
    query = query.offset(offset).limit(limit).order_by(LanguageVocabulary.difficulty, LanguageVocabulary.word)
    result = await db.execute(query)
    words = result.scalars().all()

    return {
        "total": total,
        "words": [
            {
                "id": w.id,
                "word": w.word,
                "phonetic": w.phonetic,
                "part_of_speech": w.part_of_speech,
                "definition": w.definition,
                "example_sentence": w.example_sentence,
                "difficulty": w.difficulty,
                "knowledge_point_id": w.knowledge_point_id,
                "mastered": w.mastered,
            }
            for w in words
        ],
    }


@router.patch("/vocabulary/{vocab_id}")
async def mark_vocabulary_mastered(
    vocab_id: str,
    req: MarkMasteredRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Mark a vocabulary item as mastered or not."""
    vocab = await db.get(LanguageVocabulary, vocab_id)
    if not vocab:
        raise HTTPException(404, "Vocabulary item not found")
    vocab.mastered = req.mastered
    await db.commit()
    return {"id": vocab_id, "mastered": req.mastered}
