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

  /** 树形布局：子节点紧跟在父节点周围，同级从左到右递进 */
  const computeTreeLayout = useCallback((
    rawNodes: any[], rawEdges: any[]
  ): { nodes: Node[]; edges: Edge[] } => {
    // 构建父子关系
    const childrenMap = new Map<string, string[]>()
    const parentMap = new Map<string, string>()

    for (const e of rawEdges) {
      if (e.relation === 'parent_child') {
        if (!childrenMap.has(e.source)) childrenMap.set(e.source, [])
        childrenMap.get(e.source)!.push(e.target)
        parentMap.set(e.target, e.source)
      }
    }

    // 找到根节点（无父节点的为一级）
    const rootIds = new Set<string>()
    for (const n of rawNodes) {
      if (!parentMap.has(n.id)) rootIds.add(n.id)
    }
    // 如果所有节点都有父节点，回退到 level=1 的节点作为根
    if (rootIds.size === 0) {
      for (const n of rawNodes) {
        if ((n.level || 1) === 1) rootIds.add(n.id)
      }
    }
    if (rootIds.size === 0 && rawNodes.length > 0) {
      rootIds.add(rawNodes[0].id)
    }

    // 递归计算每个子树的高度（叶子节点数量）
    const subtreeLeafCount = new Map<string, number>()
    function calcLeaves(id: string): number {
      if (subtreeLeafCount.has(id)) return subtreeLeafCount.get(id)!
      const children = childrenMap.get(id) || []
      if (children.length === 0) {
        subtreeLeafCount.set(id, 1)
        return 1
      }
      const total = children.reduce((sum, c) => sum + calcLeaves(c), 0)
      subtreeLeafCount.set(id, Math.max(total, 1))
      return Math.max(total, 1)
    }
    for (const n of rawNodes) calcLeaves(n.id)

    // 布局常量
    const H_GAP = 220          // 层级之间水平间距
    const V_GAP = 90           // 兄弟节点之间垂直间距
    const START_Y = 40

    // 为每个节点分配 y 位置：从上到下按子树排列
    const yPos = new Map<string, number>()
    const visited = new Set<string>()

    function layoutY(id: string, startY: number): number {
      if (visited.has(id)) return startY
      visited.add(id)
      const children = childrenMap.get(id) || []
      if (children.length === 0) {
        yPos.set(id, startY)
        return startY + V_GAP
      }
      let currentY = startY
      // 先布局所有子节点
      const childYValues: number[] = []
      for (const childId of children) {
        const nextY = layoutY(childId, currentY)
        childYValues.push((currentY + nextY - V_GAP) / 2) // 子节点中心
        currentY = nextY
      }
      // 父节点居中于子节点
      const parentY = (childYValues[0] + childYValues[childYValues.length - 1]) / 2
      yPos.set(id, parentY)
      return currentY
    }

    // 对根节点按标签排序后布局
    const sortedRoots = [...rootIds].sort((a, b) => {
      const na = rawNodes.find(n => n.id === a)
      const nb = rawNodes.find(n => n.id === b)
      return (na?.label || '').localeCompare(nb?.label || '')
    })

    let globalY = START_Y
    for (const rootId of sortedRoots) {
      globalY = layoutY(rootId, globalY) + 20 // 根之间额外间距
    }

    // 处理未被访问的节点（孤立节点或 cross_reference 边涉及的节点）
    for (const n of rawNodes) {
      if (!visited.has(n.id)) {
        yPos.set(n.id, globalY)
        globalY += V_GAP
      }
    }

    // 计算 x 位置（需要先确定每个节点的深度）
    const depthMap = new Map<string, number>()
    function calcDepth(id: string): number {
      if (depthMap.has(id)) return depthMap.get(id)!
      const parent = parentMap.get(id)
      if (!parent) { depthMap.set(id, 0); return 0 }
      const d = calcDepth(parent) + 1
      depthMap.set(id, d)
      return d
    }
    for (const n of rawNodes) calcDepth(n.id)

    // 构建 ReactFlow 节点
    const flowNodes: Node[] = rawNodes.map((n: any) => ({
      id: n.id,
      type: 'knowledgeNode',
      position: {
        x: (depthMap.get(n.id) || 0) * H_GAP + 30,
        y: yPos.get(n.id) || START_Y,
      },
      data: { label: n.label, level: n.level, tag: n.tag, summary: n.summary },
    }))

    // 构建带类型的边
    const flowEdges: Edge[] = rawEdges.map((e: any, i: number) => {
      const isParentChild = e.relation === 'parent_child'
      const isCross = e.relation === 'cross_reference'
      return {
        id: `${e.source}-${e.target}-${i}`,
        source: e.source,
        target: e.target,
        type: isParentChild ? 'smoothstep' : 'default',
        animated: !isParentChild,
        style: {
          stroke: isParentChild ? '#6366f1' : isCross ? '#f59e0b' : '#94a3b8',
          strokeWidth: isParentChild ? 2 : 1.5,
        },
      }
    })

    return { nodes: flowNodes, edges: flowEdges }
  }, [])

  useEffect(() => {
    if (!summaryId) return
    loadMindmap()
  }, [summaryId])

  const loadMindmap = async () => {
    try {
      setLoading(true)
      const result = await getSummaryMindmap(summaryId!)
      setData(result)

      const { nodes: flowNodes, edges: flowEdges } = computeTreeLayout(
        result.nodes || [],
        result.edges || []
      )
      setNodes(flowNodes)
      setEdges(flowEdges)
    } catch (e: any) {
      message.error('加载思维导图失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const onLayout = useCallback(() => {
    if (!data) return
    const { nodes: flowNodes, edges: flowEdges } = computeTreeLayout(
      data.nodes || [],
      data.edges || []
    )
    setNodes(flowNodes)
    setEdges(flowEdges)
  }, [data, setNodes, setEdges, computeTreeLayout])

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
