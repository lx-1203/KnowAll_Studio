"""Knowledge tree, outline, and mind map API routes"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.database import get_db
from app.models import Document, DocumentChunk, KnowledgeTree, Outline, KnowledgeEdge, KnowledgeSummary, KnowledgePointNode, KnowledgeCoverage
from app.core.knowledge import knowledge_generator
from app.core.knowledge.summary_generator import summary_generator
from app.core.parsing.outline_extractor import outline_extractor
from app.core.auth import get_optional_user, get_user_id, load_user_api_keys

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
async def generate_knowledge_tree(
    req: GenerateTreeRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Generate a knowledge tree from document chunks."""
    await load_user_api_keys(get_user_id(current_user), db)
    # Get document to check for native outline and image analyses
    doc_result = await db.execute(select(Document).where(Document.id == req.document_id))
    doc = doc_result.scalar_one_or_none()

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

    # Extract structure context from document metadata if available
    structure_context = ""
    image_descriptions = None
    if doc and doc.metadata_:
        headings = doc.metadata_.get("headings", [])
        if headings:
            # Reconstruct heading nodes for context injection
            from app.core.parsing.docling_parser import HeadingNode
            heading_nodes = _dicts_to_nodes(headings)
            structure_context = outline_extractor.inject_context(heading_nodes)

        # Check for image analysis results
        analyses = doc.metadata_.get("image_analyses", [])
        if analyses:
            image_descriptions = [a["analysis"] for a in analyses]

    # Generate via API
    try:
        tree_data = await knowledge_generator.generate_tree(
            chunk_texts, req.model,
            structure_context=structure_context,
            image_descriptions=image_descriptions,
        )
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
async def list_trees(
    limit: int = 1000,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all knowledge trees."""
    from sqlalchemy import select
    result = await db.execute(
        select(KnowledgeTree).order_by(KnowledgeTree.updated_at.desc()).offset(offset).limit(limit)
    )
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
async def generate_outline(
    req: GenerateOutlineRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Generate a markdown outline from document chunks."""
    await load_user_api_keys(get_user_id(current_user), db)
    # Get document for structure context
    doc_result = await db.execute(select(Document).where(Document.id == req.document_id))
    doc = doc_result.scalar_one_or_none()

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

    # Extract structure context
    structure_context = ""
    if doc and doc.metadata_:
        headings = doc.metadata_.get("headings", [])
        if headings:
            heading_nodes = _dicts_to_nodes(headings)
            structure_context = outline_extractor.inject_context(heading_nodes)

    try:
        markdown_content = await knowledge_generator.generate_outline(
            chunk_texts, req.model, structure_context=structure_context)
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


# ===== Knowledge Graph Cross-References (Edges) =====

class CreateEdgeRequest(BaseModel):
    tree_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str = "related_to"  # related_to/prerequisite/extends/contradicts/example_of
    description: str = ""


@router.post("/edges")
async def create_edge(req: CreateEdgeRequest, db: AsyncSession = Depends(get_db)):
    """Create a cross-reference edge between two knowledge nodes."""
    valid_types = {"related_to", "prerequisite", "extends", "contradicts", "example_of"}
    if req.relation_type not in valid_types:
        raise HTTPException(400, f"Invalid relation_type. Must be one of: {valid_types}")

    edge = KnowledgeEdge(
        tree_id=req.tree_id,
        source_node_id=req.source_node_id,
        target_node_id=req.target_node_id,
        relation_type=req.relation_type,
        description=req.description,
    )
    db.add(edge)
    await db.commit()
    await db.refresh(edge)
    return {"edge_id": edge.id, "source": edge.source_node_id, "target": edge.target_node_id, "relation_type": edge.relation_type}


@router.get("/edges/{tree_id}")
async def list_edges(tree_id: str, db: AsyncSession = Depends(get_db)):
    """Get all cross-reference edges for a knowledge tree."""
    result = await db.execute(
        select(KnowledgeEdge).where(KnowledgeEdge.tree_id == tree_id)
    )
    edges = result.scalars().all()
    return [
        {
            "id": e.id,
            "source_node_id": e.source_node_id,
            "target_node_id": e.target_node_id,
            "relation_type": e.relation_type,
            "description": e.description,
        }
        for e in edges
    ]


@router.delete("/edges/{edge_id}")
async def delete_edge(edge_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a cross-reference edge."""
    result = await db.execute(select(KnowledgeEdge).where(KnowledgeEdge.id == edge_id))
    edge = result.scalar_one_or_none()
    if not edge:
        raise HTTPException(404, "Edge not found")
    await db.delete(edge)
    await db.commit()
    return {"status": "deleted"}


def _dicts_to_nodes(dicts: list[dict]) -> list:
    """Convert heading dicts from metadata back to HeadingNode-like objects."""
    from app.core.parsing.docling_parser import HeadingNode
    nodes = []
    for d in dicts:
        node = HeadingNode(
            id=d.get("id", ""),
            label=d.get("label", ""),
            level=d.get("level", 1),
            page=d.get("page", 0),
            children=_dicts_to_nodes(d.get("children", [])),
        )
        nodes.append(node)
    return nodes
