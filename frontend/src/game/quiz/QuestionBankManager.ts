// Question Bank Manager — loads questions from local JSON or remote API

import type { GameQuestion, QuestionDifficulty } from '../types'

/** 题库源接口 */
interface QuestionSource {
  fetch(difficulty: QuestionDifficulty, count: number): Promise<GameQuestion[]>
}

/** 本地 JSON 题库源 */
class LocalQuestionSource implements QuestionSource {
  private cache: Map<string, GameQuestion[]> = new Map()

  async fetch(difficulty: QuestionDifficulty, count: number): Promise<GameQuestion[]> {
    const key = `default_${difficulty}`
    if (!this.cache.has(key)) {
      try {
        // 动态导入 JSON 题库
        const module = await import(`../data/default_${difficulty}.json`)
        const questions = (module.default || module) as GameQuestion[]
        this.cache.set(key, questions)
      } catch {
        console.warn(`[QuestionBank] 无法加载本地题库: ${key}，尝试远程回退`)
        return []
      }
    }
    const pool = this.cache.get(key) || []
    return pickRandom(pool, count)
  }
}

/** 远程 API 题库源 */
class RemoteQuestionSource implements QuestionSource {
  constructor(private baseUrl: string) {}

  async fetch(difficulty: QuestionDifficulty, count: number): Promise<GameQuestion[]> {
    try {
      const resp = await fetch(`${this.baseUrl}?difficulty=${difficulty}&count=${count}`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      return (data.questions || data) as GameQuestion[]
    } catch (e) {
      console.warn(`[QuestionBank] 远程题库请求失败: ${e}`)
      return []
    }
  }
}

/** Fisher-Yates 洗牌取前 N */
function pickRandom<T>(arr: T[], n: number): T[] {
  const shuffled = [...arr]
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
  }
  return shuffled.slice(0, n)
}

/** 题库管理器 */
export class QuestionBankManager {
  private source: QuestionSource
  private pool: GameQuestion[] = []
  private nextIndex = 0

  constructor(sourceType: 'local' | 'remote', remoteUrl?: string) {
    this.source = sourceType === 'remote' && remoteUrl
      ? new RemoteQuestionSource(remoteUrl)
      : new LocalQuestionSource()
  }

  /** 预加载指定难度的题目到内存池 */
  async preload(difficulty: QuestionDifficulty, count: number): Promise<void> {
    const questions = await this.source.fetch(difficulty, Math.max(count, 10))
    // 去重合并
    const existingIds = new Set(this.pool.map(q => q.id))
    for (const q of questions) {
      if (!existingIds.has(q.id)) {
        this.pool.push(q)
      }
    }
  }

  /** 获取下一道题（顺序循环） */
  getNext(): GameQuestion | null {
    if (this.pool.length === 0) return null
    const q = this.pool[this.nextIndex % this.pool.length]
    this.nextIndex++
    return q
  }

  /** 获取随机题 */
  getRandom(): GameQuestion | null {
    if (this.pool.length === 0) return null
    return this.pool[Math.floor(Math.random() * this.pool.length)]
  }

  /** 剩余题目数 */
  get remaining(): number {
    return Math.max(0, this.pool.length - this.nextIndex)
  }

  /** 重置指针 */
  reset(): void {
    this.nextIndex = 0
  }

  /** 清空题库 */
  clear(): void {
    this.pool = []
    this.nextIndex = 0
  }
}
