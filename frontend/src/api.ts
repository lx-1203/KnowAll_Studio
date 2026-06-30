import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
})

// 401 interceptor: clear token and redirect to login
api.interceptors.response.use(
  r => r,
  error => {
    if (error.response?.status === 401) {
      const url = error.config?.url || ''
      // Don't trigger on login/register requests themselves
      if (!url.includes('/auth/login') && !url.includes('/auth/register')) {
        setAuthToken(null)
        localStorage.removeItem('knowall_user')
        window.dispatchEvent(new Event('auth:logout'))
      }
    }
    return Promise.reject(error)
  },
)

// Documents
export const uploadDocument = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/documents/upload', form).then(r => r.data)
}
export const listDocuments = (limit?: number, offset?: number) =>
  api.get('/documents/', { params: { limit: limit || 50, offset: offset || 0 } }).then(r => r.data)
export const getDocumentChunks = (docId: string) => api.get(`/documents/${docId}/chunks`).then(r => r.data)
export const getDocumentRaw = (docId: string) => `/api/v1/documents/${docId}/raw`
export const getDocumentSlides = (docId: string) => api.get(`/documents/${docId}/slides`).then(r => r.data)
export const getNativeOutline = (docId: string) => api.get(`/documents/${docId}/native-outline`).then(r => r.data)
export const analyzeDocumentImages = (docId: string, params?: object) =>
  api.post(`/documents/${docId}/analyze-images`, params || {}).then(r => r.data)
export const deleteDocument = (docId: string) => api.delete(`/documents/${docId}`).then(r => r.data)
export const getDocumentDetail = (docId: string) => api.get(`/documents/${docId}`).then(r => r.data)
export const indexDocument = (docId: string) => api.post(`/search/index?doc_id=${docId}`).then(r => r.data)

// Knowledge Tree
export const generateTree = (params: object) => api.post('/knowledge/tree/generate', params).then(r => r.data)
export const getTree = (treeId: string) => api.get(`/knowledge/tree/${treeId}`).then(r => r.data)
export const updateTree = (treeId: string, data: object) => api.put(`/knowledge/tree/${treeId}`, data).then(r => r.data)
export const deleteTree = (treeId: string) => api.delete(`/knowledge/tree/${treeId}`).then(r => r.data)
export const listTrees = (limit?: number, offset?: number) =>
  api.get('/knowledge/trees', { params: { limit: limit || 50, offset: offset || 0 } }).then(r => r.data)
export const generateOutline = (params: object) => api.post('/knowledge/outline/generate', params).then(r => r.data)

// Quiz
export const generateQuestions = (params: object) => api.post('/quiz/generate', params).then(r => r.data)
export const saveToBank = (params: object) => api.post('/quiz/bank/save', params).then(r => r.data)
export const deleteQuestion = (questionId: string) => api.delete(`/quiz/bank/${questionId}`).then(r => r.data)
export const deleteQuestionsBatch = (ids: string[]) => api.post('/quiz/bank/delete-batch', ids).then(r => r.data)
export const createExam = (params: object) => api.post('/quiz/exam/create', params).then(r => r.data)
export const submitExam = (params: object) => api.post('/quiz/exam/submit', params).then(r => r.data)
export const getErrorQuestions = () => api.get('/quiz/errors').then(r => r.data)
export const generateVariants = (errorId: string, count: number) => api.post(`/quiz/errors/${errorId}/variants`, null, { params: { count } }).then(r => r.data)
export const listQuestions = (params?: object) =>
  api.get('/quiz/questions', { params: { limit: 200, offset: 0, ...params } }).then(r => r.data)

// Flashcards
export const generateCards = (params: object) => api.post('/flashcards/generate', params).then(r => r.data)
export const reviewCard = (cardId: string, rating: number) => api.post('/flashcards/review', { card_id: cardId, rating }).then(r => r.data)
export const getDueCards = (limit?: number) => api.get('/flashcards/due', { params: { limit } }).then(r => r.data)
export const listDecks = (limit?: number, offset?: number) =>
  api.get('/flashcards/decks', { params: { limit: limit || 50, offset: offset || 0 } }).then(r => r.data)
export const searchCards = (q: string, top_k?: number, tags?: string) =>
  api.get('/flashcards/search', { params: { q, top_k: top_k || 10, tags: tags || '' } }).then(r => r.data)
