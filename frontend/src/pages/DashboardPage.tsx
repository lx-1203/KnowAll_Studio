import { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, Table, Tag, Progress, Spin } from 'antd'
import {
  FileTextOutlined, FormOutlined, CheckCircleOutlined, CloseCircleOutlined,
  IdcardOutlined, ThunderboltOutlined, BarChartOutlined, DollarOutlined,
} from '@ant-design/icons'
import type { DashboardStats, DailyStat, TopicStat } from '../types'
import { PageSkeleton } from '../components/SkeletonLoader'

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [daily, setDaily] = useState<DailyStat[]>([])
  const [topics, setTopics] = useState<TopicStat[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetch('/api/v1/stats/overview').then(r => r.json()),
      fetch('/api/v1/stats/daily?days=7').then(r => r.json()),
      fetch('/api/v1/stats/topics').then(r => r.json()),
    ]).then(([s, d, t]) => {
      setStats(s)
      setDaily(d.days || [])
      setTopics(t.topics || [])
    }).catch(console.error).finally(() => setLoading(false))
  }, [])

  if (loading) return <PageSkeleton />

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>学习仪表盘</h2>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        {[
          { title: '文档资料', value: stats?.documents || 0, icon: <FileTextOutlined />, color: '#4f46e5' },
          { title: '题库总量', value: stats?.questions || 0, icon: <FormOutlined />, color: '#1890ff' },
          { title: '正确率', value: `${stats?.correct_rate || 0}%`, icon: <CheckCircleOutlined />, color: '#52c41a' },
          { title: '待复习卡片', value: stats?.cards_due || 0, icon: <IdcardOutlined />, color: '#faad14' },
        ].map(item => (
          <Col span={6} key={item.title}>
            <Card>
              <Statistic
                title={item.title}
                value={item.value}
                prefix={<span style={{ color: item.color }}>{item.icon}</span>}
              />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        {[
          { title: '今日复习', value: stats?.reviews_today || 0, icon: <ThunderboltOutlined />, color: '#722ed1' },
          { title: '错题数', value: stats?.errors || 0, icon: <CloseCircleOutlined />, color: '#ff4d4f' },
          { title: '闪卡总数', value: stats?.cards_total || 0, icon: <IdcardOutlined />, color: '#13c2c2' },
          { title: 'API费用(估)', value: `$${(stats?.cost_estimate || 0).toFixed(4)}`, icon: <DollarOutlined />, color: '#fa8c16' },
        ].map(item => (
          <Col span={6} key={item.title}>
            <Card>
              <Statistic
                title={item.title}
                value={item.value}
                prefix={<span style={{ color: item.color }}>{item.icon}</span>}
              />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="近7天学习活动">
            <Table
              dataSource={daily}
              rowKey="date"
              pagination={false}
              size="small"
              columns={[
                { title: '日期', dataIndex: 'date', key: 'date', render: (v: string) => v.slice(5) },
                { title: '答题', dataIndex: 'answers', key: 'answers' },
                { title: '正确', dataIndex: 'correct', key: 'correct', render: (v: number, r: DailyStat) => (
                  <span style={{ color: r.answers > 0 && v === r.answers ? '#52c41a' : undefined }}>{v}</span>
                )},
                { title: '复习', dataIndex: 'reviews', key: 'reviews' },
                { title: 'API调用', dataIndex: 'api_calls', key: 'api_calls' },
              ]}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="知识点分布">
            <Table
              dataSource={topics}
              rowKey="topic"
              pagination={false}
              size="small"
              columns={[
                { title: '知识点', dataIndex: 'topic', key: 'topic', render: (v: string) => <Tag>{v}</Tag> },
                { title: '题目数', dataIndex: 'total', key: 'total' },
                { title: '错误数', dataIndex: 'errors', key: 'errors', render: (v: number) => (
                  <span style={{ color: v > 0 ? '#ff4d4f' : '#52c41a' }}>{v}</span>
                )},
              ]}
            />
          </Card>
        </Col>
      </Row>

      {stats && (
        <Card title="Token 用量" size="small" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={8}>
              <Statistic title="输入 Token" value={stats.token_usage.input} />
            </Col>
            <Col span={8}>
              <Statistic title="输出 Token" value={stats.token_usage.output} />
            </Col>
            <Col span={8}>
              <Progress percent={Math.min(100, (stats.token_usage.total / 1_000_000) * 100)}
                format={() => `${(stats.token_usage.total / 1000).toFixed(0)}K`}
                status={stats.token_usage.total > 900_000 ? 'exception' : 'active'} />
              <div style={{ textAlign: 'center', color: '#999', fontSize: 12 }}>日限额 1M tokens</div>
            </Col>
          </Row>
        </Card>
      )}
    </div>
  )
}
