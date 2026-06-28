import { Card, Progress, Tag, Row, Col, Tooltip, Empty, Typography, Space } from 'antd'
import {
  TrophyOutlined, WarningOutlined, RiseOutlined, FallOutlined,
  MinusOutlined, QuestionCircleOutlined,
} from '@ant-design/icons'
import type { MasteryDetail, MasteryAnalysis } from '../types'

const { Text, Title } = Typography

function MasteryBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
        <Text style={{ fontSize: 12 }}>{label}</Text>
        <Text strong style={{ fontSize: 12, color }}>{(value * 100).toFixed(0)}%</Text>
      </div>
      <Progress
        percent={Math.round(value * 100)}
        showInfo={false}
        strokeColor={color}
        trailColor="#f0f0f0"
        size="small"
      />
    </div>
  )
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend === 'improving') return <RiseOutlined style={{ color: '#52c41a' }} />
  if (trend === 'declining') return <FallOutlined style={{ color: '#ff4d4f' }} />
  return <MinusOutlined style={{ color: '#999' }} />
}

function TrendLabel({ trend }: { trend: string }) {
  if (trend === 'improving') return <Tag color="green">上升</Tag>
  if (trend === 'declining') return <Tag color="red">下降</Tag>
  return <Tag color="default">稳定</Tag>
}

interface Props {
  analysis: MasteryAnalysis | null
  loading: boolean
}

export default function MasteryOverview({ analysis, loading }: Props) {
  if (loading) return null

  if (!analysis || analysis.total_knowledge_points === 0) {
    return (
      <Card>
        <Empty
          image={<QuestionCircleOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
          description="暂无答题数据，完成一次测验后即可查看知识点掌握分析"
        />
      </Card>
    )
  }

  const { overall_mastery, weak_count, moderate_count, strong_count, weak_points, moderate_points, strong_points } = analysis

  const overallColor = overall_mastery >= 0.8 ? '#52c41a' : overall_mastery >= 0.6 ? '#faad14' : '#ff4d4f'

  return (
    <div>
      {/* Overall Stats Cards */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 13, color: '#888', marginBottom: 4 }}>综合掌握度</div>
            <div style={{ fontSize: 36, fontWeight: 700, color: overallColor }}>
              {(overall_mastery * 100).toFixed(0)}%
            </div>
            <Progress
              percent={Math.round(overall_mastery * 100)}
              showInfo={false}
              strokeColor={overallColor}
              size="small"
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 13, color: '#888', marginBottom: 4 }}>
              <TrophyOutlined style={{ color: '#52c41a', marginRight: 4 }} />掌握牢固
            </div>
            <div style={{ fontSize: 36, fontWeight: 700, color: '#52c41a' }}>{strong_count}</div>
            <Text type="secondary" style={{ fontSize: 12 }}>个知识点</Text>
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 13, color: '#888', marginBottom: 4 }}>
              <WarningOutlined style={{ color: '#faad14', marginRight: 4 }} />需要巩固
            </div>
            <div style={{ fontSize: 36, fontWeight: 700, color: '#faad14' }}>{moderate_count}</div>
            <Text type="secondary" style={{ fontSize: 12 }}>个知识点</Text>
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 13, color: '#888', marginBottom: 4 }}>
              <WarningOutlined style={{ color: '#ff4d4f', marginRight: 4 }} />薄弱环节
            </div>
            <div style={{ fontSize: 36, fontWeight: 700, color: '#ff4d4f' }}>{weak_count}</div>
            <Text type="secondary" style={{ fontSize: 12 }}>个知识点</Text>
          </Card>
        </Col>
      </Row>

      {/* Mastery Distribution */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={12}>
          <Card size="small" title={<Text strong style={{ fontSize: 15 }}>薄弱知识点</Text>}
            style={{ background: '#fff7f7' }}>
            {weak_points.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 16, color: '#52c41a' }}>
                暂无薄弱知识点
              </div>
            ) : (
              <div style={{ maxHeight: 360, overflow: 'auto' }}>
                {weak_points.map(kp => (
                  <Card key={kp.kp_id} size="small" style={{ marginBottom: 8 }}
                    bodyStyle={{ padding: '8px 12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <Tooltip title={kp.explanation || kp.title}>
                        <Text strong style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {kp.title}
                        </Text>
                      </Tooltip>
                      <Space size={4}>
                        <TrendLabel trend={kp.trend} />
                        <Tag>{kp.total_attempts}次</Tag>
                      </Space>
                    </div>
                    <Progress
                      percent={Math.round(kp.mastery_score * 100)}
                      size="small"
                      strokeColor="#ff4d4f"
                      format={p => `${p}%`}
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        正确率 {(kp.accuracy * 100).toFixed(0)}% | 错{kp.error_count}次
                      </Text>
                      <TrendIcon trend={kp.trend} />
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title={<Text strong style={{ fontSize: 15 }}>掌握牢固</Text>}
            style={{ background: '#f6ffed' }}>
            {strong_points.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 16, color: '#999' }}>
                继续加油，你正在建立知识体系
              </div>
            ) : (
              <div style={{ maxHeight: 360, overflow: 'auto' }}>
                {strong_points.map(kp => (
                  <Card key={kp.kp_id} size="small" style={{ marginBottom: 8 }}
                    bodyStyle={{ padding: '8px 12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <Text strong style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {kp.title}
                      </Text>
                      <Space size={4}>
                        <TrendLabel trend={kp.trend} />
                        <Tag color="green">掌握</Tag>
                      </Space>
                    </div>
                    <Progress
                      percent={Math.round(kp.mastery_score * 100)}
                      size="small"
                      strokeColor="#52c41a"
                      format={p => `${p}%`}
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        正确率 {(kp.accuracy * 100).toFixed(0)}% | {kp.total_attempts}次练习
                      </Text>
                      <TrendIcon trend={kp.trend} />
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* Per-KP Mastery Bars */}
      {analysis.moderate_points.length > 0 && (
        <Card size="small" title={<Text strong style={{ fontSize: 15 }}>需要巩固</Text>}
          style={{ background: '#fffbe6' }}>
          <Row gutter={[12, 8]}>
            {analysis.moderate_points.map(kp => (
              <Col key={kp.kp_id} xs={24} sm={12} md={8}>
                <Card size="small" bodyStyle={{ padding: '8px 12px' }}>
                  <Tooltip title={kp.explanation || kp.title}>
                    <Text strong style={{ display: 'block', marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {kp.title}
                    </Text>
                  </Tooltip>
                  <Progress
                    percent={Math.round(kp.mastery_score * 100)}
                    size="small"
                    strokeColor="#faad14"
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      正确率 {(kp.accuracy * 100).toFixed(0)}%
                    </Text>
                    <TrendIcon trend={kp.trend} />
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}
    </div>
  )
}
