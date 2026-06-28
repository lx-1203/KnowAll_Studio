"""版本管理与冲突检测辅助端点"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["version-control"])

# 简易版本存储（生产环境应使用数据库）
_resource_versions: dict[str, int] = {}


class VersionCheckRequest(BaseModel):
    resource_type: str  # "document" | "file" | "task_list"
    resource_id: str
    base_version: int


class VersionCheckResponse(BaseModel):
    current_version: int
    is_latest: bool
    conflict: bool


@router.post("/version/check", response_model=dict)
async def check_version(req: VersionCheckRequest):
    """校验客户端版本：返回是否冲突"""
    key = f"{req.resource_type}:{req.resource_id}"
    current = _resource_versions.get(key, 0)

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
    """递增版本号（写入成功后调用）"""
    key = f"{resource_type}:{resource_id}"
    _resource_versions[key] = _resource_versions.get(key, 0) + 1
    return {
        "code": 0,
        "data": {"new_version": _resource_versions[key]},
    }
