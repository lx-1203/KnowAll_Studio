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
from app.core.auth import get_optional_user, get_user_id

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
async def quota_status(current_user = Depends(get_optional_user)):
    """Get API quota status."""
    user_id = get_user_id(current_user)
    return await rate_limiter.get_quota_status(user_id)


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


# ===== System Health =====

@router.get("/health")
async def system_health(db: AsyncSession = Depends(get_db)):
    """Comprehensive system health check."""
    import sys
    import platform
    from datetime import datetime, timezone

    health = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.2.0",
        "python": sys.version,
        "platform": platform.platform(),
    }

    # Check database connectivity
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        health["database"] = "ok"
    except Exception as e:
        health["database"] = f"error: {e}"
        health["status"] = "degraded"

    # Check ChromaDB / vector store
    try:
        from app.core.rag import get_index_stats
        stats = await get_index_stats()
        health["vector_store"] = {"status": "ok", **stats}
    except Exception as e:
        health["vector_store"] = f"error: {e}"

    # Check GraphRAG
    try:
        from app.core.graph_rag import get_graph_stats
        gstats = await get_graph_stats()
        health["graphrag"] = {"status": "ok", **gstats}
    except Exception as e:
        health["graphrag"] = f"error: {e}"

    # Check API scheduler
    try:
        from app.core.api_scheduler import api_client
        health["api_scheduler"] = api_client.get_status()
    except Exception as e:
        health["api_scheduler"] = f"error: {e}"

    # Count active users
    try:
        from app.models.user import User
        from sqlalchemy import func
        result = await db.execute(select(func.count(User.id)).where(User.is_active == True))
        health["active_users"] = result.scalar() or 0
    except Exception:
        health["active_users"] = -1

    return health
