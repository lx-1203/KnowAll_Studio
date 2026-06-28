import { useState, useEffect, useCallback } from 'react'
import {
  Card, Tabs, Table, Tag, Button, Space, Typography, Select, Row, Col,
  Statistic, Progress, Spin, message, Empty, Tooltip, DatePicker,
} from 'antd'
import {
  BarChartOutlined, HistoryOutlined, RobotOutlined, TrophyOutlined,
  CheckCircleOutlined, CloseCircleOutlined, FilterOutlined,
  ClockCircleOutlined, ThunderboltOutlined, ReloadOutlined,
  ArrowUpOutlined, ArrowDownOutlined, FormOutlined,
} from '@ant-design/icons'
import {
  getMasteryAnalysis, getAnswerHistory, getReviewStats,
  getReviewKnowledgePoints,
} from '../api'
import type {
  MasteryAnalysis, AnswerHistoryItem, ReviewStats, ReviewKnowledgePoint,
} from '../types'
import MasteryOverview from '../components/MasteryOverview'
import ReviewRecommendation from '../components/ReviewRecommendation'
import { COGNITIVE_LEVEL_LABELS, COGNITIVE_LEVEL_COLORS, type CognitiveLevel } from '../types'

const { Text, Title } = Typography
const { RangePicker } = DatePicker

