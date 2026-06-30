"""Share / Collaboration API routes"""
import secrets
import string
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from app.database import get_db
from app.models import ShareLink, KnowledgeTree, QuestionBank, Deck, Flashcard
from app.core.auth import get_optional_user, get_user_id

router = APIRouter(prefix="/api/v1/share", tags=["share"])


class CreateShareRequest(BaseModel):
    resource_type: str  # knowledge_tree / question_bank / flashcard_deck
    resource_id: str
    expires_in_days: int | None = None  # None = never expires


def _generate_access_code() -> str:
    """Generate a cryptographically secure 6-digit access code."""
    return "".join(secrets.choice(string.digits) for _ in range(6))


@router.post("/create")
async def create_share_link(
    req: CreateShareRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Create a share link for a resource."""
    if req.resource_type not in ("knowledge_tree", "question_bank", "flashcard_deck"):
        raise HTTPException(400, f"Unsupported resource type: {req.resource_type}")

    # Verify resource exists
    if req.resource_type == "knowledge_tree":
        result = await db.execute(select(KnowledgeTree).where(KnowledgeTree.id == req.resource_id))
        if not result.scalar_one_or_none():
            raise HTTPException(404, "Knowledge tree not found")
    elif req.resource_type == "flashcard_deck":
        result = await db.execute(select(Deck).where(Deck.id == req.resource_id))
        if not result.scalar_one_or_none():
            raise HTTPException(404, "Deck not found")
    elif req.resource_type == "question_bank":
        result = await db.execute(
            select(QuestionBank).where(QuestionBank.id == req.resource_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(404, "Question not found")

    access_code = _generate_access_code()

    expires_at = None
    if req.expires_in_days:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=req.expires_in_days)

    share = ShareLink(
        user_id=get_user_id(current_user),
        resource_type=req.resource_type,
        resource_id=req.resource_id,
        access_code=access_code,
        expires_at=expires_at,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)

    return {
        "share_id": share.id,
        "access_code": access_code,
        "resource_type": req.resource_type,
        "resource_id": req.resource_id,
        "expires_at": share.expires_at.isoformat() if share.expires_at else None,
        "share_url": f"/share/{share.id}",
    }


@router.get("/view/{share_id}")
async def view_shared_resource(share_id: str, access_code: str = "", db: AsyncSession = Depends(get_db)):
    """View a shared resource by share ID and access code."""
    result = await db.execute(select(ShareLink).where(ShareLink.id == share_id))
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(404, "Share link not found")

    # Check expiry
    if share.expires_at:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if now > share.expires_at:
            raise HTTPException(410, "Share link has expired")

    # Verify access code
    if access_code != share.access_code:
        raise HTTPException(403, "Invalid access code")

    # Increment view count
    share.view_count += 1
    await db.commit()

    # Return the shared resource content
    if share.resource_type == "knowledge_tree":
        result = await db.execute(select(KnowledgeTree).where(KnowledgeTree.id == share.resource_id))
        tree = result.scalar_one_or_none()
        if not tree:
            raise HTTPException(404, "Shared knowledge tree no longer exists")
        return {
            "type": "knowledge_tree",
            "data": {
                "tree_id": tree.id,
                "name": tree.name,
                "tree_data": tree.tree_data,
                "created_at": tree.created_at.isoformat(),
            },
        }

    elif share.resource_type == "flashcard_deck":
        result = await db.execute(select(Deck).where(Deck.id == share.resource_id))
        deck = result.scalar_one_or_none()
        if not deck:
            raise HTTPException(404, "Shared deck no longer exists")
        card_result = await db.execute(
            select(Flashcard).where(Flashcard.deck_id == share.resource_id)
        )
        cards = card_result.scalars().all()
        return {
            "type": "flashcard_deck",
            "data": {
                "deck_id": deck.id,
                "name": deck.name,
                "card_count": deck.card_count,
                "cards": [
                    {"id": c.id, "front": c.front, "back": c.back, "card_type": c.card_type}
                    for c in cards
                ],
            },
        }

    elif share.resource_type == "question_bank":
        result = await db.execute(
            select(QuestionBank).where(QuestionBank.id == share.resource_id)
        )
        question = result.scalar_one_or_none()
        if not question:
            raise HTTPException(404, "Shared question no longer exists")
        return {
            "type": "question_bank",
            "data": {
                "questions": [
                    {
                        "id": question.id,
                        "question_type": question.question_type,
                        "question_text": question.question_text,
                        "options": question.options,
                        "analysis": question.analysis,
                    }
                ],
            },
        }


@router.get("/my-links")
async def list_my_links(
    limit: int = 1000,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """List all share links created by the current user."""
    user_id = get_user_id(current_user)
    result = await db.execute(
        select(ShareLink)
        .where(ShareLink.user_id == user_id)
        .order_by(ShareLink.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    links = result.scalars().all()
    return [
        {
            "share_id": l.id,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "access_code": l.access_code,
            "expires_at": l.expires_at.isoformat() if l.expires_at else None,
            "view_count": l.view_count,
            "created_at": l.created_at.isoformat(),
        }
        for l in links
    ]


@router.delete("/{share_id}")
async def delete_share_link(share_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a share link."""
    result = await db.execute(select(ShareLink).where(ShareLink.id == share_id))
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(404, "Share link not found")
    await db.delete(link)
    await db.commit()
    return {"status": "deleted"}
