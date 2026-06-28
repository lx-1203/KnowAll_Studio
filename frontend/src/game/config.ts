// Game Agent Module - Default Configuration

import type { GameConfig } from './types'

export const DEFAULT_GAME_CONFIG: GameConfig = {
  gridSize: 4,
  initialTiles: 2,
  winTile: 2048,
  maxLives: 3,

  quiz: {
    source: 'local',
    remoteUrl: '/api/v1/game/quiz',
    timeLimit: 30,
    questionTypes: ['single_choice', 'multi_choice', 'true_false'],
    milestoneTiles: [256, 512, 1024, 2048],
    difficultyMap: {
      256: 'easy',
      512: 'easy',
      1024: 'medium',
      2048: 'hard',
    },
  },

  scoring: {
    quizCorrect: {
      easy: 20,
      medium: 50,
      hard: 100,
    },
    winBonus: 500,
  },
}

/** 检查是否到达里程碑 */
export function getMilestoneDifficulty(
  tileValue: number,
  config: GameConfig = DEFAULT_GAME_CONFIG,
): import('./types').QuestionDifficulty | null {
  const map = config.quiz.difficultyMap
  if (tileValue in map) {
    return map[tileValue as keyof typeof map]
  }
  return null
}

/** 是否触发答题门禁 */
export function shouldTriggerQuiz(
  tileValue: number,
  triggered: Set<number>,
  config: GameConfig = DEFAULT_GAME_CONFIG,
): boolean {
  return config.quiz.milestoneTiles.includes(tileValue) && !triggered.has(tileValue)
}

/** 瓦片颜色映射 */
export const TILE_COLORS: Record<number, { bg: string; text: string }> = {
  0: { bg: '#cdc1b4', text: '#776e65' },
  2: { bg: '#eee4da', text: '#776e65' },
  4: { bg: '#ede0c8', text: '#776e65' },
  8: { bg: '#f2b179', text: '#f9f6f2' },
  16: { bg: '#f59563', text: '#f9f6f2' },
  32: { bg: '#f67c5f', text: '#f9f6f2' },
  64: { bg: '#f65e3b', text: '#f9f6f2' },
  128: { bg: '#edcf72', text: '#f9f6f2' },
  256: { bg: '#edcc61', text: '#f9f6f2' },
  512: { bg: '#edc850', text: '#f9f6f2' },
  1024: { bg: '#edc53f', text: '#f9f6f2' },
  2048: { bg: '#edc22e', text: '#f9f6f2' },
  4096: { bg: '#3c3a32', text: '#f9f6f2' },
  8192: { bg: '#3c3a32', text: '#f9f6f2' },
}

export function getTileColor(value: number) {
  return TILE_COLORS[value] || { bg: '#3c3a32', text: '#f9f6f2' }
}

/** 字体大小随数字位数适配 */
export function getTileFontSize(value: number, cellSize: number): number {
  const len = String(value).length
  if (len <= 2) return cellSize * 0.4
  if (len <= 3) return cellSize * 0.32
  if (len <= 4) return cellSize * 0.26
  return cellSize * 0.2
}