export default function AnswerReviewPage() {
  const [activeTab, setActiveTab] = useState('mastery')

  // Mastery state
  const [mastery, setMastery] = useState<MasteryAnalysis | null>(null)
  const [masteryLoading, setMasteryLoading] = useState(false)

  // Stats state
  const [stats, setStats] = useState<ReviewStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)

  // History state
  const [history, setHistory] = useState<AnswerHistoryItem[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyPage, setHistoryPage] = useState(1)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [filterCorrect, setFilterCorrect] = useState<boolean | undefined>(undefined)
  const [filterKpId, setFilterKpId] = useState<string | undefined>(undefined)

  // Knowledge points for filter
  const [kpList, setKpList] = useState<ReviewKnowledgePoint[]>([])

  const pageSize = 20

  // Load initial data
  useEffect(() => {
    loadMastery()
    loadStats()
    loadKpList()
  }, [])

  useEffect(() => {
    if (activeTab === 'history') loadHistory()
  }, [activeTab])

  const loadMastery = async () => {
    setMasteryLoading(true)
    try {
      const data = await getMasteryAnalysis()
      setMastery(data)
    } catch (e: any) {
      message.error('加载掌握度分析失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setMasteryLoading(false)
    }
  }

  const loadStats = async () => {
    setStatsLoading(true)
    try {
      const data = await getReviewStats()
      setStats(data)
    } catch (e: any) {
      message.error('加载统计数据失败')
    } finally {
      setStatsLoading(false)
    }
  }

  const loadKpList = async () => {
    try {
      const data = await getReviewKnowledgePoints()
      setKpList(data.items || [])
    } catch {
      // Silently fail
    }
  }

  const loadHistory = useCallback(async (page?: number, correct?: boolean, kpId?: string) => {
    setHistoryLoading(true)
    try {
      const p = page || historyPage
      const data = await getAnswerHistory({
        page: p,
        page_size: pageSize,
        is_correct: correct !== undefined ? correct : filterCorrect,
        kp_id: kpId || filterKpId,
      })
      setHistory(data.items || [])
      setHistoryTotal(data.total || 0)
      setHistoryPage(p)
    } catch (e: any) {
      message.error('加载答题历史失败')
    } finally {
      setHistoryLoading(false)
    }
  }, [historyPage, filterCorrect, filterKpId])

  const handleFilterChange = (type: 'correct' | 'kp', value: any) => {
    if (type === 'correct') {
      setFilterCorrect(value)
      loadHistory(1, value, undefined)
    } else {
      setFilterKpId(value)
      loadHistory(1, undefined, value)
    }
  }

  const questionTypeLabels: Record<string, string> = {
    single_choice: '单选', multi_choice: '多选', true_false: '判断',
    fill_blank: '填空', short_answer: '简答', calculation: '计算',
    formula: '公式', coding: '编程', material_analysis: '材料分析',
  }

  // ====== History Tab ======
  const historyColumns = [
    {
      title: '题目',
      dataIndex: 'question_text',
      key: 'question_text',
      ellipsis: true,
      width: 280,
      render: (text: string, record: AnswerHistoryItem) => (
        <Tooltip title={text}>
          <Text style={{ fontSize: 13 }}>{text}</Text>
        </Tooltip>
      ),
    },
    {
      title: '类型',
      dataIndex: 'question_type',
      key: 'question_type',
      width: 70,
      render: (v: string) => (
        <Tag style={{ fontSize: 11 }}>{questionTypeLabels[v] || v}</Tag>
      ),
    },
    {
      title: '认知层',
      dataIndex: 'cognitive_level',
      key: 'cognitive_level',
      width: 70,
      render: (v: string) => v ? (
        <Tag color={COGNITIVE_LEVEL_COLORS[v as CognitiveLevel] || 'default'} style={{ fontSize: 10 }}>
          {COGNITIVE_LEVEL_LABELS[v as CognitiveLevel] || v}
        </Tag>
      ) : <span style={{ color: '#ccc' }}>-</span>,
    },
    {
      title: '结果',
      dataIndex: 'is_correct',
      key: 'is_correct',
      width: 70,
      render: (v: boolean) => v ? (
        <Tag color="green">正确</Tag>
      ) : (
        <Tag color="red">错误</Tag>
      ),
    },
    {
      title: '知识点',
      dataIndex: 'knowledge_point_titles',
      key: 'knowledge_points',
      width: 150,
      ellipsis: true,
      render: (titles: string[]) => (
        <Space size={2} wrap>
          {titles.length > 0
            ? titles.slice(0, 2).map((t, i) => <Tag key={i} style={{ fontSize: 10, margin: 1 }}>{t}</Tag>)
            : <Text type="secondary" style={{ fontSize: 11 }}>-</Text>
          }
          {titles.length > 2 && <Text type="secondary" style={{ fontSize: 10 }}>+{titles.length - 2}</Text>}
        </Space>
      ),
    },
    {
      title: '用时',
      dataIndex: 'time_spent_ms',
      key: 'time_spent_ms',
      width: 70,
      render: (v: number) => (
        <Text style={{ fontSize: 12 }}>{v > 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}ms`}</Text>
      ),
    },
    {
      title: '时间',
      dataIndex: 'answered_at',
      key: 'answered_at',
      width: 100,
      render: (v: string | null) => v ? new Date(v).toLocaleDateString() : '-',
    },
    {
      title: '解析',
      dataIndex: 'analysis',
      key: 'analysis',
      width: 100,
      ellipsis: true,
      render: (v: string) => v ? (
        <Tooltip title={v}>
          <Text style={{ fontSize: 12, color: '#888' }}>{v.slice(0, 30)}...</Text>
        </Tooltip>
      ) : <Text type="secondary">-</Text>,
    },
  ]

  // ====== Stats Tab ======
  const renderStats = () => {
    if (statsLoading) return <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
    if (!stats) return <Empty description="暂无数据" />

    const accuracyColor = stats.overall_accuracy >= 0.8 ? '#52c41a' : stats.overall_accuracy >= 0.6 ? '#faad14' : '#ff4d4f'

    return (
      <div>
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic title="总答题数" value={stats.total_answers} prefix={<FormOutlined />} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic title="正确数" value={stats.correct_answers}
                prefix={<CheckCircleOutlined />} valueStyle={{ color: '#52c41a' }} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic title="错误数" value={stats.total_answers - stats.correct_answers}
                prefix={<CloseCircleOutlined />} valueStyle={{ color: '#ff4d4f' }} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic title="总正确率" value={stats.overall_accuracy * 100}
                suffix="%" precision={1} valueStyle={{ color: accuracyColor }} />
            </Card>
          </Col>
        </Row>

        {/* 7-day trend */}
        <Card size="small" title="近7天答题趋势" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {stats.recent_7_days.map((day) => (
              <Card key={day.date} size="small" style={{ flex: '1 1 100px', minWidth: 100, textAlign: 'center' }}
                bodyStyle={{ padding: '8px' }}>
                <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>
                  {new Date(day.date).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })}
                </div>
                <div style={{ fontSize: 20, fontWeight: 600 }}>
                  {day.total > 0 ? `${Math.round((day.correct / day.total) * 100)}%` : '-'}
                </div>
                <div style={{ fontSize: 10, color: '#888' }}>
                  {day.correct}/{day.total}
                </div>
              </Card>
            ))}
          </div>
        </Card>

        {/* Cognitive breakdown */}
        <Card size="small" title="认知层次分析">
          {Object.keys(stats.cognitive_breakdown).length === 0 ? (
            <Empty description="暂无认知层次数据" />
          ) : (
            <Row gutter={[12, 8]}>
              {Object.entries(stats.cognitive_breakdown).map(([level, data]) => (
                <Col key={level} xs={12} sm={8} md={4}>
                  <Card size="small" style={{ textAlign: 'center' }} bodyStyle={{ padding: '10px 8px' }}>
                    <Tag color={COGNITIVE_LEVEL_COLORS[level as CognitiveLevel] || 'default'}>
                      {COGNITIVE_LEVEL_LABELS[level as CognitiveLevel] || level}
                    </Tag>
                    <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4 }}>
                      {data.correct}/{data.total}
                    </div>
                    <Progress
                      percent={Math.round(data.accuracy * 100)}
                      size="small"
                      strokeColor={data.accuracy >= 0.7 ? '#52c41a' : '#ff4d4f'}
                    />
                  </Card>
                </Col>
              ))}
            </Row>
          )}
        </Card>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <BarChartOutlined style={{ marginRight: 8, color: '#4f46e5' }} />
          答题情况 & 复习推荐
        </Title>
        <Text type="secondary">
          AI 分析你的答题记录，精准定位薄弱知识点，推荐个性化复习方案
        </Text>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'mastery',
            label: <span><TrophyOutlined /> 掌握度总览</span>,
            children: (
              <MasteryOverview analysis={mastery} loading={masteryLoading} />
            ),
          },
          {
            key: 'stats',
            label: <span><BarChartOutlined /> 数据统计</span>,
            children: renderStats(),
          },
          {
            key: 'history',
            label: <span><HistoryOutlined /> 答题历史</span>,
            children: (
              <Card>
                {/* Filters */}
                <Space wrap style={{ marginBottom: 16 }}>
                  <Select
                    allowClear
                    placeholder="按结果筛选"
                    value={filterCorrect}
                    onChange={(v) => handleFilterChange('correct', v)}
                    style={{ minWidth: 120 }}
                    options={[
                      { value: true, label: '正确' },
                      { value: false, label: '错误' },
                    ]}
                  />
                  <Select
                    allowClear
                    showSearch
                    placeholder="按知识点筛选"
                    value={filterKpId}
                    onChange={(v) => handleFilterChange('kp', v)}
                    style={{ minWidth: 200 }}
                    options={kpList.map(kp => ({
                      value: kp.id,
                      label: `${kp.title}${kp.mastery != null ? ` (${(kp.mastery * 100).toFixed(0)}%)` : ''}`,
                    }))}
                    filterOption={(input, option) =>
                      (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
                    }
                  />
                  <Button icon={<ReloadOutlined />} onClick={() => loadHistory(1)}>
                    刷新
                  </Button>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    共 {historyTotal} 条记录
                  </Text>
                </Space>

                <Table
                  loading={historyLoading}
                  dataSource={history}
                  rowKey="record_id"
                  columns={historyColumns}
                  size="small"
                  pagination={{
                    current: historyPage,
                    pageSize,
                    total: historyTotal,
                    onChange: (page) => loadHistory(page),
                    showSizeChanger: true,
                    pageSizeOptions: ['10', '20', '50'],
                    showTotal: (total) => `共 ${total} 条`,
                  }}
                  scroll={{ x: 1000 }}
                  locale={{ emptyText: '暂无答题记录，去完成一次测验吧' }}
                />
              </Card>
            ),
          },
          {
            key: 'recommend',
            label: <span><RobotOutlined /> AI复习推荐</span>,
            children: <ReviewRecommendation onRefresh={loadMastery} />,
          },
        ]}
      />
    </div>
  )
}

// Local workaround for missing icons
function FormOutlined() {
  return <span style={{ fontSize: 16 }}>📝</span>
}
