/**
 * SyncProvider — 实时同步上下文，提供 WebSocket、文件同步、通知、离线队列
 *
 * 基于规范文档的全部 6 大模块，将底层服务（RealtimeSyncClient、
 * FileSyncClient、NotificationService、OfflineQueue）统一初始化和
 * 生命周期管理，通过 React Context 提供给整个应用。
 */
import React, { createContext, useContext, useEffect, useRef, useCallback, useState, type ReactNode } from 'react'
import { message } from 'antd'
import { RealtimeSyncClient, type SyncMessage } from '../services/RealtimeSyncClient'
import { FileSyncClient, type FileInfo } from '../services/FileSyncClient'
import { NotificationService, type AppNotification } from '../services/NotificationService'
import { OfflineQueue } from '../services/OfflineQueue'
import { useAuthStore } from '../stores'

interface SyncContextValue {
  /** WebSocket 实时同步客户端 */
  syncClient: RealtimeSyncClient | null
  /** 文件上传/下载客户端 */
  fileSyncClient: FileSyncClient | null
  /** 通知分发服务 */
  notificationService: NotificationService
  /** 离线队列 */
  offlineQueue: OfflineQueue
  /** 通知列表 */
  notifications: AppNotification[]
  /** 未读通知数 */
  unreadCount: number
  /** 文件列表 */
  fileList: FileInfo[]
  /** 在线成员 */
  onlineUsers: Array<{ user_id: string; user_name: string }>
  /** 连接状态 */
  connected: boolean
  /** 手动重连 */
  reconnect: () => void
  /** 上传文件（带通知广播） */
  uploadFile: (file: File, parentId?: string | null) => Promise<any>
  /** 下载文件 */
  downloadFile: (fileId: string) => Promise<void>
  /** 发送聊天消息 */
  sendChat: (content: string) => void
}

const SyncContext = createContext<SyncContextValue | null>(null)

export function SyncProvider({ children, spaceId = 'default' }: { children: ReactNode; spaceId?: string }) {
  const user = useAuthStore(s => s.user)
  const userId = user?.id || 'local_user'
  const userName = user?.display_name || user?.username || '本地用户'

  // ── 服务实例（useRef 避免重创建） ──
  const syncClientRef = useRef<RealtimeSyncClient | null>(null)
  const fileSyncRef = useRef<FileSyncClient | null>(null)
  const notifRef = useRef<NotificationService>(new NotificationService())
  const offlineRef = useRef<OfflineQueue>(OfflineQueue.restore())

  // ── 响应式状态 ──
  const [notifications, setNotifications] = useState<AppNotification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [fileList, setFileList] = useState<FileInfo[]>([])
  const [onlineUsers, setOnlineUsers] = useState<Array<{ user_id: string; user_name: string }>>([])
  const [connected, setConnected] = useState(false)
  const [docId] = useState(`space_${spaceId}`)

  // ── 初始化 ──
  useEffect(() => {
    // 注册通知回调
    const unsubNotif = notifRef.current.onNotification((n) => {
      setNotifications(notifRef.current.getNotifications())
      setUnreadCount(notifRef.current.getUnreadCount())
      // 弹出 toast 通知
      if (n.category === 'file') {
        message.info(n.content)
      }
    })

    // 创建文件同步客户端
    const fsc = new FileSyncClient(spaceId, userId)
    fsc.onListChange((files) => setFileList([...files]))
    fileSyncRef.current = fsc

    // 创建 WebSocket 客户端
    const sc = new RealtimeSyncClient({
      docId,
      userId,
      userName,
      onMessage: (msg) => {
        // 路由文件事件到 FileSyncClient
        if (['file_uploaded', 'file_deleted', 'file_updated'].includes(msg.type)) {
          fsc.handleFileEvent(msg as any)
        }
        // 路由到通知服务
        notifRef.current.handleSyncMessage(msg)
      },
      onPresence: (users) => setOnlineUsers(users),
      onFileEvent: (msg) => fsc.handleFileEvent(msg as any),
      onError: (err) => {
        if (err.code === 'CONNECTION_ERROR') {
          setConnected(false)
        }
      },
    })
    sc.connect()
    syncClientRef.current = sc

    // 连接状态监控
    const checkInterval = setInterval(() => {
      setConnected(sc.isConnected())
    }, 2000)

    // 重连后重放离线队列
    const origOnOpen = sc['ws']?.onopen
    const replayInterval = setInterval(async () => {
      if (sc.isConnected() && offlineRef.current.length > 0) {
        await offlineRef.current.replay(async (op) => {
          sc.sendOperation(op.data)
        })
      }
    }, 5000)

    return () => {
      sc.disconnect()
      unsubNotif()
      clearInterval(checkInterval)
      clearInterval(replayInterval)
    }
  }, [docId, userId, userName, spaceId])

  // ── 上传文件（集成 WebSocket 广播） ──
  const uploadFile = useCallback(async (file: File, parentId: string | null = null) => {
    const fsc = fileSyncRef.current
    const sc = syncClientRef.current
    if (!fsc) throw new Error('FileSyncClient 未初始化')

    // 广播上传进度
    sc?.sendUploadProgress(file.name, 0, 'uploading')

    const result = await fsc.uploadFile(file, parentId, (progress) => {
      sc?.sendUploadProgress(file.name, progress.progress, 'uploading')
    })

    // 上传完成后通过 WebSocket 广播
    sc?.sendFileEvent('file_uploaded', {
      file_id: result.file_id,
      filename: file.name,
      size: result.size,
      mime_type: file.type,
      url: result.url,
      version: result.version,
    })

    sc?.sendUploadProgress(file.name, 1, 'completed')
    return result
  }, [])

  const downloadFile = useCallback(async (fileId: string) => {
    const fsc = fileSyncRef.current
    if (!fsc) throw new Error('FileSyncClient 未初始化')
    await fsc.downloadFile(fileId)
  }, [])

  const sendChat = useCallback((content: string) => {
    syncClientRef.current?.sendChatMessage(content)
  }, [])

  const reconnect = useCallback(() => {
    syncClientRef.current?.disconnect()
    syncClientRef.current?.connect()
  }, [])

  // ── 主动推送离线队列中的操作 ──
  const offlineOpsCount = offlineRef.current.length

  const value: SyncContextValue = {
    syncClient: syncClientRef.current,
    fileSyncClient: fileSyncRef.current,
    notificationService: notifRef.current,
    offlineQueue: offlineRef.current,
    notifications,
    unreadCount,
    fileList,
    onlineUsers,
    connected,
    reconnect,
    uploadFile,
    downloadFile,
    sendChat,
  }

  return React.createElement(SyncContext.Provider, { value }, children)
}

/** 使用实时同步上下文 */
export function useSync(): SyncContextValue {
  const ctx = useContext(SyncContext)
  if (!ctx) {
    throw new Error('useSync 必须在 SyncProvider 内部使用')
  }
  return ctx
}

/** 仅获取通知（不依赖 sync 连接） */
export function useNotifications() {
  const ctx = useContext(SyncContext)
  return {
    notifications: ctx?.notifications ?? [],
    unreadCount: ctx?.unreadCount ?? 0,
    markRead: ctx?.notificationService.markRead.bind(ctx.notificationService),
    markAllRead: ctx?.notificationService.markAllRead.bind(ctx.notificationService),
    clear: ctx?.notificationService.clear.bind(ctx.notificationService),
  }
}
