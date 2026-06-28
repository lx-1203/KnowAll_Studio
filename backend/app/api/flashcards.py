"""Flashcard and review API routes"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.database import get_db
from app.models import Flashcard, Deck, ReviewSchedule, ReviewLog
from app.core.memory import card_generator, fsrs
from app.core.anki_export import export_apkg
from app.core.auth import get_optional_user, get_user_id, load_user_api_keys

router = APIRouter(prefix="/api/v1/flashcards", tags=["flashcards"])


class GenerateCardsRequest(BaseModel):
    knowledge_text: str  # or chunk_ids
    card_type: str = "qa"  # qa/cloze/compare
    count: int = 20
    deck_name: str = "默认牌组"
    model: str = "deepseek-chat"


class ReviewRequest(BaseModel):
    card_id: str
    rating: int  # 1-4: Again/Hard/Good/Easy


@router.post("/generate")
async def generate_cards(
    req: GenerateCardsRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Generate flashcards from knowledge text via API."""
    await load_user_api_keys(get_user_id(current_user), db)

    # Ensure deck exists — commit immediately so the AI call below
    # (which writes to quota/cache/log tables via its own sessions)
    # is not blocked by this transaction's write lock.
    from sqlalchemy import select
    result = await db.execute(select(Deck).where(Deck.name == req.deck_name))
    deck = result.scalar_one_or_none()
    if not deck:
        deck = Deck(name=req.deck_name, description="")
        db.add(deck)
        await db.flush()
        await db.commit()
        # Start a fresh transaction for the rest of the request
        await db.begin()

    try:
        cards = await card_generator.generate(req.knowledge_text, req.card_type, req.count, req.model)
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {str(e)}")

    saved_cards = []
    for c in cards:
        card = Flashcard(
            card_type=c.get("card_type", req.card_type),
            front=c.get("front", ""),
            back=c.get("back", ""),
            hints=c.get("hints", ""),
            tags=c.get("tags", []),
            deck_id=deck.id,
        )
        db.add(card)
        await db.flush()

        # Initialize FSRS schedule
        schedule_state = fsrs.init_card()
        schedule = ReviewSchedule(
            card_id=card.id,
            fsrs_stability=schedule_state["stability"],
            fsrs_difficulty=schedule_state["difficulty"],
            fsrs_retrievability=schedule_state["retrievability"],
            state=schedule_state["state"],
        )
        db.add(schedule)
        saved_cards.append({
            "id": card.id,
            "card_type": card.card_type,
            "front": card.front,
            "back": card.back,
            "hints": card.hints,
        })

    deck.card_count += len(saved_cards)
    await db.commit()

    return {"generated_count": len(saved_cards), "cards": saved_cards, "deck_id": deck.id}


@router.post("/review")
async def review_card(req: ReviewRequest, db: AsyncSession = Depends(get_db)):
    """Submit a review rating for a flashcard. Returns updated schedule."""
    from sqlalchemy import select

    result = await db.execute(
        select(ReviewSchedule).where(ReviewSchedule.card_id == req.card_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(404, "Card schedule not found")

    # Build state dict
    state = {
        "stability": schedule.fsrs_stability or 0,
        "difficulty": schedule.fsrs_difficulty or 0,
        "retrievability": schedule.fsrs_retrievability or 0,
        "next_review_at": schedule.next_review_at,
        "last_review_at": schedule.last_review_at,
        "review_count": schedule.review_count,
        "state": schedule.state,
    }

    # Process with FSRS
    updated = fsrs.review(state, req.rating)

    # Update DB
    schedule.fsrs_stability = updated["stability"]
    schedule.fsrs_difficulty = updated["difficulty"]
    schedule.fsrs_retrievability = updated["retrievability"]
    schedule.next_review_at = updated["next_review_at"]
    schedule.last_review_at = updated["last_review_at"]
    schedule.review_count = updated["review_count"]
    schedule.state = updated["state"]

    # Log review
    log = ReviewLog(card_id=req.card_id, rating=req.rating)
    db.add(log)
    await db.commit()

    return {
        "card_id": req.card_id,
        "next_review_at": schedule.next_review_at.isoformat() if schedule.next_review_at else None,
        "state": schedule.state,
        "stability": round(schedule.fsrs_stability or 0, 2),
        "review_count": schedule.review_count,
    }


@router.get("/due")
async def get_due_cards(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Get cards due for review today."""
    from sqlalchemy import select

    # Get all cards with schedules
    result = await db.execute(
        select(Flashcard, ReviewSchedule)
        .join(ReviewSchedule, Flashcard.id == ReviewSchedule.card_id)
    )
    rows = result.all()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    due_cards = []
    for card, schedule in rows:
        if schedule.state == "new":
            due_cards.append(card)
        elif schedule.next_review_at and schedule.next_review_at <= now:
            due_cards.append(card)

    # Limit and format
    due_cards = due_cards[:limit]
    return {
        "due_count": len(due_cards),
        "cards": [
            {
                "id": c.id,
                "card_type": c.card_type,
                "front": c.front,
                "back": c.back,
                "hints": c.hints,
                "tags": c.tags,
            }
            for c in due_cards
        ],
    }


@router.get("/decks")
async def list_decks(
    limit: int = 1000,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all flashcard decks."""
    result = await db.execute(
        select(Deck).order_by(Deck.created_at.desc()).offset(offset).limit(limit)
    )
    decks = result.scalars().all()
    return [
        {"id": d.id, "name": d.name, "card_count": d.card_count, "created_at": d.created_at.isoformat()}
        for d in decks
    ]


@router.get("/export/anki/{deck_id}")
async def export_deck_anki(deck_id: str, db: AsyncSession = Depends(get_db)):
    """Export a deck as Anki .apkg file."""
    result = await db.execute(select(Deck).where(Deck.id == deck_id))
    deck = result.scalar_one_or_none()
    if not deck:
        raise HTTPException(404, "Deck not found")

    result = await db.execute(select(Flashcard).where(Flashcard.deck_id == deck_id))
    cards = result.scalars().all()

    card_dicts = [
        {"front": c.front, "back": c.back, "card_type": c.card_type, "tags": c.tags or []}
        for c in cards
    ]

    try:
        output_path = export_apkg(card_dicts, deck.name)
        return FileResponse(
            output_path,
            media_type="application/zip",
            filename=f"{deck.name}.apkg",
            headers={"Content-Disposition": f'attachment; filename="{deck.name}.apkg"'},
        )
    except Exception as e:
        raise HTTPException(500, f"Export failed: {str(e)}")
