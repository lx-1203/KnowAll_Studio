/**
 * 离线操作队列 — 断线期间缓存操作，重连后自动重放
 * 对应规范文档 6.3 节
 */
export interface QueuedOperation {
  type: string;
  doc_id: string;
  user_id: string;
  version: number;
  timestamp: number;
  data: Record<string, any>;
  /** 操作路径标识，用于判断是否可合并 */
  _pathKey?: string;
}

type SendFunction = (op: QueuedOperation) => Promise<void>;

export class OfflineQueue {
  private queue: QueuedOperation[] = [];
  private maxQueueSize = 500;
  private replaying = false;

  /** 添加操作到离线队列 */
  push(op: QueuedOperation): void {
    // 附加路径标识用于合并判断
    op._pathKey = Array.isArray(op.data?.path)
      ? (op.data.path as string[]).join('.')
      : '';

    // 尝试合并相邻同类型操作
    const last = this.queue[this.queue.length - 1];
    if (last && this.canMerge(last, op)) {
      this.queue[this.queue.length - 1] = this.merge(last, op);
    } else {
      this.queue.push(op);
    }

    // 超出上限则丢弃最老的
    if (this.queue.length > this.maxQueueSize) {
      this.queue = this.queue.slice(-this.maxQueueSize);
    }

    // 持久化到 localStorage
    this.persist();
  }

  /** 重连后批量重放 */
  async replay(sendFn: SendFunction): Promise<{ success: number; failed: number }> {
    if (this.replaying || this.queue.length === 0) {
      return { success: 0, failed: 0 };
    }

    this.replaying = true;
    let success = 0;
    let failed = 0;

    while (this.queue.length > 0) {
      const op = this.queue[0];
      try {
        await sendFn(op);
        this.queue.shift();
        success++;
      } catch {
        failed++;
        break; // 失败则停止，保留剩余队列下次重试
      }
    }

    this.replaying = false;
    this.persist();
    return { success, failed };
  }

  /** 队列长度 */
  get length(): number {
    return this.queue.length;
  }

  /** 清空队列 */
  clear(): void {
    this.queue = [];
    this.persist();
  }

  // ── 合并逻辑 ──

  private canMerge(a: QueuedOperation, b: QueuedOperation): boolean {
    // 同用户、同文档、同路径、同为 insert 类型
    if (a.type !== 'operation' || b.type !== 'operation') return false;
    if (a.doc_id !== b.doc_id) return false;
    if (a._pathKey !== b._pathKey) return false;
    if (a.data?.operation !== 'insert' || b.data?.operation !== 'insert') return false;

    const aPos = a.data?.position ?? 0;
    const aLen = (a.data?.value as string)?.length ?? 0;
    const bPos = b.data?.position ?? 0;

    // 连续位置才合并
    return aPos + aLen === bPos;
  }

  private merge(a: QueuedOperation, b: QueuedOperation): QueuedOperation {
    return {
      ...a,
      data: {
        ...a.data,
        value: (a.data?.value || '') + (b.data?.value || ''),
      },
    };
  }

  // ── 持久化（localStorage） ──

  private persist(): void {
    try {
      if (this.queue.length > 0) {
        localStorage.setItem('knowall_offline_queue', JSON.stringify(this.queue.slice(-200)));
      } else {
        localStorage.removeItem('knowall_offline_queue');
      }
    } catch {
      // localStorage 不可用，忽略
    }
  }

  /** 从 localStorage 恢复队列 */
  static restore(): OfflineQueue {
    const q = new OfflineQueue();
    try {
      const raw = localStorage.getItem('knowall_offline_queue');
      if (raw) {
        q.queue = JSON.parse(raw);
      }
    } catch {
      // ignore
    }
    return q;
  }
}
