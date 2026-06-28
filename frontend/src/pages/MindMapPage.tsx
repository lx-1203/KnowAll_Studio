import { useState, useEffect, useCallback, useMemo } from 'react'
import ReactFlow, {
  Node, Edge, Controls, Background, MiniMap, useNodesState, useEdgesState,
  ReactFlowProvider,
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
import KnowledgeNode, { levelEdgeColors, levelEdgeWidths, defaultEdgeColor, defaultEdgeWidth } from '../components/KnowledgeNode'
import MindMapEdge from '../components/MindMapEdge'

const { Title, Text, Paragraph } = Typography
const nodeTypes = { knowledgeNode: KnowledgeNode }
const edgeTypes = { bezier: MindMapEdge }

// ── 常量 ──
const MAX_CHILDREN_PER_COLUMN = 8      // 每列最多子节点数，超过自动换列
const NODE_MIN_SPACING_RATIO = 1.5     // 同层级节点最小间距 = 节点高度 × 此比例
const MIN_ZOOM = 0.3
const MAX_ZOOM = 3.0
const VIRTUALIZATION_THRESHOLD = 500   // 节点数超过此值时启用虚拟化
const ANIMATION_DURATION_MS = 300      // 展开/折叠动画最大时长

/** BOIS 评分对应的颜色 */
function getScoreColor(score: number): string {
  if (score >= 90) return '#22c55e'
  if (score >= 75) return '#3b82f6'
  if (score >= 60) return '#f59e0b'
  return '#ef4444'
}

function getGradeTag(grade: string) {
  if (grade.startsWith('A')) return <Tag color="green">优秀</Tag>
  if (grade.startsWith('B')) return <Tag color="blue">良好</Tag>
  if (grade.startsWith('C')) return <Tag color="orange">合格</Tag>
  return <Tag color="red">待改进</Tag>
}

// ── BOIS 子组件（保持原有逻辑）──

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
        <Progress type="circle" percent={Math.round(metrics.score)} size={64}
          strokeColor={getScoreColor(metrics.score)}
          format={(p) => <span style={{ fontSize: 18, fontWeight: 700 }}>{p}</span>} />
        <div>
          <Space><Text strong style={{ fontSize: 16 }}>BOIS 结构评分</Text>{getGradeTag(metrics.grade)}</Space>
          <br /><Text type="secondary" style={{ fontSize: 12 }}>基于托尼·巴赞 BOIS（基本分类概念）理论评估</Text>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        {metricsItems.map(item => (
          <Tooltip key={item.label} title={item.tooltip}>
            <Card size="small" bodyStyle={{ padding: '8px 12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {item.icon}<Text type="secondary" style={{ fontSize: 12 }}>{item.label}</Text>
              </div>
              <Text strong style={{ fontSize: 14 }}>{item.value}</Text>
            </Card>
          </Tooltip>
        ))}
      </div>
    </div>
  )
}

function SuggestionsPanel({ metrics, plan }: { metrics: BOISMetrics; plan?: RestructurePlan }) {
  const items = [
    {
      key: 'suggestions', label: <span><BulbOutlined style={{ color: '#f59e0b', marginRight: 8 }} />BOIS 优化建议 ({metrics.suggestions.length})</span>,
      children: <div>{metrics.suggestions.map((s, i) => <Paragraph key={i} style={{ marginBottom: 8, padding: '6px 10px', background: '#fff7ed', borderRadius: 6, fontSize: 13 }}>{s}</Paragraph>)}</div>,
    },
    ...(plan ? [{
      key: 'restructure', label: <span><WarningOutlined style={{ color: '#3b82f6', marginRight: 8 }} />重构建议详情</span>,
      children: (
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>{plan.summary}</Text>
          {plan.merge_suggestions.length > 0 && <div style={{ marginTop: 8 }}><Text strong style={{ fontSize: 13 }}>合并建议：</Text>{plan.merge_suggestions.map((m, i) => <div key={i} style={{ padding: '4px 8px', margin: '4px 0', background: '#f0f9ff', borderRadius: 4, fontSize: 12 }}>"{m.parent.label}" ← "{m.child.label}" — {m.reason}</div>)}</div>}
          {plan.split_suggestions.length > 0 && <div style={{ marginTop: 8 }}><Text strong style={{ fontSize: 13 }}>拆分建议（子节点过多）：</Text>{plan.split_suggestions.map((s, i) => <div key={i} style={{ padding: '4px 8px', margin: '4px 0', background: '#fef3c7', borderRadius: 4, fontSize: 12 }}>"{s.node.label}" — {s.reason}</div>)}</div>}
          {plan.reclassify_suggestions.length > 0 && <div style={{ marginTop: 8 }}><Text strong style={{ fontSize: 13 }}>重分类建议：</Text>{plan.reclassify_suggestions.slice(0, 5).map((r, i) => <div key={i} style={{ padding: '4px 8px', margin: '4px 0', background: '#fce7f3', borderRadius: 4, fontSize: 12 }}>"{r.node.label}" (当前 L{r.current_level}) — {r.reason}</div>)}</div>}
        </div>
      ),
    }] : []),
    {
      key: 'distribution', label: <span><ApartmentOutlined style={{ color: '#8b5cf6', marginRight: 8 }} />层级分布</span>,
      children: <div style={{ display: 'flex', gap: 8 }}>{Object.entries(metrics.depth_distribution).map(([level, count]) => <Card key={level} size="small" bodyStyle={{ padding: '6px 14px', textAlign: 'center' }}><Text type="secondary" style={{ fontSize: 11 }}>L{level}</Text><br /><Text strong style={{ fontSize: 16 }}>{count}</Text><Text style={{ fontSize: 11 }}> 个</Text></Card>)}</div>,
    },
  ]
  return <Collapse items={items} size="small" style={{ marginTop: 12 }} />
}

function CategoryFrameworkPanel({ framework }: { framework: CategoryFramework }) {
  const upper = framework['上位阶（大类）'] || []
  const middle = framework['中位阶（中类）'] || []
  const lower = framework['下位阶（小类）'] || []
  return (
    <div style={{ padding: '8px 0' }}>
      <div style={{ marginBottom: 10 }}><Tag color="red" style={{ marginRight: 8 }}>上位阶 (大类)</Tag><Text style={{ fontSize: 12 }}>{upper.map(u => `${u.label}(${u.child_count ?? 0}子)`).join(' | ') || '无'}</Text></div>
      <div style={{ marginBottom: 10 }}><Tag color="blue" style={{ marginRight: 8 }}>中位阶 (中类)</Tag><Text style={{ fontSize: 12 }}>{middle.map(m => m.label).join(' | ') || '无'}</Text></div>
      <div><Tag color="green" style={{ marginRight: 8 }}>下位阶 (小类)</Tag><Text style={{ fontSize: 12 }}>{lower.map(l => l.label).slice(0, 10).join(' | ') || '无'}{lower.length > 10 && ` ...等共${lower.length}个`}</Text></div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════
// 核心：思维导图页面
// ═══════════════════════════════════════════════════════════════

export default function MindMapPage() {
  const { summaryId } = useParams<{ summaryId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<MindMapData | null>(null)
  const [loading, setLoading] = useState(true)
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [showPanel, setShowPanel] = useState(true)

  // ── 折叠状态 ──
  // 记录所有处于折叠状态的节点 ID。根节点始终不在此集合中。
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set())

  // ── 布局模式：tree（正交树）| force（力导向） ──
  const [layoutMode, setLayoutMode] = useState<'tree' | 'force'>('tree')

  /** 估算节点渲染高度 */
  const estNodeHeight = useCallback((n: any): number => {
    const hasSummary = n.summary && n.summary.length > 0
    const labelLen = (n.label || '').length
    let h = 48
    if (n.tag) h += 20
    if (hasSummary) h += 36
    if (labelLen > 12) h += 16
    return h
  }, [])

  /** 获取节点的所有后代 ID（用于折叠时隐藏） */
  const getAllDescendants = useCallback((nodeId: string, childrenMap: Map<string, string[]>): Set<string> => {
    const result = new Set<string>()
    const stack = [nodeId]
    while (stack.length > 0) {
      const current = stack.pop()!
      const kids = childrenMap.get(current) || []
      for (const kid of kids) {
        if (!result.has(kid)) {
          result.add(kid)
          stack.push(kid)
        }
      }
    }
    return result
  }, [])

  /** 计算可见节点集（排除被折叠节点隐藏的后代） */
  const computeVisibleSet = useCallback((
    allNodeIds: string[],
    childrenMap: Map<string, string[]>,
    parentMap: Map<string, string>,
    collapsed: Set<string>,
  ): Set<string> => {
    const hidden = new Set<string>()
    for (const cid of collapsed) {
      const descendants = getAllDescendants(cid, childrenMap)
      descendants.forEach(d => hidden.add(d))
    }
    const visible = new Set<string>()
    for (const id of allNodeIds) {
      if (!hidden.has(id)) visible.add(id)
    }
    return visible
  }, [getAllDescendants])

  // ── 树形布局（正交树形布局） ──
  const computeTreeLayout = useCallback((
    rawNodes: any[], rawEdges: any[], collapsed: Set<string>
  ): { nodes: Node[]; edges: Edge[] } => {
    if (rawNodes.length === 0) return { nodes: [], edges: [] }

    // 1. 构建父子关系
    const childrenMap = new Map<string, string[]>()
    const parentMap = new Map<string, string>()
    for (const e of rawEdges) {
      if (e.relation === 'parent_child') {
        if (!childrenMap.has(e.source)) childrenMap.set(e.source, [])
        childrenMap.get(e.source)!.push(e.target)
        parentMap.set(e.target, e.source)
      }
    }

    // 2. 计算可见节点
    const allIds = rawNodes.map(n => n.id)
    const visibleSet = computeVisibleSet(allIds, childrenMap, parentMap, collapsed)

    // 3. 找到可见的根节点
    const rootIds: string[] = []
    for (const n of rawNodes) {
      if (!visibleSet.has(n.id)) continue
      if (!parentMap.has(n.id)) rootIds.push(n.id)
    }
    if (rootIds.length === 0) {
      for (const n of rawNodes) {
        if (!visibleSet.has(n.id)) continue
        if ((n.level || 1) === 1) rootIds.push(n.id)
      }
    }
    if (rootIds.length === 0 && rawNodes.length > 0) {
      const firstVisible = rawNodes.find(n => visibleSet.has(n.id))
      if (firstVisible) rootIds.push(firstVisible.id)
    }
    rootIds.sort((a, b) => {
      const na = rawNodes.find(n => n.id === a)
      const nb = rawNodes.find(n => n.id === b)
      return (na?.label || '').localeCompare(nb?.label || '')
    })

    // 4. 布局常量
    const H_GAP = 280
    const SIBLING_GAP = 30
    const ROOT_GAP = 60
    const START_X = 30
    const START_Y = 30
    const COL_GAP = 260   // 多列之间水平间距

    // 节点高度
    const nodeH = new Map<string, number>()
    for (const n of rawNodes) nodeH.set(n.id, estNodeHeight(n))
    const defaultH = 80

    // 5. 后序遍历：计算子树高度（仅可见节点）
    const subtreeH = new Map<string, number>()

    function calcSubtreeH(id: string): number {
      if (!visibleSet.has(id)) return 0
      if (subtreeH.has(id)) return subtreeH.get(id)!
      const children = (childrenMap.get(id) || []).filter(c => visibleSet.has(c))
      if (children.length === 0) {
        const h = Math.max(nodeH.get(id) || defaultH, defaultH)
        subtreeH.set(id, h)
        return h
      }

      const childCount = children.length
      const columns = Math.ceil(childCount / MAX_CHILDREN_PER_COLUMN)
      let maxColH = 0
      for (let col = 0; col < columns; col++) {
        let colH = 0
        for (let i = col * MAX_CHILDREN_PER_COLUMN; i < Math.min((col + 1) * MAX_CHILDREN_PER_COLUMN, childCount); i++) {
          colH += calcSubtreeH(children[i]) + (i > col * MAX_CHILDREN_PER_COLUMN ? SIBLING_GAP : 0)
        }
        maxColH = Math.max(maxColH, colH)
      }
      const myH = nodeH.get(id) || defaultH
      // 父节点高度取自身高度与子节点总高度中的较大值
      const total = Math.max(myH, maxColH)
      subtreeH.set(id, total)
      return total
    }

    for (const n of rawNodes) {
      if (visibleSet.has(n.id)) calcSubtreeH(n.id)
    }

    // 6. 前序遍历：分配坐标
    const xPos = new Map<string, number>()
    const yPos = new Map<string, number>()
    const depthMap = new Map<string, number>()

    function setDepth(id: string, d: number) {
      if (!visibleSet.has(id)) return
      depthMap.set(id, d)
      for (const c of (childrenMap.get(id) || [])) setDepth(c, d + 1)
    }
    for (const rid of rootIds) setDepth(rid, 0)

    function layoutSubtree(id: string, yOffset: number): number {
      if (!visibleSet.has(id)) return yOffset
      const children = (childrenMap.get(id) || []).filter(c => visibleSet.has(c))
      const myH = nodeH.get(id) || defaultH

      if (children.length === 0) {
        yPos.set(id, yOffset)
        return yOffset + myH
      }

      const childCount = children.length
      const columns = Math.ceil(childCount / MAX_CHILDREN_PER_COLUMN)

      // 为每个子节点递归布局
      const colCenters: Array<{ col: number; y: number }> = []
      const colOffsets: number[] = new Array(columns).fill(yOffset)

      for (let i = 0; i < childCount; i++) {
        const col = Math.floor(i / MAX_CHILDREN_PER_COLUMN)
        const idxInCol = i % MAX_CHILDREN_PER_COLUMN
        if (idxInCol === 0) {
          // 每列第一个从头开始
        } else {
          colOffsets[col] += SIBLING_GAP
        }
        const endY = layoutSubtree(children[i], colOffsets[col])
        const childH = subtreeH.get(children[i]) || myH
        colCenters.push({ col, y: colOffsets[col] + childH / 2 })
        colOffsets[col] = endY
      }

      // 父节点居中：取所有列的中心
      const colMidYs: number[] = new Array(columns).fill(0)
      const colCounts: number[] = new Array(columns).fill(0)
      for (const cc of colCenters) { colMidYs[cc.col] += cc.y; colCounts[cc.col]++ }
      for (let c = 0; c < columns; c++) {
        if (colCounts[c] > 0) colMidYs[c] /= colCounts[c]
        else colMidYs[c] = yOffset + myH / 2
      }

      // 父节点垂直位置 = 所有列中心的平均值
      let parentCenter = 0
      let nonEmptyCols = 0
      for (let c = 0; c < columns; c++) {
        if (colCounts[c] > 0) { parentCenter += colMidYs[c]; nonEmptyCols++ }
      }
      if (nonEmptyCols > 0) parentCenter /= nonEmptyCols
      else parentCenter = yOffset + myH / 2

      const parentY = Math.max(yOffset, parentCenter - myH / 2)
      yPos.set(id, parentY)

      const actualParentBottom = parentY + myH
      const maxColEnd = Math.max(...colOffsets)
      return Math.max(actualParentBottom, maxColEnd)
    }

    let globalY = START_Y
    for (const rid of rootIds) {
      globalY = layoutSubtree(rid, globalY) + ROOT_GAP
    }

    // 处理孤立可见节点
    const placed = new Set(yPos.keys())
    for (const n of rawNodes) {
      if (visibleSet.has(n.id) && !placed.has(n.id)) {
        yPos.set(n.id, globalY)
        globalY += (nodeH.get(n.id) || defaultH) + SIBLING_GAP
      }
    }

    // 分配 x 坐标（考虑多列偏移）
    for (const n of rawNodes) {
      if (!visibleSet.has(n.id)) continue
      const depth = depthMap.get(n.id) || 0
      const parentId = parentMap.get(n.id)
      let colOffset = 0
      if (parentId && visibleSet.has(parentId)) {
        const siblings = (childrenMap.get(parentId) || []).filter(c => visibleSet.has(c))
        const idx = siblings.indexOf(n.id)
        if (idx >= 0) {
          const col = Math.floor(idx / MAX_CHILDREN_PER_COLUMN)
          colOffset = col * COL_GAP
        }
      }
      xPos.set(n.id, START_X + depth * H_GAP + colOffset)
    }

    // 7. 强制检查：同深度+同父节点下的节点 y 间距 >= 1.5 × 节点高度
    // 对于每对兄弟节点，确保间距足够
    for (const [parentId, kids] of childrenMap) {
      if (!visibleSet.has(parentId)) continue
      const visibleKids = kids.filter(k => visibleSet.has(k))
      // 按 y 排序
      const sorted = [...visibleKids].sort((a, b) => (yPos.get(a) || 0) - (yPos.get(b) || 0))
      for (let i = 1; i < sorted.length; i++) {
        const prev = sorted[i - 1]
        const curr = sorted[i]
        const prevY = yPos.get(prev) || 0
        const currY = yPos.get(curr) || 0
        const prevH = nodeH.get(prev) || defaultH
        const minSpacing = prevH * NODE_MIN_SPACING_RATIO
        if (currY - prevY < minSpacing) {
          // 向下推移
          const delta = minSpacing - (currY - prevY)
          // 递归下推
          const pushDown = (nid: string, dy: number) => {
            if (!visibleSet.has(nid)) return
            const oldY = yPos.get(nid)
            if (oldY == null) return
            yPos.set(nid, oldY + dy)
            for (const c of (childrenMap.get(nid) || [])) pushDown(c, dy)
          }
          pushDown(curr, delta)
        }
      }
    }

    // 最后：更新全局 Y 偏移以避免因 pushDown 导致节点越界
    // 实际上 pushDown 保留了相对顺序，无需额外处理

    // 8. 构建 ReactFlow 数据
    const flowNodes: Node[] = []
    for (const n of rawNodes) {
      if (!visibleSet.has(n.id)) continue
      const level = n.level || 1
      const nChildren = (childrenMap.get(n.id) || []).filter(c => visibleSet.has(c))
      const isCollapsed = collapsed.has(n.id)

      flowNodes.push({
        id: n.id,
        type: 'knowledgeNode',
        position: {
          x: xPos.get(n.id) || START_X,
          y: yPos.get(n.id) || START_Y,
        },
        data: {
          label: n.label,
          level,
          tag: n.tag,
          summary: n.summary,
          collapsed: isCollapsed && nChildren.length > 0,
          childCount: nChildren.length,
          onToggleCollapse: undefined, // 将在后续绑定
        },
        style: {
          // CSS transition 用于展开/折叠动画，不超过 300ms
          transition: `all ${ANIMATION_DURATION_MS}ms ease`,
        },
      })
    }

    const flowEdges: Edge[] = []
    for (const e of rawEdges) {
      if (!visibleSet.has(e.source) || !visibleSet.has(e.target)) continue
      const isPC = e.relation === 'parent_child'
      const isCross = e.relation === 'cross_reference'
      const sourceNode = rawNodes.find(n => n.id === e.source)
      const level = sourceNode?.level || 1
      const edgeColor = isPC ? (levelEdgeColors[level] || defaultEdgeColor) : '#f59e0b'
      const edgeW = isPC ? (levelEdgeWidths[level] || defaultEdgeWidth) : 1.5

      flowEdges.push({
        id: `${e.source}-${e.target}-pc`,
        source: e.source,
        target: e.target,
        type: isPC ? 'bezier' : 'default',
        animated: !isPC,
        data: { level, color: edgeColor, strokeWidth: edgeW },
        style: !isPC ? {
          stroke: isCross ? '#f59e0b' : '#94a3b8',
          strokeWidth: 1.5,
        } : {},
      })
    }

    return { nodes: flowNodes, edges: flowEdges }
  }, [estNodeHeight, computeVisibleSet])

  // ── 力导向布局 ──
  const computeForceLayout = useCallback((
    rawNodes: any[], rawEdges: any[], collapsed: Set<string>
  ): { nodes: Node[]; edges: Edge[] } => {
    // 先用树形布局做初始位置
    const treeResult = computeTreeLayout(rawNodes, rawEdges, collapsed)
    if (treeResult.nodes.length <= 1) return treeResult

    // 简化的力导向迭代
    const positions = new Map<string, { x: number; y: number; vx: number; vy: number }>()
    for (const n of treeResult.nodes) {
      positions.set(n.id, { x: n.position.x, y: n.position.y, vx: 0, vy: 0 })
    }

    const nodeMap = new Map<string, any>()
    for (const n of rawNodes) nodeMap.set(n.id, n)

    // 构建可见父子边
    const parentChildEdges: Array<[string, string]> = []
    for (const e of rawEdges) {
      if (e.relation === 'parent_child' && positions.has(e.source) && positions.has(e.target)) {
        parentChildEdges.push([e.source, e.target])
      }
    }

    const iterations = 80
    const idealLen = 250
    const repulsionStrength = 8000
    const attractionStrength = 0.01
    const damping = 0.85

    for (let iter = 0; iter < iterations; iter++) {
      // 重置速度
      for (const p of positions.values()) { p.vx = 0; p.vy = 0 }

      // 斥力：所有节点对
      const entries = Array.from(positions.entries())
      for (let i = 0; i < entries.length; i++) {
        for (let j = i + 1; j < entries.length; j++) {
          const [idA, pA] = entries[i]
          const [idB, pB] = entries[j]
          let dx = pB.x - pA.x
          let dy = pB.y - pA.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = repulsionStrength / (dist * dist)
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          pA.vx -= fx; pA.vy -= fy
          pB.vx += fx; pB.vy += fy
        }
      }

      // 引力：父子边
      for (const [src, tgt] of parentChildEdges) {
        const pS = positions.get(src)
        const pT = positions.get(tgt)
        if (!pS || !pT) continue
        let dx = pT.x - pS.x
        let dy = pT.y - pS.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = (dist - idealLen) * attractionStrength
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        pS.vx += fx; pS.vy += fy
        pT.vx -= fx; pT.vy -= fy
      }

      // 应用速度 + 阻尼
      // 根节点固定 x（层次约束）
      const allIds = rawNodes.map(n => n.id)
      const parentMap = new Map<string, string>()
      for (const e of rawEdges) { if (e.relation === 'parent_child') parentMap.set(e.target, e.source) }

      for (const [id, p] of positions) {
        // 根节点水平位置不参与力导向（保持树形层次）
        if (!parentMap.has(id)) {
          p.vx *= 0.3
        }
        p.x += p.vx * damping
        p.y += p.vy * damping
      }
    }

    // 更新节点位置
    const flowNodes = treeResult.nodes.map(n => {
      const p = positions.get(n.id)
      if (p) {
        return { ...n, position: { x: p.x, y: p.y } }
      }
      return n
    })

    return { nodes: flowNodes, edges: treeResult.edges }
  }, [computeTreeLayout])

  // ── 数据加载 ──
  useEffect(() => {
    if (!summaryId) return
    loadMindmap()
  }, [summaryId])

  const loadMindmap = async () => {
    try {
      setLoading(true)
      const result = await getSummaryMindmap(summaryId!)
      setData(result)

      // 初始状态：根节点展开（level 1 不折叠），其他所有节点折叠
      const initialCollapsed = new Set<string>()
      const childrenMap = new Map<string, string[]>()
      const parentMap = new Map<string, string>()
      for (const e of result.edges || []) {
        if (e.relation === 'parent_child') {
          if (!childrenMap.has(e.source)) childrenMap.set(e.source, [])
          childrenMap.get(e.source)!.push(e.target)
          parentMap.set(e.target, e.source)
        }
      }
      // 折叠所有非根节点且有子节点的节点（level > 1）
      for (const n of result.nodes || []) {
        const hasChildren = (childrenMap.get(n.id) || []).length > 0
        if (hasChildren && (n.level || 1) > 1) {
          initialCollapsed.add(n.id)
        }
      }

      setCollapsedIds(initialCollapsed)

      const { nodes: flowNodes, edges: flowEdges } = computeTreeLayout(
        result.nodes || [], result.edges || [], initialCollapsed
      )
      setNodes(flowNodes)
      setEdges(flowEdges)
    } catch (e: any) {
      message.error('加载思维导图失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  // ── 折叠/展开处理 ──
  const handleToggleCollapse = useCallback((nodeId: string) => {
    if (!data) return
    setCollapsedIds(prev => {
      const next = new Set(prev)
      if (next.has(nodeId)) {
        next.delete(nodeId)  // 展开
      } else {
        next.add(nodeId)     // 折叠
      }
      return next
    })
  }, [data])

  // 当 collapsedIds 或 layoutMode 变化时重新布局
  useEffect(() => {
    if (!data) return
    const layoutFn = layoutMode === 'force' ? computeForceLayout : computeTreeLayout
    const { nodes: flowNodes, edges: flowEdges } = layoutFn(
      data.nodes || [], data.edges || [], collapsedIds
    )

    // 绑定 toggle 回调
    const nodesWithToggle = flowNodes.map(n => ({
      ...n,
      data: { ...n.data, onToggleCollapse: () => handleToggleCollapse(n.id) },
    }))

    setNodes(nodesWithToggle)
    setEdges(flowEdges)
  }, [collapsedIds, layoutMode, data, handleToggleCollapse, computeTreeLayout, computeForceLayout, setNodes, setEdges])

  // ── 自动布局按钮 ──
  const onLayout = useCallback(() => {
    if (!data) return
    const layoutFn = layoutMode === 'force' ? computeForceLayout : computeTreeLayout
    const { nodes: flowNodes, edges: flowEdges } = layoutFn(
      data.nodes || [], data.edges || [], collapsedIds
    )
    const nodesWithToggle = flowNodes.map(n => ({
      ...n,
      data: { ...n.data, onToggleCollapse: () => handleToggleCollapse(n.id) },
    }))
    setNodes(nodesWithToggle)
    setEdges(flowEdges)
  }, [data, collapsedIds, layoutMode, computeTreeLayout, computeForceLayout, setNodes, setEdges, handleToggleCollapse])

  // ── 全部展开 / 全部折叠 ──
  const expandAll = useCallback(() => {
    if (!data) return
    setCollapsedIds(new Set())
  }, [data])

  const collapseAll = useCallback(() => {
    if (!data) return
    const childrenMap = new Map<string, string[]>()
    for (const e of data.edges || []) {
      if (e.relation === 'parent_child') {
        if (!childrenMap.has(e.source)) childrenMap.set(e.source, [])
        childrenMap.get(e.source)!.push(e.target)
      }
    }
    const all = new Set<string>()
    for (const n of data.nodes || []) {
      if ((childrenMap.get(n.id) || []).length > 0) all.add(n.id)
    }
    setCollapsedIds(all)
  }, [data])

  // ── 虚拟化判断 ──
  const totalNodeCount = data?.nodes?.length || 0
  const useVirtualization = totalNodeCount > VIRTUALIZATION_THRESHOLD

  if (loading) return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>
  if (!data) return <div style={{ textAlign: 'center', padding: 100 }}><Empty description="无法加载思维导图" /></div>

  const { bois_metrics, restructure_plan, category_framework, llm_restructured } = data

  return (
    <div style={{ height: 'calc(100vh - 120px)', display: 'flex', gap: 0 }}>
      {/* 主画布区 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* 工具栏 */}
        <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} type="text">返回</Button>
          <Title level={4} style={{ margin: 0 }}>思维导图</Title>
          <Button icon={<ExpandOutlined />} onClick={onLayout}>自动布局</Button>

          <Space size={4}>
            <Button size="small" onClick={expandAll}>全部展开</Button>
            <Button size="small" onClick={collapseAll}>全部折叠</Button>
          </Space>

          <Space size={4}>
            <Text style={{ fontSize: 12, color: '#888' }}>布局:</Text>
            <Button
              size="small"
              type={layoutMode === 'tree' ? 'primary' : 'default'}
              onClick={() => setLayoutMode('tree')}
            >树形</Button>
            <Button
              size="small"
              type={layoutMode === 'force' ? 'primary' : 'default'}
              onClick={() => setLayoutMode('force')}
            >力导向</Button>
          </Space>

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

          {totalNodeCount > 0 && (
            <Text style={{ fontSize: 12, color: '#aaa' }}>
              可见 {nodes.length}/{totalNodeCount} 节点
            </Text>
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
            edgeTypes={edgeTypes}
            fitView
            minZoom={MIN_ZOOM}
            maxZoom={MAX_ZOOM}
            onlyRenderVisibleElements={useVirtualization}
            defaultEdgeOptions={{
              type: 'bezier',
            }}
          >
            <Controls />
            <MiniMap />
            <Background gap={16} color="#e2e8f0" />
          </ReactFlow>
        </Card>

        {/* 图例 */}
        <div style={{
          position: 'absolute',
          bottom: 12,
          left: 12,
          background: 'rgba(255,255,255,0.92)',
          borderRadius: 8,
          padding: '8px 14px',
          fontSize: 11,
          border: '1px solid #e5e7eb',
          boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
          display: 'flex',
          gap: 14,
          flexWrap: 'wrap',
        }}>
          {[1, 2, 3, 4].map(lv => (
            <span key={lv} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{
                display: 'inline-block', width: 10, height: 10, borderRadius: 2,
                background: levelEdgeColors[lv] || defaultEdgeColor,
              }} />
              L{lv}
            </span>
          ))}
          <span style={{ color: '#888' }}>|</span>
          <span style={{ color: '#888' }}>点击节点 ▶ 展开 / ▼ 折叠</span>
          <span style={{ color: '#888' }}>|</span>
          <span style={{ color: '#888' }}>滚轮缩放 · 拖拽平移</span>
        </div>
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
