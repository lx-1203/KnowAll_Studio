"""Notification model for user message center"""
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from app.database import Base
from app.models import gen_uuid, now


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    category = Column(String(50), default="system")  # system/quiz/study/share/reminder
    is_read = Column(Boolean, default=False)
    resource_type = Column(String(50), default="")    # optional linked resource
    resource_id = Column(String, default="")
    created_at = Column(DateTime, default=now)
