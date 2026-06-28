"""版本管理与冲突检测 — 持久化版本号 + 文件版本历史 + 回滚"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.sync import sync_store

router = APIRouter(prefix="/api", tags=["version-control"])


class VersionCheckRequest(BaseModel):
    resource_type: str  # "document" | "file" | "task_list"
    resource_id: str
    base_version: int


@router.post("/version/check", response_model=dict)
async def check_version(req: VersionCheckRequest):
    """校验客户端版本：返回是否冲突（基于持久化版本号）"""
    current = await sync_store.get_room_version(f"{req.resource_type}:{req.resource_id}")

    return {
        "code": 0,
        "data": {
            "current_version": current,
            "is_latest": req.base_version >= current,
            "conflict": req.base_version < current,
        },
    }


@router.post("/version/increment")
async def increment_version(resource_type: str, resource_id: str):
    """递增版本号（写入成功后调用）。将写入操作日志来驱动版本号递增。"""
    room_id = f"{resource_type}:{resource_id}"
    current = await sync_store.get_room_version(room_id)
    new_version = current + 1
    await sync_store.append_op_log(
        room_id=room_id,
        version=new_version,
        user_id="system",
        operation="version_increment",
        data={"resource_type": resource_type, "resource_id": resource_id},
    )
    return {
        "code": 0,
        "data": {"new_version": new_version},
    }


# ── 文件版本历史 ───────────────────────────────────────────────────────

@router.get("/file/{file_id}/versions")
async def file_versions(file_id: str):
    """获取文件版本历史列表（持久化，保留最近 10 个版本）"""
    versions = await sync_store.get_file_versions(file_id)
    current = await sync_store.get_current_file_version(file_id)
    return {
        "code": 0,
        "data": {
            "file_id": file_id,
            "current_version": current,
            "versions": versions,
        },
    }


class RollbackRequest(BaseModel):
    target_version: int


@router.post("/file/{file_id}/rollback")
async def file_rollback(file_id: str, req: RollbackRequest):
    """回滚到指定版本。以目标版本内容创建一个新版本（版本号 +1）。"""
    versions = await sync_store.get_file_versions(file_id)
    target = next((v for v in versions if v["version"] == req.target_version), None)
    if not target:
        raise HTTPException(404, f"版本 {req.target_version} 不存在")

    current = await sync_store.get_current_file_version(file_id)
    new_version = current + 1
    await sync_store.record_file_version(
        file_id=file_id,
        version=new_version,
        filename=target["filename"],
        file_size=target["file_size"],
        storage_path=f"rollback_to_v{req.target_version}",
        updated_by="rollback",
    )

    return {
        "code": 0,
        "data": {
            "file_id": file_id,
            "new_version": new_version,
            "rolled_back_from": req.target_version,
            "filename": target["filename"],
        },
    }
