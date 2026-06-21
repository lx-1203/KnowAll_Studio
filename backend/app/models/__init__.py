"""All database models for KnowAll Studio"""
import uuid
import json
from datetime import datetime, date, timezone
from sqlalchemy import Column, String, Integer, Boolean, Float, Date, DateTime, Text, ForeignKey, JSON, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ==================== Document Models ====================

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=gen_uuid)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # pdf/docx/pptx/md/image/xmind/url/text
    file_size = Column(Integer)
    sha256 = Column(String, unique=True, nullable=False)
    local_path = Column(String)
    status = Column(String, default="pending")  # pending/parsing/ready/error
    page_count = Column(Integer)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=gen_uuid)
    doc_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content_hash = Column(String, unique=True)  # SHA256 of normalized text
    text_content = Column(Text, nullable=False)
    token_count = Column(Integer)
    page_range = Column(String)  # "p3-p5"
    vector_id = Column(String)  # ChromaDB reference
    created_at = Column(DateTime, default=now)

    document = relationship("Document", back_populates="chunks")


# ==================== Knowledge Structure Models ====================

class KnowledgeTree(Base):
    __tablename__ = "knowledge_trees"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    doc_ids = Column(JSON, default=list)
    tree_data = Column(JSON, nullable=False, default=dict)
    generation_cache_key = Column(String)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Outline(Base):
    __tablename__ = "outlines"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String, nullable=False)
    content_markdown = Column(Text, nullable=False)
    source_tree_id = Column(String, ForeignKey("knowledge_trees.id"))
    generation_cache_key = Column(String)
    created_at = Column(DateTime, default=now)


# ==================== Quiz System Models ====================

class QuestionBank(Base):
    __tablename__ = "question_bank"

    id = Column(String, primary_key=True, default=gen_uuid)
    question_type = Column(String, nullable=False)  # single_choice/multi_choice/true_false/fill_blank/cloze/short_answer/calculation/formula/coding/material_analysis
    difficulty = Column(String, default="medium")  # easy/medium/hard
    tags = Column(JSON, default=list)
    question_text = Column(Text, nullable=False)
    options = Column(JSON, default=list)  # [{"label":"A","text":"..."}]
    correct_answer = Column(Text, nullable=False)
    analysis = Column(Text)
    source_chunk_id = Column(String, ForeignKey("document_chunks.id"))
    parent_question_id = Column(String)  # variant question origin
    generation_cache_key = Column(String)
    created_at = Column(DateTime, default=now)


class ExamPaper(Base):
    __tablename__ = "exam_papers"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String, nullable=False)
    description = Column(Text)
    question_ids = Column(JSON, nullable=False, default=list)
    config = Column(JSON, default=dict)  # time_limit, total_score, difficulty distribution
    created_at = Column(DateTime, default=now)


class AnswerRecord(Base):
    __tablename__ = "answer_records"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, nullable=False, default="local_user")
    question_id = Column(String, ForeignKey("question_bank.id"), nullable=False)
    paper_id = Column(String, ForeignKey("exam_papers.id"))
    user_answer = Column(Text)
    is_correct = Column(Boolean)
    time_spent = Column(Integer)  # seconds
    answered_at = Column(DateTime, default=now)


class ErrorLog(Base):
    __tablename__ = "error_log"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, nullable=False, default="local_user")
    question_id = Column(String, ForeignKey("question_bank.id"), nullable=False)
    error_count = Column(Integer, default=1)
    last_error_at = Column(DateTime, default=now)
    variant_generated = Column(Boolean, default=False)


# ==================== Flashcard Models ====================

class Deck(Base):
    __tablename__ = "decks"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    description = Column(Text)
    card_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)


