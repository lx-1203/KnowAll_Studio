import { useState, useEffect, useCallback } from 'react'
import ReactFlow, {
  Node, Edge, Controls, Background, MiniMap, useNodesState, useEdgesState,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Button, Spin, message, Typography } from 'antd'
import { ArrowLeftOutlined, ExpandOutlined, CompressOutlined } from '@ant-design/icons'
import { getSummaryMindmap } from '../api'
import type { MindMapData } from '../types'
import KnowledgeNode from '../components/KnowledgeNode'

const { Title } = Typography

const nodeTypes = { knowledgeNode: KnowledgeNode }

export default function MindMapPage() {
  const { summaryId } = useParams<{ summaryId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<MindMapData | null>(null)
  const [loading, setLoading] = useState(true)
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  useEffect(() => {
    if (!summaryId) return
    loadMindmap()
  }, [summaryId])

  const loadMindmap = async () => {
    try {
      setLoading(true)
      const result = await getSummaryMindmap(summaryId!)
      setData(result)

      // Convert to ReactFlow format
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
        style: { stroke: e.relation === 'parent_child' ? '#6366f1' : '#f59e0b' },
      }))
      setEdges(flowEdges)
    } catch (e: any) {
      message.error('加载思维导图失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const onLayout = useCallback(() => {
    // Simple auto-layout
    const layouted = nodes.map((node, i) => {
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

  return (
    <div style={{ height: 'calc(100vh - 120px)' }}>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} type="text">返回</Button>
        <Title level={4} style={{ margin: 0 }}>思维导图</Title>
        <Button icon={<ExpandOutlined />} onClick={onLayout}>自动布局</Button>
      </div>
      <Card bodyStyle={{ padding: 0 }} style={{ height: 'calc(100% - 60px)' }}>
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
  )
}
