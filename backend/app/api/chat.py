"""AI Assistant chat API routes with SSE streaming support"""
import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.database import get_db
from app.models import Conversation, Message
from app.core.assistant import assistant as ai_assistant
from app.core.rag_assistant import rag_assistant

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    role_preset: str = "tutor"
    model: str = "deepseek-chat"
    knowledge_context: str | None = None


@router.post("/assistant")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Non-streaming chat: send message, get full response."""
    conv = await _get_or_create_conversation(db, req)

    # Save user message
    user_msg = Message(conversation_id=conv.id, role="user", content=req.message)
    db.add(user_msg)
    await db.flush()

    # Get history
    history = await _get_history(db, conv.id)

    try:
        if req.knowledge_context:
            response_text = await ai_assistant.chat_with_context(
                req.message, req.knowledge_context, req.role_preset, history, req.model
            )
        else:
            response_text = await ai_assistant.chat(
                req.message, req.role_preset, history, req.model
            )
    except Exception as e:
        raise HTTPException(500, f"Chat failed: {str(e)}")

    # Save assistant message
    assistant_msg = Message(conversation_id=conv.id, role="assistant", content=response_text)
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(conv)

    return {
        "conversation_id": conv.id,
        "role_preset": conv.role_preset,
        "message": response_text,
    }


@router.post("/assistant/stream")
async def chat_stream(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """SSE streaming chat: events stream real-time tokens."""
    conv = await _get_or_create_conversation(db, req)

    # Save user message
    user_msg = Message(conversation_id=conv.id, role="user", content=req.message)
    db.add(user_msg)
    await db.flush()
    await db.commit()

    # Get history
    history = await _get_history(db, conv.id)

    async def event_generator():
        full_response = ""
        try:
            async for chunk in ai_assistant.chat_stream(
                req.message, req.role_preset, history, req.model
            ):
                full_response += chunk
                yield f"data: {json.dumps({'token': chunk, 'done': False})}\n\n"
            # Save full response after streaming completes
            async with db.begin():
                assistant_msg = Message(
                    conversation_id=conv.id, role="assistant", content=full_response
                )
                db.add(assistant_msg)
            yield f"data: {json.dumps({'token': '', 'done': True, 'conversation_id': conv.id})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations")
async def list_conversations(db: AsyncSession = Depends(get_db), limit: int = 50, offset: int = 0):
    """List conversations with pagination."""
    result = await db.execute(
        select(Conversation).order_by(Conversation.created_at.desc()).offset(offset).limit(limit)
    )
    convs = result.scalars().all()
    return [
        {"id": c.id, "title": c.title, "role_preset": c.role_preset, "created_at": c.created_at.isoformat()}
        for c in convs
    ]


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    """Get conversation with all messages."""
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return {
        "conversation_id": conv.id, "title": conv.title, "role_preset": conv.role_preset,
        "messages": [{"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in messages],
    }


@router.get("/roles")
async def list_roles():
    return ai_assistant.get_role_presets()


class RAGChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    role_preset: str = "tutor"
    model: str = "deepseek-chat"
    top_k: int = 3


@router.post("/assistant/rag")
async def chat_with_rag(req: RAGChatRequest, db: AsyncSession = Depends(get_db)):
    """Chat with RAG: searches local documents and grounds answers in retrieved context."""
    conv = await _get_or_create_conversation(db, ChatRequest(
        message=req.message, conversation_id=req.conversation_id,
        role_preset=req.role_preset, model=req.model,
    ))
    user_msg = Message(conversation_id=conv.id, role="user", content=req.message)
    db.add(user_msg)
    await db.flush()
    history = await _get_history(db, conv.id)

    try:
        response_text = await rag_assistant.chat_with_rag(
            req.message, req.role_preset, history, req.model, req.top_k,
        )
    except Exception as e:
        raise HTTPException(500, f"RAG chat failed: {str(e)}")

    assistant_msg = Message(conversation_id=conv.id, role="assistant", content=response_text)
    db.add(assistant_msg)
    await db.commit()
    return {"conversation_id": conv.id, "role_preset": conv.role_preset, "message": response_text}


@router.post("/assistant/rag/stream")
async def chat_rag_stream(req: RAGChatRequest, db: AsyncSession = Depends(get_db)):
    """SSE streaming version of RAG chat."""
    conv = await _get_or_create_conversation(db, ChatRequest(
        message=req.message, conversation_id=req.conversation_id,
        role_preset=req.role_preset, model=req.model,
    ))
    user_msg = Message(conversation_id=conv.id, role="user", content=req.message)
    db.add(user_msg)
    await db.flush()
    await db.commit()
    history = await _get_history(db, conv.id)

    async def event_generator():
        full = ""
        try:
            async for chunk in rag_assistant.chat_stream_with_rag(
                req.message, req.role_preset, history, req.model, req.top_k,
            ):
                full += chunk
                yield f"data: {json.dumps({'token': chunk, 'done': False})}\n\n"
            async with db.begin():
                db.add(Message(conversation_id=conv.id, role="assistant", content=full))
            yield f"data: {json.dumps({'token': '', 'done': True, 'conversation_id': conv.id})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/search")
async def search_documents(query: str, top_k: int = 5):
    """Search documents without AI (returns raw chunks)."""
    results = rag_assistant.search_only(query, top_k)
    return {"query": query, "results": results, "count": len(results)}


# -- helpers --

async def _get_or_create_conversation(db: AsyncSession, req: ChatRequest) -> Conversation:
    if req.conversation_id:
        result = await db.execute(select(Conversation).where(Conversation.id == req.conversation_id))
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(404, "Conversation not found")
        return conv
    conv = Conversation(title=req.message[:30], role_preset=req.role_preset)
    db.add(conv)
    await db.flush()
    return conv


async def _get_history(db: AsyncSession, conv_id: str) -> list[dict]:
    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    )
    return [{"role": m.role, "content": m.content} for m in result.scalars().all()]
