"""Document upload and parsing API routes"""
import os
import hashlib
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.database import get_db
from app.models import Document, DocumentChunk
from app.core.parsing import parser, cleaner, splitter
from app.config import settings

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# MIME type mapping for raw file serving
MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "csv": "text/csv",
    "md": "text/markdown",
    "markdown": "text/markdown",
    "txt": "text/plain",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "webp": "image/webp",
    "html": "text/html",
    "json": "application/json",
    "xml": "application/xml",
    "yaml": "text/yaml",
    "yml": "text/yaml",
}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Upload and parse a document. Returns document ID and chunks."""
    # Validate file
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    supported = {"pdf", "docx", "pptx", "md", "markdown", "txt",
                 "png", "jpg", "jpeg", "gif", "bmp", "webp",
                 "xmind", "html",
                 "py", "js", "ts", "jsx", "tsx", "java", "cpp", "c",
                 "go", "rs", "sql", "yaml", "yml", "json", "xml", "css"}
    if ext not in supported:
        raise HTTPException(400, f"Unsupported file type: .{ext}. Supported: {supported}")

    if file.size and file.size > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(400, f"File too large. Max {settings.max_upload_size_mb}MB")

    # Save original file locally
    import hashlib
    content = await file.read()
    sha256 = hashlib.sha256(content).hexdigest()
    file_dir = os.path.join(settings.document_dir, sha256[:2])
    os.makedirs(file_dir, exist_ok=True)
    local_path = os.path.join(file_dir, sha256)
    with open(local_path, "wb") as f:
        f.write(content)

    # Parse document
    try:
        parsed = await parser.parse(local_path, ext)
    except Exception as e:
        raise HTTPException(500, f"Failed to parse document: {str(e)}")

    # Clean text
    cleaned_text = cleaner.clean(parsed.text)

    # Split into chunks
    chunks = splitter.split(cleaned_text, parsed.page_count)

    # Save to database
    doc = Document(
        filename=file.filename,
        file_type=ext,
        file_size=len(content),
        sha256=sha256,
        local_path=local_path,
        status="ready",
        page_count=parsed.page_count,
        metadata_=parsed.metadata,
    )
    db.add(doc)
    await db.flush()  # ensure doc.id is generated before creating chunks

    for chunk in chunks:
        db.add(DocumentChunk(
            doc_id=doc.id,
            chunk_index=chunk.index,
            content_hash=chunk.content_hash,
            text_content=chunk.text,
            token_count=chunk.token_count,
            page_range=chunk.page_range,
        ))

    await db.commit()

    return {
        "document_id": doc.id,
        "filename": file.filename,
        "file_type": ext,
        "status": "ready",
        "page_count": parsed.page_count,
        "chunks": [
            {
                "id": None,  # will be filled after refresh
                "index": c.index,
                "token_count": c.token_count,
                "page_range": c.page_range,
                "preview": c.text[:200] + "..." if len(c.text) > 200 else c.text,
            }
            for c in chunks
        ],
        "total_chunks": len(chunks),
    }




class URLImportRequest(BaseModel):
    url: str


@router.post("/import-url")
async def import_from_url(req: URLImportRequest, db: AsyncSession = Depends(get_db)):
    """Import content from a URL (web page)."""
    import tempfile
    try:
        parsed = await parser.parse(req.url, "url")
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch URL: {str(e)}")

    cleaned_text = cleaner.clean(parsed.text)
    chunks = splitter.split(cleaned_text, 1)

    # Use URL hash as document identifier
    sha256 = hashlib.sha256(req.url.encode()).hexdigest()
    file_dir = os.path.join(settings.document_dir, sha256[:2])
    os.makedirs(file_dir, exist_ok=True)
    local_path = os.path.join(file_dir, sha256)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(f"URL: {req.url}\n\n{cleaned_text}")

    doc = Document(
        filename=req.url[:80],
        file_type="url",
        file_size=len(cleaned_text.encode()),
        sha256=sha256,
        local_path=local_path,
        status="ready",
        page_count=1,
        metadata_={"source_url": req.url},
    )
    db.add(doc)
    await db.flush()
    for chunk in chunks:
        db.add(DocumentChunk(
            doc_id=doc.id, chunk_index=chunk.index,
            content_hash=chunk.content_hash, text_content=chunk.text,
            token_count=chunk.token_count, page_range=chunk.page_range,
        ))
    await db.commit()

    return {"document_id": doc.id, "filename": req.url[:80], "file_type": "url",
            "status": "ready", "total_chunks": len(chunks),
            "chunks": [{"index": c.index, "preview": c.text[:200]} for c in chunks]}


@router.get("/")
async def list_documents(db: AsyncSession = Depends(get_db)):
    """List all uploaded documents."""
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    docs = result.scalars().all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "status": d.status,
            "page_count": d.page_count,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.get("/{doc_id}/chunks")
async def get_document_chunks(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Get all chunks for a document."""
    # Verify document exists
    result = await db.execute(select(Document).where(Document.id == doc_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Document not found")
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.doc_id == doc_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = result.scalars().all()
    return [
        {
            "id": c.id,
            "index": c.chunk_index,
            "text": c.text_content,
            "token_count": c.token_count,
            "page_range": c.page_range,
        }
        for c in chunks
    ]


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a document and its chunks."""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Delete local file
    if doc.local_path and os.path.exists(doc.local_path):
        os.remove(doc.local_path)

    # Delete cached slide images if any
    slide_cache_dir = os.path.join(settings.export_dir, doc_id)
    if os.path.exists(slide_cache_dir):
        import shutil
        shutil.rmtree(slide_cache_dir)

    await db.delete(doc)
    await db.commit()
    return {"status": "deleted"}


@router.get("/{doc_id}/raw")
async def get_document_raw(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Serve the original file for client-side preview rendering."""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    if not doc.local_path or not os.path.exists(doc.local_path):
        raise HTTPException(404, "原始文件不可用")
    media_type = MIME_TYPES.get(doc.file_type, "application/octet-stream")
    return FileResponse(
        doc.local_path,
        media_type=media_type,
        filename=doc.filename.encode("ascii", "ignore").decode(),
    )


@router.get("/{doc_id}/slides")
async def get_pptx_slides(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Return slide metadata (count and image URLs) for a PPTX document."""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc.file_type not in ("pptx",):
        raise HTTPException(400, "幻灯片预览仅支持 PPTX 格式")
    if not doc.local_path or not os.path.exists(doc.local_path):
        raise HTTPException(404, "原始文件不可用")

    from app.core.parsing.pptx_renderer import pptx_renderer
    slide_count = pptx_renderer.get_slide_count(doc.local_path)
    return {
        "document_id": doc_id,
        "slide_count": slide_count,
        "slides": [
            {
                "index": i,
                "image_url": f"/api/v1/documents/{doc_id}/slides/{i}/image",
            }
            for i in range(slide_count)
        ],
    }


@router.get("/{doc_id}/slides/{slide_index}/image")
async def get_pptx_slide_image(doc_id: str, slide_index: int, db: AsyncSession = Depends(get_db)):
    """Return a single PPTX slide rendered as PNG image."""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    if not doc.local_path or not os.path.exists(doc.local_path):
        raise HTTPException(404, "原始文件不可用")

    from app.core.parsing.pptx_renderer import pptx_renderer
    try:
        image_bytes = pptx_renderer.render_slide(doc.local_path, slide_index)
    except IndexError:
        raise HTTPException(404, f"Slide {slide_index} not found")
    except Exception as e:
        raise HTTPException(500, f"幻灯片渲染失败: {str(e)}")

    from fastapi.responses import Response
    return Response(content=image_bytes, media_type="image/png")
