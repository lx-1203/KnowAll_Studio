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


# ===== Knowledge Summary Schemas =====

class GenerateSummaryRequest(BaseModel):
    document_id: str
    model: str = "deepseek-chat"
    language_type: str = "auto"  # auto/chinese/english/japanese
    max_depth: int = Field(default=3, ge=2, le=4)


class KnowledgeSummaryResponse(BaseModel):
    summary_id: str
    document_id: str
    content_md: str
    node_count: int
    level_stats: dict
    generated_at: str | None = None
    model_used: str | None = None


class KnowledgePointNodeResponse(BaseModel):
    id: str
    summary_id: str | None = None
    parent_id: str | None = None
    level: int
    sequence: int
    title: str
    explanation: str
    related_concepts: str | None = None
    examples: str | None = None
    tags: list[str] = []


class KnowledgePointNodeListResponse(BaseModel):
    total: int
    nodes: list[KnowledgePointNodeResponse]


class MindMapNode(BaseModel):
    id: str
    label: str
    level: int
    tag: str | None = None
    summary: str | None = None
    children: list["MindMapNode"] = []


class MindMapEdge(BaseModel):
    source: str
    target: str
    relation: str = "parent_child"


class MindMapDataResponse(BaseModel):
    nodes: list[MindMapNode]
    edges: list[MindMapEdge] = []


# ===== Agent Orchestration Schemas =====

class AgentOrchestrateRequest(BaseModel):
    summary_id: str
    document_id: str
    agents: list[str] | None = None  # None = all, e.g. ["question_bank","mindmap","study_plan"]
    language_type: str | None = None
    config: dict = Field(default_factory=dict)


class AgentResult(BaseModel):
    agent: str
    status: str  # success/error/skipped
    result: dict | None = None
    error: str | None = None


class AgentOrchestrateResponse(BaseModel):
    summary_id: str
    results: dict[str, AgentResult]
    coverage_report: dict | None = None


# ===== Interactive Quiz Schemas =====

class InteractiveQuizStartResponse(BaseModel):
    session_id: str
    questions: list[dict]
    total: int


class InteractiveAnswerSubmit(BaseModel):
    question_id: str
    user_answer: str
    time_spent_ms: int = 0
    knowledge_point_id: str | None = None


class InteractiveAnswerResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    analysis: str | None = None
    stats: dict  # {total_answered, correct, accuracy}


class InteractiveQuizStatsResponse(BaseModel):
    total_answered: int
    correct: int
    accuracy: float
    time_spent_total_ms: int
    questions_detail: list[dict]


# ===== Coverage Report Schemas =====

class CoverageReportResponse(BaseModel):
    total_knowledge_points: int
    covered_by_questions: int
    covered_by_flashcards: int
    full_coverage: int  # 同时有题目+记忆卡
    coverage_rate_questions: float
    coverage_rate_flashcards: float
    full_coverage_rate: float
    uncovered_points: list[dict]  # [{id, title, level}]
    weak_points: list[dict]  # [{id, title, accuracy, recommendation}]


# ===== Memory Feedback Schemas =====

class FeedbackScanRequest(BaseModel):
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class ReviewQueueItemResponse(BaseModel):
    queue_id: str
    resource_type: str
    resource_id: str
    knowledge_point_id: str | None = None
    priority: int
    reason: str | None = None
    pushed_at: str | None = None
    completed: bool


class ReviewQueueListResponse(BaseModel):
    total: int
    items: list[ReviewQueueItemResponse]


class CompleteReviewRequest(BaseModel):
    queue_id: str


class MemoryStatsResponse(BaseModel):
    total_cards: int
    total_reviews: int
    average_accuracy: float
    weak_points_count: int
    due_today: int
    review_queue_count: int


# ===== Language Vocabulary Schemas =====

class GenerateVocabularyRequest(BaseModel):
    document_id: str
    summary_id: str
    language_type: str = "auto"


class LanguageVocabularyItem(BaseModel):
    id: str
    word: str
    phonetic: str | None = None
    part_of_speech: str | None = None
    definition: str
    example_sentence: str | None = None
    difficulty: str = "medium"
    knowledge_point_id: str | None = None
    mastered: bool = False


class LanguageVocabularyListResponse(BaseModel):
    total: int
    words: list[LanguageVocabularyItem]


# ===== Enhanced Study Plan Schemas =====

class GenerateEnhancedPlanRequest(BaseModel):
    summary_id: str
    plan_type: str = "both"  # short/long/both
    daily_hours: float = 2.0
    start_date: str | None = None
    ebbinghaus_enabled: bool = True


class EbbinghausNode(BaseModel):
    day: int
    review: bool
    description: str = ""


class StudyPlanEnhancedResponse(BaseModel):
    plan_id: str
    name: str
    plan_type: str
    daily_hours: float
    short_term_plan: list[dict] | None = None  # 短期(1-3天,按小时)
    long_term_plan: list[dict] | None = None    # 长期(1-4周,按天)
    ebbinghaus_nodes: list[EbbinghausNode] = []
    knowledge_point_ids: list[str] = []
