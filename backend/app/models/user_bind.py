"""UserBind model for third-party account binding"""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from app.database import Base
from app.models import gen_uuid, now


class UserBind(Base):
    __tablename__ = "user_binds"
    __table_args__ = (UniqueConstraint("user_id", "provider"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)       # wechat/qq/github/google
    provider_name = Column(String(100), default="")      # display name on the platform
    provider_uid = Column(String(200), default="")       # user id on the third-party platform
    is_bound = Column(Boolean, default=True)
    bound_at = Column(DateTime, default=now)
    unbound_at = Column(DateTime, nullable=True)
