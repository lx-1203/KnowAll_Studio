"""Authentication utilities: password hashing, JWT, and auth dependency"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt, JWTError
import bcrypt

from app.config import settings
from app.database import get_db
from app.models.user import User

# Bearer token scheme (used in OpenAPI docs)
security = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt. Returns the hash string."""
    # bcrypt has a 72-byte limit; truncate to 72 bytes encoded
    plain_bytes = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    plain_bytes = plain.encode("utf-8")[:72]
    hashed_bytes = hashed.encode("utf-8")
    return bcrypt.checkpw(plain_bytes, hashed_bytes)


def create_access_token(user_id: str) -> str:
    """Create a JWT access token for the given user_id."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Decode a JWT and return user_id, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: extract and validate the current user from Bearer token.

    Raises 401 if the token is missing, invalid, expired, or the user is disabled.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="请先登录")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token 无效或已过期，请重新登录")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已被禁用")

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """FastAPI dependency: extract the current user if a valid token is present.

    Returns None if no token is provided or the token is invalid.
    Use this for routes that support both authenticated and anonymous access.
    """
    if credentials is None:
        return None
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return None

    return user


def get_user_id(user: Optional[User]) -> str:
    """Helper: return user ID if authenticated, otherwise 'local_user'."""
    return user.id if user is not None else "local_user"


async def load_user_api_keys(user_id: str, db: AsyncSession) -> None:
    """Load the user's stored API keys from DB and register them with api_client.

    Call this at the beginning of any AI-calling route handler that has a user.
    If the user has no stored keys, the global (env) adapter is used as fallback.
    """
    if user_id == "local_user":
        return

    from app.models import APIKey
    from app.core.crypto import decrypt_api_key
    from app.core.api_scheduler import api_client, set_current_user_id

    set_current_user_id(user_id)

    result = await db.execute(
        select(APIKey).where(
            APIKey.user_id == user_id,
            APIKey.is_active == True,
        )
    )
    keys = result.scalars().all()

    if not keys:
        return

    _PROVIDER_MODEL_ALIASES = {
        "deepseek": ["deepseek", "deepseek-chat", "deepseek-reasoner"],
        "openai": ["openai", "gpt-4o", "gpt-4o-mini"],
        "anthropic": ["anthropic", "claude-opus-4-6", "claude-sonnet-4-6"],
        "qwen": ["qwen", "qwen-turbo", "qwen-plus", "qwen-max"],
        "zhipu": ["zhipu", "glm-4", "glm-4-flash"],
        "ollama": ["ollama"],
    }
    _PROVIDER_BASE_URLS = {
        "deepseek": "https://api.deepseek.com/anthropic",
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        "ollama": "http://localhost:11434/v1",
    }

    for key in keys:
        try:
            plain = decrypt_api(key.key_encrypted)
        except Exception:
            continue

        aliases = _PROVIDER_MODEL_ALIASES.get(key.provider, [key.provider])
        base_url = _PROVIDER_BASE_URLS.get(key.provider, "")
        for alias in aliases:
            adapter_key = f"{alias}_{user_id}"
            api_client.configure_adapter(
                adapter_key,
                plain,
                base_url=base_url,
                model_name=alias if alias not in ("deepseek", "openai", "anthropic", "qwen", "zhipu", "ollama") else "",
            )
