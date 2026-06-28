import { useState, useEffect } from 'react'
import { Card, Button, Modal, Input, DatePicker, Select, Progress, List, Checkbox, Tag, Empty, message, Popconfirm, Table, Space } from 'antd'
import { PlusOutlined, DeleteOutlined, ClockCircleOutlined, CheckCircleOutlined, BellOutlined, RobotOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useAppStore } from '../stores'

const API = '/api/v1/study'

export default function StudyPage() {
  const [plans, setPlans] = useState<any[]>([])
  const [selectedPlan, setSelectedPlan] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newEndDate, setNewEndDate] = useState<string | null>(null)
  const [newGoals, setNewGoals] = useState('')
  const [reminders, setReminders] = useState<any[]>([])
  const [aiGenerating, setAiGenerating] = useState(false)
  const { selectedDoc } = useAppStore()

  const fetchPlans = async () => {
    setLoading(true)
    try {
      const res = await fetch(API + '/plans')
      if (!res.ok) throw new Error()
      const data = await res.json()
      setPlans(Array.isArray(data) ? data : [])
    } catch { message.error('Failed to load plans'); setPlans([]) }
    setLoading(false)
  }

  const fetchReminders = async () => {
    try {
      const res = await fetch(API + '/reminders/due')
      if (!res.ok) throw new Error()
      const data = await res.json()
      setReminders(data.reminders || [])
    } catch { setReminders([]) }
  }

  const fetchPlanDetail = async (planId: string) => {
    try {
      const res = await fetch(API + `/plans/${planId}`)
      if (!res.ok) { message.error('Failed to load plan detail'); return }
      const data = await res.json()
      setSelectedPlan(data)
    } catch { message.error('Failed to load plan detail') }
  }

  useEffect(() => { fetchPlans(); fetchReminders() }, [])

  const handleCreate = async () => {
    const goals = newGoals ? newGoals.split('\n').filter(Boolean).map((t, i) => ({ title: t.trim(), priority: 'medium' })) : []
    const body = { name: newName, description: newDesc, target_end_date: newEndDate, goals }
    try {
      const res = await fetch(API + '/plans', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (res.ok) { message.success('Plan created'); setCreateOpen(false); setNewName(''); setNewDesc(''); setNewEndDate(null); setNewGoals(''); fetchPlans() }
      else message.error('Failed to create plan')
    } catch { message.error('Error creating plan') }
  }

  const handleAIGenerate = async () => {
    if (!selectedDoc) { message.warning('请先在资料导入页面选择文档'); return }
    setAiGenerating(true)
    try {
      const res = await fetch(API + '/generate-plan', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_id: selectedDoc, plan_duration_weeks: 4 }),
      })
      if (res.ok) {
        const data = await res.json()
        message.success(`AI已生成学习计划: ${data.name} (${data.goal_count} 个目标)`)
        setCreateOpen(false)
        fetchPlans()
      } else {
        const err = await res.json()
        message.error(err.detail || 'AI生成失败')
      }
    } catch { message.error('AI生成失败') }
    finally { setAiGenerating(false) }
  }

  const handleDeletePlan = async (id: string) => {
    await fetch(API + `/plans/${id}`, { method: 'DELETE' })
    message.success('Plan deleted')
    if (selectedPlan?.id === id) setSelectedPlan(null)
    fetchPlans()
  }

  const handleToggleGoal = async (goalId: string) => {
    await fetch(API + `/goals/${goalId}/toggle`, { method: 'PUT' })
    if (selectedPlan) fetchPlanDetail(selectedPlan.id)
    fetchPlans()
  }

  const handleAddGoal = async () => {
    if (!selectedPlan) return
    const title = prompt('Goal title:')
    if (!title) return
    await fetch(API + '/goals', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan_id: selectedPlan.id, title }),
    })
    fetchPlanDetail(selectedPlan.id)
    fetchPlans()
  }

  const handleDeleteGoal = async (goalId: string) => {
    await fetch(API + `/goals/${goalId}`, { method: 'DELETE' })
    if (selectedPlan) fetchPlanDetail(selectedPlan.id)
    fetchPlans()
  }

  const handleMarkRead = async (rId: string) => {
    await fetch(API + `/reminders/${rId}/read`, { method: 'POST' })
    fetchReminders()
  }

  const priorityColor = (p: string) => p === 'high' ? 'red' : p === 'medium' ? 'orange' : 'green'

  return (
    <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
      {/* Left: Plan list */}
      <Card title="Study Plans" extra={<Space>
        <Button icon={<RobotOutlined />} loading={aiGenerating} onClick={handleAIGenerate} disabled={!selectedDoc}>AI 生成计划</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>New Plan</Button>
      </Space>}
        style={{ flex: '1 1 300px' }} loading={loading}>
        {plans.length === 0 && <Empty description="No study plans yet" />}
        <Table
          dataSource={plans}
          rowKey="id"
          locale={{ emptyText: 'No study plans yet' }}
          columns={[
            {
              title: '名称',
              dataIndex: 'name',
              render: (name: string, record: any) => (
                <span>{name} <Tag color={record.status === 'completed' ? 'green' : record.status === 'paused' ? 'default' : 'blue'}>{record.status}</Tag></span>
              ),
            },
            {
              title: '进度',
              dataIndex: 'progress',
              width: 200,
              render: (v: number) => <Progress percent={v} size="small" />,
            },
            {
              title: '操作',
              width: 80,
              render: (_: any, record: any) => (
                <Popconfirm title="Delete?" onConfirm={() => handleDeletePlan(record.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              ),
            },
          ]}
          pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total) => `共 ${total} 个计划` }}
          onRow={(record) => ({
            onClick: () => fetchPlanDetail(record.id),
            style: { cursor: 'pointer', background: selectedPlan?.id === record.id ? '#e6f4ff' : undefined },
          })}
          size="middle"
        />
      </Card>

      {/* Middle: Plan detail & goals */}
      <Card title={selectedPlan ? selectedPlan.name : 'Plan Detail'} style={{ flex: '2 1 400px' }}
        extra={selectedPlan && <Button size="small" icon={<PlusOutlined />} onClick={handleAddGoal}>Add Goal</Button>}>
        {!selectedPlan && <Empty description="Select a plan to view details" />}
        {selectedPlan && (
          <div>
            <p>{selectedPlan.description}</p>
            {selectedPlan.target_end_date && <p><ClockCircleOutlined /> Target: {selectedPlan.target_end_date}</p>}
            <Progress percent={selectedPlan.progress} />
            <List style={{ marginTop: 16 }} dataSource={selectedPlan.goals || []} renderItem={(g: any) => (
              <List.Item actions={[
                <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteGoal(g.id)} />,
              ]}>
                <Checkbox checked={g.completed} onChange={() => handleToggleGoal(g.id)} />
                <span style={{ marginLeft: 8, textDecoration: g.completed ? 'line-through' : undefined }}>{g.title}</span>
                <Tag color={priorityColor(g.priority)} style={{ marginLeft: 8 }}>{g.priority}</Tag>
                {g.due_date && <Tag icon={<ClockCircleOutlined />}>{g.due_date}</Tag>}
              </List.Item>
            )} />
          </div>
        )}
      </Card>

      {/* Right: Reminders */}
      <Card title={<span><BellOutlined /> Reminders ({reminders.length})</span>} style={{ flex: '1 1 250px' }}>
        {reminders.length === 0 && <Empty description="No pending reminders" />}
        <List dataSource={reminders} renderItem={(r: any) => (
          <List.Item actions={[
            <Button size="small" onClick={() => handleMarkRead(r.id)}>Dismiss</Button>,
          ]}>
            <List.Item.Meta title={r.message} description={r.remind_at} />
          </List.Item>
        )} />
      </Card>

      {/* Create Plan Modal */}
      <Modal title="New Study Plan" open={createOpen} onOk={handleCreate} onCancel={() => setCreateOpen(false)}>
        <Input placeholder="Plan name" value={newName} onChange={e => setNewName(e.target.value)} style={{ marginBottom: 8 }} />
        <Input.TextArea placeholder="Description (optional)" value={newDesc} onChange={e => setNewDesc(e.target.value)} style={{ marginBottom: 8 }} />
        <DatePicker placeholder="Target end date" style={{ width: '100%', marginBottom: 8 }} onChange={d => setNewEndDate(d ? d.toISOString() : null)} />
        <Input.TextArea placeholder="Goals (one per line)" value={newGoals} onChange={e => setNewGoals(e.target.value)} rows={4} />
      </Modal>
    </div>
  )
}
