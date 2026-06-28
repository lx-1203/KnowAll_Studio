"""Knowledge Points CRUD API — user-scoped knowledge base"""
import re
import html
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel, field_validator

from app.database import get_db
from app.models.user import KnowledgePoint, User
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/knowledge-points", tags=["knowledge-points"])

# Strip HTML tags for input sanitization
_TAG_RE = re.compile(r"<[^>]*>")


def _sanitize(text: str) -> str:
    """Remove HTML tags from user input to prevent XSS."""
    return _TAG_RE.sub("", text or "")


def _sanitize_tags(tags: list) -> list[str]:
    """Sanitize each tag in a list."""
    if not tags:
        return []
    return [_sanitize(t)[:50] for t in tags if _sanitize(t).strip()]


# ---- Request Schemas ----


class CreateKnowledgePointRequest(BaseModel):
    title: str
    content: str
    tags: list[str] = []
    category: str = ""

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = _sanitize(v.strip())
        if not v or len(v) > 500:
            raise ValueError("标题不能为空且不超过 500 字符")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("内容不能为空")
        if len(v) > 50000:
            raise ValueError("内容不能超过 50000 字符")
        return _sanitize(v)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list) -> list:
        return _sanitize_tags(v)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        return _sanitize(v.strip())[:200]


class UpdateKnowledgePointRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    category: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = _sanitize(v.strip())
        if not v or len(v) > 500:
            raise ValueError("标题不能为空且不超过 500 字符")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("内容不能为空")
        if len(v) > 50000:
            raise ValueError("内容不能超过 50000 字符")
        return _sanitize(v)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list | None) -> list | None:
        if v is None:
            return None
        return _sanitize_tags(v)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _sanitize(v.strip())[:200]


# ---- Helper ----

def _kp_to_response(kp: KnowledgePoint) -> dict:
    """Convert a KnowledgePoint ORM object to a safe dict response."""
    return {
        "id": kp.id,
        "title": kp.title,
        "content": kp.content,
        "tags": kp.tags or [],
        "category": kp.category or "",
        "created_at": kp.created_at.isoformat() if kp.created_at else None,
        "updated_at": kp.updated_at.isoformat() if kp.updated_at else None,
    }


# ---- Routes ----

@router.post("", status_code=201)
async def create_knowledge_point(
    req: CreateKnowledgePointRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建一条知识点（归属于当前登录用户）"""
    kp = KnowledgePoint(
        user_id=current_user.id,
        title=req.title,
        content=req.content,
        tags=req.tags,
        category=req.category,
    )
    db.add(kp)
    await db.commit()
    await db.refresh(kp)
    return _kp_to_response(kp)


@router.get("")
async def list_knowledge_points(
    tag: str | None = Query(None, description="按标签筛选"),
    category: str | None = Query(None, description="按分类筛选"),
    search: str | None = Query(None, description="标题/内容关键词搜索"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的知识点列表，支持筛选、搜索和分页"""
    conditions = [KnowledgePoint.user_id == current_user.id]

    if category:
        conditions.append(KnowledgePoint.category == _sanitize(category.strip())[:200])
    if search:
        search_term = f"%{_sanitize(search.strip())}%"
        conditions.append(
            (KnowledgePoint.title.like(search_term)) |
            (KnowledgePoint.content.like(search_term))
        )

    base_query = select(KnowledgePoint).where(and_(*conditions))

    # Count total
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Fetch page
    result = await db.execute(
        base_query
        .order_by(KnowledgePoint.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = result.scalars().all()

    # Client-side tag filtering (JSON field in SQLite)
    if tag:
        tag_clean = _sanitize(tag.strip())
        items = [kp for kp in items if tag_clean in (kp.tags or [])]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_kp_to_response(kp) for kp in items],
    }


@router.get("/{kp_id}")
async def get_knowledge_point(
    kp_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单条知识点（仅限本人）"""
    result = await db.execute(
        select(KnowledgePoint).where(
            and_(KnowledgePoint.id == kp_id, KnowledgePoint.user_id == current_user.id)
        )
    )
    kp = result.scalar_one_or_none()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在或无权访问")
    return _kp_to_response(kp)


@router.put("/{kp_id}")
async def update_knowledge_point(
    kp_id: str,
    req: UpdateKnowledgePointRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新知识点（仅限本人）。只更新请求中提供的字段。"""
    result = await db.execute(
        select(KnowledgePoint).where(
            and_(KnowledgePoint.id == kp_id, KnowledgePoint.user_id == current_user.id)
        )
    )
    kp = result.scalar_one_or_none()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在或无权访问")

    if req.title is not None:
        kp.title = req.title
    if req.content is not None:
        kp.content = req.content
    if req.tags is not None:
        kp.tags = req.tags
    if req.category is not None:
        kp.category = req.category

    kp.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await db.refresh(kp)
    return _kp_to_response(kp)


@router.delete("/{kp_id}")
async def delete_knowledge_point(
    kp_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除知识点（仅限本人）"""
    result = await db.execute(
        select(KnowledgePoint).where(
            and_(KnowledgePoint.id == kp_id, KnowledgePoint.user_id == current_user.id)
        )
    )
    kp = result.scalar_one_or_none()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在或无权访问")
    await db.delete(kp)
    await db.commit()
    return {"status": "deleted", "id": kp_id}
