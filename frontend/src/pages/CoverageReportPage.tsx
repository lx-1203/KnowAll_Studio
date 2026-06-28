import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Button, Spin, App, Table, Tag, Progress, Space, Typography, Row, Col, Statistic } from 'antd'
import { ArrowLeftOutlined, ReloadOutlined, WarningOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { getCoverageReport, refreshCoverage } from '../api'
import type { CoverageReport } from '../types'

const { Title, Text } = Typography

export default function CoverageReportPage() {
  const { summaryId } = useParams<{ summaryId: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const [report, setReport] = useState<CoverageReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    if (!summaryId) return
    loadReport()
  }, [summaryId])

  const loadReport = async () => {
    try {
      setLoading(true)
      const data = await getCoverageReport(summaryId!)
      setReport(data)
    } catch (e: any) {
      message.error('加载覆盖率报告失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    if (!summaryId) return
    try {
      setRefreshing(true)
      const result = await refreshCoverage({ summary_id: summaryId, document_id: '' })
      if (result.generated_questions || result.generated_cards) {
        message.success(`已补充生成 ${result.generated_questions} 道题 + ${result.generated_cards} 张记忆卡`)
      }
      await loadReport()
    } catch (e: any) {
      message.error('刷新覆盖率失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setRefreshing(false)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>
  if (!report) return <div style={{ textAlign: 'center', padding: 100 }}>报告未找到</div>

  const uncoveredColumns = [
    { title: '知识点 ID', dataIndex: 'id', key: 'id' },
    { title: '标题', dataIndex: 'title', key: 'title' },
    { title: '层级', dataIndex: 'level', key: 'level', render: (l: number) => <Tag>{`L${l}`}</Tag> },
  ]

  const weakColumns = [
    { title: '知识点', dataIndex: 'title', key: 'title' },
    { title: '正确率', dataIndex: 'accuracy', key: 'accuracy',
      render: (v: number) => <Progress percent={Math.round(v * 100)} size="small"
        status={v < 0.7 ? 'exception' : 'active'} /> },
    { title: '建议', dataIndex: 'recommendation', key: 'recommendation' },
  ]

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} type="text">返回</Button>
          <Title level={4} style={{ margin: 0 }}>覆盖率报告</Title>
        </Space>
        <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={refreshing}>
          补充覆盖
        </Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card><Statistic title="知识点总数" value={report.total_knowledge_points} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="题目覆盖" value={report.covered_by_questions}
            suffix={`/ ${report.total_knowledge_points}`}
            valueStyle={{ color: report.coverage_rate_questions >= 0.8 ? '#3f8600' : '#cf1322' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="记忆卡覆盖" value={report.covered_by_flashcards}
            suffix={`/ ${report.total_knowledge_points}`}
            valueStyle={{ color: report.coverage_rate_flashcards >= 0.8 ? '#3f8600' : '#cf1322' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="全覆盖率" value={report.full_coverage_rate * 100}
            suffix="%" precision={1}
            valueStyle={{ color: report.full_coverage_rate >= 0.8 ? '#3f8600' : '#cf1322' }} /></Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card title={<Space><WarningOutlined style={{ color: '#faad14' }} />未覆盖知识点</Space>}
            style={{ marginBottom: 16 }}>
            {report.uncovered_points.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 24 }}>
                <CheckCircleOutlined style={{ fontSize: 32, color: '#52c41a' }} />
                <div style={{ marginTop: 8 }}><Text type="success">所有知识点均已覆盖！</Text></div>
              </div>
            ) : (
              <Table dataSource={report.uncovered_points} columns={uncoveredColumns}
                rowKey="id" size="small" pagination={false} />
            )}
          </Card>
        </Col>
        <Col span={12}>
          <Card title={<Space><WarningOutlined style={{ color: '#ff4d4f' }} />薄弱知识点</Space>}
            style={{ marginBottom: 16 }}>
            {report.weak_points.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 24 }}>
                <CheckCircleOutlined style={{ fontSize: 32, color: '#52c41a' }} />
                <div style={{ marginTop: 8 }}><Text type="success">没有薄弱知识点！</Text></div>
              </div>
            ) : (
              <Table dataSource={report.weak_points} columns={weakColumns}
                rowKey="id" size="small" pagination={false} />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
