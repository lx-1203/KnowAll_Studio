"""User profile, password, and third-party binding API"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.user_bind import UserBind
from app.models.user_history import UserHistory
from app.core.auth import get_current_user, hash_password, verify_password
from app.schemas import (
    UserProfileResponse,
    UpdateProfileRequest,
    ChangePasswordRequest,
    UserBindItem,
    BindAccountRequest,
    UserHistoryItem,
    UserHistoryListResponse,
    AddUserAPIKeyRequest,
    UserAPIKeyItem,
)
from app.models import APIKey
from app.core.crypto import encrypt_api_key, decrypt_api_key

router = APIRouter(prefix="/api/v1/user", tags=["user"])


# ==================== Profile ====================

@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile information."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "nickname": current_user.nickname or "",
        "phone": current_user.phone or "",
        "avatar_url": current_user.avatar_url or "",
        "is_active": bool(current_user.is_active),
        "created_at": current_user.created_at.isoformat() if current_user.created_at else "",
        "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None,
    }


@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user profile (nickname, phone, avatar_url, email)."""
    if req.nickname is not None:
        if len(req.nickname) > 100:
            raise HTTPException(status_code=400, detail="昵称长度不能超过 100 字符")
        current_user.nickname = req.nickname.strip()

    if req.phone is not None:
        phone = req.phone.strip()
        if phone and not phone.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            raise HTTPException(status_code=400, detail="手机号格式不正确")
        if len(phone) > 20:
            raise HTTPException(status_code=400, detail="手机号长度不能超过 20 字符")
        current_user.phone = phone

    if req.avatar_url is not None:
        url = req.avatar_url.strip()
        if len(url) > 500:
            raise HTTPException(status_code=400, detail="头像 URL 长度不能超过 500 字符")
        current_user.avatar_url = url

    if req.email is not None:
        email = req.email.strip().lower()
        if email != current_user.email:
            existing = await db.execute(select(User).where(User.email == email))
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=409, detail="该邮箱已被使用")
            if len(email) > 255:
                raise HTTPException(status_code=400, detail="邮箱长度不能超过 255 字符")
            current_user.email = email

    await db.commit()
    await db.refresh(current_user)

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "nickname": current_user.nickname or "",
        "phone": current_user.phone or "",
        "avatar_url": current_user.avatar_url or "",
        "is_active": bool(current_user.is_active),
        "created_at": current_user.created_at.isoformat() if current_user.created_at else "",
        "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None,
    }


# ==================== Password ====================

