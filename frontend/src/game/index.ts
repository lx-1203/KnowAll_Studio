// Game Agent Module — barrel export

export { DEFAULT_GAME_CONFIG, getTileColor, getTileFontSize, getMilestoneDifficulty, shouldTriggerQuiz } from './config'
export type { GameConfig, GameState, Grid, Tile, Direction, MoveResult, GameQuestion, GameQuestionType, QuestionDifficulty, QuizResult, GameStats, QuizGateState, QuizBankConfig, GameOption } from './types'
export { useGameStore, useTiles, getGameStats } from './hooks/useGameState'
export { useQuizGate } from './hooks/useQuizGate'
export { useQuizGateStore } from './hooks/useQuizGateStore'
export { QuestionBankManager } from './quiz/QuestionBankManager'
export { QuestionScheduler } from './quiz/QuestionScheduler'
export { initGame, move, addRandomTile, hasAvailableMoves, getMaxTile, extractTiles } from './engine/Game2048'
