// Game Agent Module - Type Definitions

/** 游戏状态枚举 */
export type GameState = 'ready' | 'playing' | 'answering' | 'paused' | 'game_over'

/** 2048 棋盘：4x4 二维数组，0 表示空格 */
export type Grid = number[][]

/** 单个瓦片 */
export interface Tile {
  id: number
  value: number
  row: number
  col: number
  /** 是否刚合并生成 */
  merged: boolean
  /** 是否新生成 */
  isNew: boolean
}

/** 移动方向 */
export type Direction = 'up' | 'down' | 'left' | 'right'

/** 移动结果 */
export interface MoveResult {
  moved: boolean
  scoreGained: number
  mergedTiles: { row: number; col: number; value: number }[]
}

/** 题目难度 */
export type QuestionDifficulty = 'easy' | 'medium' | 'hard'

/** 题目类型（游戏内支持的类型） */
export type GameQuestionType = 'single_choice' | 'multi_choice' | 'true_false'

/** 题目选项 */
export interface GameOption {
  label: string
  text: string
}

/** 一道游戏题目 */
export interface GameQuestion {
  id: string
  question_type: GameQuestionType
  difficulty: QuestionDifficulty
  question_text: string
  options: GameOption[]
  answer: string           // 正确答案标签，多选用逗号分隔
  analysis?: string
}

/** 题库配置 */
export interface QuizBankConfig {
  source: 'local' | 'remote'
  remoteUrl: string
  timeLimit: number               // 秒
  questionTypes: GameQuestionType[]
  /** 里程碑 → 难度映射 */
  difficultyMap: Record<number, QuestionDifficulty>
  /** 触发答题的里程碑瓦片值 */
  milestoneTiles: number[]
}

/** 游戏配置 */
export interface GameConfig {
  gridSize: number                // 4
  initialTiles: number            // 2
  winTile: number                 // 2048
  maxLives: number                // 3
  quiz: QuizBankConfig
  scoring: {
    quizCorrect: Record<QuestionDifficulty, number>
    winBonus: number
  }
}

/** 答题结果 */
export interface QuizResult {
  questionId: string
  userAnswer: string
  correctAnswer: string
  isCorrect: boolean
  timeSpent: number               // 毫秒
}

/** 游戏统计 */
export interface GameStats {
  score: number
  maxTile: number
  moves: number
  quizTotal: number
  quizCorrect: number
  lives: number
  startTime: number
  elapsedTime: number
}

/** QuizGate 状态 */
export interface QuizGateState {
  question: GameQuestion | null
  userAnswer: string
  timeLeft: number
  isSubmitted: boolean
  result: QuizResult | null
  showFeedback: boolean
}
