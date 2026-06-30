"""User gamification: learning streaks, achievements, and focus sessions."""
from datetime import datetime, timedelta, timezone, date
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Date, Float, ForeignKey, JSON
from app.database import Base
from app.models import gen_uuid, now


class LearningStreak(Base):
    """Daily learning streak tracking."""
    __tablename__ = "learning_streaks"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    streak_date = Column(Date, nullable=False)
    study_minutes = Column(Integer, default=0)
    questions_answered = Column(Integer, default=0)
    cards_reviewed = Column(Integer, default=0)
    documents_uploaded = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)


class Achievement(Base):
    """Unlockable achievement badges."""
    __tablename__ = "achievements"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    achievement_key = Column(String(64), nullable=False)  # e.g. 'streak_7', 'cards_100'
    name = Column(String(128), nullable=False)
    description = Column(String(256), default="")
    icon = Column(String(32), default="🏆")
    unlocked_at = Column(DateTime, default=now)


class FocusSession(Base):
    """Pomodoro / focus timer sessions."""
    __tablename__ = "focus_sessions"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=False)
    session_type = Column(String(32), default="study")  # study / break / review
    completed = Column(Boolean, default=True)
    tags = Column(JSON, default=list)
    started_at = Column(DateTime, default=now)
    ended_at = Column(DateTime, nullable=True)


# ── Achievement Definitions ──
ACHIEVEMENTS = [
    {"key": "first_quiz", "name": "初试锋芒", "desc": "完成第一次测验", "icon": "⚔️"},
    {"key": "streak_3", "name": "三日之约", "desc": "连续学习3天", "icon": "🔥"},
    {"key": "streak_7", "name": "七日之约", "desc": "连续学习7天", "icon": "🔥"},
    {"key": "streak_30", "name": "月之恒", "desc": "连续学习30天", "icon": "🌟"},
    {"key": "cards_50", "name": "记忆大师", "desc": "复习50张闪卡", "icon": "🃏"},
    {"key": "cards_200", "name": "记忆宗师", "desc": "复习200张闪卡", "icon": "🎴"},
    {"key": "questions_100", "name": "刷题达人", "desc": "回答100道题目", "icon": "📝"},
    {"key": "questions_500", "name": "刷题狂人", "desc": "回答500道题目", "icon": "📚"},
    {"key": "docs_5", "name": "求知若渴", "desc": "上传5份学习资料", "icon": "📄"},
    {"key": "focus_10", "name": "专注学徒", "desc": "完成10次专注计时", "icon": "⏱️"},
    {"key": "focus_60", "name": "深度专注", "desc": "累计专注60分钟", "icon": "🧠"},
    {"key": "perfect_quiz", "name": "完美答卷", "desc": "一次测验获得满分", "icon": "💯"},
    {"key": "early_bird", "name": "晨间学者", "desc": "早上6-8点完成学习", "icon": "🌅"},
    {"key": "night_owl", "name": "夜间学者", "desc": "晚上22点后完成学习", "icon": "🦉"},
]
