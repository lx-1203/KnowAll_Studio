import { useState } from 'react'
import { Card, Input, Button, Space, Tag, Switch, App, List, Typography } from 'antd'
import { SearchOutlined, FileTextOutlined, ApartmentOutlined } from '@ant-design/icons'
import { searchDocuments, ragQuery } from '../api'

const apiBase = '/api/v1'

export default function SearchPage() {
  const { message } = App.useApp()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [ragMode, setRagMode] = useState(false)
  const [ragContext, setRagContext] = useState('')
  const [searched, setSearched] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) { message.warning('请输入搜索关键词'); return }
    setLoading(true)
    setSearched(true)
    try {
      if (ragMode) {
        const data = await ragQuery(query.trim(), 5)
        setRagContext(data.context || '')
        setResults([])
      } else {
        const data = await searchDocuments(query.trim(), 10)
        setResults(data.results || [])
        setRagContext('')
      }
    } catch (e: any) {
      message.error('搜索失败')
    } finally {
      setLoading(false)
    }
  }

  const handleViewDocument = (docId: string) => {
    window.open(`${apiBase}/documents/${docId}/raw`, '_blank')
  }

  return (
    <div>
      <Card title="文档搜索" extra={
        <Space>
          <Switch checked={ragMode} onChange={setRagMode}
            checkedChildren="RAG" unCheckedChildren="搜索" />
        </Space>
      }>
        <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
          <Input
            size="large"
            placeholder={ragMode ? '输入问题，AI将从文档中检索并回答...' : '搜索文档内容...'}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
            prefix={<SearchOutlined />}
          />
          <Button type="primary" size="large" loading={loading} onClick={handleSearch}>
            搜索
          </Button>
        </Space.Compact>

        {!searched && (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <SearchOutlined style={{ fontSize: 64, marginBottom: 16 }} />
            <p>输入关键词搜索已索引的文档内容</p>
            <p style={{ fontSize: 12 }}>提示: 先在「资料导入」页面上传并索引文档，然后在此搜索</p>
          </div>
        )}

        {ragMode && ragContext && (
          <Card size="small" title="AI 检索回答" style={{ background: '#f0f5ff', marginBottom: 16 }}>
            <div style={{ fontSize: 14, lineHeight: 2, whiteSpace: 'pre-wrap' }}>{ragContext}</div>
          </Card>
        )}

        {!ragMode && results.length > 0 && (
          <div>
            <div style={{ marginBottom: 8, color: '#666' }}>
              找到 {results.length} 条相关结果
            </div>
            <List
              dataSource={results}
              renderItem={(item: any) => (
                <List.Item
                  key={item.id}
                  actions={[
                    <Button
                      key="view"
                      size="small"
                      icon={<FileTextOutlined />}
                      onClick={() => handleViewDocument(item.metadata?.doc_id)}
                    >
                      查看原文
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space size={4}>
                        <Tag color="blue">
                          <ApartmentOutlined /> 分片
                        </Tag>
                        {item.metadata?.page_range && (
                          <Tag>{item.metadata.page_range}</Tag>
                        )}
                      </Space>
                    }
                    description={
                      <div style={{ fontSize: 14, lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
                        {highlightText(item.text || '', query)}
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          </div>
        )}

        {!ragMode && searched && results.length === 0 && !loading && (
          <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
            <p>未找到相关内容</p>
            <p style={{ fontSize: 12 }}>请确认文档已建立向量索引，或尝试其他关键词</p>
          </div>
        )}
      </Card>
    </div>
  )
}

function highlightText(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text
  const parts = text.split(new RegExp(`(${escapeRegExp(query)})`, 'gi'))
  return (
    <span>
      {parts.map((part, i) =>
        part.toLowerCase() === query.toLowerCase()
          ? <mark key={i} style={{ background: '#ffd666', padding: '0 2px' }}>{part}</mark>
          : part
      )}
    </span>
  )
}

function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
