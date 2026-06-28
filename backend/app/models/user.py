"""User and KnowledgePoint models for authentication and personal knowledge base"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(100), default="")
    phone = Column(String(20), default="")
    avatar_url = Column(String(500), default="")
    is_active = Column(Boolean, default=True)  # True=active, False=disabled
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    knowledge_points = relationship(
        "KnowledgePoint", back_populates="user",
        cascade="all, delete-orphan",
    )


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JSON, default=list)     # e.g. ["Python", "算法"]
    category = Column(String(200), default="")  # 分类/学科
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    user = relationship("User", back_populates="knowledge_points")

    __table_args__ = (
        Index("idx_kp_user_updated", "user_id", "updated_at"),
    )
