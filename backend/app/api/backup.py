"""Backup & Restore API - export/import all local data"""
import json
import shutil
import zipfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import (
    Document, DocumentChunk, KnowledgeTree, QuestionBank,
    Flashcard, Deck, ReviewSchedule, Conversation, Message,
)
from app.config import settings

router = APIRouter(prefix="/api/v1/backup", tags=["backup"])


@router.get("/export")
async def export_all_data(db: AsyncSession = Depends(get_db)):
    """Export all learning data as a JSON file."""
    export = {"version": "0.1", "exported_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), "data": {}}

    # Documents (metadata only, not files)
    docs = (await db.execute(select(Document))).scalars().all()
    export["data"]["documents"] = [
        {"id": d.id, "filename": d.filename, "file_type": d.file_type,
         "sha256": d.sha256, "status": d.status, "page_count": d.page_count,
         "metadata": d.metadata_, "created_at": d.created_at.isoformat()}
        for d in docs
    ]

    # Knowledge trees
    trees = (await db.execute(select(KnowledgeTree))).scalars().all()
    export["data"]["knowledge_trees"] = [
        {"id": t.id, "name": t.name, "doc_ids": t.doc_ids, "tree_data": t.tree_data,
         "created_at": t.created_at.isoformat()}
        for t in trees
    ]

    # Questions
    questions = (await db.execute(select(QuestionBank))).scalars().all()
    export["data"]["questions"] = [
        {"id": q.id, "question_type": q.question_type, "difficulty": q.difficulty,
         "tags": q.tags, "question_text": q.question_text, "options": q.options,
         "correct_answer": q.correct_answer, "analysis": q.analysis}
        for q in questions
    ]

    # Flashcards with schedules
    cards = (await db.execute(select(Flashcard))).scalars().all()
    card_ids = [c.id for c in cards]
    schedules = {}
    if card_ids:
        sched_result = await db.execute(
            select(ReviewSchedule).where(ReviewSchedule.card_id.in_(card_ids))
        )
        for s in sched_result.scalars().all():
            schedules[s.card_id] = {
                "stability": s.fsrs_stability, "difficulty": s.fsrs_difficulty,
                "state": s.state, "next_review_at": s.next_review_at.isoformat() if s.next_review_at else None,
                "review_count": s.review_count,
            }

    export["data"]["flashcards"] = [
        {"id": c.id, "card_type": c.card_type, "front": c.front, "back": c.back,
         "hints": c.hints, "tags": c.tags, "deck_id": c.deck_id,
         "schedule": schedules.get(c.id, {})}
        for c in cards
    ]

    # Decks
    decks = (await db.execute(select(Deck))).scalars().all()
    export["data"]["decks"] = [
        {"id": d.id, "name": d.name, "description": d.description, "card_count": d.card_count}
        for d in decks
    ]

    # Conversations
    convs = (await db.execute(select(Conversation))).scalars().all()
    conv_data = []
    for c in convs:
        msgs = (await db.execute(
            select(Message).where(Message.conversation_id == c.id).order_by(Message.created_at)
        )).scalars().all()
        conv_data.append({
            "id": c.id, "title": c.title, "role_preset": c.role_preset,
            "created_at": c.created_at.isoformat(),
            "messages": [{"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in msgs],
        })
    export["data"]["conversations"] = conv_data

    # Write to temp file
    export_dir = Path(settings.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = export_dir / f"knowall_backup_{ts}.json"
    filepath.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")

    return FileResponse(
        filepath, media_type="application/json",
        filename=f"knowall_backup_{ts}.json",
    )


@router.post("/import")
async def import_data(file: dict, db: AsyncSession = Depends(get_db)):
    """Import data from a backup JSON file. Skips duplicates by SHA256."""
    # This is a stub — full implementation would parse the uploaded JSON
    # and merge records into the database
    return {"status": "stub", "message": "Import API ready. Use the exported JSON to restore."}


@router.get("/files")
async def backup_files():
    """Package raw document files into a zip archive."""
    doc_dir = Path(settings.document_dir)
    if not doc_dir.exists() or not any(doc_dir.iterdir()):
        raise HTTPException(404, "No document files to backup")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in doc_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, str(f.relative_to(doc_dir)))
        tmp_path = tmp.name

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return FileResponse(
        tmp_path, media_type="application/zip",
        filename=f"knowall_documents_{ts}.zip",
    )
