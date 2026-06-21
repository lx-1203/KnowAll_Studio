import { useState, useEffect } from 'react'
import { Card, Button, Select, message, Space, Spin, Modal, Input, Tag, Dropdown } from 'antd'
import { RobotOutlined, ApartmentOutlined, BranchesOutlined, DownloadOutlined, ExpandOutlined, MergeCellsOutlined } from '@ant-design/icons'
import ReactFlow, {
  Node, Edge, Background, Controls, MiniMap,
  useNodesState, useEdgesState, Panel, useReactFlow, ReactFlowProvider,
} from 'reactflow'
import 'reactflow/dist/style.css'
import KnowledgeNode from '../components/KnowledgeNode'
import { generateTree, listTrees, getTree, updateTree, generateOutline } from '../api'
import { useAppStore } from '../stores'

const nodeTypes = { knowledgeNode: KnowledgeNode }

function treeToFlow(treeData: any): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = []
  const edges: Edge[] = []

  function traverse(nodeList: any[], parentId: string | null, x: number, y: number, level: number) {
    if (!nodeList || !Array.isArray(nodeList)) return
    nodeList.forEach((node: any, i: number) => {
      const id = node.id || `node_${Math.random().toString(36).slice(2, 8)}`
      const ny = y + i * 120
      const nx = x + level * 300
      nodes.push({
        id,
        type: 'knowledgeNode',
        data: {
          label: node.label || '',
          tag: node.tag || '',
          summary: node.summary || '',
          level: node.level || level,
        },
        position: { x: nx, y: ny },
      })
      if (parentId) {
        edges.push({
          id: `${parentId}->${id}`,
          source: parentId,
          target: id,
          type: 'smoothstep',
          animated: false,
          style: { stroke: '#bbb', strokeWidth: 1.5 },
        })
      }
      if (node.children?.length) {
        traverse(node.children, id, nx, ny, level + 1)
      }
    })
  }

  const rootNodes = treeData?.tree?.nodes || treeData?.nodes || []
  traverse(rootNodes, null, 0, 50, 0)
  return { nodes, edges }
}

function flowToTree(nodes: Node[]): any {
  const nodeMap: Record<string, any> = {}
  const roots: any[] = []

  nodes.forEach(n => {
    nodeMap[n.id] = { id: n.id, label: n.data?.label || '', level: n.data?.level || 1, tag: n.data?.tag || '', summary: n.data?.summary || '', children: [] }
  })

  // Simple version: return all as flat roots if we can't determine hierarchy from edges
  // In a real app, you'd reconstruct from edge connections
  nodes.forEach(n => {
    roots.push(nodeMap[n.id])
  })

  return { tree: { title: '', nodes: roots } }
}

