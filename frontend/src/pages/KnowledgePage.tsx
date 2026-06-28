import { useState, useEffect, useCallback } from 'react'
import { Card, Button, Select, App, Space, Spin, Modal, Input, Tag, Dropdown, Table, Switch, List, Divider, Popconfirm, Tabs } from 'antd'
import { RobotOutlined, ApartmentOutlined, BranchesOutlined, DownloadOutlined, ExpandOutlined, MergeCellsOutlined, LinkOutlined, DeleteOutlined, FileTextOutlined, PictureOutlined } from '@ant-design/icons'
import ReactFlow, {
  Node, Edge, Background, Controls, MiniMap,
  useNodesState, useEdgesState, Panel, useReactFlow, ReactFlowProvider,
  Connection, addEdge,
} from 'reactflow'
import 'reactflow/dist/style.css'
import ReactMarkdown from 'react-markdown'
import KnowledgeNode from '../components/KnowledgeNode'
import { generateTree, listTrees, getTree, updateTree, generateOutline, listEdges, createEdge, deleteEdge, getNativeOutline, analyzeDocumentImages } from '../api'
import { useAppStore } from '../stores'

const nodeTypes = { knowledgeNode: KnowledgeNode }

function treeToFlow(treeData: any): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = []
  const edges: Edge[] = []
  const seenEdgeIds = new Set<string>()

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
        const edgeId = `${parentId}->${id}`
        if (!seenEdgeIds.has(edgeId)) {
          seenEdgeIds.add(edgeId)
          edges.push({
            id: edgeId,
            source: parentId,
            target: id,
            type: 'smoothstep',
            animated: false,
            style: { stroke: '#bbb', strokeWidth: 1.5 },
          })
        }
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
  const { message } = App.useApp()
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [generating, setGenerating] = useState(false)
  const [outlineVisible, setOutlineVisible] = useState(false)
  const [outlineContent, setOutlineContent] = useState('')
  const [treeName, setTreeName] = useState('知识树')
  const { fitView } = useReactFlow()
  // Knowledge edge (cross-reference) state
  const [edgeMode, setEdgeMode] = useState(false)
  const [knowledgeEdges, setKnowledgeEdges] = useState<any[]>([])
  const [edgeModalOpen, setEdgeModalOpen] = useState(false)
  const [pendingConnection, setPendingConnection] = useState<Connection | null>(null)
  const [edgeRelationType, setEdgeRelationType] = useState('related_to')
  const [edgeDescription, setEdgeDescription] = useState('')
  // Native outline state
  const [activeTab, setActiveTab] = useState('knowledge')
  const [nativeOutline, setNativeOutline] = useState('')
  const [nativeHeadings, setNativeHeadings] = useState<any[]>([])
  const [imageCount, setImageCount] = useState(0)
  const [analyzingImages, setAnalyzingImages] = useState(false)

  useEffect(() => { listTrees().then(setTrees).catch(console.error) }, [])

  // Fetch native outline when document changes
  useEffect(() => {
    if (selectedDoc) {
      getNativeOutline(selectedDoc).then(data => {
        setNativeOutline(data.outline_markdown || '')
        setNativeHeadings(data.headings || [])
        setImageCount(data.image_count || 0)
      }).catch(() => {
        setNativeOutline('')
        setNativeHeadings([])
        setImageCount(0)
      })
    } else {
      setNativeOutline('')
      setNativeHeadings([])
      setImageCount(0)
    }
  }, [selectedDoc])

  useEffect(() => {
    if (selectedTree) {
      // Clear previous tree while loading new one
      setNodes([])
      setEdges([])
      setKnowledgeEdges([])
      getTree(selectedTree).then(tree => {
        if (tree?.tree_data) {
          const flow = treeToFlow(tree.tree_data)
          setNodes(flow.nodes)
          setEdges(flow.edges)
          setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 100)
        }
        // Load cross-reference edges
        listEdges(selectedTree).then(setKnowledgeEdges).catch(console.error)
      }).catch(console.error)
    } else {
      setNodes([])
      setEdges([])
      setKnowledgeEdges([])
    }
  }, [selectedTree])

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

  const handleAnalyzeImages = async () => {
    if (!selectedDoc) { message.warning('请先选择文档'); return }
    if (imageCount === 0) { message.info('该文档未检测到图片'); return }
    setAnalyzingImages(true)
    try {
      const result = await analyzeDocumentImages(selectedDoc)
      message.success(result.message || `已分析 ${result.images_analyzed} 张图片`)
    } catch (e: any) {
      message.error(`图片分析失败: ${e.response?.data?.detail || e.message}`)
    } finally {
      setAnalyzingImages(false)
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

  const onConnect = useCallback((connection: Connection) => {
    if (!edgeMode || !selectedTree) return
    setPendingConnection(connection)
    setEdgeRelationType('related_to')
    setEdgeDescription('')
    setEdgeModalOpen(true)
  }, [edgeMode, selectedTree])

  const handleConfirmEdge = async () => {
    if (!pendingConnection || !selectedTree) return
    try {
      const result = await createEdge({
        tree_id: selectedTree,
        source_node_id: pendingConnection.source!,
        target_node_id: pendingConnection.target!,
        relation_type: edgeRelationType,
        description: edgeDescription,
      })
      // Add visual edge to ReactFlow
      const relationColors: Record<string, string> = {
        related_to: '#4f46e5',
        prerequisite: '#faad14',
        extends: '#52c41a',
        contradicts: '#ff4d4f',
        example_of: '#1890ff',
      }
      const newEdge: Edge = {
        id: result.edge_id,
        source: pendingConnection.source!,
        target: pendingConnection.target!,
        type: 'smoothstep',
        animated: true,
        style: { stroke: relationColors[edgeRelationType] || '#4f46e5', strokeWidth: 2, strokeDasharray: '6 3' },
        label: edgeRelationType,
        labelStyle: { fontSize: 10, fill: '#666' },
      }
      setEdges(eds => [...eds, newEdge])
      setKnowledgeEdges(prev => [...prev, { id: result.edge_id, source_node_id: pendingConnection.source!, target_node_id: pendingConnection.target!, relation_type: edgeRelationType, description: edgeDescription }])
      setEdgeModalOpen(false)
      message.success('连线已创建')
    } catch (e: any) {
      message.error('创建连线失败')
    }
  }

  const handleDeleteEdge = async (edgeId: string) => {
    try {
      await deleteEdge(edgeId)
      setEdges(eds => eds.filter(e => e.id !== edgeId))
      setKnowledgeEdges(prev => prev.filter(e => e.id !== edgeId))
      message.success('连线已删除')
    } catch { message.error('删除失败') }
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
          {imageCount > 0 && (
            <Button icon={<PictureOutlined />} loading={analyzingImages} onClick={handleAnalyzeImages}>
              分析图片 ({imageCount})
            </Button>
          )}
          <Button icon={<MergeCellsOutlined />} onClick={handleMerge} disabled={trees.length < 2}>合并</Button>
          <Button onClick={handleSaveChanges}>保存编辑</Button>
          <Dropdown menu={{ items: exportItems, onClick: ({ key }) => handleExport(key) }}>
            <Button icon={<DownloadOutlined />}>导出</Button>
          </Dropdown>
          <Select placeholder="历史知识树" style={{ width: 180 }} value={selectedTree} onChange={setSelectedTree}
            options={trees.map(t => ({ value: t.tree_id, label: t.name }))} allowClear />
          <Button icon={<ExpandOutlined />} onClick={() => fitView({ padding: 0.2, duration: 300 })}>适应画布</Button>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#666' }}>
            <Switch size="small" checked={edgeMode} onChange={setEdgeMode} />
            连线模式
          </span>
        </Space>
      } style={{ marginBottom: 0 }}>
        <Tabs activeKey={activeTab} onChange={setActiveTab}
          items={[
            {
              key: 'knowledge',
              label: 'AI 知识树',
              children: !selectedTree && !generating ? (
                <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
                  <ApartmentOutlined style={{ fontSize: 64, marginBottom: 16 }} />
                  <p>上传文档后点击「AI 生成知识树」开始</p>
                  <p style={{ fontSize: 12 }}>知识树由大模型 API 生成，节点支持拖拽编辑</p>
                </div>
              ) : generating ? (
                <div style={{ textAlign: 'center', padding: 60 }}>
                  <Spin size="large" />
                  <p style={{ marginTop: 16, color: '#666' }}>正在调用 AI 生成知识结构...</p>
                </div>
              ) : null,
            },
            {
              key: 'native',
              label: '原生大纲',
              children: nativeOutline ? (
                <div style={{ maxHeight: 'calc(100vh - 320px)', overflow: 'auto', padding: '16px 24px', background: '#fafafa', borderRadius: 8 }}>
                  <ReactMarkdown>{nativeOutline}</ReactMarkdown>
                  {imageCount > 0 && (
                    <Divider />
                  )}
                  {imageCount > 0 && (
                    <div style={{ fontSize: 13, color: '#888' }}>
                      文档包含 {imageCount} 张图片。
                      <Button type="link" size="small" icon={<PictureOutlined />} loading={analyzingImages}
                        onClick={handleAnalyzeImages} style={{ padding: 0, marginLeft: 8 }}>
                        点击分析图片内容
                      </Button>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
                  <FileTextOutlined style={{ fontSize: 64, marginBottom: 16 }} />
                  <p>上传文档后自动提取原生大纲</p>
                  <p style={{ fontSize: 12 }}>支持 PDF/DOCX/PPTX 格式的结构化文档</p>
                </div>
              ),
            },
          ]}
        />
      </Card>
      {activeTab === 'knowledge' && selectedTree && !generating && (
        <div style={{ height: 'calc(100vh - 260px)', background: '#fff', borderRadius: 8, marginTop: 16 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="bottom-left"
          >
            <Background color="#f0f0f0" gap={20} />
            <Controls />
            <MiniMap nodeColor="#4f46e5" maskColor="rgba(0,0,0,0.08)" />
            <Panel position="top-right">
              <Space direction="vertical" size={4}>
                <Tag color="blue" style={{ fontSize: 12 }}>拖拽节点编辑 · 滚轮缩放</Tag>
                {edgeMode && <Tag color="orange" style={{ fontSize: 12 }}>连线模式: 拖拽节点端口创建连线</Tag>}
              </Space>
            </Panel>
            {knowledgeEdges.length > 0 && (
              <Panel position="bottom-left">
                <Card size="small" title="跨引用连线" style={{ maxHeight: 200, overflow: 'auto', width: 260 }}>
                  {knowledgeEdges.map((e: any) => {
                    const relLabels: Record<string, string> = { related_to: '相关', prerequisite: '前置', extends: '扩展', contradicts: '矛盾', example_of: '举例' }
                    return (
                      <div key={e.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 12 }}>
                        <Tag>{relLabels[e.relation_type] || e.relation_type}</Tag>
                        <span style={{ color: '#999' }}>{e.source_node_id?.slice(0, 6)}→{e.target_node_id?.slice(0, 6)}</span>
                        <Button size="small" type="link" danger icon={<DeleteOutlined />} onClick={() => handleDeleteEdge(e.id)} />
                      </div>
                    )
                  })}
                </Card>
              </Panel>
            )}
          </ReactFlow>
        </div>
      )}

      <Card title="知识树列表" style={{ marginTop: 16 }}>
        <Table
          dataSource={trees}
          rowKey="tree_id"
          locale={{ emptyText: '暂无知识树' }}
          columns={[
            { title: '名称', dataIndex: 'name', ellipsis: true },
            { title: '创建时间', dataIndex: 'created_at', width: 140, render: (v: string) => v?.slice(0, 10) },
            {
              title: '操作', width: 100,
              render: (_: any, record: any) => (
                <Button
                  size="small"
                  type={selectedTree === record.tree_id ? 'primary' : 'default'}
                  onClick={() => setSelectedTree(selectedTree === record.tree_id ? null : record.tree_id)}
                >
                  {selectedTree === record.tree_id ? '已选择' : '选择'}
                </Button>
              ),
            },
          ]}
          pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total) => `共 ${total} 棵知识树` }}
          size="middle"
        />
      </Card>

      <Modal title="生成大纲" open={outlineVisible} onCancel={() => setOutlineVisible(false)}
        footer={<Button onClick={() => setOutlineVisible(false)}>关闭</Button>} width={800}>
        <pre style={{ whiteSpace: 'pre-wrap', maxHeight: 500, overflow: 'auto', background: '#f5f5f5', padding: 16, borderRadius: 8, fontSize: 14, lineHeight: 1.8 }}>
          {outlineContent}
        </pre>
      </Modal>

      <Modal title="创建知识连线" open={edgeModalOpen} onOk={handleConfirmEdge} onCancel={() => setEdgeModalOpen(false)} okText="创建">
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <span style={{ fontWeight: 500 }}>源节点: </span>
            <Tag>{pendingConnection?.source?.slice(0, 12)}</Tag>
          </div>
          <div>
            <span style={{ fontWeight: 500 }}>目标节点: </span>
            <Tag>{pendingConnection?.target?.slice(0, 12)}</Tag>
          </div>
          <div>
            <span style={{ fontWeight: 500 }}>关系类型:</span>
            <Select value={edgeRelationType} onChange={setEdgeRelationType} style={{ width: '100%', marginTop: 4 }}
              options={[
                { value: 'related_to', label: '相关' },
                { value: 'prerequisite', label: '前置知识' },
                { value: 'extends', label: '扩展延伸' },
                { value: 'contradicts', label: '矛盾对立' },
                { value: 'example_of', label: '举例说明' },
              ]} />
          </div>
          <Input placeholder="描述 (可选)" value={edgeDescription} onChange={e => setEdgeDescription(e.target.value)} />
        </Space>
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
