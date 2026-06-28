// Quiz Gate Store — shared Zustand store for quiz gate state
// This MUST be a singleton so GamePage and QuizGateModal share the same state

import { create } from 'zustand'
import type { GameQuestion, QuizGateState, QuestionDifficulty } from '../types'
import { DEFAULT_GAME_CONFIG } from '../config'
import { QuestionBankManager } from '../quiz/QuestionBankManager'
import { QuestionScheduler } from '../quiz/QuestionScheduler'
import { useGameStore } from './useGameState'

interface QuizGateStore {
  // ---- 状态 ----
  quizState: QuizGateState

  // ---- 内部引用 ----
  _bank: QuestionBankManager | null
  _scheduler: QuestionScheduler | null
  _timer: ReturnType<typeof setInterval> | null

  // ---- 操作 ----
  init: () => Promise<void>
  triggerQuiz: (milestoneValue: number) => Promise<void>
  selectAnswer: (answer: string) => void
  submitAnswer: () => void
  dismissFeedback: () => void
  cleanup: () => void
}

function checkAnswer(q: GameQuestion, userAnswer: string): boolean {
  const correct = q.answer.trim()
  const user = userAnswer.trim()
  if (q.question_type === 'multi_choice') {
    const cSet = correct.split(',').map(s => s.trim()).sort().join(',')
    const uSet = user.split(',').map(s => s.trim()).filter(Boolean).sort().join(',')
    return cSet === uSet
  }
  return correct.toUpperCase() === user.toUpperCase()
}

function getFallbackQuestion(difficulty: QuestionDifficulty): GameQuestion {
  return {
    id: 'fallback_' + Date.now(),
    question_type: 'single_choice',
    difficulty,
    question_text: '以下哪项是软件工程中「高内聚低耦合」原则的正确理解？',
    options: [
      { label: 'A', text: '模块内部功能高度相关，模块之间依赖尽量少' },
      { label: 'B', text: '模块之间紧密关联，模块内部功能分散' },
      { label: 'C', text: '所有代码写在一起，方便调用' },
      { label: 'D', text: '模块独立运行，不需要任何通信' },
    ],
    answer: 'A',
    analysis: '高内聚：模块内部功能紧密相关；低耦合：模块之间依赖尽可能少。',
  }
}

export const useQuizGateStore = create<QuizGateStore>((set, get) => ({
  quizState: {
    question: null,
    userAnswer: '',
    timeLeft: DEFAULT_GAME_CONFIG.quiz.timeLimit,
    isSubmitted: false,
    result: null,
    showFeedback: false,
  },

  _bank: null,
  _scheduler: null,
  _timer: null,

  init: async () => {
    const cfg = DEFAULT_GAME_CONFIG.quiz
    const bank = new QuestionBankManager(cfg.source, cfg.remoteUrl)
    const scheduler = new QuestionScheduler(bank)

    await Promise.all(
      (['easy', 'medium', 'hard'] as QuestionDifficulty[]).map(d =>
        scheduler.prepareFor(d, 10),
      ),
    )

    set({ _bank: bank, _scheduler: scheduler })
  },

  triggerQuiz: async (milestoneValue: number) => {
    const { _scheduler, _timer } = get()
    const cfg = DEFAULT_GAME_CONFIG.quiz
    const difficulty = cfg.difficultyMap[
      milestoneValue as keyof typeof cfg.difficultyMap
    ] || 'easy'

    // 确保有足够题目
    if (_scheduler) {
      await _scheduler.prepareFor(difficulty, 5)
    }

    const question = _scheduler?.pick(difficulty) || getFallbackQuestion(difficulty)

    // 清除旧timer
    if (_timer) clearInterval(_timer)

    set({
      quizState: {
        question,
        userAnswer: '',
        timeLeft: cfg.timeLimit,
        isSubmitted: false,
        result: null,
        showFeedback: false,
      },
    })

    // 启动倒计时
    const timer = setInterval(() => {
      const { quizState } = get()
      if (quizState.isSubmitted) {
        clearInterval(timer)
        return
      }
      const newTimeLeft = quizState.timeLeft - 1
      if (newTimeLeft <= 0) {
        clearInterval(timer)
        // 超时自动提交
        get().submitAnswer()
        return
      }
      set({ quizState: { ...quizState, timeLeft: newTimeLeft } })
    }, 1000)

    set({ _timer: timer })
  },

  selectAnswer: (answer: string) => {
    const { quizState } = get()
    if (quizState.isSubmitted) return

    if (quizState.question?.question_type === 'multi_choice') {
      const vals = quizState.userAnswer ? quizState.userAnswer.split(',').filter(Boolean) : []
      const idx = vals.indexOf(answer)
      if (idx >= 0) vals.splice(idx, 1)
      else vals.push(answer)
      set({ quizState: { ...quizState, userAnswer: vals.join(',') } })
    } else {
      set({ quizState: { ...quizState, userAnswer: answer } })
    }
  },

  submitAnswer: () => {
    const { quizState, _timer } = get()
    if (quizState.isSubmitted || !quizState.question) return

    if (_timer) {
      clearInterval(_timer)
      set({ _timer: null })
    }

    const question = quizState.question
    const userAnswer = quizState.userAnswer || ''
    const isCorrect = checkAnswer(question, userAnswer)
    const elapsed = DEFAULT_GAME_CONFIG.quiz.timeLimit - quizState.timeLeft

    set({
      quizState: {
        ...quizState,
        isSubmitted: true,
        result: {
          questionId: question.id,
          userAnswer,
          correctAnswer: question.answer,
          isCorrect,
          timeSpent: elapsed * 1000,
        },
        showFeedback: true,
      },
    })

    // 1.5秒后自动关闭
    setTimeout(() => {
      get().dismissFeedback()
    }, 1500)
  },

  dismissFeedback: () => {
    const { quizState } = get()
    const result = quizState.result
    if (result) {
      // 通知游戏 store
      const { useGameStore } = require('../hooks/useGameState')
      useGameStore.getState().onQuizResult(result)
    }
    set({
      quizState: {
        question: null,
        userAnswer: '',
        timeLeft: DEFAULT_GAME_CONFIG.quiz.timeLimit,
        isSubmitted: false,
        result: null,
        showFeedback: false,
      },
    })
  },

  cleanup: () => {
    const { _timer } = get()
    if (_timer) clearInterval(_timer)
    set({
      quizState: {
        question: null,
        userAnswer: '',
        timeLeft: DEFAULT_GAME_CONFIG.quiz.timeLimit,
        isSubmitted: false,
        result: null,
        showFeedback: false,
      },
      _bank: null,
      _scheduler: null,
      _timer: null,
    })
  },
}))
