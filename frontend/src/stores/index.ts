import { create } from 'zustand'
import type { AuthUser } from '../types'
import { setAuthToken } from '../api'

interface Document {
  id: string; filename: string; file_type: string; status: string;
  page_count: number; created_at: string;
}
interface Tree { tree_id: string; name: string; tree_data: any; created_at: string; }
interface Question {
  id: string; question_type: string; difficulty: string; tags: string[];
  question_text: string; options: any[]; answer: string; analysis: string;
}
interface Flashcard {
  id: string; card_type: string; front: string; back: string; hints: string; tags: string[];
}

// ========== Auth Store ==========

interface AuthState {
  token: string | null
  user: AuthUser | null
  isAuthenticated: boolean
  login: (token: string, user: AuthUser) => void
  logout: () => void
  restore: () => boolean
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  isAuthenticated: false,

  login: (token, user) => {
    setAuthToken(token)
    localStorage.setItem('knowall_user', JSON.stringify(user))
    set({ token, user, isAuthenticated: true })
  },

  logout: () => {
    setAuthToken(null)
    localStorage.removeItem('knowall_user')
    set({ token: null, user: null, isAuthenticated: false })
  },

  restore: () => {
    const token = localStorage.getItem('knowall_token')
    if (!token) return false
    try {
      const user = JSON.parse(localStorage.getItem('knowall_user') || '')
      if (user && user.id) {
        setAuthToken(token)
        set({ token, user, isAuthenticated: true })
        return true
      }
    } catch {}
    // Token exists but no user data — clear stale token
    setAuthToken(null)
    localStorage.removeItem('knowall_user')
    return false
  },
}))

// Listen for unauthorized event from API interceptor
if (typeof window !== 'undefined') {
  window.addEventListener('auth:logout', () => {
    useAuthStore.getState().logout()
  })
}

export const useAppStore = create<{
  documents: Document[];
  trees: Tree[];
  questions: Question[];
  selectedDoc: string | null;
  selectedTree: string | null;
  loading: boolean;
  error: string | null;
  setDocuments: (docs: Document[]) => void;
  setTrees: (trees: Tree[]) => void;
  setQuestions: (qs: Question[]) => void;
  setSelectedDoc: (id: string | null) => void;
  setSelectedTree: (id: string | null) => void;
  setLoading: (v: boolean) => void;
  setError: (e: string | null) => void;
}>(set => ({
  documents: [], trees: [], questions: [],
  selectedDoc: null, selectedTree: null,
  loading: false, error: null,
  setDocuments: (docs) => set({ documents: docs }),
  setTrees: (trees) => set({ trees }),
  setQuestions: (qs) => set({ questions: qs }),
  setSelectedDoc: (id) => set({ selectedDoc: id }),
  setSelectedTree: (id) => set({ selectedTree: id }),
  setLoading: (v) => set({ loading: v }),
  setError: (e) => set({ error: e }),
}))

export const useQuizStore = create<{
  currentExam: any | null;
  userAnswers: Record<string, string>;
  results: any | null;
  setCurrentExam: (e: any) => void;
  setAnswer: (questionId: string, answer: string) => void;
  setResults: (r: any) => void;
  reset: () => void;
}>(set => ({
  currentExam: null, userAnswers: {}, results: null,
  setCurrentExam: (e) => set({ currentExam: e, userAnswers: {}, results: null }),
  setAnswer: (qid, ans) => set(s => ({ userAnswers: { ...s.userAnswers, [qid]: ans } })),
  setResults: (r) => set({ results: r }),
  reset: () => set({ currentExam: null, userAnswers: {}, results: null }),
}))

export const useFlashcardStore = create<{
  dueCards: Flashcard[];
  currentIndex: number;
  isFlipped: boolean;
  reviewLimit: number;
  setDueCards: (cards: Flashcard[]) => void;
  flip: () => void;
  next: () => void;
  prev: () => void;
  setCurrentIndex: (i: number) => void;
  setReviewLimit: (n: number) => void;
}>(set => ({
  dueCards: [], currentIndex: 0, isFlipped: false,
  reviewLimit: Number(localStorage.getItem('knowall_review_limit') || 20),
  setDueCards: (cards) => set({ dueCards: cards, currentIndex: 0, isFlipped: false }),
  flip: () => set(s => ({ isFlipped: !s.isFlipped })),
  next: () => set(s => ({
    currentIndex: Math.min(s.currentIndex + 1, s.dueCards.length - 1),
    isFlipped: false,
  })),
  prev: () => set(s => ({
    currentIndex: Math.max(s.currentIndex - 1, 0),
    isFlipped: false,
  })),
  setCurrentIndex: (i) => set({ currentIndex: i, isFlipped: false }),
  setReviewLimit: (n) => {
    localStorage.setItem('knowall_review_limit', String(n))
    set({ reviewLimit: n })
  },
}))