export const getRelatedCards = (cardId: string, top_k?: number) =>
  api.get(`/flashcards/related/${cardId}`, { params: { top_k: top_k || 5 } }).then(r => r.data)
export const generateDeckSummary = (deckId: string, model?: string) =>
  api.post(`/flashcards/deck/${deckId}/summary`, { model: model || 'deepseek-chat' }).then(r => r.data)

// Memory Feedback
export const scanFeedback = (params?: object) => api.post('/memory/feedback/scan', params || {}).then(r => r.data)
export const getReviewQueue = (limit?: number) =>
  api.get('/memory/review-queue', { params: { limit: limit || 20 } }).then(r => r.data)
export const completeReviewItem = (queueId: string) =>
  api.post('/memory/review-queue/complete', { queue_id: queueId }).then(r => r.data)
export const getMemoryStats = () => api.get('/memory/stats').then(r => r.data)
export const recordFlashcardResult = (cardId: string, isCorrect: boolean) =>
  api.post(`/memory/flashcards/${cardId}/record`, null, { params: { is_correct: isCorrect } }).then(r => r.data)
export const detectDecay = (lookbackReviews?: number, decayThreshold?: number) =>
  api.post('/memory/feedback/detect-decay', null, {
    params: { lookback_reviews: lookbackReviews || 5, decay_threshold: decayThreshold || 2 },
  }).then(r => r.data)
export const getRelatedFlashcards = (cardId: string, limit?: number) =>
  api.get(`/memory/flashcards/${cardId}/related`, { params: { limit: limit || 5 } }).then(r => r.data)

// Chat
export const chatWithAssistant = (params: object) => api.post('/chat/assistant', params).then(r => r.data)
export const listConversations = () => api.get('/chat/conversations').then(r => r.data)
export const getConversation = (convId: string) => api.get(`/chat/conversations/${convId}`).then(r => r.data)
export const deleteConversation = (convId: string) => api.delete(`/chat/conversations/${convId}`).then(r => r.data)
export const renameConversation = (convId: string, title: string) => api.put(`/chat/conversations/${convId}`, { title }).then(r => r.data)
export const listRoles = () => api.get('/chat/roles').then(r => r.data)

// Admin
export const addAPIKey = (params: object) => api.post('/admin/keys', params).then(r => r.data)
export const getQuotaStatus = () => api.get('/admin/quota/status').then(r => r.data)
export const getCacheStats = () => api.get('/admin/cache/stats').then(r => r.data)

// Pipeline
export const runPipeline = (params: object) => api.post('/pipeline/run', params).then(r => r.data)
export const runPipelineStream = (params: object) =>
  fetch('/api/v1/pipeline/run/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params) })
export const cancelPipeline = (documentId: string) => api.post('/pipeline/cancel', null, { params: { document_id: documentId } }).then(r => r.data)

// Game
export const generateGameLevels = (params: object) => api.post('/generate/game-levels', params).then(r => r.data)
export const saveGameProgress = (params: object) => api.post('/generate/game-progress', params).then(r => r.data)
export const getGameProgress = (gameType?: string) =>
  api.get('/generate/game-progress', { params: { game_type: gameType } }).then(r => r.data)

// Game Quiz (new)
export const getGameQuizQuestions = (difficulty: string, count = 5, source = 'local') =>
  api.get('/game/quiz', { params: { difficulty, count, source } }).then(r => r.data)
export const getLocalQuizInfo = () =>
  api.get('/game/quiz/local').then(r => r.data)

// URL Import
export const importURL = (url: string) => api.post('/documents/import-url', { url }).then(r => r.data)

// Knowledge Merge
export const mergeTrees = (treeIds: string[], name: string) =>
  api.post('/knowledge/tree/merge', { tree_ids: treeIds, merged_name: name }).then(r => r.data)

// Knowledge Edges
export const createEdge = (params: object) => api.post('/knowledge/edges', params).then(r => r.data)
export const listEdges = (treeId: string) => api.get(`/knowledge/edges/${treeId}`).then(r => r.data)
export const deleteEdge = (edgeId: string) => api.delete(`/knowledge/edges/${edgeId}`).then(r => r.data)

// Search / RAG
export const searchDocuments = (query: string, topK?: number) =>
  api.post('/search/', { query, top_k: topK || 5 }).then(r => r.data)
export const ragQuery = (query: string, topK?: number) =>
  api.post('/search/rag', { query, top_k: topK || 3 }).then(r => r.data)

// Stats
export const getOverview = () => api.get('/stats/overview').then(r => r.data)
export const getDailyStats = (days?: number) => api.get('/stats/daily', { params: { days } }).then(r => r.data)
export const getTopicStats = () => api.get('/stats/topics').then(r => r.data)

// Backup
export const exportBackup = () => api.get('/backup/export').then(r => r.data)
export const exportFiles = () => api.get('/backup/files', { responseType: 'blob' }).then(r => r.data)
export const importBackup = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/backup/import', form).then(r => r.data)
}

