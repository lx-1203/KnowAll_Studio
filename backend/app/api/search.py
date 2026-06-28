"""RAG search API routes"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.core.rag import search, rag_query, get_index_stats, index_chunks
from app.models import DocumentChunk

router = APIRouter(prefix="/api/v1/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/")
async def search_chunks(req: SearchRequest):
    """Search for relevant document chunks using vector similarity."""
    results = search(req.query, n_results=req.top_k)
    return {"query": req.query, "results": results, "count": len(results)}


@router.post("/rag")
async def retrieve_and_generate(req: SearchRequest):
    """Retrieve relevant context for RAG (to be combined with LLM call)."""
    context = rag_query(req.query, top_k=req.top_k)
    return {"query": req.query, "context": context, "has_results": bool(context)}


@router.post("/index")
async def index_document_chunks(doc_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    """Index all chunks of a document into vector store."""
    from sqlalchemy import select
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.doc_id == doc_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = result.scalars().all()

    if not chunks:
        raise HTTPException(404, "No chunks found for this document")

    chunk_dicts = [
        {
            "id": c.id,
            "text": c.text_content,
            "metadata": {"doc_id": c.doc_id, "chunk_index": c.chunk_index, "page_range": c.page_range, "token_count": c.token_count},
        }
        for c in chunks
    ]

    count = index_chunks(chunk_dicts)

    # Update vector_id in database for tracking/deletion
    for c in chunks:
        c.vector_id = c.id  # ChromaDB uses the chunk UUID as the vector ID
    await db.commit()

    return {"indexed": count, "doc_id": doc_id}


@router.get("/stats")
async def search_stats():
    """Get vector index statistics."""
    return get_index_stats()
