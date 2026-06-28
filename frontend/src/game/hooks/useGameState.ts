// Game State Management — Zustand store

import { create } from 'zustand'
import type { GameState, Grid, GameStats, QuizResult } from '../types'
import { DEFAULT_GAME_CONFIG } from '../config'
import {
  initGame,
  move,
  addRandomTile,
  hasAvailableMoves,
  getMaxTile,
  extractTiles,
} from '../engine/Game2048'
import type { Direction } from '../types'

interface GameStore {
  // ---- 状态 ----
  state: GameState
  grid: Grid
  prevGrid: Grid | null
  score: number
  maxTile: number
  lives: number
  moves: number
  quizTotal: number
  quizCorrect: number
  startTime: number
  elapsedTime: number
  /** 已触发的里程碑 */
  triggeredMilestones: Set<number>
  /** 最近一次合并生成的瓦片位置，用于动画 */
  lastMergedPositions: Set<string>

  // ---- 操作 ----
  startGame: () => void
  makeMove: (dir: Direction) => { moved: boolean; newTiles: number[] }
  pauseGame: () => void
  resumeGame: () => void
  onQuizResult: (result: QuizResult) => void
  endGame: () => void
  tickTimer: () => void
  resetGame: () => void
}

export const useGameStore = create<GameStore>((set, get) => ({
  state: 'ready',
  grid: [],
  prevGrid: null,
  score: 0,
  maxTile: 0,
  lives: DEFAULT_GAME_CONFIG.maxLives,
  moves: 0,
  quizTotal: 0,
  quizCorrect: 0,
  startTime: 0,
  elapsedTime: 0,
  triggeredMilestones: new Set(),
  lastMergedPositions: new Set(),

  startGame: () => {
    const grid = initGame(DEFAULT_GAME_CONFIG.gridSize, DEFAULT_GAME_CONFIG.initialTiles)
    set({
      state: 'playing',
      grid,
      prevGrid: null,
      score: 0,
      maxTile: 2,
      lives: DEFAULT_GAME_CONFIG.maxLives,
      moves: 0,
      quizTotal: 0,
      quizCorrect: 0,
      startTime: Date.now(),
      elapsedTime: 0,
      triggeredMilestones: new Set(),
      lastMergedPositions: new Set(),
    })
  },

  makeMove: (dir: Direction) => {
    const { grid, state } = get()
    if (state !== 'playing') return { moved: false, newTiles: [] }

    const { grid: newGrid, result } = move(grid, dir)
    if (!result.moved) return { moved: false, newTiles: [] }

    // 检测新合并的高值瓦片（里程碑）
    const newMaxTiles: number[] = []
    for (const mt of result.mergedTiles) {
      if (DEFAULT_GAME_CONFIG.quiz.milestoneTiles.includes(mt.value)) {
        newMaxTiles.push(mt.value)
      }
    }

    // 添加随机瓦片
    const finalGrid = addRandomTile(newGrid) || newGrid
    const maxTile = getMaxTile(finalGrid)

    const mergedPosSet = new Set(
      result.mergedTiles.map(m => `${m.row},${m.col}`),
    )

    set({
      prevGrid: grid,
      grid: finalGrid,
      score: get().score + result.scoreGained,
      maxTile,
      moves: get().moves + 1,
      lastMergedPositions: mergedPosSet,
      state: newMaxTiles.length > 0 ? 'answering' : (hasAvailableMoves(finalGrid) ? 'playing' : 'game_over'),
    })

    return { moved: true, newTiles: newMaxTiles }
  },

  pauseGame: () => {
    set({ state: 'paused' })
  },

  resumeGame: () => {
    set({ state: 'playing' })
  },

  onQuizResult: (result: QuizResult) => {
    const { lives, quizTotal, quizCorrect, score, grid } = get()
    const newQuizTotal = quizTotal + 1
    const newQuizCorrect = quizCorrect + (result.isCorrect ? 1 : 0)
    const newLives = result.isCorrect ? lives : lives - 1
    const diff = DEFAULT_GAME_CONFIG.quiz.difficultyMap[
      getMaxTile(grid) as keyof typeof DEFAULT_GAME_CONFIG.quiz.difficultyMap
    ] || 'easy'
    const bonusPoints = result.isCorrect ? DEFAULT_GAME_CONFIG.scoring.quizCorrect[diff] : 0

    // 记录已触发的里程碑
    const newTriggered = new Set(get().triggeredMilestones)
    const currentMaxTile = getMaxTile(grid)
    if (DEFAULT_GAME_CONFIG.quiz.milestoneTiles.includes(currentMaxTile)) {
      newTriggered.add(currentMaxTile)
    }

    const canContinue = newLives > 0 && hasAvailableMoves(grid)

    set({
      state: canContinue ? 'playing' : 'game_over',
      quizTotal: newQuizTotal,
      quizCorrect: newQuizCorrect,
      score: score + bonusPoints,
      lives: newLives,
      triggeredMilestones: newTriggered,
    })
  },

  endGame: () => {
    set({ state: 'game_over' })
  },

  tickTimer: () => {
    const { startTime } = get()
    if (startTime > 0) {
      set({ elapsedTime: Math.floor((Date.now() - startTime) / 1000) })
    }
  },

  resetGame: () => {
    set({
      state: 'ready',
      grid: [],
      prevGrid: null,
      score: 0,
      maxTile: 0,
      lives: DEFAULT_GAME_CONFIG.maxLives,
      moves: 0,
      quizTotal: 0,
      quizCorrect: 0,
      startTime: 0,
      elapsedTime: 0,
      triggeredMilestones: new Set(),
      lastMergedPositions: new Set(),
    })
  },
}))

/** 提取当前棋盘瓦片 */
export function useTiles() {
  return extractTiles(useGameStore.getState().grid, useGameStore.getState().prevGrid)
}

/** 获取游戏统计 */
export function getGameStats(): GameStats {
  const s = useGameStore.getState()
  return {
    score: s.score,
    maxTile: s.maxTile,
    moves: s.moves,
    quizTotal: s.quizTotal,
    quizCorrect: s.quizCorrect,
    lives: s.lives,
    startTime: s.startTime,
    elapsedTime: Math.floor((Date.now() - s.startTime) / 1000),
  }
}
