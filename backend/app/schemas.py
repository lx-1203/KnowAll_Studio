"""Pydantic schemas for API request/response validation"""
from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime


# ===== Document Schemas =====

class ChunkPreview(BaseModel):
    index: int
    token_count: int
    page_range: str
    preview: str


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    file_type: str
    status: str
    page_count: int
    chunks: list[dict]
    total_chunks: int


class DocumentListItem(BaseModel):
    id: str
    filename: str
    file_type: str
    status: str
    page_count: int
    created_at: str


class DocumentChunkItem(BaseModel):
    id: str
    index: int
    text: str
    token_count: int
    page_range: str


# ===== Knowledge Tree Schemas =====

class GenerateTreeRequest(BaseModel):
    document_id: str
    chunk_ids: list[str] | None = None
    model: str = "deepseek-chat"
    tree_name: str = "知识树"


class KnowledgeTreeResponse(BaseModel):
    tree_id: str
    name: str
    tree_data: dict
    created_at: str | None = None
    updated_at: str | None = None


class KnowledgeTreeListItem(BaseModel):
    tree_id: str
    name: str
    doc_count: int
    created_at: str | None = None


class OutlineResponse(BaseModel):
    outline_id: str
    title: str
    content: str


# ===== Quiz Schemas =====

class GenerateQuestionsRequest(BaseModel):
    document_id: str
    chunk_ids: list[str] | None = None
    question_type: str = "single_choice"
    count: int = Field(default=10, ge=1, le=50)
    difficulty: str = "medium"
    model: str = "deepseek-chat"


class QuestionItem(BaseModel):
    id: str
    question_type: str
    difficulty: str
    tags: list[str]
    question_text: str
    options: list[dict]
    answer: str
    analysis: str | None = None


class GenerateQuestionsResponse(BaseModel):
    generated_count: int
    questions: list[dict]


class CreateExamRequest(BaseModel):
    title: str = "试卷"
    question_ids: list[str] | None = None
    config: dict = Field(default_factory=dict)


class CreateExamResponse(BaseModel):
    paper_id: str
    title: str
    question_count: int
    total_score: int
    questions: list[dict]


class SubmitExamRequest(BaseModel):
    paper_id: str
    answers: dict[str, str]


class GradeDetail(BaseModel):
    question_id: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    analysis: str


class SubmitExamResponse(BaseModel):
    total: int
    correct: int
    score: int
    percentage: float
    details: list[dict]


# ===== Flashcard Schemas =====

class GenerateCardsRequest(BaseModel):
    knowledge_text: str
    card_type: str = "qa"
    count: int = Field(default=20, ge=1, le=100)
    deck_name: str = "默认牌组"
    model: str = "deepseek-chat"


class CardItem(BaseModel):
    id: str
    card_type: str
    front: str
    back: str
    hints: str | None = None


class GenerateCardsResponse(BaseModel):
    generated_count: int
    cards: list[dict]
    deck_id: str


class ReviewRequest(BaseModel):
    card_id: str
    rating: int = Field(ge=1, le=4)


class ReviewResponse(BaseModel):
    card_id: str
    next_review_at: str | None = None
    state: str
    stability: float
    review_count: int


class DueCardsResponse(BaseModel):
    due_count: int
    cards: list[dict]


class DeckItem(BaseModel):
    id: str
    name: str
    card_count: int
    created_at: str


# ===== Chat Schemas =====

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    role_preset: str = "tutor"
    model: str = "deepseek-chat"
    knowledge_context: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    role_preset: str
    message: str


class ConversationItem(BaseModel):
    id: str
    title: str
    role_preset: str
    created_at: str


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


# ===== Admin Schemas =====

class QuotaStatus(BaseModel):
    daily_limit: int
    used_today: int
    remaining: int


class CacheStats(BaseModel):
    total_entries: int
    total_tokens_saved: int


# ===== User Profile Schemas =====

class UserProfileResponse(BaseModel):
    id: str
    username: str
    email: str
    nickname: str
    phone: str
    avatar_url: str
    is_active: bool
    created_at: str
    updated_at: str | None = None


class UpdateProfileRequest(BaseModel):
    nickname: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    email: str | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ===== User Bind Schemas =====

class UserBindItem(BaseModel):
    id: str
    provider: str
    provider_name: str
    is_bound: bool
    bound_at: str | None = None


class BindAccountRequest(BaseModel):
    provider: str
    provider_name: str = ""
    provider_uid: str = ""


# ===== Notification Schemas =====

class NotificationItem(BaseModel):
    id: str
    title: str
    content: str
    category: str
    is_read: bool
    resource_type: str
    resource_id: str
    created_at: str


class NotificationListResponse(BaseModel):
    total: int
    unread_count: int
    items: list[NotificationItem]


# ===== User History Schemas =====

class UserHistoryItem(BaseModel):
    id: str
    action_type: str
    action_label: str
    resource_type: str
    resource_id: str
    detail: str
    created_at: str


class UserHistoryListResponse(BaseModel):
    total: int
    items: list[UserHistoryItem]


# ===== User API Key Schemas =====

class AddUserAPIKeyRequest(BaseModel):
    provider: str  # deepseek/openai/anthropic/qwen/...
    api_key: str
    key_alias: str = ""
    base_url: str = ""  # optional custom base URL


class UserAPIKeyItem(BaseModel):
    id: str
    provider: str
    key_alias: str
    key_masked: str
    base_url: str
    is_active: bool
    created_at: str