@router.put("/password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change account password. Requires old password verification."""
    if not verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")

    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码不能少于 6 个字符")
    if len(req.new_password) > 128:
        raise HTTPException(status_code=400, detail="新密码不能超过 128 个字符")
    if req.old_password == req.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")

    current_user.password_hash = hash_password(req.new_password)
    await db.commit()

    return {"detail": "密码修改成功"}


# ==================== Third-party Binding ====================

@router.get("/binds", response_model=list[UserBindItem])
async def get_binds(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's third-party account bindings."""
    result = await db.execute(
        select(UserBind).where(UserBind.user_id == current_user.id)
    )
    binds = result.scalars().all()

    # Supported providers with defaults
    supported = {"wechat": "微信", "qq": "QQ", "github": "GitHub", "google": "Google"}
    existing_providers = {b.provider for b in binds}

    items = []
    for b in binds:
        items.append(UserBindItem(
            id=b.id,
            provider=b.provider,
            provider_name=b.provider_name or supported.get(b.provider, b.provider),
            is_bound=b.is_bound,
            bound_at=b.bound_at.isoformat() if b.bound_at else None,
        ))

    # Add unbound providers
    for provider, name in supported.items():
        if provider not in existing_providers:
            items.append(UserBindItem(
                id="",
                provider=provider,
                provider_name=name,
                is_bound=False,
                bound_at=None,
            ))

    return items


@router.post("/bind")
async def bind_account(
    req: BindAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bind a third-party account."""
    allowed = {"wechat", "qq", "github", "google"}
    if req.provider not in allowed:
        raise HTTPException(status_code=400, detail=f"不支持的平台，仅支持: {', '.join(sorted(allowed))}")

    existing = await db.execute(
        select(UserBind).where(
            UserBind.user_id == current_user.id,
            UserBind.provider == req.provider,
        )
    )
    bind = existing.scalar_one_or_none()

    if bind and bind.is_bound:
        raise HTTPException(status_code=409, detail=f"已绑定 {req.provider} 账号")

    if bind:
        bind.is_bound = True
        bind.provider_name = req.provider_name or bind.provider_name
        bind.provider_uid = req.provider_uid or bind.provider_uid
        bind.bound_at = None  # will be updated by default
    else:
        bind = UserBind(
            user_id=current_user.id,
            provider=req.provider,
            provider_name=req.provider_name,
            provider_uid=req.provider_uid,
        )
        db.add(bind)

    await db.commit()
    await db.refresh(bind)

    return {"detail": f"成功绑定 {req.provider} 账号", "bind_id": bind.id}


@router.delete("/bind/{provider}")
async def unbind_account(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unbind a third-party account."""
    result = await db.execute(
        select(UserBind).where(
            UserBind.user_id == current_user.id,
            UserBind.provider == provider,
            UserBind.is_bound == True,
        )
    )
    bind = result.scalar_one_or_none()

    if not bind:
        raise HTTPException(status_code=404, detail="未找到该绑定记录")

    from app.models import now as model_now
    bind.is_bound = False
    bind.unbound_at = model_now()
    await db.commit()

    return {"detail": f"已解除 {provider} 账号绑定"}


# ==================== Operation History ====================

@router.get("/history", response_model=UserHistoryListResponse)
async def get_history(
    page: int = 1,
    page_size: int = 20,
    action_type: str = "",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's operation history with pagination."""
    if page < 1:
        raise HTTPException(status_code=400, detail="页码必须大于 0")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="每页条数需在 1-100 之间")

    base_query = select(UserHistory).where(UserHistory.user_id == current_user.id)
    count_query = select(UserHistory).where(UserHistory.user_id == current_user.id)

    if action_type:
        base_query = base_query.where(UserHistory.action_type == action_type)
        count_query = count_query.where(UserHistory.action_type == action_type)

    # Count total
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count()).select_from(count_query.subquery())
    )
    total = count_result.scalar() or 0

    # Fetch page
    offset = (page - 1) * page_size
    result = await db.execute(
        base_query.order_by(UserHistory.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    records = result.scalars().all()

    items = [
        UserHistoryItem(
            id=r.id,
            action_type=r.action_type,
            action_label=r.action_label or "",
            resource_type=r.resource_type or "",
            resource_id=r.resource_id or "",
            detail=r.detail or "",
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in records
    ]

    return UserHistoryListResponse(total=total, items=items)


@router.post("/history", status_code=201)
async def create_history(
    action_type: str = "",
    action_label: str = "",
    resource_type: str = "",
    resource_id: str = "",
    detail: str = "",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record a user operation history entry (called internally by other modules)."""
    valid_types = {"browse", "quiz", "flashcard", "document", "study", "game", "order", "favorite", "search", "chat"}
    if action_type and action_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"不支持的操作类型: {action_type}")

    record = UserHistory(
        user_id=current_user.id,
        action_type=action_type or "browse",
        action_label=action_label,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return {"id": record.id, "detail": "记录已保存"}


# ==================== User API Keys ====================

_PROVIDER_DEFAULTS = {
    "deepseek": "https://api.deepseek.com/anthropic",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "ollama": "http://localhost:11434/v1",
}


@router.get("/keys", response_model=list[UserAPIKeyItem])
async def get_user_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's saved API keys (masked)."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.user_id == current_user.id,
            APIKey.is_active == True,
        )
    )
    keys = result.scalars().all()
    return [
        UserAPIKeyItem(
            id=k.id,
            provider=k.provider,
            key_alias=k.key_alias or "",
            key_masked="****" + k.key_encrypted[-6:] if len(k.key_encrypted) > 6 else "****",
            base_url="",
            is_active=bool(k.is_active),
            created_at=k.created_at.isoformat() if k.created_at else "",
        )
        for k in keys
    ]


@router.post("/keys", status_code=201)
async def add_user_key(
    req: AddUserAPIKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add or update an API key for the current user.
    If a key for the same provider already exists, it will be updated.
    """
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API Key 不能为空")
    if not req.provider.strip():
        raise HTTPException(status_code=400, detail="provider 不能为空")

    allowed = {"openai", "deepseek", "anthropic", "qwen", "zhipu", "ernie", "kimi", "ollama"}
    if req.provider not in allowed:
        raise HTTPException(status_code=400, detail=f"不支持的 provider，支持: {', '.join(sorted(allowed))}")

    key_encrypted = encrypt_api_key(req.api_key.strip())

    # Check if user already has a key for this provider
    result = await db.execute(
        select(APIKey).where(
            APIKey.user_id == current_user.id,
            APIKey.provider == req.provider,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.key_encrypted = key_encrypted
        existing.key_alias = req.key_alias.strip() or existing.key_alias
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        key_id = existing.id
        action = "updated"
    else:
        key = APIKey(
            user_id=current_user.id,
            provider=req.provider,
            key_encrypted=key_encrypted,
            key_alias=req.key_alias.strip(),
            permission_level="personal",
        )
        db.add(key)
        await db.commit()
        await db.refresh(key)
        key_id = key.id
        action = "added"

    # Dynamically register the key with api_client for immediate use
    from app.core.api_scheduler import api_client
    base_url = req.base_url.strip() or _PROVIDER_DEFAULTS.get(req.provider, "")

    # Model aliases that callers may use to reference this provider
    _PROVIDER_MODEL_ALIASES = {
        "deepseek": ["deepseek", "deepseek-chat", "deepseek-reasoner"],
        "openai": ["openai", "gpt-4o", "gpt-4o-mini"],
        "anthropic": ["anthropic", "claude-opus-4-6", "claude-sonnet-4-6"],
        "qwen": ["qwen", "qwen-turbo", "qwen-plus", "qwen-max"],
        "zhipu": ["zhipu", "glm-4", "glm-4-flash"],
        "ollama": ["ollama"],
    }
    aliases = _PROVIDER_MODEL_ALIASES.get(req.provider, [req.provider])

    try:
        # Register adapter for each model alias the caller might use
        for alias in aliases:
            adapter_key = f"{alias}_{current_user.id}"
            api_client.configure_adapter(
                adapter_key,
                req.api_key.strip(),
                base_url=base_url or None,
                model_name=alias if alias not in ("deepseek", "openai", "anthropic", "qwen", "zhipu", "ollama") else "",
            )
    except Exception:
        pass

    return {"status": action, "provider": req.provider, "key_id": key_id}


@router.delete("/keys/{key_id}")
async def delete_user_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user's API key (must belong to the current user)."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.user_id == current_user.id,
        )
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="Key 不存在或无权操作")

    await db.delete(key)
    await db.commit()
    return {"status": "deleted"}
