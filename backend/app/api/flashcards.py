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
    """Get cards due for review today (SQL-level filtering for performance)."""
    from sqlalchemy import select, and_, or_

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # SQL-level filtering: new cards OR cards past their review time
    result = await db.execute(
        select(Flashcard, ReviewSchedule)
        .join(ReviewSchedule, Flashcard.id == ReviewSchedule.card_id)
        .where(
            or_(
                ReviewSchedule.state == "new",
                and_(
                    ReviewSchedule.next_review_at.isnot(None),
                    ReviewSchedule.next_review_at <= now,
                ),
            )
        )
        .order_by(ReviewSchedule.next_review_at.asc().nullsfirst())
        .limit(limit)
    )
    rows = result.all()

    due_cards = []
    for card, schedule in rows:
        due_cards.append({
            "id": card.id,
            "card_type": card.card_type,
            "front": card.front,
            "back": card.back,
            "hints": card.hints,
            "tags": card.tags,
            "schedule": {
                "state": schedule.state,
                "stability": schedule.fsrs_stability,
                "difficulty": schedule.fsrs_difficulty,
                "next_review_at": schedule.next_review_at.isoformat() if schedule.next_review_at else None,
                "review_count": schedule.review_count,
            },
        })

    # Load balancing: if all cards are due within the same hour, spread them
    if len(due_cards) > 50:
        from app.core.memory import fsrs
        # Only reorder cards, don't replace the list with balance_load output
        balanced = fsrs.balance_load(
            [{"schedule": c["schedule"], "_idx": i} for i, c in enumerate(due_cards)],
            max_per_day=50,
        )
        # Reorder due_cards based on balanced output
        if isinstance(balanced, list) and len(balanced) == len(due_cards):
            reordered = []
            seen = set()
            for item in balanced:
                idx = item.get("_idx", 0) if isinstance(item, dict) else 0
                if idx not in seen and 0 <= idx < len(due_cards):
                    reordered.append(due_cards[idx])
                    seen.add(idx)
            # Append any cards not covered by balanced output
            for i, card in enumerate(due_cards):
                if i not in seen:
                    reordered.append(card)
            due_cards = reordered

    return {
        "due_count": len(due_cards),
        "cards": due_cards,
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


# ── Search & Related Cards ──────────────────────────────────────


@router.get("/search")
async def search_cards(
    q: str = "",
    top_k: int = 10,
    tags: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Semantic/keyword search for flashcards.

    Falls back to SQL LIKE search when ChromaDB is unavailable.
    """
    from sqlalchemy import or_

    if not q.strip():
        return {"results": [], "search_method": "empty_query"}

    # Try ChromaDB semantic search first
    try:
        from app.core.memory.retrieval import card_retriever
        results = await card_retriever.search(q, top_k)
        if results:
            return {"results": results, "search_method": "semantic"}
    except Exception:
        pass

    # Fallback: SQL LIKE keyword search
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    conditions = [
        or_(
            Flashcard.front.ilike(f"%{q}%"),
            Flashcard.back.ilike(f"%{q}%"),
            Flashcard.hints.ilike(f"%{q}%"),
        )
    ]

    stmt = select(Flashcard).where(*conditions).limit(top_k)
    result = await db.execute(stmt)
    cards = result.scalars().all()

    return {
        "results": [
            {
                "id": c.id,
                "card_type": c.card_type,
                "front": c.front,
                "back": c.back,
                "hints": c.hints,
                "tags": c.tags,
                "deck_id": c.deck_id,
            }
            for c in cards
        ],
        "search_method": "keyword_fallback",
    }


@router.get("/related/{card_id}")
async def get_related_cards(
    card_id: str,
    top_k: int = 5,
    db: AsyncSession = Depends(get_db),
):
    """Get cards related to the given card (same knowledge point or deck)."""
    from app.core.memory.feedback_loop import feedback_engine

    related = await feedback_engine.get_related_cards(card_id, top_k)
    return {"card_id": card_id, "related_count": len(related), "cards": related}


# ── Deck Summary ─────────────────────────────────────────────────


class DeckSummaryRequest(BaseModel):
    model: str = "deepseek-chat"


@router.post("/deck/{deck_id}/summary")
async def generate_deck_summary(
    deck_id: str,
    req: DeckSummaryRequest = DeckSummaryRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Generate an AI summary of a flashcard deck's content."""
    from app.prompts import prompt_engine
    from app.core.api_scheduler import api_client, TaskType, GenerationConfig

    # Load deck
    result = await db.execute(select(Deck).where(Deck.id == deck_id))
    deck = result.scalar_one_or_none()
    if not deck:
        raise HTTPException(404, "Deck not found")

    # Load cards
    result = await db.execute(
        select(Flashcard).where(Flashcard.deck_id == deck_id).limit(50)
    )
    cards = result.scalars().all()

    if not cards:
        raise HTTPException(404, "No cards in deck")

    # Build type distribution
    type_dist = {}
    for c in cards:
        type_dist[c.card_type] = type_dist.get(c.card_type, 0) + 1
    type_dist_str = ", ".join(f"{k}: {v}张" for k, v in type_dist.items())

    # Sample cards for context
    sample = "\n\n".join(
        f"[{c.card_type}] Q: {c.front[:100]}\nA: {c.back[:100]}"
        for c in cards[:10]
    )

    messages = prompt_engine.render(
        "flashcard", "deck_summary",
        deck_name=deck.name,
        card_count=str(len(cards)),
        type_distribution=type_dist_str,
        sample_cards=sample,
    )

    result = await api_client.generate(
        task_type=TaskType.FLASHCARD_GEN,
        messages=messages,
        prompt_template_id="flashcard.deck_summary",
        generation_content=deck.name + str(len(cards)),
        config=GenerationConfig(model=req.model, max_tokens=1024, temperature=0.5),
    )

    import json as json_module
    try:
        summary = json_module.loads(result.content)
    except json_module.JSONDecodeError:
        summary = {"summary": result.content[:300]}

    return {
        "deck_id": deck_id,
        "deck_name": deck.name,
        "card_count": len(cards),
        "summary": summary.get("summary", ""),
        "core_topics": summary.get("core_topics", []),
        "difficulty_level": summary.get("difficulty_level", "medium"),
        "estimated_study_time_minutes": summary.get("estimated_study_time_minutes", 30),
        "learning_tips": summary.get("learning_tips", ""),
    }
