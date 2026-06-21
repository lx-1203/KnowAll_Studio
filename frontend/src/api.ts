import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
})

// Documents
export const uploadDocument = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/documents/upload', form).then(r => r.data)
}
export const listDocuments = () => api.get('/documents/').then(r => r.data)
export const getDocumentChunks = (docId: string) => api.get(`/documents/${docId}/chunks`).then(r => r.data)
export const getDocumentRaw = (docId: string) => `/api/v1/documents/${docId}/raw`
export const getDocumentSlides = (docId: string) => api.get(`/documents/${docId}/slides`).then(r => r.data)
export const deleteDocument = (docId: string) => api.delete(`/documents/${docId}`).then(r => r.data)

// Knowledge Tree
export const generateTree = (params: object) => api.post('/knowledge/tree/generate', params).then(r => r.data)
export const getTree = (treeId: string) => api.get(`/knowledge/tree/${treeId}`).then(r => r.data)
export const updateTree = (treeId: string, data: object) => api.put(`/knowledge/tree/${treeId}`, data).then(r => r.data)
export const listTrees = () => api.get('/knowledge/trees').then(r => r.data)
export const generateOutline = (params: object) => api.post('/knowledge/outline/generate', params).then(r => r.data)

// Quiz
export const generateQuestions = (params: object) => api.post('/quiz/generate', params).then(r => r.data)
export const createExam = (params: object) => api.post('/quiz/exam/create', params).then(r => r.data)
export const submitExam = (params: object) => api.post('/quiz/exam/submit', params).then(r => r.data)
export const getErrorQuestions = () => api.get('/quiz/errors').then(r => r.data)
export const generateVariants = (errorId: string, count: number) => api.post(`/quiz/errors/${errorId}/variants`, null, { params: { count } }).then(r => r.data)
export const listQuestions = (params?: object) => api.get('/quiz/questions', { params }).then(r => r.data)

// Flashcards
export const generateCards = (params: object) => api.post('/flashcards/generate', params).then(r => r.data)
export const reviewCard = (cardId: string, rating: number) => api.post('/flashcards/review', { card_id: cardId, rating }).then(r => r.data)
export const getDueCards = (limit?: number) => api.get('/flashcards/due', { params: { limit } }).then(r => r.data)
export const listDecks = () => api.get('/flashcards/decks').then(r => r.data)

// Chat
export const chatWithAssistant = (params: object) => api.post('/chat/assistant', params).then(r => r.data)
export const listConversations = () => api.get('/chat/conversations').then(r => r.data)
export const getConversation = (convId: string) => api.get(`/chat/conversations/${convId}`).then(r => r.data)
export const listRoles = () => api.get('/chat/roles').then(r => r.data)

// Admin
export const addAPIKey = (params: object) => api.post('/admin/keys', params).then(r => r.data)
export const getQuotaStatus = () => api.get('/admin/quota/status').then(r => r.data)
export const getCacheStats = () => api.get('/admin/cache/stats').then(r => r.data)

// Pipeline
export const runPipeline = (params: object) => api.post('/pipeline/run', params).then(r => r.data)
export const runPipelineStream = (params: object) =>
  fetch('/api/v1/pipeline/run/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params) })

// Game
export const generateGameLevels = (params: object) => api.post('/generate/game-levels', params).then(r => r.data)

// URL Import
export const importURL = (url: string) => api.post('/documents/import-url', { url }).then(r => r.data)

// Knowledge Merge
export const mergeTrees = (treeIds: string[], name: string) =>
  api.post('/knowledge/tree/merge', { tree_ids: treeIds, merged_name: name }).then(r => r.data)

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

export default api
