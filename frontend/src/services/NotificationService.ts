/**
 * 统一通知分发服务
 * 对应规范文档第四章 — 消息通知实时推送
 */
import type { SyncMessage } from './RealtimeSyncClient';

export type NotificationLevel = 'info' | 'warning' | 'error';

export interface AppNotification {
  id: string;
  level: NotificationLevel;
  title: string;
  content: string;
  category: 'file' | 'chat' | 'system' | 'presence';
  timestamp: number;
  read: boolean;
}

type NotificationHandler = (notification: AppNotification) => void;

export class NotificationService {
  private notifications: AppNotification[] = [];
  private handlers: Set<NotificationHandler> = new Set();
  private seenIds: Set<string> = new Set(); // 去重
  private maxStored = 200;

  /** 从 WebSocket 消息解析通知 */
  handleSyncMessage(msg: SyncMessage): void {
    switch (msg.type) {
      case 'file_uploaded':
        this.add({
          level: 'info',
          title: '文件上传',
          content: `${msg.data?.uploaded_by_name || '未知用户'} 上传了 "${msg.data?.filename || '文件'}"`,
          category: 'file',
          timestamp: msg.data?.timestamp || Date.now(),
        });
        break;

      case 'file_deleted':
        this.add({
          level: 'warning',
          title: '文件删除',
          content: `${msg.data?.deleted_by_name || '未知用户'} 删除了 "${msg.data?.filename || '文件'}"`,
          category: 'file',
          timestamp: msg.data?.timestamp || Date.now(),
        });
        break;

      case 'file_updated':
        this.add({
          level: 'info',
          title: '文件更新',
          content: `${msg.data?.updated_by_name || '未知用户'} 更新了 "${msg.data?.filename || '文件'}"`,
          category: 'file',
          timestamp: msg.data?.timestamp || Date.now(),
        });
        break;

      case 'chat_message':
        this.add({
          level: 'info',
          title: `${msg.data?.from_user_name || '未知用户'}`,
          content: msg.data?.content || '',
          category: 'chat',
          timestamp: msg.data?.timestamp || Date.now(),
        });
        break;

      case 'system_notify':
        this.add({
          level: msg.data?.level || 'info',
          title: msg.data?.title || '系统通知',
          content: msg.data?.content || '',
          category: 'system',
          timestamp: msg.data?.timestamp || Date.now(),
        });
        break;

      case 'presence':
        this.add({
          level: 'info',
          title: '在线状态更新',
          content: `当前在线 ${msg.data?.total_online || 0} 人`,
          category: 'presence',
          timestamp: Date.now(),
        });
        break;
    }
  }

  /** 添加通知（自动去重） */
  private add(opts: { level: NotificationLevel; title: string; content: string; category: AppNotification['category']; timestamp: number }): void {
    const id = `${opts.category}_${opts.timestamp}_${opts.title}`;
    if (this.seenIds.has(id)) return;
    this.seenIds.add(id);

    const notification: AppNotification = {
      id,
      ...opts,
      read: false,
    };

    this.notifications.unshift(notification);
    if (this.notifications.length > this.maxStored) {
      this.notifications = this.notifications.slice(0, this.maxStored);
    }

    // 通知所有 handler
    for (const h of this.handlers) {
      h(notification);
    }
  }

  /** 注册通知处理器（用于 UI 弹窗、toast 等） */
  onNotification(handler: NotificationHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  /** 标记已读 */
  markRead(id: string): void {
    const n = this.notifications.find(n => n.id === id);
    if (n) n.read = true;
  }

  /** 全部已读 */
  markAllRead(): void {
    for (const n of this.notifications) n.read = true;
  }

  /** 获取通知列表 */
  getNotifications(category?: AppNotification['category'], limit = 50): AppNotification[] {
    let list = this.notifications;
    if (category) list = list.filter(n => n.category === category);
    return list.slice(0, limit);
  }

  /** 未读数量 */
  getUnreadCount(): number {
    return this.notifications.filter(n => !n.read).length;
  }

  /** 清空 */
  clear(): void {
    this.notifications = [];
    this.seenIds.clear();
  }
}
