"""文件分片上传/下载 API — 大文件不阻塞，进度实时可见"""
from __future__ import annotations
import hashlib
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger("knowall.sync_upload")

router = APIRouter(prefix="/api", tags=["sync-upload"])

UPLOAD_DIR = Path(settings.document_dir) / "sync_uploads"
CHUNK_DIR = UPLOAD_DIR / "chunks"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CHUNK_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 5 * 1024 * 1024  # 5MB

# 上传会话（生产环境应使用 Redis）
_upload_sessions: dict[str, dict] = {}


class UploadInitRequest(BaseModel):
    filename: str
    file_size: int
    mime_type: str = "application/octet-stream"
    space_id: str = "default"
    parent_id: str | None = None


class UploadInitResponse(BaseModel):
    upload_id: str
    chunk_size: int
    total_chunks: int
    status: str = "uploading"


class ChunkResponse(BaseModel):
    upload_id: str
    chunk_index: int
    received: int
    total: int
    progress: float


class UploadCompleteResponse(BaseModel):
    file_id: str
    filename: str
    size: int
    url: str
    version: int
    created_at: str


# ── 上传初始化 ─────────────────────────────────────────────────────────

@router.post("/upload/init", response_model=dict)
async def upload_init(req: UploadInitRequest):
    """初始化分片上传，返回 upload_id 和分片信息"""
    upload_id = uuid.uuid4().hex[:12]
    total_chunks = max(1, (req.file_size + CHUNK_SIZE - 1) // CHUNK_SIZE)

    _upload_sessions[upload_id] = {
        "filename": req.filename,
        "file_size": req.file_size,
        "mime_type": req.mime_type,
        "space_id": req.space_id,
        "parent_id": req.parent_id,
        "total_chunks": total_chunks,
        "received_chunks": set(),
        "received_bytes": 0,
        "status": "uploading",
        "created_at": None,
    }

    logger.info("上传初始化: id=%s file=%s chunks=%d", upload_id, req.filename, total_chunks)

    return {
        "code": 0,
        "data": {
            "upload_id": upload_id,
            "chunk_size": CHUNK_SIZE,
            "total_chunks": total_chunks,
            "status": "uploading",
        },
    }


# ── 分片上传 ───────────────────────────────────────────────────────────

@router.put("/upload/{upload_id}/chunk/{chunk_index}")
async def upload_chunk(
    upload_id: str,
    chunk_index: int,
    request: Request,
    x_chunk_hash: str | None = Header(None),
):
    """上传单个分片（接收原始二进制流，Content-Type: application/octet-stream）"""
    session = _upload_sessions.get(upload_id)
    if not session:
        raise HTTPException(404, "上传会话不存在或已过期")

    if session["status"] != "uploading":
        raise HTTPException(400, "上传状态异常")

    # 读取原始二进制流
    chunk_data = await request.body()

    # 校验 hash（按规范 3.2.2：X-Chunk-Hash: sha256=<hash>）
    if x_chunk_hash:
        algo, _, expected = x_chunk_hash.partition("=")
        actual = hashlib.new(algo or "sha256", chunk_data).hexdigest()
        if actual != expected:
            raise HTTPException(400, f"分片 hash 校验失败")

    # 写入分片文件
    chunk_path = CHUNK_DIR / f"{upload_id}_{chunk_index:06d}"
    chunk_path.write_bytes(chunk_data)
    session["received_chunks"].add(chunk_index)
    session["received_bytes"] += len(chunk_data)

    progress = session["received_bytes"] / session["file_size"] if session["file_size"] else 0

    return {
        "code": 0,
        "data": {
            "upload_id": upload_id,
            "chunk_index": chunk_index,
            "received": session["received_bytes"],
            "total": session["file_size"],
            "progress": round(progress, 2),
        },
    }


# ── 完成上传 ───────────────────────────────────────────────────────────

@router.post("/upload/{upload_id}/complete")
async def upload_complete(upload_id: str):
    """合并分片，生成最终文件"""
    session = _upload_sessions.get(upload_id)
    if not session:
        raise HTTPException(404, "上传会话不存在或已过期")

    total = session["total_chunks"]
    received = session["received_chunks"]

    # 检查分片完整性
    missing = set(range(total)) - received
    if missing:
        raise HTTPException(400, f"缺少分片: {sorted(missing)}")

    # 合并分片
    filename = session["filename"]
    file_id = uuid.uuid4().hex[:16]
    base, ext = os.path.splitext(filename)
    final_name = f"{base}_{file_id}{ext}"  # 避免同名覆盖
    final_path = UPLOAD_DIR / final_name

    with open(final_path, "wb") as dst:
        for i in range(total):
            chunk_path = CHUNK_DIR / f"{upload_id}_{i:06d}"
            dst.write(chunk_path.read_bytes())
            chunk_path.unlink(missing_ok=True)  # 清理分片

    file_size = final_path.stat().st_size
    session["status"] = "completed"

    import datetime
    now = datetime.datetime.utcnow().isoformat() + "Z"

    # 持久化文件版本
    from app.core.sync import sync_store
    current_version = await sync_store.get_current_file_version(file_id)
    new_version = current_version + 1
    await sync_store.record_file_version(
        file_id=file_id,
        version=new_version,
        filename=filename,
        file_size=file_size,
        storage_path=str(final_path),
        updated_by="user",
    )

    logger.info("上传完成: file_id=%s name=%s size=%d version=%d", file_id, final_name, file_size, new_version)

    return {
        "code": 0,
        "data": {
            "file_id": file_id,
            "filename": filename,
            "size": file_size,
            "url": f"/api/download/{file_id}",
            "version": new_version,
            "created_at": now,
        },
    }


# ── 文件下载 ───────────────────────────────────────────────────────────

@router.get("/download/{file_id}")
async def download_file(file_id: str):
    """下载文件：小文件直传，大文件（>10MB）302 跳转"""
    # 查找文件
    for f in UPLOAD_DIR.iterdir():
        if f.is_file() and file_id in f.name:
            file_size = f.stat().st_size
            if file_size > 10 * 1024 * 1024:
                # 大文件返回直接路径（生产环境应生成预签名 URL）
                return FileResponse(
                    f,
                    media_type="application/octet-stream",
                    filename=f.name,
                )
            return FileResponse(
                f,
                media_type="application/octet-stream",
                filename=f.name,
            )

    raise HTTPException(404, "文件不存在")


# ── 事件补拉 ───────────────────────────────────────────────────────────

@router.get("/events/catchup")
async def catchup_events(space_id: str = "default", from_seq: int = 0):
    """客户端重连后补拉遗漏的事件（从持久化存储读取）"""
    from app.core.sync import sync_store
    events, current_seq = await sync_store.get_events_since(space_id, from_seq)
    return {"code": 0, "events": events, "current_seq": current_seq}
