// Quiz Gate Hook — manages the quiz flow within the game

import { useState, useCallback, useEffect, useRef } from 'react'
import type { GameQuestion, QuizGateState, QuestionDifficulty } from '../types'
import { DEFAULT_GAME_CONFIG } from '../config'
import { QuestionBankManager } from '../quiz/QuestionBankManager'
import { QuestionScheduler } from '../quiz/QuestionScheduler'
import { useGameStore } from './useGameState'

interface UseQuizGateReturn {
  quizState: QuizGateState
  /** 为指定里程碑触发答题门禁 */
  triggerQuiz: (milestoneValue: number) => Promise<void>
  /** 选择答案 */
  selectAnswer: (answer: string) => void
  /** 提交答案 */
  submitAnswer: () => void
  /** 关闭反馈并继续 */
  dismissFeedback: () => void
  /** 倒计时 tick */
  tick: () => void
  /** 初始化题库 */
  init: () => Promise<void>
}

export function useQuizGate(): UseQuizGateReturn {
  const [quizState, setQuizState] = useState<QuizGateState>({
    question: null,
    userAnswer: '',
    timeLeft: DEFAULT_GAME_CONFIG.quiz.timeLimit,
    isSubmitted: false,
    result: null,
    showFeedback: false,
  })

  const bankRef = useRef<QuestionBankManager | null>(null)
  const schedulerRef = useRef<QuestionScheduler | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 初始化题库
  const init = useCallback(async () => {
    const cfg = DEFAULT_GAME_CONFIG.quiz
    const bank = new QuestionBankManager(cfg.source, cfg.remoteUrl)
    const scheduler = new QuestionScheduler(bank)

    // 预加载所有难度
    await Promise.all(
      (['easy', 'medium', 'hard'] as QuestionDifficulty[]).map(d =>
        scheduler.prepareFor(d, 10),
      ),
    )

    bankRef.current = bank
    schedulerRef.current = scheduler
  }, [])

  // 触发答题
  const triggerQuiz = useCallback(async (milestoneValue: number) => {
    const scheduler = schedulerRef.current
    const cfg = DEFAULT_GAME_CONFIG.quiz
    const difficulty = cfg.difficultyMap[
      milestoneValue as keyof typeof cfg.difficultyMap
    ] || 'easy'

    // 确保有足够题目
    if (scheduler) {
      await scheduler.prepareFor(difficulty, 5)
    }

    const question = scheduler?.pick(difficulty) || getFallbackQuestion(difficulty)

    setQuizState({
      question,
      userAnswer: '',
      timeLeft: cfg.timeLimit,
      isSubmitted: false,
      result: null,
      showFeedback: false,
    })

    // 启动倒计时
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setQuizState(prev => {
        if (prev.isSubmitted) return prev
        const newTimeLeft = prev.timeLeft - 1
        if (newTimeLeft <= 0) {
          // 超时自动提交
          return { ...prev, timeLeft: 0 }
        }
        return { ...prev, timeLeft: newTimeLeft }
      })
    }, 1000)
  }, [])

  // 选择答案
  const selectAnswer = useCallback((answer: string) => {
    setQuizState(prev => {
      if (prev.isSubmitted) return prev
      if (prev.question?.question_type === 'multi_choice') {
        // 多选：toggle
        const vals = prev.userAnswer ? prev.userAnswer.split(',').filter(Boolean) : []
        const idx = vals.indexOf(answer)
        if (idx >= 0) vals.splice(idx, 1)
        else vals.push(answer)
        return { ...prev, userAnswer: vals.join(',') }
      }
      return { ...prev, userAnswer: answer }
    })
  }, [])

  // 提交答案
  const submitAnswer = useCallback(() => {
    setQuizState(prev => {
      if (prev.isSubmitted || !prev.question) return prev

      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }

      const correctAnswer = prev.question.answer
      const userAnswer = prev.userAnswer || ''
      const isCorrect = checkAnswer(prev.question, userAnswer)
      const elapsed = DEFAULT_GAME_CONFIG.quiz.timeLimit - prev.timeLeft

      return {
        ...prev,
        isSubmitted: true,
        result: {
          questionId: prev.question.id,
          userAnswer,
          correctAnswer,
          isCorrect,
          timeSpent: elapsed * 1000,
        },
        showFeedback: true,
      }
    })
  }, [])

  // 关闭反馈
  const dismissFeedback = useCallback(() => {
    const result = quizState.result
    if (result) {
      useGameStore.getState().onQuizResult(result)
    }
    setQuizState({
      question: null,
      userAnswer: '',
      timeLeft: DEFAULT_GAME_CONFIG.quiz.timeLimit,
      isSubmitted: false,
      result: null,
      showFeedback: false,
    })
  }, [quizState.result])

  // Tick for override
  const tick = useCallback(() => {
    // This is handled by the interval, but available for manual ticking
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  return { quizState, triggerQuiz, selectAnswer, submitAnswer, dismissFeedback, tick, init }
}

/** 判断答案是否正确 */
function checkAnswer(q: GameQuestion, userAnswer: string): boolean {
  const correct = q.answer.trim()
  const user = userAnswer.trim()

  if (q.question_type === 'multi_choice') {
    // 多选题：排序后比较
    const cSet = correct.split(',').map(s => s.trim()).sort().join(',')
    const uSet = user.split(',').map(s => s.trim()).filter(Boolean).sort().join(',')
    return cSet === uSet
  }

  // 单选/判断：大小写不敏感
  return correct.toUpperCase() === user.toUpperCase()
}

/** 回退题目：当题库无法加载时使用 */
function getFallbackQuestion(difficulty: QuestionDifficulty): GameQuestion {
  const id = 'fallback_' + Date.now()
  return {
    id,
    question_type: 'single_choice',
    difficulty,
    question_text: '以下哪项是软件工程中"高内聚低耦合"原则的正确理解？',
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
