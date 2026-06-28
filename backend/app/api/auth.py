"""Authentication API: register, login, profile"""
import re
import html
import time
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator

from app.database import get_db
from app.models.user import User
from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Simple in-memory rate limiter for auth endpoints
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 10      # max attempts per window


def _check_rate_limit(key: str) -> None:
    """Check and update rate limit. Raises 429 if exceeded."""
    now = time.time()
    window_start = now - _RATE_LIMIT_WINDOW
    # Prune old entries
    _rate_limit_store[key] = [t for t in _rate_limit_store[key] if t > window_start]
    if len(_rate_limit_store[key]) >= _RATE_LIMIT_MAX:
        raise HTTPException(429, "操作过于频繁，请稍后再试")
    _rate_limit_store[key].append(now)

# ---- Request / Response Schemas ----

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\u4e00-\u9fff]{2,50}$")
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not _USERNAME_RE.match(v):
            raise ValueError("用户名需 2-50 字符，仅支持中英文、数字、下划线")
        return html.escape(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("邮箱格式不正确")
        if len(v) > 255:
            raise ValueError("邮箱长度不能超过 255 字符")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码不能少于 6 个字符")
        if len(v) > 128:
            raise ValueError("密码不能超过 128 个字符")
        return v


class LoginRequest(BaseModel):
    username: str   # 可以是用户名或邮箱
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ---- Routes ----

@router.post("/register", status_code=201)
async def register(req: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """注册新用户。用户名和邮箱全局唯一。"""
    _check_rate_limit(f"register:{request.client.host}")

    # 检查用户名是否已存在
    existing = await db.execute(
        select(User).where(User.username == req.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名已被注册")

    # 检查邮箱是否已存在
    existing = await db.execute(
        select(User).where(User.email == req.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该邮箱已被注册")

    # 创建用户，密码 bcrypt 哈希
    user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 注册成功直接返回 token（自动登录）
    token = create_access_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.isoformat(),
        },
    }


@router.post("/login")
async def login(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """登录：支持用户名或邮箱 + 密码"""
    _check_rate_limit(f"login:{request.client.host}")

    login_id = req.username.strip().lower()

    # 按用户名或邮箱查找
    result = await db.execute(
        select(User).where(
            (User.username == req.username.strip()) | (User.email == login_id)
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已被禁用，请联系管理员")

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.isoformat(),
        },
    }


@router.get("/me")
async def get_profile(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息（需携带 Bearer token）"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_active": bool(current_user.is_active),
        "created_at": current_user.created_at.isoformat(),
        "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None,
    }
