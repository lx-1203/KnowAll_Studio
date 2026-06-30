import { useState, useEffect } from 'react'
import { Card, Button, Tag, Spin, Space, Collapse, Empty } from 'antd'
import { FileTextOutlined, SearchOutlined } from '@ant-design/icons'
import { RichText } from './LaTeX'
import api from '../api'

interface Chunk {
  id: string
  index: number
  text: string
  token_count: number
  page_range: string
}

interface Props {
  documentId: string
  title?: string
  onSearch?: (text: string) => void
}

export default function DocumentViewer({ documentId, title, onSearch }: Props) {
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedText, setSelectedText] = useState('')

  useEffect(() => {
    if (!documentId) return
    setLoading(true)
    api.get(`/documents/${documentId}/chunks`)
      .then(r => setChunks(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [documentId])

  const handleTextSelect = () => {
    const sel = window.getSelection()
    const text = sel?.toString().trim()
    if (text && text.length > 5) {
      setSelectedText(text)
    }
  }

  if (loading) return <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '60vh', gap: 16 }}><Spin size="large" /><span style={{ color: '#999' }}>加载文档...</span></div>
  if (!chunks.length) return <Empty description="暂无文档内容" />

  return (
    <div style={{ maxHeight: '60vh', overflow: 'auto' }}>
      {title && (
        <div style={{ marginBottom: 12, fontWeight: 600, fontSize: 15 }}>{title}</div>
      )}

      {selectedText && (
        <Card size="small" style={{ marginBottom: 12, background: '#f0f5ff' }}
          extra={
            <Space size={4}>
              {onSearch && (
                <Button size="small" icon={<SearchOutlined />}
                  onClick={() => { onSearch(selectedText); setSelectedText('') }}>
                  搜索
                </Button>
              )}
              <Button size="small" onClick={() => setSelectedText('')}>清除</Button>
            </Space>
          }>
          <div style={{ fontSize: 13, color: '#666' }}>选中文本:</div>
          <div style={{ fontSize: 14 }}>{selectedText.slice(0, 200)}{selectedText.length > 200 ? '...' : ''}</div>
        </Card>
      )}

      <Collapse
        size="small"
        items={chunks.map((c, i) => ({
          key: c.id,
          label: (
            <Space size={4}>
              <Tag color="blue">分片 {c.index + 1}</Tag>
              <span style={{ fontSize: 12, color: '#999' }}>{c.page_range}</span>
              <span style={{ fontSize: 12, color: '#999' }}>{c.token_count} tokens</span>
            </Space>
          ),
          children: (
            <div onMouseUp={handleTextSelect}
              style={{ fontSize: 14, lineHeight: 2, whiteSpace: 'pre-wrap', userSelect: 'text', cursor: 'text' }}>
              <RichText text={c.text} />
            </div>
          ),
        }))}
        defaultActiveKey={chunks.length <= 3 ? chunks.map(c => c.id) : [chunks[0]?.id]}
      />
    </div>
  )
}
