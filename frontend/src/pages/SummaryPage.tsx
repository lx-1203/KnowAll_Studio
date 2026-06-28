import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Layout, Card, Button, Spin, message, Tabs, Space, Tag, Typography, Progress, List, Statistic, Row, Col, Empty } from 'antd'
import {
  ArrowLeftOutlined, ThunderboltOutlined, FileTextOutlined, FormOutlined,
  ApartmentOutlined, IdcardOutlined, ScheduleOutlined, ReadOutlined,
  PieChartOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined,
  RocketOutlined,
} from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  getSummary, getSummaryNodes, getSummaryMindmap, orchestrateAgents,
  getCoverageReport, getReviewQueue, getMemoryStats, startInteractiveQuiz,
} from '../api'
import type { MindMapData, CoverageReport, ReviewQueueItem, MemoryStats, Question } from '../types'
import MarkdownTOC from '../components/MarkdownTOC'
import ReviewQueuePanel from '../components/ReviewQueuePanel'

const { Sider, Content } = Layout
const { Title, Text } = Typography

const AGENTS = ['question_bank', 'mindmap', 'study_plan', 'language']
const AGENT_LABELS: Record<string, string> = {
  question_bank: '题库生成',
  mindmap: '思维导图',
  study_plan: '学习计划',
  language: '生词表',
}
const AGENT_TAB_MAP: Record<string, string> = {
  question_bank: 'quiz',
  mindmap: 'mindmap',
  study_plan: 'plan',
  language: 'vocab',
}

