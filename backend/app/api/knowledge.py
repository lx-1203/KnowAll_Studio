"""Knowledge tree, outline, and mind map API routes"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models import DocumentChunk, KnowledgeTree, Outline
from app.core.knowledge import knowledge_generator

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class GenerateTreeRequest(BaseModel):
    document_id: str
    chunk_ids: list[str] | None = None  # specific chunks, or all if None
    model: str = "deepseek-chat"
    tree_name: str = "知识树"


class GenerateOutlineRequest(BaseModel):
    document_id: str
    chunk_ids: list[str] | None = None
    model: str = "deepseek-chat"


@router.post("/tree/generate")
async def generate_knowledge_tree(req: GenerateTreeRequest, db: AsyncSession = Depends(get_db)):
    """Generate a knowledge tree from document chunks."""
    from sqlalchemy import select

    # Get chunks
    if req.chunk_ids:
        result = await db.execute(
            select(DocumentChunk).where(DocumentChunk.id.in_(req.chunk_ids))
        )
    else:
        result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.doc_id == req.document_id)
            .order_by(DocumentChunk.chunk_index)
        )
    chunks = result.scalars().all()

    if not chunks:
        raise HTTPException(404, "No chunks found for this document")

    chunk_texts = [c.text_content for c in chunks]

    # Generate via API
    try:
        tree_data = await knowledge_generator.generate_tree(chunk_texts, req.model)
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {str(e)}")

    # Save to database
    tree = KnowledgeTree(
        name=req.tree_name,
        doc_ids=[req.document_id],
        tree_data=tree_data,
    )
    db.add(tree)
    await db.commit()
    await db.refresh(tree)

    return {
        "tree_id": tree.id,
        "name": tree.name,
        "tree_data": tree.tree_data,
        "created_at": tree.created_at.isoformat(),
    }


@router.get("/tree/{tree_id}")
async def get_knowledge_tree(tree_id: str, db: AsyncSession = Depends(get_db)):
    """Get a knowledge tree by ID."""
    from sqlalchemy import select
    result = await db.execute(select(KnowledgeTree).where(KnowledgeTree.id == tree_id))
    tree = result.scalar_one_or_none()
    if not tree:
        raise HTTPException(404, "Knowledge tree not found")
    return {
        "tree_id": tree.id,
        "name": tree.name,
        "tree_data": tree.tree_data,
        "created_at": tree.created_at.isoformat(),
        "updated_at": tree.updated_at.isoformat(),
    }


@router.put("/tree/{tree_id}")
async def update_knowledge_tree(tree_id: str, tree_data: dict, db: AsyncSession = Depends(get_db)):
    """Update a knowledge tree (e.g., after drag-and-drop edits)."""
    from sqlalchemy import select
    result = await db.execute(select(KnowledgeTree).where(KnowledgeTree.id == tree_id))
    tree = result.scalar_one_or_none()
    if not tree:
        raise HTTPException(404, "Knowledge tree not found")

    tree.tree_data = tree_data.get("tree_data", tree.tree_data)
    tree.name = tree_data.get("name", tree.name)
    await db.commit()
    return {"status": "updated", "tree_id": tree.id}


class MergeTreesRequest(BaseModel):
    tree_ids: list[str]
    merged_name: str = "合并知识体系"


@router.post("/tree/merge")
async def merge_trees(req: MergeTreesRequest, db: AsyncSession = Depends(get_db)):
    """Merge multiple knowledge trees into one comprehensive tree."""
    from sqlalchemy import select

    if len(req.tree_ids) < 2:
        raise HTTPException(400, "Need at least 2 trees to merge")

    result = await db.execute(
        select(KnowledgeTree).where(KnowledgeTree.id.in_(req.tree_ids))
    )
    trees = result.scalars().all()
    if len(trees) < 2:
        raise HTTPException(404, "Not enough valid trees found")

    # Merge tree data
    merged_nodes = []
    all_doc_ids = []
    for i, tree in enumerate(trees):
        nodes = tree.tree_data.get("tree", {}).get("nodes", [])
        for node in nodes:
            node["id"] = f"m{i}_{node['id']}"
            merged_nodes.append(node)
        all_doc_ids.extend(tree.doc_ids)

    merged_data = {
        "tree": {
            "title": req.merged_name,
            "nodes": merged_nodes,
        }
    }

    merged_tree = KnowledgeTree(
        name=req.merged_name,
        doc_ids=list(set(all_doc_ids)),
        tree_data=merged_data,
    )
    db.add(merged_tree)
    await db.commit()
    await db.refresh(merged_tree)

    return {
        "tree_id": merged_tree.id,
        "name": merged_tree.name,
        "node_count": len(merged_nodes),
        "source_trees": len(trees),
        "tree_data": merged_tree.tree_data,
    }


@router.get("/trees")
async def list_trees(db: AsyncSession = Depends(get_db)):
    """List all knowledge trees."""
    from sqlalchemy import select
    result = await db.execute(select(KnowledgeTree).order_by(KnowledgeTree.updated_at.desc()))
    trees = result.scalars().all()
    return [
        {
            "tree_id": t.id,
            "name": t.name,
            "doc_count": len(t.doc_ids),
            "created_at": t.created_at.isoformat(),
        }
        for t in trees
    ]


@router.post("/outline/generate")
async def generate_outline(req: GenerateOutlineRequest, db: AsyncSession = Depends(get_db)):
    """Generate a markdown outline from document chunks."""
    from sqlalchemy import select

    if req.chunk_ids:
        result = await db.execute(
            select(DocumentChunk).where(DocumentChunk.id.in_(req.chunk_ids))
        )
    else:
        result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.doc_id == req.document_id)
            .order_by(DocumentChunk.chunk_index)
        )
    chunks = result.scalars().all()
    if not chunks:
        raise HTTPException(404, "No chunks found")

    chunk_texts = [c.text_content for c in chunks]

    try:
        markdown_content = await knowledge_generator.generate_outline(chunk_texts, req.model)
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {str(e)}")

    outline = Outline(
        title=f"Outline-{req.document_id[:8]}",
        content_markdown=markdown_content,
    )
    db.add(outline)
    await db.commit()
    await db.refresh(outline)

    return {
        "outline_id": outline.id,
        "title": outline.title,
        "content": outline.content_markdown,
    }
