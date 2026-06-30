"""System-wide key-value configuration model"""
from sqlalchemy import Column, String, Text, DateTime
from app.database import Base
from app.models import now


class SystemConfig(Base):
    """Persistent key-value configuration store."""
    __tablename__ = "system_config"

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(String(256), default="")
    updated_at = Column(DateTime, default=now, onupdate=now)