export default function SummaryPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('summary')

  // Agent orchestration state
  const [agentResults, setAgentResults] = useState<Record<string, any>>({})
  const [agentProgress, setAgentProgress] = useState<Record<string, 'pending' | 'running' | 'done' | 'error'>>({})
  const [orchestrating, setOrchestrating] = useState(false)
  const [orchestrateDone, setOrchestrateDone] = useState(false)

  // Preloaded data for tabs
  const [mindmapData, setMindmapData] = useState<MindMapData | null>(null)
  const [coverageReport, setCoverageReport] = useState<CoverageReport | null>(null)
  const [previewQuestions, setPreviewQuestions] = useState<Question[]>([])
  const [memoryStats, setMemoryStats] = useState<MemoryStats | null>(null)

  useEffect(() => {
    if (!id) return
    loadSummary()
  }, [id])

  const loadSummary = async () => {
    try {
      setLoading(true)
      const data = await getSummary(id!)
      setSummary(data)
      // Auto-load coverage report
      try {
        const cov = await getCoverageReport(id!)
        setCoverageReport(cov)
      } catch {}
      // Load memory stats
      try {
        const stats = await getMemoryStats()
        setMemoryStats(stats)
      } catch {}
    } catch (e: any) {
      message.error('加载知识总纲失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const handleOrchestrate = async () => {
    if (!id || !summary) return
    const docIds = summary.document_ids || []
    if (docIds.length === 0) {
      message.warning('缺少文档关联信息')
      return
    }

    setOrchestrating(true)
    setOrchestrateDone(false)
    setAgentResults({})
    const initialProgress: Record<string, 'pending' | 'running' | 'done' | 'error'> = {}
    AGENTS.forEach(a => { initialProgress[a] = 'pending' })
    setAgentProgress(initialProgress)

    try {
      const result = await orchestrateAgents({
        summary_id: id,
        document_id: docIds[0],
        config: { question_count: 30 },
      })

      // Process results
      const newResults: Record<string, any> = {}
      const newProgress: Record<string, 'pending' | 'running' | 'done' | 'error'> = {}
      for (const [name, r] of Object.entries(result.results || {}) as [string, any][]) {
        newResults[name] = r
        newProgress[name] = r.status === 'success' ? 'done' : 'error'
      }
      setAgentResults(newResults)
      setAgentProgress(newProgress)
      setOrchestrateDone(true)

      // Auto-load coverage report after orchestration
      try {
        const cov = await getCoverageReport(id!)
        setCoverageReport(cov)
      } catch {}

      // Auto-load mindmap data
      if (newResults.mindmap?.status === 'success') {
        try {
          const mm = await getSummaryMindmap(id!)
          setMindmapData(mm)
        } catch {}
      }

      // Load preview questions
      if (newResults.question_bank?.status === 'success') {
        try {
          const quiz = await startInteractiveQuiz({ summary_id: id, count: 5 })
          setPreviewQuestions(quiz.questions || [])
        } catch {}
      }

      const successCount = Object.values(newProgress).filter(p => p === 'done').length
      message.success(`全部配套内容生成完成！成功 ${successCount}/${AGENTS.length} 项`)
    } catch (e: any) {
      message.error('生成失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setOrchestrating(false)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" tip="加载知识总纲..."><div style={{ minHeight: 200 }} /></Spin></div>
  if (!summary) return <div style={{ textAlign: 'center', padding: 100 }}>知识总纲未找到</div>

  const tabItems = [
    {
      key: 'summary',
      label: <span><FileTextOutlined /> 知识总纲</span>,
      children: (
        <Card>
          <div className="markdown-body" style={{ maxWidth: 900, margin: '0 auto' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {summary.content_md}
            </ReactMarkdown>
          </div>
        </Card>
      ),
    },
    {
      key: 'quiz',
      label: <span><FormOutlined /> 题库 ({previewQuestions.length || '?'})</span>,
      children: (
        <Card
          title="题库概览"
          extra={
            <Button type="link" onClick={() => navigate(`/quiz/interactive/${id}`)}>
              进入答题 →
            </Button>
          }
        >
          {previewQuestions.length > 0 ? (
            <List
              dataSource={previewQuestions.slice(0, 10)}
              renderItem={(q: any) => (
                <List.Item>
                  <List.Item.Meta
                    title={q.question_text?.slice(0, 80) + (q.question_text?.length > 80 ? '...' : '')}
                    description={
                      <Space>
                        <Tag>{q.question_type === 'single_choice' ? '单选题' : q.question_type}</Tag>
                        <Tag color={q.difficulty === 'hard' ? 'red' : q.difficulty === 'easy' ? 'green' : 'blue'}>{q.difficulty}</Tag>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          ) : (
            <Empty description="尚未生成题目">
              {!orchestrateDone && (
                <Button type="primary" onClick={handleOrchestrate}>一键生成全部配套</Button>
              )}
            </Empty>
          )}
        </Card>
      ),
    },
    {
      key: 'mindmap',
      label: <span><ApartmentOutlined /> 思维导图</span>,
      children: (
        <Card
          title="思维导图概览"
          extra={
            <Button type="link" onClick={() => navigate(`/mindmap/${id}`)}>
              查看完整导图 →
            </Button>
          }
        >
          {mindmapData ? (
            <div style={{ textAlign: 'center', padding: 24 }}>
              <Row gutter={16}>
                <Col span={8}><Statistic title="节点数" value={mindmapData.nodes?.length || 0} /></Col>
                <Col span={8}><Statistic title="连线数" value={mindmapData.edges?.length || 0} /></Col>
                <Col span={8}>
                  <Statistic
                    title="BOIS 评分"
                    value={mindmapData.bois_metrics?.score || 0}
                    suffix="分"
                    valueStyle={{ color: (mindmapData.bois_metrics?.score || 0) >= 75 ? '#52c41a' : '#faad14' }}
                  />
                </Col>
              </Row>
              <Button style={{ marginTop: 16 }} onClick={() => navigate(`/mindmap/${id}`)}>
                打开思维导图
              </Button>
            </div>
          ) : (
            <Empty description="尚未生成思维导图">
              {!orchestrateDone && (
                <Button type="primary" onClick={handleOrchestrate}>一键生成全部配套</Button>
              )}
            </Empty>
          )}
        </Card>
      ),
    },
    {
      key: 'flashcards',
      label: <span><IdcardOutlined /> 记忆卡</span>,
      children: (
        <Card
          title="记忆卡概览"
          extra={
            <Button type="link" onClick={() => navigate('/flashcards')}>
              进入闪卡复习 →
            </Button>
          }
        >
          {memoryStats ? (
            <div style={{ textAlign: 'center', padding: 24 }}>
              <Row gutter={16}>
                <Col span={6}><Statistic title="总卡片数" value={memoryStats.total_cards} /></Col>
                <Col span={6}><Statistic title="待复习" value={memoryStats.due_today} valueStyle={{ color: '#faad14' }} /></Col>
                <Col span={6}><Statistic title="平均正确率" value={memoryStats.average_accuracy * 100} suffix="%" precision={1} /></Col>
                <Col span={6}><Statistic title="复习队列" value={memoryStats.review_queue_count} valueStyle={{ color: '#ff4d4f' }} /></Col>
              </Row>
            </div>
          ) : (
            <Empty description="加载记忆卡统计中..." />
          )}
        </Card>
      ),
    },
    {
      key: 'plan',
      label: <span><ScheduleOutlined /> 学习计划</span>,
      children: (
        <Card
          title="学习计划"
          extra={
            <Button type="link" onClick={() => navigate('/study')}>
              管理学习计划 →
            </Button>
          }
        >
          {agentResults.study_plan ? (
            <div style={{ padding: 16 }}>
              <Text strong>计划名称: </Text>
              <Text>{agentResults.study_plan.result?.name || '学习计划'}</Text>
              <br /><br />
              {agentResults.study_plan.result?.ebbinghaus_nodes && (
                <div>
                  <Text strong>艾宾浩斯复习节点: </Text>
                  <Space wrap>
                    {agentResults.study_plan.result.ebbinghaus_nodes.map((n: any) => (
                      <Tag key={n.day} color="blue">第{n.day}天复习</Tag>
                    ))}
                  </Space>
                </div>
              )}
            </div>
          ) : (
            <Empty description="尚未生成学习计划">
              {!orchestrateDone && (
                <Button type="primary" onClick={handleOrchestrate}>一键生成全部配套</Button>
              )}
            </Empty>
          )}
        </Card>
      ),
    },
    {
      key: 'vocab',
      label: <span><ReadOutlined /> 生词表</span>,
      children: (
        <Card
          title="生词表"
          extra={
            <Button type="link" onClick={() => navigate(`/language?docId=${summary.document_ids?.[0] || ''}`)}>
              查看完整生词表 →
            </Button>
          }
        >
          {agentResults.language?.status === 'success' ? (
            <div style={{ textAlign: 'center', padding: 24 }}>
              <Statistic title="提取生词数" value={agentResults.language.result?.total_words || 0} />
            </div>
          ) : agentResults.language?.status === 'skipped' ? (
            <Empty description="非语言类材料，已跳过生词提取" />
          ) : (
            <Empty description="尚未提取生词">
              {!orchestrateDone && (
                <Button type="primary" onClick={handleOrchestrate}>一键生成全部配套</Button>
              )}
            </Empty>
          )}
        </Card>
      ),
    },
    {
      key: 'coverage',
      label: <span><PieChartOutlined /> 覆盖率</span>,
      children: (
        <Card
          title="覆盖率报告"
          extra={
            <Button type="link" onClick={() => navigate(`/coverage/${id}`)}>
              查看详细报告 →
            </Button>
          }
        >
          {coverageReport ? (
            <div style={{ textAlign: 'center', padding: 24 }}>
              <Row gutter={16}>
                <Col span={6}>
                  <Progress type="circle" percent={Math.round(coverageReport.full_coverage_rate * 100)} size={80} />
                  <div style={{ marginTop: 8 }}><Text>全覆盖率</Text></div>
                </Col>
                <Col span={6}><Statistic title="知识点总数" value={coverageReport.total_knowledge_points} /></Col>
                <Col span={6}><Statistic title="题目覆盖" value={coverageReport.covered_by_questions} /></Col>
                <Col span={6}><Statistic title="记忆卡覆盖" value={coverageReport.covered_by_flashcards} /></Col>
              </Row>
              {coverageReport.uncovered_points.length > 0 && (
                <Tag color="warning" style={{ marginTop: 16 }}>
                  还有 {coverageReport.uncovered_points.length} 个知识点未覆盖
                </Tag>
              )}
            </div>
          ) : (
            <Empty description="加载覆盖率中..." />
          )}
        </Card>
      ),
    },
  ]

  // Agent progress indicators
  const agentStatusTags = AGENTS.map(name => {
    const status = agentProgress[name]
    if (!status || status === 'pending') return <Tag key={name}>{AGENT_LABELS[name]}: 等待中</Tag>
    if (status === 'running') return <Tag key={name} color="processing" icon={<LoadingOutlined />}>{AGENT_LABELS[name]}: 生成中</Tag>
    if (status === 'done') return <Tag key={name} color="success" icon={<CheckCircleOutlined />}>{AGENT_LABELS[name]}: 完成</Tag>
    return <Tag key={name} color="error" icon={<CloseCircleOutlined />}>{AGENT_LABELS[name]}: 失败</Tag>
  })

  return (
    <Layout style={{ minHeight: '100%', background: 'transparent' }}>
      {/* Left Sidebar */}
      <Sider width={260} style={{ background: 'transparent', paddingRight: 16 }}>
        <Card size="small" title="知识总纲目录" style={{ position: 'sticky', top: 0 }}>
          <MarkdownTOC content={summary.content_md} />
        </Card>
        <Card size="small" title="统计" style={{ marginTop: 12 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text>知识点总数: <Text strong>{summary.node_count}</Text></Text>
            {summary.level_stats && Object.entries(summary.level_stats).map(([k, v]) => (
              <Tag key={k}>{k}: {v as number}个</Tag>
            ))}
            {summary.document_ids?.length > 0 && (
              <Text type="secondary">来源: {summary.document_ids.length} 个文档</Text>
            )}
          </Space>
        </Card>
        <Card size="small" title="快捷操作" style={{ marginTop: 12 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Button
              block
              icon={<RocketOutlined />}
              type="primary"
              onClick={handleOrchestrate}
              loading={orchestrating}
              disabled={orchestrating}
            >
              {orchestrateDone ? '重新生成全部配套' : '一键生成全部配套'}
            </Button>
            <Button block icon={<FormOutlined />} onClick={() => navigate(`/quiz/interactive/${id}`)}>
              开始交互答题
            </Button>
            <Button block icon={<ApartmentOutlined />} onClick={() => navigate(`/mindmap/${id}`)}>
              查看思维导图
            </Button>
            <Button block icon={<IdcardOutlined />} onClick={() => navigate('/flashcards')}>
              复习记忆卡
            </Button>
            <Button block icon={<PieChartOutlined />} onClick={() => navigate(`/coverage/${id}`)}>
              覆盖率报告
            </Button>
            <Button block icon={<ScheduleOutlined />} onClick={() => navigate('/study')}>
              学习计划
            </Button>
          </Space>
        </Card>
        <Card size="small" title="复习队列" style={{ marginTop: 12 }}>
          <ReviewQueuePanel />
        </Card>
      </Sider>

      {/* Main Content */}
      <Content style={{ paddingLeft: 24 }}>
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/upload')} type="text">
              返回资料库
            </Button>
          </Space>
          <Title level={3} style={{ marginTop: 8 }}>
            <RocketOutlined style={{ marginRight: 8, color: '#4f46e5' }} />
            知识中枢
          </Title>
          <div style={{ marginBottom: 12 }}>
            <Space wrap>{agentStatusTags}</Space>
          </div>
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          size="large"
        />
      </Content>
    </Layout>
  )
}
