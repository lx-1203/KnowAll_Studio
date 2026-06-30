"""Backup & Restore API - export/import all local data"""
import json
import shutil
import zipfile
import tempfile
import os
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import (
    Document, DocumentChunk, KnowledgeTree, QuestionBank,
    Flashcard, Deck, ReviewSchedule, Conversation, Message,
)
from app.config import settings
from app.models.user import User
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/backup", tags=["backup"])

BACKUP_VERSION = "0.2"


def _cleanup_temp_file(path: str) -> None:
    """Remove a temp file if it exists."""
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


@router.get("/export")
async def export_all_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export all learning data as a JSON file."""
    export = {
        "version": BACKUP_VERSION,
        "exported_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "data": {},
    }

    # Documents (metadata only)
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

    # Flashcards with schedules (single query with join)
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

    # Conversations with messages (single query for all messages)
    convs = (await db.execute(select(Conversation))).scalars().all()
    conv_ids = [c.id for c in convs]
    conv_data = []
    if conv_ids:
        all_msgs_result = await db.execute(
            select(Message).where(Message.conversation_id.in_(conv_ids)).order_by(Message.created_at)
        )
        msgs_by_conv: dict[str, list] = {}
        for m in all_msgs_result.scalars().all():
            msgs_by_conv.setdefault(m.conversation_id, []).append(m)

        for c in convs:
            msgs = msgs_by_conv.get(c.id, [])
            conv_data.append({
                "id": c.id, "title": c.title, "role_preset": c.role_preset,
                "created_at": c.created_at.isoformat(),
                "messages": [{"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in msgs],
            })
    export["data"]["conversations"] = conv_data

    # Write to temp file with cleanup
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
async def import_data(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import data from a backup JSON file. Skips duplicates by SHA256/doc_id."""
    import json as json_module

    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(400, "请上传 .json 备份文件")

    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(400, "备份文件过大，最大支持 50MB")

    content = await file.read()
    try:
        backup = json_module.loads(content.decode("utf-8"))
    except (json_module.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "无效的 JSON 文件")

    version = backup.get("version", "0.0")
    # Support 0.1 and 0.2 versions
    if version not in ("0.1", "0.2"):
        raise HTTPException(400, f"不支持的备份版本: {version}。支持: 0.1, 0.2")

    data = backup.get("data", {})
    stats = {"documents": 0, "knowledge_trees": 0, "questions": 0,
             "flashcards": 0, "decks": 0, "conversations": 0}

    # Import documents (skip by sha256)
    if "documents" in data:
        existing_shas = set()
        result = await db.execute(select(Document.sha256))
        for row in result.scalars().all():
            if row:
                existing_shas.add(row)

        for doc_data in data["documents"]:
            sha = doc_data.get("sha256", "")
            if not sha or sha in existing_shas:
                continue
            doc = Document(
                id=doc_data.get("id", ""),
                filename=doc_data.get("filename", "imported"),
                file_type=doc_data.get("file_type", "unknown"),
                sha256=sha,
                status=doc_data.get("status", "pending"),
                page_count=doc_data.get("page_count", 1),
                metadata_=doc_data.get("metadata", {}),
            )
            db.add(doc)
            existing_shas.add(sha)
            stats["documents"] += 1

    await db.flush()

    # Import knowledge trees
    if "knowledge_trees" in data:
        existing_ids = set()
        result = await db.execute(select(KnowledgeTree.id))
        for row in result.scalars().all():
            existing_ids.add(row)

        for tree_data in data["knowledge_trees"]:
            tid = tree_data.get("id", "")
            if not tid or tid in existing_ids:
                continue
            tree = KnowledgeTree(
                id=tid,
                name=tree_data.get("name", "Imported"),
                doc_ids=tree_data.get("doc_ids", []),
                tree_data=tree_data.get("tree_data", {}),
            )
            db.add(tree)
            existing_ids.add(tid)
            stats["knowledge_trees"] += 1

    await db.flush()

    # Import questions
    if "questions" in data:
        existing_ids = set()
        result = await db.execute(select(QuestionBank.id))
        for row in result.scalars().all():
            existing_ids.add(row)

        for q_data in data["questions"]:
            qid = q_data.get("id", "")
            if not qid or qid in existing_ids:
                continue
            correct = q_data.get("correct_answer", q_data.get("answer"))
            q = QuestionBank(
                id=qid,
                question_type=q_data.get("question_type", "single_choice"),
                difficulty=q_data.get("difficulty", "medium"),
                tags=q_data.get("tags", []),
                question_text=q_data.get("question_text", ""),
                options=q_data.get("options", []),
                correct_answer=str(correct) if correct is not None else "",
                analysis=q_data.get("analysis", ""),
            )
            db.add(q)
            existing_ids.add(qid)
            stats["questions"] += 1

    await db.flush()

    # Import decks and flashcards
    if "decks" in data:
        existing_deck_ids = set()
        result = await db.execute(select(Deck.id))
        for row in result.scalars().all():
            existing_deck_ids.add(row)

        for deck_data in data["decks"]:
            did = deck_data.get("id", "")
            if not did or did in existing_deck_ids:
                continue
            deck = Deck(
                id=did, name=deck_data.get("name", "Imported Deck"),
                description=deck_data.get("description", ""),
                card_count=deck_data.get("card_count", 0),
            )
            db.add(deck)
            existing_deck_ids.add(did)
            stats["decks"] += 1

    await db.flush()

    if "flashcards" in data:
        existing_card_ids = set()
        result = await db.execute(select(Flashcard.id))
        for row in result.scalars().all():
            existing_card_ids.add(row)

        for card_data in data["flashcards"]:
            cid = card_data.get("id", "")
            if not cid or cid in existing_card_ids:
                continue
            card = Flashcard(
                id=cid,
                card_type=card_data.get("card_type", "qa"),
                front=card_data.get("front", ""),
                back=card_data.get("back", ""),
                hints=card_data.get("hints", ""),
                tags=card_data.get("tags", []),
                deck_id=card_data.get("deck_id"),
            )
            db.add(card)
            existing_card_ids.add(cid)

            schedule = card_data.get("schedule", {})
            if schedule:
                next_review_str = schedule.get("next_review_at")
                next_review = None
                if next_review_str:
                    try:
                        from datetime import datetime as dt
                        next_review = dt.fromisoformat(next_review_str)
                    except (ValueError, TypeError):
                        pass
                rs = ReviewSchedule(
                    card_id=cid,
                    fsrs_stability=float(schedule.get("stability", 0)),
                    fsrs_difficulty=float(schedule.get("difficulty", 0)),
                    state=schedule.get("state", "new"),
                    next_review_at=next_review,
                    review_count=int(schedule.get("review_count", 0)),
                )
                db.add(rs)
            stats["flashcards"] += 1

    await db.flush()

    # Import conversations with messages
    if "conversations" in data:
        existing_conv_ids = set()
        result = await db.execute(select(Conversation.id))
        for row in result.scalars().all():
            existing_conv_ids.add(row)

        for conv_data in data["conversations"]:
            cid = conv_data.get("id", "")
            if not cid or cid in existing_conv_ids:
                continue
            conv = Conversation(
                id=cid,
                title=conv_data.get("title", "Imported"),
                role_preset=conv_data.get("role_preset", "tutor"),
            )
            db.add(conv)
            existing_conv_ids.add(cid)
            for msg_data in conv_data.get("messages", []):
                msg = Message(
                    conversation_id=cid,
                    role=msg_data.get("role", "user"),
                    content=msg_data.get("content", ""),
                )
                db.add(msg)
            stats["conversations"] += 1

    await db.commit()
    return {"status": "imported", "stats": stats}


@router.get("/files")
async def backup_files(current_user: User = Depends(get_current_user)):
    """Package raw document files into a zip archive."""
    doc_dir = Path(settings.document_dir)
    if not doc_dir.exists() or not any(doc_dir.iterdir()):
        raise HTTPException(404, "没有可备份的文档文件")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = tmp.name
            with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in doc_dir.rglob("*"):
                    if f.is_file():
                        zf.write(f, str(f.relative_to(doc_dir)))

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        response = FileResponse(
            tmp_path, media_type="application/zip",
            filename=f"knowall_documents_{ts}.zip",
        )
        # Register cleanup after response is sent
        response.background = None  # FileResponse doesn't support background
        return response
    except Exception:
        _cleanup_temp_file(tmp_path or "")
        raise
