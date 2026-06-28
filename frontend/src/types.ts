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
  difficulty_score: number           // NEW: continuous 0.0-1.0
  cognitive_level: CognitiveLevel    // NEW: Bloom level
  tags: string[]
  question_text: string
  options: Option[]
  answer: string
  analysis: string | null
  review_scores?: Record<string, number>  // NEW: LLM-as-Judge quality scores
  review_total?: number                   // NEW: total review score
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

export type CognitiveLevel =
  | 'L1_remember'
  | 'L2_understand'
  | 'L3_apply'
  | 'L4_analyze'
  | 'L5_evaluate'
  | 'L6_create'

export const COGNITIVE_LEVEL_LABELS: Record<CognitiveLevel, string> = {
  L1_remember: '记忆',
  L2_understand: '理解',
  L3_apply: '应用',
  L4_analyze: '分析',
  L5_evaluate: '评价',
  L6_create: '创造',
}

export const COGNITIVE_LEVEL_COLORS: Record<CognitiveLevel, string> = {
  L1_remember: 'blue',
  L2_understand: 'cyan',
  L3_apply: 'green',
  L4_analyze: 'orange',
  L5_evaluate: 'red',
  L6_create: 'purple',
}

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
  cognitive_breakdown?: Record<string, { total: number; correct: number; accuracy: number }>
}

