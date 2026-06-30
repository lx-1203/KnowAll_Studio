import { useState, useEffect } from 'react'
import { Card, Button, Input, Select, Table, Tag, App, Modal, Empty, Popconfirm } from 'antd'
import { ShareAltOutlined, LinkOutlined, DeleteOutlined, CopyOutlined } from '@ant-design/icons'

const API = '/api/v1/share'

export default function SharePage() {
  const { message } = App.useApp()
  const [links, setLinks] = useState<any[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [viewOpen, setViewOpen] = useState(false)
  const [viewData, setViewData] = useState<any>(null)
  const [viewAccessCode, setViewAccessCode] = useState('')
  const [viewShareId, setViewShareId] = useState('')
  const [loading, setLoading] = useState(false)
  // Create form
  const [resType, setResType] = useState('knowledge_tree')
  const [resId, setResId] = useState('')
  const [expDays, setExpDays] = useState<number | undefined>()

  const fetchLinks = async () => {
    setLoading(true)
    try {
      const data = await listShareLinks()
      setLinks(Array.isArray(data) ? data : data?.items || [])
    } catch { message.error('加载分享链接失败') }
    setLoading(false)
  }

  useEffect(() => { fetchLinks() }, [])

  const handleCreate = async () => {
    if (!resId) { message.warning('请输入资源ID'); return }
    try {
      const data = await createShareLink({ resource_type: resType, resource_id: resId, expires_in_days: expDays || undefined })
      message.success(`分享链接已创建！访问码: ${data.access_code}`)
      setCreateOpen(false)
      fetchLinks()
    } catch (e: any) { message.error(e?.response?.data?.detail || '创建失败') }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteShareLink(id)
      message.success('已删除')
      fetchLinks()
    } catch { message.error('删除失败') }
  }

  const handleCopy = (code: string) => {
    navigator.clipboard.writeText(code).then(() => message.success('Code copied!'))
  }

  const handleViewShared = async () => {
    if (!viewShareId || !viewAccessCode) { message.warning('Enter share ID and access code'); return }
    try {
      const res = await fetch(API + `/view/${viewShareId}?access_code=${viewAccessCode}`)
      if (res.ok) {
        const data = await res.json()
        setViewData(data)
      } else {
        const err = await res.json()
        message.error(err.detail || 'Failed to load')
      }
    } catch { message.error('Error loading shared resource') }
  }

  const typeLabels: Record<string, string> = { knowledge_tree: 'Knowledge Tree', question_bank: 'Question Bank', flashcard_deck: 'Flashcard Deck' }
  const typeColors: Record<string, string> = { knowledge_tree: 'blue', question_bank: 'green', flashcard_deck: 'purple' }

  return (
    <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
      <Card title="My Share Links" extra={<Button type="primary" icon={<ShareAltOutlined />} onClick={() => setCreateOpen(true)}>Create Share</Button>}
        style={{ flex: '2 1 500px' }} loading={loading}>
        {links.length === 0 && <Empty description="No share links created yet" />}
        <Table dataSource={links} rowKey="share_id" pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
          columns={[
            { title: 'Resource Type', dataIndex: 'resource_type', render: (v: string) => <Tag color={typeColors[v] || 'default'}>{typeLabels[v] || v}</Tag> },
            { title: 'Resource ID', dataIndex: 'resource_id', ellipsis: true },
            { title: 'Access Code', dataIndex: 'access_code', render: (v: string) => <Tag>{v} <Button size="small" type="link" icon={<CopyOutlined />} onClick={() => handleCopy(v)} /></Tag> },
            { title: 'Views', dataIndex: 'view_count' },
            { title: 'Expires', dataIndex: 'expires_at', render: (v: string | null) => v || 'Never' },
            { title: '', render: (_: any, r: any) => <Popconfirm title="Delete?" onConfirm={() => handleDelete(r.share_id)}><Button size="small" danger icon={<DeleteOutlined />} /></Popconfirm> },
          ]} />
      </Card>

      <Card title="View Shared Resource" style={{ flex: '1 1 300px' }}>
        <Input placeholder="Share ID" value={viewShareId} onChange={e => setViewShareId(e.target.value)} style={{ marginBottom: 8 }} />
        <Input placeholder="6-digit Access Code" value={viewAccessCode} onChange={e => setViewAccessCode(e.target.value)} style={{ marginBottom: 8 }} />
        <Button type="primary" block icon={<LinkOutlined />} onClick={handleViewShared}>View</Button>
        {viewData && (
          <Card size="small" style={{ marginTop: 16 }}>
            <Tag color="blue">{viewData.type}</Tag>
            {viewData.type === 'knowledge_tree' && <p><strong>{viewData.data.name}</strong></p>}
            {viewData.type === 'flashcard_deck' && <p><strong>{viewData.data.name}</strong> ({viewData.data.card_count} cards)</p>}
            {viewData.type === 'question_bank' && <p>{viewData.data.questions?.length || 0} questions</p>}
          </Card>
        )}
      </Card>

      <Modal title="Create Share Link" open={createOpen} onOk={handleCreate} onCancel={() => setCreateOpen(false)}>
        <Select value={resType} onChange={setResType} style={{ width: '100%', marginBottom: 8 }}
          options={[
            { label: 'Knowledge Tree', value: 'knowledge_tree' },
            { label: 'Question Bank', value: 'question_bank' },
            { label: 'Flashcard Deck', value: 'flashcard_deck' },
          ]} />
        <Input placeholder="Resource ID" value={resId} onChange={e => setResId(e.target.value)} style={{ marginBottom: 8 }} />
        <Input placeholder="Expires in days (blank = never)" type="number" value={expDays} onChange={e => setExpDays(e.target.value ? parseInt(e.target.value) : undefined)} />
      </Modal>
    </div>
  )
}
