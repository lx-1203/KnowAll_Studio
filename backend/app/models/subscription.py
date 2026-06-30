"""Subscription & License models for commercial features."""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Float
from app.database import Base
from app.models import gen_uuid, now


class UserTier(Base):
    """User subscription tier."""
    __tablename__ = "user_tiers"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    tier = Column(String(20), nullable=False, default="free")  # free/pro/enterprise
    started_at = Column(DateTime, default=now)
    expires_at = Column(DateTime, nullable=True)  # None = never expires (lifetime)
    auto_renew = Column(Boolean, default=False)
    daily_ai_calls_limit = Column(Integer, default=50)  # 50 for free
    daily_token_limit = Column(Integer, default=500_000)  # 500K for free
    max_documents = Column(Integer, default=10)  # 10 docs for free
    max_file_size_mb = Column(Integer, default=20)  # 20MB for free
    features_extra = Column(String(500), default="")  # JSON: enabled features list
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

TierConfig = {
    "free": {
        "name": "免费版",
        "daily_ai_calls_limit": 50,
        "daily_token_limit": 500_000,
        "max_documents": 10,
        "max_file_size_mb": 20,
        "features": ["documents", "knowledge_tree", "quiz_basic", "flashcards_basic", "chat_basic"],
    },
    "pro": {
        "name": "专业版",
        "daily_ai_calls_limit": 500,
        "daily_token_limit": 5_000_000,
        "max_documents": 200,
        "max_file_size_mb": 100,
        "features": ["documents", "knowledge_tree", "quiz_advanced", "flashcards_advanced",
                     "chat_advanced", "ai_writing", "graphrag", "export_anki", "games"],
    },
    "enterprise": {
        "name": "企业版",
        "daily_ai_calls_limit": 5000,
        "daily_token_limit": 50_000_000,
        "max_documents": 2000,
        "max_file_size_mb": 500,
        "features": ["documents", "knowledge_tree", "quiz_advanced", "flashcards_advanced",
                     "chat_advanced", "ai_writing", "graphrag", "export_anki", "games",
                     "team_collaboration", "sso", "audit_log", "api_access", "white_label"],
    },
}


class License(Base):
    """Software license / activation keys."""
    __tablename__ = "licenses"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    license_key = Column(String(64), unique=True, nullable=False, index=True)
    tier = Column(String(20), nullable=False, default="pro")
    activations_max = Column(Integer, default=1)
    activations_used = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    issued_to = Column(String(200), default="")
    issued_at = Column(DateTime, default=now)
    expires_at = Column(DateTime, nullable=True)


class LicenseActivation(Base):
    """Tracks which user activated which license."""
    __tablename__ = "license_activations"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    license_id = Column(String(36), ForeignKey("licenses.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(String(128), default="")
    activated_at = Column(DateTime, default=now)


class PaymentOrder(Base):
    """Payment order records."""
    __tablename__ = "payment_orders"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    order_no = Column(String(32), unique=True, nullable=False, index=True)
    tier = Column(String(20), nullable=False)
    amount_cents = Column(Integer, nullable=False)  # Amount in cents (USD or CNY)
    currency = Column(String(3), default="CNY")
    status = Column(String(20), default="pending")  # pending/paid/cancelled/refunded
    payment_method = Column(String(20), default="")  # wechat/alipay/stripe
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)
