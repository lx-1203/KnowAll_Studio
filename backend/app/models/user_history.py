"""UserHistory model for operation records (orders, favorites, browsing, etc.)"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from app.database import Base
from app.models import gen_uuid, now


class UserHistory(Base):
    __tablename__ = "user_history"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)  # browse/quiz/flashcard/document/study/game/order/favorite
    action_label = Column(String(200), default="")     # human-readable description
    resource_type = Column(String(50), default="")
    resource_id = Column(String(36), default="")
    detail = Column(Text, default="")                  # extra JSON or text detail
    created_at = Column(DateTime, default=now)