// Study Plan
export const listPlans = (limit?: number, offset?: number) =>
  api.get('/study/plans', { params: { limit: limit || 50, offset: offset || 0 } }).then(r => r.data)
export const getPlan = (planId: string) => api.get(`/study/plans/${planId}`).then(r => r.data)
export const createPlan = (params: object) => api.post('/study/plans', params).then(r => r.data)
export const deletePlan = (planId: string) => api.delete(`/study/plans/${planId}`).then(r => r.data)
export const createGoal = (params: object) => api.post('/study/goals', params).then(r => r.data)
export const toggleGoal = (goalId: string) => api.put(`/study/goals/${goalId}/toggle`).then(r => r.data)
export const getDueReminders = () => api.get('/study/reminders/due').then(r => r.data)

// Share
export const createShareLink = (params: object) => api.post('/share/create', params).then(r => r.data)
export const listShareLinks = (limit?: number, offset?: number) =>
  api.get('/share/my-links', { params: { limit: limit || 50, offset: offset || 0 } }).then(r => r.data)
export const deleteShareLink = (shareId: string) => api.delete(`/share/${shareId}`).then(r => r.data)

// Auth
export const register = (params: { username: string; email: string; password: string }) =>
  api.post('/auth/register', params).then(r => r.data)
export const login = (params: { username: string; password: string }) =>
  api.post('/auth/login', params).then(r => r.data)
export const getProfile = () => api.get('/auth/me').then(r => r.data)

// User Profile & Settings
export const getUserProfile = () => api.get('/user/profile').then(r => r.data)
export const updateUserProfile = (params: { nickname?: string; phone?: string; avatar_url?: string; email?: string }) =>
  api.put('/user/profile', params).then(r => r.data)
export const changePassword = (params: { old_password: string; new_password: string }) =>
  api.put('/user/password', params).then(r => r.data)
export const getUserBinds = () => api.get('/user/binds').then(r => r.data)
export const bindAccount = (params: { provider: string; provider_name?: string; provider_uid?: string }) =>
  api.post('/user/bind', params).then(r => r.data)
export const unbindAccount = (provider: string) => api.delete(`/user/bind/${provider}`).then(r => r.data)
export const getUserHistory = (page?: number, pageSize?: number, actionType?: string) =>
  api.get('/user/history', { params: { page: page || 1, page_size: pageSize || 20, action_type: actionType || '' } }).then(r => r.data)
export const createHistory = (params: { action_type?: string; action_label?: string; resource_type?: string; resource_id?: string; detail?: string }) =>
  api.post('/user/history', null, { params }).then(r => r.data)

// Notifications
export const getNotifications = (page?: number, pageSize?: number, isRead?: string, category?: string) =>
  api.get('/notifications', { params: { page: page || 1, page_size: pageSize || 20, is_read: isRead || '', category: category || '' } }).then(r => r.data)
export const markNotificationRead = (id: string) => api.put(`/notifications/${id}/read`).then(r => r.data)
export const markAllNotificationsRead = () => api.put('/notifications/read-all').then(r => r.data)
export const deleteNotification = (id: string) => api.delete(`/notifications/${id}`).then(r => r.data)
export const batchDeleteNotifications = (ids: string[]) =>
  api.delete('/notifications', { params: { ids: ids.join(',') } }).then(r => r.data)

// Reading Language (阅读语言) - Progressive Chinese-English Mixed Reading
export const getReadingArticles = (difficulty?: number) =>
  api.get('/reading/articles', { params: difficulty ? { difficulty } : {} }).then(r => r.data)
export const getReadingArticle = (id: string) =>
  api.get(`/reading/articles/${id}`).then(r => r.data)
export const convertReadingText = (text: string, level: number, knownWords?: {cn:string;en:string}[], seenWords?: {cn:string;en:string}[]) =>
  api.post('/reading/convert', { text, level, known_words: knownWords || [], seen_words: seenWords || [] }).then(r => r.data)
