// Question Scheduler — selects questions based on game progress

import type { GameQuestion, QuestionDifficulty } from '../types'
import { QuestionBankManager } from './QuestionBankManager'

/** 题目调度器：根据里程碑和难度选题，避免重复 */
export class QuestionScheduler {
  private bank: QuestionBankManager
  private usedIds = new Set<string>()
  private preloadedDifficulties = new Set<QuestionDifficulty>()

  constructor(bank: QuestionBankManager) {
    this.bank = bank
  }

  /** 为指定里程碑预加载题目 */
  async prepareFor(difficulty: QuestionDifficulty, count = 5): Promise<void> {
    if (this.preloadedDifficulties.has(difficulty)) return
    await this.bank.preload(difficulty, count)
    this.preloadedDifficulties.add(difficulty)
  }

  /** 选择一道未用过的题目 */
  pick(difficulty: QuestionDifficulty): GameQuestion | null {
    // 尝试从题库中找未用过的
    const maxAttempts = 50
    for (let i = 0; i < maxAttempts; i++) {
      const q = this.bank.getNext()
      if (!q) break
      if (!this.usedIds.has(q.id) && q.difficulty === difficulty) {
        this.usedIds.add(q.id)
        return q
      }
    }

    // 回退：允许不同难度
    for (let i = 0; i < maxAttempts; i++) {
      const q = this.bank.getNext()
      if (!q) break
      if (!this.usedIds.has(q.id)) {
        this.usedIds.add(q.id)
        return q
      }
    }

    // 最终回退：复用已出过的题
    return this.bank.getRandom()
  }

  /** 重置已用记录 */
  reset(): void {
    this.usedIds.clear()
    this.bank.reset()
  }
}