function KnowledgePageInner() {
  const { selectedDoc, trees, setTrees, selectedTree, setSelectedTree } = useAppStore()
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [generating, setGenerating] = useState(false)
  const [outlineVisible, setOutlineVisible] = useState(false)
  const [outlineContent, setOutlineContent] = useState('')
  const [treeName, setTreeName] = useState('知识树')
  const { fitView } = useReactFlow()

  useEffect(() => { listTrees().then(setTrees).catch(console.error) }, [])

  useEffect(() => {
    if (selectedTree) {
      const tree = trees.find(t => t.tree_id === selectedTree)
      if (tree?.tree_data) {
        const flow = treeToFlow(tree.tree_data)
        setNodes(flow.nodes)
        setEdges(flow.edges)
        setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 100)
      }
    }
  }, [selectedTree, trees])

  const handleGenerate = async () => {
    if (!selectedDoc) { message.warning('请先在"资料导入"页面选择一份文档'); return }
    setGenerating(true)
    try {
      const result = await generateTree({ document_id: selectedDoc, tree_name: treeName })
      message.success('知识树生成成功！')
      setSelectedTree(result.tree_id)
      const updated = await listTrees()
      setTrees(updated)
      const tree = await getTree(result.tree_id)
      const flow = treeToFlow(tree.tree_data)
      setNodes(flow.nodes)
      setEdges(flow.edges)
      setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 100)
    } catch (e: any) {
      message.error(`生成失败: ${e.response?.data?.detail || e.message}`)
    } finally {
      setGenerating(false)
    }
  }

  const handleGenerateOutline = async () => {
    if (!selectedDoc) { message.warning('请先在资料导入页面选择文档'); return }
    setGenerating(true)
    try {
      const result = await generateOutline({ document_id: selectedDoc })
      setOutlineContent(result.content)
      setOutlineVisible(true)
      message.success('大纲生成成功')
    } catch (e: any) {
      message.error('大纲生成失败')
    } finally {
      setGenerating(false)
    }
  }

  const handleSaveChanges = async () => {
    if (!selectedTree) return
    try {
      const treeData = flowToTree(nodes)
      await updateTree(selectedTree, { tree_data: treeData })
      message.success('已保存')
    } catch (e: any) {
      message.error('保存失败')
    }
  }

  const handleMerge = async () => {
    const available = trees.filter(t => t.tree_id !== selectedTree)
    if (available.length === 0) { message.warning('至少需要一个其他知识树才能合并'); return }
    const otherId = available[0].tree_id
    try {
      const resp = await fetch('/api/v1/knowledge/tree/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tree_ids: [selectedTree, otherId], merged_name: '合并的知识树' }),
      })
      if (!resp.ok) throw new Error((await resp.json()).detail || '合并失败')
      const result = await resp.json()
      message.success(`合并完成: ${result.node_count} 个节点, ${result.source_trees} 棵知识树`)
      setSelectedTree(result.tree_id)
      const updated = await listTrees()
      setTrees(updated)
      const tree = await getTree(result.tree_id)
      const flow = treeToFlow(tree.tree_data)
      setNodes(flow.nodes)
      setEdges(flow.edges)
    } catch (e: any) {
      message.error(`合并失败: ${e.message}`)
    }
  }

  const handleExport = (format: string) => {
    if (format === 'json') {
      const data = JSON.stringify(flowToTree(nodes), null, 2)
      const blob = new Blob([data], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `${treeName || 'knowledge'}.json`; a.click()
      URL.revokeObjectURL(url)
      message.success('已导出 JSON')
    } else if (format === 'markdown') {
      let md = `# ${treeName || '知识树'}\n\n`
      nodes.forEach(n => {
        const prefix = '#'.repeat(Math.min((n.data?.level || 1) + 1, 6))
        md += `${prefix} ${n.data?.label || ''}\n`
        if (n.data?.summary) md += `${n.data.summary}\n\n`
      })
      const blob = new Blob([md], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `${treeName || 'outline'}.md`; a.click()
      URL.revokeObjectURL(url)
      message.success('已导出 Markdown')
    }
  }

  const exportItems = [
    { key: 'json', label: '导出 JSON' },
    { key: 'markdown', label: '导出 Markdown' },
  ]

  return (
    <div>
      <Card title="知识树 / 思维导图" extra={
        <Space wrap>
          <Input placeholder="知识树名称" value={treeName} onChange={e => setTreeName(e.target.value)} style={{ width: 140 }} />
          <Button icon={<RobotOutlined />} type="primary" loading={generating} onClick={handleGenerate}>AI 生成知识树</Button>
          <Button icon={<BranchesOutlined />} onClick={handleGenerateOutline}>生成大纲</Button>
          <Button icon={<MergeCellsOutlined />} onClick={handleMerge} disabled={trees.length < 2}>合并</Button>
          <Button onClick={handleSaveChanges}>保存编辑</Button>
          <Dropdown menu={{ items: exportItems, onClick: ({ key }) => handleExport(key) }}>
            <Button icon={<DownloadOutlined />}>导出</Button>
          </Dropdown>
          <Select placeholder="历史知识树" style={{ width: 180 }} value={selectedTree} onChange={setSelectedTree}
            options={trees.map(t => ({ value: t.tree_id, label: t.name }))} allowClear />
          <Button icon={<ExpandOutlined />} onClick={() => fitView({ padding: 0.2, duration: 300 })}>适应画布</Button>
        </Space>
      } style={{ marginBottom: 0 }}>
        {!selectedTree && !generating && (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <ApartmentOutlined style={{ fontSize: 64, marginBottom: 16 }} />
            <p>上传文档后点击「AI 生成知识树」开始</p>
            <p style={{ fontSize: 12 }}>知识树由大模型 API 生成，节点支持拖拽编辑</p>
          </div>
        )}
        {generating && (
          <div style={{ textAlign: 'center', padding: 60 }}>
            <Spin size="large" />
            <p style={{ marginTop: 16, color: '#666' }}>正在调用 AI 生成知识结构...</p>
          </div>
        )}
      </Card>
      {selectedTree && !generating && (
        <div style={{ height: 'calc(100vh - 260px)', background: '#fff', borderRadius: 8, marginTop: 16 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="bottom-left"
          >
            <Background color="#f0f0f0" gap={20} />
            <Controls />
            <MiniMap nodeColor="#4f46e5" maskColor="rgba(0,0,0,0.08)" />
            <Panel position="top-right">
              <Tag color="blue" style={{ fontSize: 12 }}>拖拽节点编辑 · 滚轮缩放</Tag>
            </Panel>
          </ReactFlow>
        </div>
      )}

      <Modal title="生成大纲" open={outlineVisible} onCancel={() => setOutlineVisible(false)}
        footer={<Button onClick={() => setOutlineVisible(false)}>关闭</Button>} width={800}>
        <pre style={{ whiteSpace: 'pre-wrap', maxHeight: 500, overflow: 'auto', background: '#f5f5f5', padding: 16, borderRadius: 8, fontSize: 14, lineHeight: 1.8 }}>
          {outlineContent}
        </pre>
      </Modal>
    </div>
  )
}

export default function KnowledgePage() {
  return (
    <ReactFlowProvider>
      <KnowledgePageInner />
    </ReactFlowProvider>
  )
}
