import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Layout, Card, Button, Spin, message, Tabs, Space, Tag, Typography, Divider } from 'antd'
import { ArrowLeftOutlined, ApartmentOutlined, ThunderboltOutlined, FileTextOutlined, FormOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getSummary, getSummaryNodes, orchestrateAgents } from '../api'
import type { KnowledgeSummary, KnowledgePointNode } from '../types'
import MarkdownTOC from '../components/MarkdownTOC'

const { Sider, Content } = Layout
const { Title, Text } = Typography

export default function SummaryPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [summary, setSummary] = useState<KnowledgeSummary | null>(null)
  const [nodes, setNodes] = useState<KnowledgePointNode[]>([])
  const [loading, setLoading] = useState(true)
  const [orchestrating, setOrchestrating] = useState(false)

  useEffect(() => {
    if (!id) return
    loadSummary()
  }, [id])

  const loadSummary = async () => {
    try {
      setLoading(true)
      const [summaryData, nodesData] = await Promise.all([
        getSummary(id!),
        getSummaryNodes(id!),
      ])
      setSummary(summaryData)
      setNodes(nodesData.nodes || [])
    } catch (e: any) {
      message.error('加载知识点总结失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const handleOrchestrate = async () => {
    if (!id || !summary) return
    try {
      setOrchestrating(true)
      const result = await orchestrateAgents({
        summary_id: id,
        document_id: summary.document_id,
        config: { question_count: 30 },
      })
      message.success(`Agent 调度完成！生成了 ${Object.keys(result.results || {}).length} 项内容`)
      if (result.coverage_report) {
        message.info(`知识点覆盖率: ${(result.coverage_report.full_coverage_rate * 100).toFixed(1)}%`)
      }
    } catch (e: any) {
      message.error('Agent 调度失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setOrchestrating(false)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>
  if (!summary) return <div style={{ textAlign: 'center', padding: 100 }}>总结未找到</div>

  return (
    <Layout style={{ minHeight: '100%', background: 'transparent' }}>
      <Sider width={250} style={{ background: 'transparent', paddingRight: 16 }}>
        <Card size="small" title="目录导航" style={{ position: 'sticky', top: 0 }}>
          <MarkdownTOC content={summary.content_md} />
        </Card>
        <Card size="small" title="操作" style={{ marginTop: 12 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Button block icon={<ThunderboltOutlined />} type="primary"
              onClick={handleOrchestrate} loading={orchestrating}>
              并行生成所有内容
            </Button>
            <Button block icon={<ApartmentOutlined />}
              onClick={() => navigate(`/mindmap/${id}`)}>
              查看思维导图
            </Button>
            <Button block icon={<FormOutlined />}
              onClick={() => navigate(`/quiz/interactive/${id}`)}>
              交互式答题
            </Button>
            <Button block icon={<FileTextOutlined />}
              onClick={() => navigate(`/coverage/${id}`)}>
              覆盖率报告
            </Button>
          </Space>
        </Card>
        <Card size="small" title="统计" style={{ marginTop: 12 }}>
          <Space direction="vertical">
            <Text>知识点总数: {summary.node_count}</Text>
            {summary.level_stats && Object.entries(summary.level_stats).map(([k, v]) => (
              <Tag key={k}>{k}: {v as number}个</Tag>
            ))}
          </Space>
        </Card>
      </Sider>
      <Content style={{ paddingLeft: 24 }}>
        <div style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} type="text">
            返回
          </Button>
          <Title level={3} style={{ marginTop: 8 }}>知识点总结</Title>
        </div>
        <Card>
          <div className="markdown-body" style={{ maxWidth: 900, margin: '0 auto' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {summary.content_md}
            </ReactMarkdown>
          </div>
        </Card>
      </Content>
    </Layout>
  )
}
