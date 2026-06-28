import { useState } from 'react'
import {
  Card, Button, Tag, List, Typography, Space, Alert, Spin, Collapse, Progress, Row, Col, message,
} from 'antd'
import {
  RobotOutlined, ThunderboltOutlined, ClockCircleOutlined,
  BookOutlined, CaretRightOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { generateReviewRecommendations } from '../api'
import type { ReviewRecommendations, AIRecommendation } from '../types'

const { Text, Title, Paragraph } = Typography

interface Props {
  onRefresh?: () => void
}

export default function ReviewRecommendation({ onRefresh }: Props) {
  const [data, setData] = useState<ReviewRecommendations | null>(null)
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const result = await generateReviewRecommendations()
      setData(result)
      if (!result.has_weak_points) {
        message.success(result.message || '所有知识点掌握良好！')
      } else {
        message.success(`已生成 ${result.recommendations.length} 条复习建议`)
      }
      onRefresh?.()
    } catch (e: any) {
      message.error('生成复习建议失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setGenerating(false)
    }
  }

  const priorityColors: Record<string, string> = { high: 'red', medium: 'orange' }
  const priorityLabels: Record<string, string> = { high: '优先复习', medium: '建议复习' }

  return (
    <div>
      <Card
        title={
          <Space>
            <RobotOutlined style={{ color: '#4f46e5' }} />
            <Text strong style={{ fontSize: 15 }}>AI 复习建议</Text>
          </Space>
        }
        extra={
          <Button
            type="primary"
            icon={<RobotOutlined />}
            loading={generating}
            onClick={handleGenerate}
            style={{ background: '#4f46e5' }}
          >
            {data ? '重新生成' : '生成复习建议'}
          </Button>
        }
      >
        {!data && !generating && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <RobotOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />
            <div>
              <Text type="secondary">
                AI 将分析你的答题记录，找出薄弱知识点，<br />
                并生成个性化复习计划
              </Text>
            </div>
            <Button
              type="primary"
              size="large"
              icon={<RobotOutlined />}
              onClick={handleGenerate}
              loading={generating}
              style={{ marginTop: 16, background: '#4f46e5' }}
            >
              开始分析
            </Button>
          </div>
        )}

        {generating && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin size="large" />
            <div style={{ marginTop: 16 }}>
              <Text type="secondary">AI 正在分析答题数据并生成复习建议...</Text>
            </div>
            <div style={{ marginTop: 8, color: '#888', fontSize: 12 }}>
              正在评估知识点掌握度、识别薄弱环节、制定个性化复习计划
            </div>
          </div>
        )}

        {data && !generating && (
          <>
            {data.message && !data.has_weak_points && (
              <Alert
                type="success"
                message="太棒了！"
                description={data.message}
                showIcon
                icon={<TrophyOutlined />}
                style={{ marginBottom: 16 }}
              />
            )}

            {data.has_weak_points && (
              <>
                {/* Summary */}
                <Row gutter={16} style={{ marginBottom: 16 }}>
                  <Col span={8}>
                    <Card size="small" style={{ textAlign: 'center', background: '#f0f5ff' }}>
                      <div style={{ fontSize: 12, color: '#888' }}>综合掌握度</div>
                      <div style={{ fontSize: 28, fontWeight: 700, color: '#4f46e5' }}>
                        {(data.overall_mastery * 100).toFixed(0)}%
                      </div>
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small" style={{ textAlign: 'center', background: '#fff7f7' }}>
                      <div style={{ fontSize: 12, color: '#888' }}>薄弱知识点</div>
                      <div style={{ fontSize: 28, fontWeight: 700, color: '#ff4d4f' }}>
                        {data.weak_point_count}
                      </div>
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small" style={{ textAlign: 'center', background: '#fffbe6' }}>
                      <div style={{ fontSize: 12, color: '#888' }}>需巩固知识点</div>
                      <div style={{ fontSize: 28, fontWeight: 700, color: '#faad14' }}>
                        {data.moderate_point_count}
                      </div>
                    </Card>
                  </Col>
                </Row>

                {/* Recommendations List */}
                <div style={{ marginTop: 16 }}>
                  <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 12 }}>
                    <ThunderboltOutlined style={{ color: '#faad14', marginRight: 4 }} />
                    复习建议列表
                  </Text>
                  <List
                    dataSource={data.recommendations}
                    renderItem={(item: AIRecommendation) => (
                      <List.Item style={{ padding: '12px 0' }}>
                        <Card
                          size="small"
                          style={{ width: '100%' }}
                          bodyStyle={{ padding: '12px 16px' }}
                          title={
                            <Space>
                              <Tag color={priorityColors[item.priority]}>
                                {priorityLabels[item.priority]}
                              </Tag>
                              <Text strong>{item.knowledge_point}</Text>
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                掌握度 {(item.mastery_current * 100).toFixed(0)}%
                              </Text>
                            </Space>
                          }
                          extra={
                            <Space size={4} style={{ fontSize: 12, color: '#888' }}>
                              <ClockCircleOutlined />
                              ~{item.estimated_review_time_min}分钟
                            </Space>
                          }
                        >
                          <div style={{ marginBottom: 8 }}>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              <BookOutlined style={{ marginRight: 4 }} />
                              复习重点：{item.review_focus}
                            </Text>
                          </div>
                          <div>
                            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                              建议行动：
                            </Text>
                            <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13 }}>
                              {item.suggested_actions.map((action, i) => (
                                <li key={i} style={{ marginBottom: 2 }}>{action}</li>
                              ))}
                            </ul>
                          </div>
                          <div style={{ marginTop: 8 }}>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              推荐资源：{item.recommended_resources}
                            </Text>
                          </div>
                        </Card>
                      </List.Item>
                    )}
                  />
                </div>

                {/* Weak Points Summary */}
                {data.weak_points_summary.length > 0 && (
                  <Collapse
                    ghost
                    style={{ marginTop: 16 }}
                    items={[{
                      key: 'weak-summary',
                      label: <Text type="secondary">薄弱知识点原始数据</Text>,
                      children: (
                        <List
                          size="small"
                          dataSource={data.weak_points_summary}
                          renderItem={(wp: any) => (
                            <List.Item>
                              <Space>
                                <Text>{wp.title}</Text>
                                <Tag>掌握度 {(wp.mastery * 100).toFixed(0)}%</Tag>
                                <Tag color={wp.trend === 'improving' ? 'green' : wp.trend === 'declining' ? 'red' : 'default'}>
                                  {wp.trend}
                                </Tag>
                                <Text type="secondary">错{wp.errors}次/{wp.attempts}次</Text>
                              </Space>
                            </List.Item>
                          )}
                        />
                      ),
                    }]}
                  />
                )}
              </>
            )}
          </>
        )}
      </Card>
    </div>
  )
}

// Workaround for missing imports
const { Row, Col } = { Row: ({ children, ...p }: any) => <div style={{ display: 'flex', gap: 16, ...p }}>{children}</div>, Col: ({ children, ...p }: any) => <div style={{ flex: p.span ? p.span / 24 : 1, ...p }}>{children}</div> }
