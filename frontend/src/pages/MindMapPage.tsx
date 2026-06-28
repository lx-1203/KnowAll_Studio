import { useState, useEffect, useCallback } from 'react'
import ReactFlow, {
  Node, Edge, Controls, Background, MiniMap, useNodesState, useEdgesState,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Button, Spin, message, Typography, Tag, Progress, Collapse, Empty, Tooltip, Space, Divider } from 'antd'
import {
  ArrowLeftOutlined, ExpandOutlined, TrophyOutlined,
  ApartmentOutlined, BranchesOutlined, DashboardOutlined,
  CheckCircleOutlined, WarningOutlined, BulbOutlined,
} from '@ant-design/icons'
import { getSummaryMindmap } from '../api'
import type { MindMapData, BOISMetrics, RestructurePlan, CategoryFramework } from '../types'
import KnowledgeNode from '../components/KnowledgeNode'

const { Title, Text, Paragraph } = Typography
const nodeTypes = { knowledgeNode: KnowledgeNode }

/** BOIS 评分对应的颜色和描述 */
function getScoreColor(score: number): string {
  if (score >= 90) return '#22c55e'
  if (score >= 75) return '#3b82f6'
  if (score >= 60) return '#f59e0b'
  return '#ef4444'
}

/** BOIS 评分对应的中文标签 */
function getGradeTag(grade: string) {
  if (grade.startsWith('A')) return <Tag color="green">优秀</Tag>
  if (grade.startsWith('B')) return <Tag color="blue">良好</Tag>
  if (grade.startsWith('C')) return <Tag color="orange">合格</Tag>
  return <Tag color="red">待改进</Tag>
}

