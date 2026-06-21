"""Admin API routes - API key management, cache, quota, logs"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from app.database import get_db
from app.models import APIKey, APICache, APICallLog
from app.core.api_scheduler.cache import cache_manager
from app.core.api_scheduler.rate_limiter import rate_limiter
from app.core.crypto import encrypt_api_key, decrypt_api_key

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class AddAPIKeyRequest(BaseModel):
    provider: str  # openai/deepseek/qwen/ollama/...
    api_key: str
    key_alias: str = ""
    permission_level: str = "personal"


class ModelConfigRequest(BaseModel):
    model: str
    fallback_models: list[str] = []
    daily_token_limit: int = 1_000_000


# ===== API Key Management =====

@router.post("/keys")
async def add_api_key(req: AddAPIKeyRequest, db: AsyncSession = Depends(get_db)):
    """Add a new API key (encrypted with AES-256)."""
    key_encrypted = encrypt_api_key(req.api_key)

    key = APIKey(
        provider=req.provider,
        key_encrypted=key_encrypted,
        key_alias=req.key_alias,
        permission_level=req.permission_level,
    )
    db.add(key)
    await db.commit()

    # Configure the adapter with the real key
    from app.core.api_scheduler import api_client
    try:
        api_client.configure_adapter(req.provider, req.api_key)
    except Exception:
        pass

    return {"status": "added", "provider": req.provider, "key_id": key.id}


@router.get("/keys")
async def list_keys(db: AsyncSession = Depends(get_db)):
    """List all API keys (masked for security)."""
    result = await db.execute(select(APIKey))
    keys = result.scalars().all()
    return [
        {
            "id": k.id,
            "provider": k.provider,
            "key_alias": k.key_alias,
            "key_masked": "****" + k.key_encrypted[-8:] if len(k.key_encrypted) > 8 else "****",
            "permission_level": k.permission_level,
            "is_active": k.is_active,
        }
        for k in keys
    ]


@router.delete("/keys/{key_id}")
async def delete_key(key_id: str, db: AsyncSession = Depends(get_db)):
    """Delete an API key."""
    from sqlalchemy import select
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")
    await db.delete(key)
    await db.commit()
    return {"status": "deleted"}


# ===== Model Configuration =====

@router.post("/models")
async def configure_model(req: ModelConfigRequest):
    """Configure model settings."""
    return {
        "model": req.model,
        "fallback_models": req.fallback_models,
        "daily_token_limit": req.daily_token_limit,
        "status": "configured",
    }


# ===== Cache Management =====

@router.get("/cache/stats")
async def cache_stats():
    """Get API response cache statistics."""
    return await cache_manager.stats()


@router.delete("/cache/clear")
async def clear_cache(db: AsyncSession = Depends(get_db)):
    """Clear all cached API responses."""
    from sqlalchemy import delete
    await db.execute(delete(APICache))
    await db.commit()
    return {"status": "cache_cleared"}


# ===== Quota Management =====

@router.get("/quota/status")
async def quota_status():
    """Get API quota status."""
    return await rate_limiter.get_quota_status("local_user")


# ===== Usage Logs =====

@router.get("/logs")
async def usage_logs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get recent API call logs (summaries only, no original content)."""
    from sqlalchemy import select
    from app.models import APICallLog
    result = await db.execute(
        select(APICallLog)
        .order_by(APICallLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "task_type": l.task_type,
            "model_name": l.model_name,
            "tokens_input": l.tokens_input,
            "tokens_output": l.tokens_output,
            "cost_estimate": l.cost_estimate,
            "from_cache": l.from_cache,
            "success": l.success,
            "duration_ms": l.duration_ms,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]