class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(String, primary_key=True, default=gen_uuid)
    card_type = Column(String, nullable=False)  # qa/cloze/definition/compare
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    hints = Column(Text)
    tags = Column(JSON, default=list)
    source_node_id = Column(String)  # trace back to knowledge tree node
    source_error_id = Column(String)  # trace back to error question
    deck_id = Column(String, ForeignKey("decks.id"))
    generation_cache_key = Column(String)
    created_at = Column(DateTime, default=now)


class ReviewSchedule(Base):
    __tablename__ = "review_schedule"

    id = Column(String, primary_key=True, default=gen_uuid)
    card_id = Column(String, ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False)
    fsrs_stability = Column(Float)
    fsrs_difficulty = Column(Float)
    fsrs_retrievability = Column(Float)
    next_review_at = Column(DateTime)
    last_review_at = Column(DateTime)
    review_count = Column(Integer, default=0)
    state = Column(String, default="new")  # new/learning/review/relearning


class ReviewLog(Base):
    __tablename__ = "review_log"

    id = Column(String, primary_key=True, default=gen_uuid)
    card_id = Column(String, ForeignKey("flashcards.id"), nullable=False)
    rating = Column(Integer)  # 1-4 FSRS self-rating
    review_at = Column(DateTime, default=now)
    time_spent_ms = Column(Integer)


# ==================== Game Models ====================

class GameLevel(Base):
    __tablename__ = "game_levels"

    id = Column(String, primary_key=True, default=gen_uuid)
    game_type = Column(String, nullable=False)  # matching/ladder/cloze/fix/coding
    level_index = Column(Integer, nullable=False)
    difficulty = Column(String, default="medium")
    level_data = Column(JSON, nullable=False, default=dict)
    unlock_condition = Column(JSON)
    generation_cache_key = Column(String)


class GameProgress(Base):
    __tablename__ = "game_progress"
    __table_args__ = (UniqueConstraint("user_id", "level_id"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, nullable=False, default="local_user")
    game_type = Column(String, nullable=False)
    level_id = Column(String, ForeignKey("game_levels.id"), nullable=False)
    best_score = Column(Integer)
    stars = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=now, onupdate=now)


# ==================== AI Assistant Models ====================

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String)
    role_preset = Column(String, nullable=False)  # lecturer/tutor/mentor/expand
    created_at = Column(DateTime, default=now)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # user/assistant/system
    content = Column(Text, nullable=False)
    tokens_input = Column(Integer)
    tokens_output = Column(Integer)
    model_used = Column(String)
    created_at = Column(DateTime, default=now)

    conversation = relationship("Conversation", back_populates="messages")


# ==================== API Management Models ====================

class APICallLog(Base):
    __tablename__ = "api_call_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, default="local_user")
    task_type = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    tokens_input = Column(Integer)
    tokens_output = Column(Integer)
    cost_estimate = Column(Float)
    from_cache = Column(Boolean, default=False)
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    content_summary = Column(String(200))  # max 200 chars, NO original content
    duration_ms = Column(Integer)
    created_at = Column(DateTime, default=now)


class APIQuota(Base):
    __tablename__ = "api_quota"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, unique=True, nullable=False, default="local_user")
    daily_limit = Column(Integer, default=1_000_000)
    used_today = Column(Integer, default=0)
    reset_at = Column(Date)
    total_used = Column(Integer, default=0)


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=gen_uuid)
    provider = Column(String, nullable=False)  # openai/deepseek/qwen/ernie/kimi/zhipu/ollama
    key_encrypted = Column(String, nullable=False)  # AES encrypted
    key_alias = Column(String)
    permission_level = Column(String, default="student")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now)


# ==================== Cache Table (for SQLite-based caching) ====================

class APICache(Base):
    __tablename__ = "api_cache"

    cache_key = Column(String, primary_key=True)  # SHA256 hash
    response_content = Column(Text, nullable=False)
    model_used = Column(String, nullable=False)
    tokens_input = Column(Integer)
    tokens_output = Column(Integer)
    created_at = Column(DateTime, default=now)
    ttl_days = Column(Integer, default=30)