/** BOIS 指标仪表盘组件 */
function BOISDashboard({ metrics }: { metrics: BOISMetrics }) {
  const metricsItems = [
    { label: '最大深度', value: `${metrics.max_depth} 层`, icon: <ApartmentOutlined />, tooltip: '知识树的层级深度，推荐 2-4 层' },
    { label: '平均分支', value: metrics.avg_children_per_node.toFixed(1), icon: <BranchesOutlined />, tooltip: '每个节点平均子节点数，推荐 2-7' },
    { label: '层级均衡', value: `${(metrics.hierarchy_balance * 100).toFixed(0)}%`, icon: <DashboardOutlined />, tooltip: '各层节点数分布均匀程度' },
    { label: '覆盖完整', value: `${(metrics.coverage_completeness * 100).toFixed(0)}%`, icon: <CheckCircleOutlined />, tooltip: '是否存在层级跳跃' },
    { label: '同位阶方差', value: metrics.peer_variance.toFixed(0), icon: <BranchesOutlined />, tooltip: '同级节点数方差，越小越均衡' },
    { label: '分支因子', value: metrics.branching_factor.toFixed(2), icon: <ApartmentOutlined />, tooltip: '边数/节点数，反映整体发散度' },
  ]

  return (
    <div style={{ padding: '12px 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <Progress
          type="circle"
          percent={Math.round(metrics.score)}
          size={64}
          strokeColor={getScoreColor(metrics.score)}
          format={(p) => <span style={{ fontSize: 18, fontWeight: 700 }}>{p}</span>}
        />
        <div>
          <Space>
            <Text strong style={{ fontSize: 16 }}>BOIS 结构评分</Text>
            {getGradeTag(metrics.grade)}
          </Space>
          <br />
          <Text type="secondary" style={{ fontSize: 12 }}>
            基于托尼·巴赞 BOIS（基本分类概念）理论评估
          </Text>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        {metricsItems.map((item) => (
          <Tooltip key={item.label} title={item.tooltip}>
            <Card size="small" bodyStyle={{ padding: '8px 12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {item.icon}
                <Text type="secondary" style={{ fontSize: 12 }}>{item.label}</Text>
              </div>
              <Text strong style={{ fontSize: 14 }}>{item.value}</Text>
            </Card>
          </Tooltip>
        ))}
      </div>
    </div>
  )
}

/** 结构重构建议面板 */
function SuggestionsPanel({ metrics, plan }: { metrics: BOISMetrics; plan?: RestructurePlan }) {
  const items = [
    {
      key: 'suggestions',
      label: (
        <span>
          <BulbOutlined style={{ color: '#f59e0b', marginRight: 8 }} />
          BOIS 优化建议 ({metrics.suggestions.length})
        </span>
      ),
      children: (
        <div>
          {metrics.suggestions.map((s, i) => (
            <Paragraph key={i} style={{ marginBottom: 8, padding: '6px 10px', background: '#fff7ed', borderRadius: 6, fontSize: 13 }}>
              {s}
            </Paragraph>
          ))}
        </div>
      ),
    },
    ...(plan ? [{
      key: 'restructure',
      label: (
        <span>
          <WarningOutlined style={{ color: '#3b82f6', marginRight: 8 }} />
          重构建议详情
        </span>
      ),
      children: (
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>{plan.summary}</Text>
          {plan.merge_suggestions.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <Text strong style={{ fontSize: 13 }}>合并建议：</Text>
              {plan.merge_suggestions.map((m, i) => (
                <div key={i} style={{ padding: '4px 8px', margin: '4px 0', background: '#f0f9ff', borderRadius: 4, fontSize: 12 }}>
                  "{m.parent.label}" ← "{m.child.label}" — {m.reason}
                </div>
              ))}
            </div>
          )}
          {plan.split_suggestions.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <Text strong style={{ fontSize: 13 }}>拆分建议（子节点过多）：</Text>
              {plan.split_suggestions.map((s, i) => (
                <div key={i} style={{ padding: '4px 8px', margin: '4px 0', background: '#fef3c7', borderRadius: 4, fontSize: 12 }}>
                  "{s.node.label}" — {s.reason}
                </div>
              ))}
            </div>
          )}
          {plan.reclassify_suggestions.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <Text strong style={{ fontSize: 13 }}>重分类建议：</Text>
              {plan.reclassify_suggestions.slice(0, 5).map((r, i) => (
                <div key={i} style={{ padding: '4px 8px', margin: '4px 0', background: '#fce7f3', borderRadius: 4, fontSize: 12 }}>
                  "{r.node.label}" (当前 L{r.current_level}) — {r.reason}
                </div>
              ))}
            </div>
          )}
        </div>
      ),
    }] : []),
    {
      key: 'distribution',
      label: (
        <span>
          <ApartmentOutlined style={{ color: '#8b5cf6', marginRight: 8 }} />
          层级分布
        </span>
      ),
      children: (
        <div style={{ display: 'flex', gap: 8 }}>
          {Object.entries(metrics.depth_distribution).map(([level, count]) => (
            <Card key={level} size="small" bodyStyle={{ padding: '6px 14px', textAlign: 'center' }}>
              <Text type="secondary" style={{ fontSize: 11 }}>L{level}</Text>
              <br />
              <Text strong style={{ fontSize: 16 }}>{count}</Text>
              <Text style={{ fontSize: 11 }}> 个</Text>
            </Card>
          ))}
        </div>
      ),
    },
  ]

  return <Collapse items={items} size="small" style={{ marginTop: 12 }} />
}

/** 分类框架面板 */
function CategoryFrameworkPanel({ framework }: { framework: CategoryFramework }) {
  const upper = framework['上位阶（大类）'] || []
  const middle = framework['中位阶（中类）'] || []
  const lower = framework['下位阶（小类）'] || []

  return (
    <div style={{ padding: '8px 0' }}>
      <div style={{ marginBottom: 10 }}>
        <Tag color="red" style={{ marginRight: 8 }}>上位阶 (大类)</Tag>
        <Text style={{ fontSize: 12 }}>
          {upper.map(u => `${u.label}(${u.child_count ?? 0}子)`).join(' | ') || '无'}
        </Text>
      </div>
      <div style={{ marginBottom: 10 }}>
        <Tag color="blue" style={{ marginRight: 8 }}>中位阶 (中类)</Tag>
        <Text style={{ fontSize: 12 }}>
          {middle.map(m => m.label).join(' | ') || '无'}
        </Text>
      </div>
      <div>
        <Tag color="green" style={{ marginRight: 8 }}>下位阶 (小类)</Tag>
        <Text style={{ fontSize: 12 }}>
          {lower.map(l => l.label).slice(0, 10).join(' | ') || '无'}
          {lower.length > 10 && ` ...等共${lower.length}个`}
        </Text>
      </div>
    </div>
  )
}

export default function MindMapPage() {
  const { summaryId } = useParams<{ summaryId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<MindMapData | null>(null)
  const [loading, setLoading] = useState(true)
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [showPanel, setShowPanel] = useState(true)

  useEffect(() => {
    if (!summaryId) return
    loadMindmap()
  }, [summaryId])

  const loadMindmap = async () => {
    try {
      setLoading(true)
      const result = await getSummaryMindmap(summaryId!)
      setData(result)

      const flowNodes: Node[] = (result.nodes || []).map((n: any, i: number) => ({
        id: n.id,
        type: 'knowledgeNode',
        position: { x: n.level * 250, y: i * 80 },
        data: { label: n.label, level: n.level, tag: n.tag, summary: n.summary },
      }))
      setNodes(flowNodes)

      const flowEdges: Edge[] = (result.edges || []).map((e: any, i: number) => ({
        id: `${e.source}-${e.target}-${i}`,
        source: e.source,
        target: e.target,
        animated: true,
        style: { stroke: e.relation === 'parent_child' ? '#6366f1' : e.relation === 'cross_reference' ? '#f59e0b' : '#94a3b8' },
      }))
      setEdges(flowEdges)
    } catch (e: any) {
      message.error('加载思维导图失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const onLayout = useCallback(() => {
    const layouted = nodes.map((node) => {
      const level = node.data?.level || 1
      const siblings = nodes.filter(n => n.data?.level === level)
      const idx = siblings.indexOf(node)
      return {
        ...node,
        position: { x: (level - 1) * 280, y: idx * 90 + 50 },
      }
    })
    setNodes(layouted)
  }, [nodes, setNodes])

  if (loading) return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>
  if (!data) return <div style={{ textAlign: 'center', padding: 100 }}><Empty description="无法加载思维导图" /></div>

  const { bois_metrics, restructure_plan, category_framework, llm_restructured } = data

  return (
    <div style={{ height: 'calc(100vh - 120px)', display: 'flex', gap: 0 }}>
      {/* 主画布区 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} type="text">返回</Button>
          <Title level={4} style={{ margin: 0 }}>思维导图</Title>
          <Button icon={<ExpandOutlined />} onClick={onLayout}>自动布局</Button>
          {bois_metrics && (
            <Space size={4}>
              <Tooltip title={`BOIS 评分: ${bois_metrics.score.toFixed(0)}/100`}>
                <Tag color={bois_metrics.score >= 75 ? 'green' : bois_metrics.score >= 60 ? 'orange' : 'red'}>
                  <TrophyOutlined /> BOIS {bois_metrics.score.toFixed(0)}
                </Tag>
              </Tooltip>
              {llm_restructured && <Tag color="purple">AI 优化</Tag>}
            </Space>
          )}
          <Button
            type={showPanel ? 'primary' : 'default'}
            size="small"
            onClick={() => setShowPanel(!showPanel)}
          >
            {showPanel ? '收起面板' : 'BOIS 分析'}
          </Button>
        </div>
        <Card bodyStyle={{ padding: 0 }} style={{ flex: 1 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
          >
            <Controls />
            <MiniMap />
            <Background gap={16} />
          </ReactFlow>
        </Card>
      </div>

      {/* 侧边 BOIS 分析面板 */}
      {showPanel && bois_metrics && (
        <div style={{
          width: 380, borderLeft: '1px solid #e5e7eb',
          padding: '16px', overflowY: 'auto', background: '#fafafa',
        }}>
          <Title level={5} style={{ marginTop: 0 }}>
            <TrophyOutlined style={{ color: '#f59e0b', marginRight: 8 }} />
            BOIS 知识导图分析
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>
            基于托尼·巴赞 Basic Ordering Ideas（基本分类概念）理论
          </Text>

          <Divider style={{ margin: '12px 0' }} />

          <BOISDashboard metrics={bois_metrics} />

          {category_framework && (
            <>
              <Divider style={{ margin: '12px 0' }} />
              <Text strong style={{ fontSize: 13 }}>BOIS 三级分类框架</Text>
              <CategoryFrameworkPanel framework={category_framework} />
            </>
          )}

          <SuggestionsPanel metrics={bois_metrics} plan={restructure_plan} />

          <div style={{ marginTop: 12, padding: '8px 12px', background: '#eff6ff', borderRadius: 6 }}>
            <Text style={{ fontSize: 11, color: '#3b82f6' }}>
              BOIS 三步法：上找大类 → 中找同类 → 下找小类
            </Text>
          </div>
        </div>
      )}
    </div>
  )
}
