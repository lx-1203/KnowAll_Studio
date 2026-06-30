import { useState, useEffect, useRef } from 'react'
import { Card, Button, Input, Select, Space, App, Switch, Tag, Modal, Popconfirm } from 'antd'
import { SendOutlined, RobotOutlined, UserOutlined, PlusOutlined, ThunderboltOutlined, SearchOutlined, FileTextOutlined, DeleteOutlined, CopyOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { listConversations, getConversation, listRoles, deleteConversation } from '../api'
import { useAppStore } from '../stores'
import { ChatSkeleton } from '../components/SkeletonLoader'
import DocumentViewer from '../components/DocumentViewer'

interface Message { id: string; role: string; content: string; created_at: string; }
interface Conv { id: string; title: string; role_preset: string; created_at: string; }

let _msgIdCounter = 0
function nextMsgId() { return `${Date.now()}_${++_msgIdCounter}_${Math.random().toString(36).slice(2, 8)}` }

export default function ChatPage() {
  const { selectedDoc } = useAppStore()
  const { message } = App.useApp()
  const [convs, setConvs] = useState<Conv[]>([])
  const [currentConv, setCurrentConv] = useState<Conv | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [role, setRole] = useState('tutor')
  const [roles, setRoles] = useState<Record<string, { name: string }>>({})
  const [loading, setLoading] = useState(false)
  const [streamMode, setStreamMode] = useState(true)
  const [ragMode, setRagMode] = useState(false)
  const [docViewerOpen, setDocViewerOpen] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const chatEnd = useRef<HTMLDivElement>(null)

  useEffect(() => {
    Promise.all([
      listConversations().then(setConvs),
      listRoles().then(setRoles),
    ]).catch(console.error).finally(() => setInitialLoading(false))
  }, [])

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const handleSendRetry = async (msgText: string) => {
    try {
      const resp = await fetch(`${apiBase}/chat/assistant`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msgText, conversation_id: currentConv?.id || null, role_preset: role }),
      })
      const result = await resp.json()
      if (result.conversation_id && !currentConv) {
        setCurrentConv({ id: result.conversation_id, title: msgText.slice(0, 30), role_preset: role, created_at: new Date().toISOString() })
        setConvs(prev => [{ id: result.conversation_id, title: msgText.slice(0, 30), role_preset: role, created_at: new Date().toISOString() }, ...prev])
      }
      setMessages(prev => [...prev, { id: nextMsgId(), role: 'assistant', content: result.message || result.detail || '无响应', created_at: new Date().toISOString() }])
    } catch {
      message.error('重试失败，请再试一次')
    }
  }

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMsg: Message = { id: nextMsgId(), role: 'user', content: input, created_at: new Date().toISOString() }
    setMessages(prev => [...prev, userMsg])
    const msgText = input
    setInput('')
    setLoading(true)

    if (streamMode) {
      // SSE streaming (RAG or normal)
      const endpoint = ragMode ? '/api/v1/chat/assistant/rag/stream' : '/api/v1/chat/assistant/stream'
      const aiMsgId = nextMsgId()
      const aiMsg: Message = { id: aiMsgId, role: 'assistant', content: '', created_at: new Date().toISOString() }
      setMessages(prev => [...prev, aiMsg])

      try {
        const token = localStorage.getItem('knowall_token')
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message: msgText,
            conversation_id: currentConv?.id || null,
            role_preset: role,
          }),
        })

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()
        if (!reader) throw new Error('No reader')

        let buffer = ''
        let convId = currentConv?.id

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                if (data.token) {
                  setMessages(prev => prev.map(m =>
                    m.id === aiMsgId ? { ...m, content: m.content + data.token } : m
                  ))
                }
                if (data.conversation_id) convId = data.conversation_id
                if (data.error) message.error(data.error)
              } catch {}
            }
          }
        }

        if (convId && !currentConv) {
          setCurrentConv({ id: convId, title: msgText.slice(0, 30), role_preset: role, created_at: new Date().toISOString() })
          setConvs(prev => [{ id: convId, title: msgText.slice(0, 30), role_preset: role, created_at: new Date().toISOString() }, ...prev])
        }
      } catch (e: any) {
        // Remove the empty AI message on error
        setMessages(prev => prev.filter(m => m.id !== aiMsgId))
        message.error('流式传输失败，切换到普通模式重试...')
        setStreamMode(false)
        // Retry with non-streaming
        setTimeout(() => handleSendRetry(msgText), 500)
        setLoading(false)
        return
      }
    } else {
      // Non-streaming (RAG or normal)
      try {
        const { chatWithAssistant } = await import('../api')
        const endpoint = ragMode ? '/chat/assistant/rag' : '/chat/assistant'
        const resp = await fetch(`${apiBase}${endpoint}`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msgText, conversation_id: currentConv?.id || null, role_preset: role }),
        })
        const result = await resp.json()
        if (!currentConv && result.conversation_id) {
          setCurrentConv({ id: result.conversation_id, title: msgText.slice(0, 30), role_preset: role, created_at: new Date().toISOString() })
          setConvs(prev => [{ id: result.conversation_id, title: msgText.slice(0, 30), role_preset: role, created_at: new Date().toISOString() }, ...prev])
        }
        setMessages(prev => [...prev, { id: nextMsgId(), role: 'assistant', content: result.message, created_at: new Date().toISOString() }])
      } catch (e: any) {
        message.error('发送失败')
      }
    }

    setLoading(false)
  }

  const handleSelectConv = async (convId: string) => {
    try {
      const data = await getConversation(convId)
      setCurrentConv({ id: data.conversation_id, title: data.title, role_preset: data.role_preset, created_at: '' })
      setMessages(data.messages || [])
    } catch { message.error('加载失败') }
  }

  if (initialLoading) return <ChatSkeleton />

  return (
    <div style={{ display: 'flex', gap: 16, height: 'calc(100vh - 140px)' }}>
      <Card title="对话列表" size="small" style={{ width: 260, overflow: 'auto' }}
        extra={<Button icon={<PlusOutlined />} size="small" onClick={() => { setCurrentConv(null); setMessages([]) }}>新对话</Button>}>
        {convs.map(c => (
          <div key={c.id} onClick={() => handleSelectConv(c.id)}
            style={{ padding: '8px 12px', marginBottom: 4, cursor: 'pointer', borderRadius: 8,
              background: currentConv?.id === c.id ? '#f0f5ff' : undefined }}>
            <div style={{ fontWeight: 500, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {c.title}
            </div>
            <Space size={4}>
              <Tag style={{ fontSize: 10 }}>{c.role_preset}</Tag>
              <span style={{ fontSize: 11, color: '#999' }}>{c.created_at?.slice(0, 10)}</span>
            </Space>
          </div>
        ))}
      </Card>

      <Card title={currentConv?.title || '新对话'} style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        extra={
          <Space wrap>
            <Select value={role} onChange={setRole} size="small" style={{ width: 130 }}
              options={Object.entries(roles).map(([k, v]) => ({ value: k, label: v.name }))} />
            <Switch checked={ragMode} onChange={setRagMode} size="small"
              checkedChildren={<><SearchOutlined /> RAG</>} unCheckedChildren="普通" />
            <Switch checked={streamMode} onChange={setStreamMode} size="small"
              checkedChildren={<ThunderboltOutlined />} unCheckedChildren="普通" />
            {selectedDoc && (
              <Button icon={<FileTextOutlined />} size="small"
                onClick={() => setDocViewerOpen(true)}>文档</Button>
            )}
          </Space>
        }>
        <div style={{ flex: 1, overflow: 'auto', marginBottom: 12 }}>
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
              <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
              <p>选择一个角色预设，开始与 AI 助教对话</p>
              <Space style={{ marginTop: 8 }}>
                {Object.entries(roles).map(([k, v]) => (
                  <Tag key={k} color={role === k ? 'blue' : 'default'}
                    style={{ cursor: 'pointer' }} onClick={() => setRole(k)}>{v.name}</Tag>
                ))}
              </Space>
            </div>
          )}
          {messages.map(m => (
            <div key={m.id} style={{ marginBottom: 16, display: 'flex', gap: 8,
              flexDirection: m.role === 'user' ? 'row-reverse' : 'row' }}>
              <div style={{
                width: 36, height: 36, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: m.role === 'user' ? '#4f46e5' : '#52c41a', color: '#fff', flexShrink: 0,
              }}>
                {m.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
              </div>
              <div style={{
                maxWidth: '70%', padding: '10px 14px', borderRadius: 12,
                background: m.role === 'user' ? '#f0f5ff' : '#f6ffed',
                fontSize: 14, lineHeight: 1.8, whiteSpace: 'pre-wrap',
              }}>
                {m.content || (loading && m.role === 'assistant' ? '思考中...' : '')}
              </div>
            </div>
          ))}
          <div ref={chatEnd} />
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Input.TextArea value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
            placeholder="输入问题，Enter 发送，Shift+Enter 换行..."
            rows={2} disabled={loading} />
          <Button icon={<SendOutlined />} type="primary" loading={loading} onClick={handleSend}
            style={{ height: 'auto' }}>发送</Button>
        </div>
      </Card>

      <Modal title="文档浏览" open={docViewerOpen} onCancel={() => setDocViewerOpen(false)}
        footer={null} width={800} destroyOnHidden>
        {selectedDoc && <DocumentViewer documentId={selectedDoc}
          onSearch={(text) => { setInput(text); setDocViewerOpen(false); setRagMode(true); }} />}
      </Modal>
    </div>
  )
}