export interface ResultDetail {
  question_id: string
  user_answer: string
  correct_answer: string
  is_correct: boolean
  analysis: string
  grading_method?: 'semantic' | 'local'
  semantic_scores?: { correctness: number; completeness: number; clarity: number }
  semantic_total?: number
  feedback?: {
    strengths: string[]
    weaknesses: string[]
    suggestion: string
  }
  key_points_matched?: string[]
  key_points_missed?: string[]
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

// ===== Knowledge Summary Types =====

export interface KnowledgeSummary {
  summary_id: string
  document_id: string
  content_md: string
  node_count: number
  level_stats: Record<string, number>
  generated_at: string | null
  model_used: string | null
}

export interface KnowledgePointNode {
  id: string
  summary_id: string | null
  parent_id: string | null
  level: number
  sequence: number
  title: string
  explanation: string
  related_concepts: string | null
  examples: string | null
  tags: string[]
}

export interface MindMapNode {
  id: string
  label: string
  level: number
  tag: string | null
  summary: string | null
  children: MindMapNode[]
}

export interface MindMapEdge {
  source: string
  target: string
  relation: string
}

export interface BOISMetrics {
  score: number
  max_depth: number
  depth_distribution: Record<string, number>
  avg_children_per_node: number
  branching_factor: number
  hierarchy_balance: number
  coverage_completeness: number
  peer_variance: number
  suggestions: string[]
  grade: string
}

export interface RestructurePlan {
  merge_suggestions: Array<{
    parent: { id: string; label: string }
    child: { id: string; label: string }
    reason: string
  }>
  split_suggestions: Array<{
    node: { id: string; label: string }
    child_count: number
    reason: string
    suggested_groups: Array<{
      suggested_category: string
      members: Array<{ id: string; label: string }>
      count: number
    }>
  }>
  reclassify_suggestions: Array<{
    node: { id: string; label: string }
    current_level: number
    reason: string
  }>
  summary: string
}

export interface CategoryFramework {
  '上位阶（大类）': Array<{ id: string; label: string; child_count?: number }>
  '中位阶（中类）': Array<{ id: string; label: string; parent_id?: string }>
  '下位阶（小类）': Array<{ id: string; label: string }>
}

export interface MindMapData {
  nodes: MindMapNode[]
  edges: MindMapEdge[]
  bois_metrics?: BOISMetrics
  restructure_plan?: RestructurePlan
  category_framework?: CategoryFramework
  llm_restructured?: boolean
}

// ===== Agent Orchestration Types =====

export type AgentType = 'question_bank' | 'mindmap' | 'study_plan' | 'language' | 'quiz_interactive'

export interface AgentOrchestrateConfig {
  question_count?: number
  question_types?: string[]
  study_plan?: {
    type: 'short' | 'long' | 'both'
    daily_hours?: number
  }
}

export interface AgentResult {
  agent: string
  status: 'success' | 'error' | 'skipped'
  result: Record<string, any> | null
  error: string | null
}

export interface AgentOrchestrateResponse {
  summary_id: string
  results: Record<string, AgentResult>
  coverage_report: CoverageReport | null
}

// ===== Interactive Quiz Types =====

export interface InteractiveQuizSession {
  session_id: string
  questions: Question[]
  total: number
  current_index: number
  answers: Record<string, InteractiveAnswerResult>
}

export interface InteractiveAnswerResult {
  question_id: string
  user_answer: string
  is_correct: boolean
  correct_answer: string
  analysis: string | null
  time_spent_ms: number
}

export interface InteractiveQuizStats {
  total_answered: number
  correct: number
  accuracy: number
  time_spent_total_ms: number
  questions_detail: InteractiveAnswerResult[]
}

// ===== Coverage Report Types =====

export interface CoverageReport {
  total_knowledge_points: number
  covered_by_questions: number
  covered_by_flashcards: number
  full_coverage: number
  coverage_rate_questions: number
  coverage_rate_flashcards: number
  full_coverage_rate: number
  uncovered_points: Array<{ id: string; title: string; level: number }>
  weak_points: Array<{ id: string; title: string; accuracy: number; recommendation: string }>
}

// ===== Memory Feedback Types =====

export interface ReviewQueueItem {
  queue_id: string
  resource_type: 'flashcard' | 'question'
  resource_id: string
  knowledge_point_id: string | null
  priority: number
  reason: string | null
  pushed_at: string | null
  completed: boolean
}

export interface MemoryStats {
  total_cards: number
  total_reviews: number
  average_accuracy: number
  weak_points_count: number
  due_today: number
  review_queue_count: number
}

// ===== Language Vocabulary Types =====

export interface LanguageVocabulary {
  id: string
  word: string
  phonetic: string | null
  part_of_speech: string | null
  definition: string
  example_sentence: string | null
  difficulty: 'easy' | 'medium' | 'hard'
  knowledge_point_id: string | null
  mastered: boolean
}

// ===== Answer Review & Mastery Types =====

export interface MasteryDetail {
  kp_id: string
  title: string
  level: number
  explanation: string
  mastery_score: number
  accuracy: number
  total_attempts: number
  error_count: number
  last_attempt_at: string | null
  recency_score: number
  consistency_score: number
  trend: 'improving' | 'declining' | 'stable'
}

export interface MasteryAnalysis {
  overall_mastery: number
  total_knowledge_points: number
  weak_count: number
  moderate_count: number
  strong_count: number
  weak_points: MasteryDetail[]
  moderate_points: MasteryDetail[]
  strong_points: MasteryDetail[]
  mastery_map: Record<string, {
    mastery: number
    accuracy: number
    total_attempts: number
    error_count: number
    trend: string
  }>
}

export interface KpMasteryDetail extends MasteryDetail {
  question_details: Array<{
    question_id: string
    question_text: string
    is_correct: boolean
    user_answer: string
    time_spent_ms: number
    answered_at: string | null
  }>
}

export interface AnswerHistoryItem {
  record_id: string
  question_id: string
  question_text: string
  question_type: string
  cognitive_level: string
  difficulty_score: number
  user_answer: string
  correct_answer: string
  is_correct: boolean
  analysis: string
  time_spent_ms: number
  knowledge_point_ids: string[]
  knowledge_point_titles: string[]
  answered_at: string | null
}

export interface AnswerHistoryResponse {
  total: number
  page: number
  page_size: number
  items: AnswerHistoryItem[]
}

export interface ReviewStats {
  total_answers: number
  correct_answers: number
  overall_accuracy: number
  recent_7_days: Array<{
    date: string
    total: number
    correct: number
  }>
  cognitive_breakdown: Record<string, {
    total: number
    correct: number
    accuracy: number
  }>
}

export interface AIRecommendation {
  knowledge_point: string
  priority: 'high' | 'medium'
  mastery_current: number
  suggested_actions: string[]
  review_focus: string
  estimated_review_time_min: number
  recommended_resources: string
}

export interface ReviewRecommendations {
  has_weak_points: boolean
  message?: string
  weak_point_count: number
  moderate_point_count: number
  overall_mastery: number
  recommendations: AIRecommendation[]
  weak_points_summary: Array<{
    title: string
    mastery: number
    accuracy: number
    attempts: number
    errors: number
    trend: string
  }>
  moderate_points_summary: Array<{
    title: string
    mastery: number
    accuracy: number
    trend: string
  }>
  analysis: MasteryAnalysis
}

export interface ReviewKnowledgePoint {
  id: string
  title: string
  level: number
  explanation: string
  mastery: number | null
  accuracy: number | null
  total_attempts: number
  error_count: number
  trend: string | null
  has_data: boolean
}

export interface EbbinghausNode {
  day: number
  review: boolean
  description: string
}

export interface StudyPlanEnhanced {
  plan_id: string
  name: string
  plan_type: 'short' | 'long'
  daily_hours: number
  short_term_plan: StudyPlanDayHour[] | null
  long_term_plan: StudyPlanWeekDay[] | null
  ebbinghaus_nodes: EbbinghausNode[]
  knowledge_point_ids: string[]
}

export interface StudyPlanDayHour {
  day: number
  date: string
  hours: StudyHourBlock[]
}

export interface StudyHourBlock {
  hour: string
  topic: string
  knowledge_point_ids: string[]
  is_review: boolean
}

export interface StudyPlanWeekDay {
  week: number
  days: StudyDayItem[]
}

export interface StudyDayItem {
  day: number
  date: string
  topics: string[]
  hours: number
  is_review_day: boolean
  ebbinghaus_day: number | null
}

// Extended Flashcard with review tracking
export interface FlashcardExtended extends Flashcard {
  knowledge_point_id: string | null
  review_count: number
  correct_count: number
  last_review_at: string | null
  accuracy_rate: number
}
