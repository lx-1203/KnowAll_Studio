// Shared TypeScript types for KnowAll Studio

export interface Document {
  id: string
  filename: string
  file_type: string
  status: 'pending' | 'parsing' | 'ready' | 'error'
  page_count: number
  created_at: string
}

export interface DocumentChunk {
  id: string
  index: number
  text: string
  token_count: number
  page_range: string
}

export interface KnowledgeTreeNode {
  id: string
  label: string
  level: number
  tag: string
  summary: string
  children: KnowledgeTreeNode[]
}

export interface KnowledgeTree {
  tree_id: string
  name: string
  tree_data: { tree: { title: string; nodes: KnowledgeTreeNode[] } }
  created_at: string
  updated_at?: string
}

export interface Question {
  id: string
  question_type: QuestionType
  difficulty: 'easy' | 'medium' | 'hard'
  tags: string[]
  question_text: string
  options: Option[]
  answer: string
  analysis: string | null
}

export type QuestionType =
  | 'single_choice'
  | 'multi_choice'
  | 'true_false'
  | 'fill_blank'
  | 'cloze'
  | 'short_answer'
  | 'calculation'
  | 'formula'
  | 'coding'
  | 'material_analysis'

export interface Option {
  label: string
  text: string
}

export interface ExamPaper {
  paper_id: string
  title: string
  question_count: number
  total_score: number
  questions: Question[]
}

export interface ExamResult {
  total: number
  correct: number
  score: number
  percentage: number
  details: ResultDetail[]
}

export interface ResultDetail {
  question_id: string
  user_answer: string
  correct_answer: string
  is_correct: boolean
  analysis: string
}

export interface Flashcard {
  id: string
  card_type: 'qa' | 'cloze' | 'compare'
  front: string
  back: string
  hints: string | null
  tags: string[]
}

export interface Deck {
  id: string
  name: string
  card_count: number
  created_at: string
}

export interface ReviewResult {
  card_id: string
  next_review_at: string | null
  state: 'new' | 'learning' | 'review' | 'relearning'
  stability: number
  review_count: number
}

export interface ChatConversation {
  id: string
  title: string
  role_preset: string
  created_at: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
}

export interface PipelineState {
  stage: 'parse' | 'knowledge_tree' | 'quiz' | 'flashcards' | 'done' | 'error'
  progress: number
  message: string
  error: string | null
  result: {
    document_id: string
    tree_id: string
    question_count: number
    question_ids: string[]
    deck_id: string
    card_count: number
  } | null
}

export interface DashboardStats {
  documents: number
  questions: number
  answers_submitted: number
  correct_rate: number
  errors: number
  cards_total: number
  cards_due: number
  reviews_today: number
  token_usage: { input: number; output: number; total: number }
  cost_estimate: number
}

export interface DailyStat {
  date: string
  reviews: number
  answers: number
  correct: number
  api_calls: number
}

export interface TopicStat {
  topic: string
  total: number
  errors: number
}

export interface GameLevel {
  id: string
  game_type: 'matching' | 'cloze_ladder'
  level_index: number
  difficulty: 'easy' | 'medium' | 'hard'
  level_data: any
  unlock_condition: any
}

// ===== Personal Center Types =====

export interface UserProfile {
  id: string
  username: string
  email: string
  nickname: string
  phone: string
  avatar_url: string
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export interface UpdateProfileRequest {
  nickname?: string
  phone?: string
  avatar_url?: string
  email?: string
}

export interface ChangePasswordRequest {
  old_password: string
  new_password: string
}

export interface UserBind {
  id: string
  provider: string
  provider_name: string
  is_bound: boolean
  bound_at: string | null
}

export interface Notification {
  id: string
  title: string
  content: string
  category: string
  is_read: boolean
  resource_type: string
  resource_id: string
  created_at: string
}

export interface NotificationListResponse {
  total: number
  unread_count: number
  items: Notification[]
}

export interface UserHistory {
  id: string
  action_type: string
  action_label: string
  resource_type: string
  resource_id: string
  detail: string
  created_at: string
}

export interface UserHistoryListResponse {
  total: number
  items: UserHistory[]
}

// Auth types
export interface AuthUser {
  id: string
  username: string
  email: string
  created_at: string
}