export const convertReadingStream = (params: { text: string; known_words: {cn:string;en:string}[]; seen_words: {cn:string;en:string}[]; skip_cache?: boolean }) =>
  fetch('/api/v1/reading/convert/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': api.defaults.headers.common['Authorization'] as string || '' },
    body: JSON.stringify(params),
  })
export const uploadReadingArticle = (title: string, content: string) =>
  api.post('/reading/articles/upload', { title, content }).then(r => r.data)
export const uploadReadingArticleFile = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/reading/articles/upload-file', form).then(r => r.data)
}
export const deleteReadingArticle = (id: string) =>
  api.delete(`/reading/articles/${id}`).then(r => r.data)

// ===== Knowledge Summary (NEW) =====
export const generateSummary = (params: object) => api.post('/knowledge/summary/generate', params).then(r => r.data)
export const getSummary = (summaryId: string) => api.get(`/knowledge/summary/${summaryId}`).then(r => r.data)
export const getSummaryNodes = (summaryId: string, level?: number) =>
  api.get(`/knowledge/summary/${summaryId}/nodes`, { params: { level } }).then(r => r.data)
export const getSummaryMindmap = (summaryId: string) =>
  api.get(`/knowledge/summary/${summaryId}/mindmap`).then(r => r.data)
export const deleteSummary = (summaryId: string) =>
  api.delete(`/knowledge/summary/${summaryId}`).then(r => r.data)

// ===== Agent Orchestration (NEW) =====
export const orchestrateAgents = (params: object) => api.post('/agents/orchestrate', params).then(r => r.data)
export const listAgents = () => api.get('/agents/list').then(r => r.data)

// ===== Interactive Quiz (NEW) =====
export const startInteractiveQuiz = (params: object) =>
  api.get('/quiz/interactive/start', { params }).then(r => r.data)
export const submitInteractiveAnswer = (params: object) =>
  api.post('/quiz/interactive/submit', params).then(r => r.data)

// ===== Language Vocabulary (NEW) =====
export const generateVocabulary = (params: object) => api.post('/language/vocabulary/generate', params).then(r => r.data)
export const getVocabulary = (params?: object) => api.get('/language/vocabulary', { params }).then(r => r.data)
export const markVocabularyMastered = (vocabId: string, mastered: boolean) =>
  api.patch(`/language/vocabulary/${vocabId}`, { mastered }).then(r => r.data)

// ===== Coverage Report (NEW) =====
export const getCoverageReport = (summaryId: string) =>
  api.get(`/knowledge/coverage/${summaryId}`).then(r => r.data)
export const refreshCoverage = (params: object) =>
  api.post('/knowledge/coverage/refresh', params).then(r => r.data)

// ===== Answer Review & Mastery (NEW) =====
export const getMasteryAnalysis = () => api.get('/review/mastery').then(r => r.data)
export const getKpMasteryDetail = (kpId: string) => api.get(`/review/mastery/${kpId}`).then(r => r.data)
export const getAnswerHistory = (params?: { kp_id?: string; is_correct?: boolean; page?: number; page_size?: number }) =>
  api.get('/review/history', { params }).then(r => r.data)
export const getReviewStats = () => api.get('/review/stats').then(r => r.data)
export const generateReviewRecommendations = (model?: string) =>
  api.post('/review/recommend', { model: model || 'deepseek-chat' }).then(r => r.data)
export const getReviewKnowledgePoints = () => api.get('/review/knowledge-points').then(r => r.data)

// ===== Enhanced Study Plan (NEW) =====
export const generateEnhancedPlan = (params: object) =>
  api.post('/study/generate-plan-enhanced', params).then(r => r.data)
export const getEbbinghausNodes = (planId: string) =>
  api.get(`/study/plans/${planId}/ebbinghaus`).then(r => r.data)

// Attach token to all requests after login
export const setAuthToken = (token: string | null) => {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`
    localStorage.setItem('knowall_token', token)
  } else {
    delete api.defaults.headers.common['Authorization']
    localStorage.removeItem('knowall_token')
  }
}

// Restore token on app load
const savedToken = localStorage.getItem('knowall_token')
if (savedToken) {
  api.defaults.headers.common['Authorization'] = `Bearer ${savedToken}`
}

export default api
