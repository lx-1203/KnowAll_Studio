/**
 * 实时同步 WebSocket 客户端
 * 对应规范文档 2.5 节 - 客户端处理流程
 */
type MessageHandler = (msg: SyncMessage) => void;

export interface SyncMessage {
  type: string;
  doc_id?: string;
  room_id?: string;
  user_id?: string;
  user_name?: string;
  version?: number;
  local_version?: number;
  timestamp?: number;
  data: Record<string, any>;
}

export interface SyncClientOptions {
  docId: string;
  userId: string;
  userName: string;
  token?: string;
  url?: string;
  onMessage?: MessageHandler;
  onPresence?: (users: Array<{ user_id: string; user_name: string }>) => void;
  onFileEvent?: (event: SyncMessage) => void;
  onError?: (error: { code: string; msg: string }) => void;
}

export class RealtimeSyncClient {
  private ws: WebSocket | null = null;
  private options: Required<SyncClientOptions>;
  private localVersion = 0;
  private pendingOps: SyncMessage[] = [];
  private offlineQueue: SyncMessage[] = [];
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectDelay = 3000;
  private handlers: Map<string, Set<MessageHandler>> = new Map();

  constructor(options: SyncClientOptions) {
    this.options = {
      url: `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/sync`,
      token: '',
      onMessage: () => {},
      onPresence: () => {},
      onFileEvent: () => {},
      onError: () => {},
      ...options,
    };
  }

  /** 建立连接 */
  connect(): void {
    const { url, docId, userId, userName, token } = this.options;
    const params = new URLSearchParams({ doc_id: docId, user_id: userId, user_name: userName });
    if (token) params.set('token', token);

    try {
      this.ws = new WebSocket(`${url}?${params.toString()}`);
    } catch (e) {
      console.error('[SyncClient] WebSocket 创建失败:', e);
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log('[SyncClient] 已连接, doc=%s', this.options.docId);
      this.reconnectDelay = 3000; // 重置重连间隔
      this.startHeartbeat();
      this.flushOfflineQueue();
    };

    this.ws.onmessage = (event) => {
      try {
        const msg: SyncMessage = JSON.parse(event.data);
        this.handleMessage(msg);
      } catch {
        console.error('[SyncClient] 消息解析失败');
      }
    };

    this.ws.onclose = () => {
      console.log('[SyncClient] 连接断开');
      this.stopHeartbeat();
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      console.error('[SyncClient] WebSocket 错误');
      this.options.onError({ code: 'CONNECTION_ERROR', msg: '连接异常' });
    };
  }

  /** 断开连接 */
  disconnect(): void {
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      // Null all handlers to prevent callbacks after disconnect
      this.ws.onopen = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      // Only close if already OPEN — calling close() on CONNECTING (0)
      // causes "closed before connection is established" error (e.g. React StrictMode double-mount)
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.close();
      }
      this.ws = null;
    }
  }

  /** 用户发起编辑操作 */
  sendOperation(operation: Record<string, any>): void {
    const msg: SyncMessage = {
      type: 'operation',
      doc_id: this.options.docId,
      user_id: this.options.userId,
      version: this.localVersion,
      timestamp: Date.now(),
      data: operation,
    };
    this.send(msg);
  }

  /** 发送光标位置 */
  sendCursor(data: Record<string, any>): void {
    this.send({ type: 'cursor', data } as SyncMessage);
  }

  /** 广播文件上传事件 */
  sendFileEvent(type: string, data: Record<string, any>): void {
    this.send({ type, data } as SyncMessage);
  }

  /** 发送聊天消息 */
  sendChatMessage(content: string, contentType = 'text', fileRef?: string): void {
    this.send({
      type: 'chat_message',
      data: { content, content_type: contentType, file_ref: fileRef || null },
    } as SyncMessage);
  }

  /** 发送上传进度 */
  sendUploadProgress(filename: string, progress: number, status: string): void {
    this.send({
      type: 'upload_progress',
      data: { filename, progress, status },
    } as SyncMessage);
  }

  /** 注册消息处理器 */
  on(type: string, handler: MessageHandler): void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type)!.add(handler);
  }

  /** 移除消息处理器 */
  off(type: string, handler: MessageHandler): void {
    this.handlers.get(type)?.delete(handler);
  }

  getVersion(): number {
    return this.localVersion;
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // ── 私有方法 ──

  private send(msg: SyncMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    } else {
      this.offlineQueue.push(msg); // 离线 → 进队列
      if (this.offlineQueue.length > 500) {
        this.offlineQueue = this.offlineQueue.slice(-500);
      }
    }
  }

  private handleMessage(msg: SyncMessage): void {
    switch (msg.type) {
      case 'ack':
        this.localVersion = msg.data?.new_version ?? this.localVersion;
        break;

      case 'operation':
        if (msg.user_id === this.options.userId) return;
        this.localVersion = msg.version ?? this.localVersion;
        this.options.onMessage(msg);
        break;

      case 'sync_full':
        this.localVersion = msg.data?.version ?? 0;
        this.options.onMessage(msg);
        break;

      case 'sync_diff': {
        const ops = msg.data?.ops ?? [];
        for (const op of ops) {
          this.options.onMessage({ type: 'operation', data: op } as SyncMessage);
        }
        this.localVersion = msg.data?.version ?? this.localVersion;
        break;
      }

      case 'cursor':
        this.options.onMessage(msg);
        break;

      case 'presence':
        this.options.onPresence(msg.data?.online_users ?? []);
        break;

      case 'file_uploaded':
      case 'file_deleted':
      case 'file_updated':
      case 'upload_progress':
        this.options.onFileEvent(msg);
        break;

      case 'chat_message':
      case 'system_notify':
        this.options.onMessage(msg);
        break;

      case 'heartbeat_ack':
        break;

      case 'error':
        if (msg.data?.code === 'VERSION_CONFLICT') {
          this.requestFullSync();
        }
        this.options.onError({
          code: msg.data?.code ?? 'UNKNOWN',
          msg: msg.data?.msg ?? '',
        });
        break;
    }

    // 分发给注册的 handler
    const handlers = this.handlers.get(msg.type);
    if (handlers) {
      for (const h of handlers) h(msg);
    }
  }

  private requestFullSync(): void {
    this.send({
      type: 'reconnect',
      local_version: this.localVersion,
      data: {},
    } as SyncMessage);
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: 'heartbeat', data: {} } as SyncMessage);
    }, 15000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    console.log('[SyncClient] %s 后重连...', this.reconnectDelay);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
      // 指数退避，上限 60s
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 60000);
    }, this.reconnectDelay);
  }

  private async flushOfflineQueue(): Promise<void> {
    while (this.offlineQueue.length > 0) {
      const op = this.offlineQueue.shift();
      if (op && this.ws?.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify(op));
        } catch {
          this.offlineQueue.unshift(op!);
          break;
        }
      }
    }
    if (this.offlineQueue.length > 0) {
      console.log('[SyncClient] 离线队列剩余 %d 条', this.offlineQueue.length);
    }
  }
}
