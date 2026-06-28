import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, Button, Card, Table, App, Tag, Space, Popconfirm, Modal, Input } from 'antd'
import { UploadOutlined, FilePdfOutlined, FileTextOutlined, FileMarkdownOutlined, DeleteOutlined, FileImageOutlined, BranchesOutlined, LinkOutlined, CodeOutlined, EyeOutlined, DatabaseOutlined, PictureOutlined, ApartmentOutlined, RocketOutlined, CheckSquareOutlined } from '@ant-design/icons'
import { uploadDocument, listDocuments, deleteDocument, indexDocument, getDocumentDetail, analyzeDocumentImages, generateSummary } from '../api'
import { useAppStore } from '../stores'
import FilePreview from '../components/previews/FilePreview'

const { Dragger } = Upload

const typeIcons: Record<string, React.ReactNode> = {
  pdf: <FilePdfOutlined style={{ color: '#f5222d' }} />,
  docx: <FileTextOutlined style={{ color: '#1890ff' }} />,
  pptx: <FileTextOutlined style={{ color: '#fa8c16' }} />,
  md: <FileMarkdownOutlined style={{ color: '#52c41a' }} />,
  txt: <FileTextOutlined />,
  jpeg: <FileImageOutlined style={{ color: '#722ed1' }} />,
  png: <FileImageOutlined style={{ color: '#722ed1' }} />,
  xmind: <BranchesOutlined style={{ color: '#13c2c2' }} />,
  code: <CodeOutlined style={{ color: '#13c2c2' }} />,
  url: <LinkOutlined style={{ color: '#eb2f96' }} />,
}

export default function UploadPage() {
  const navigate = useNavigate()
  const { documents, setDocuments, setSelectedDoc, selectedDoc, loading, setLoading } = useAppStore()
  const { message } = App.useApp()
  const [uploading, setUploading] = useState(false)
  const [urlModalOpen, setUrlModalOpen] = useState(false)
  const [importUrl, setImportUrl] = useState('')
  const [urlImporting, setUrlImporting] = useState(false)
  const [previewVisible, setPreviewVisible] = useState(false)
  const [previewDoc, setPreviewDoc] = useState<{ id: string; type: string; name: string } | null>(null)
  const [indexingId, setIndexingId] = useState<string | null>(null)
  const [analyzingDocId, setAnalyzingDocId] = useState<string | null>(null)
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([])
  const [generatingSummary, setGeneratingSummary] = useState(false)

  useEffect(() => {
    listDocuments().then(setDocuments).catch(console.error)
  }, [])

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      const result = await uploadDocument(file)
      let successMsg = `上传成功: ${result.filename} (${result.total_chunks} 个分片)`
      if (result.native_outline) {
        successMsg += '，已自动提取原生大纲'
      }
      if (result.image_count > 0) {
        successMsg += `，检测到 ${result.image_count} 张图片`
      }
      message.success(successMsg)
      setSelectedDoc(result.document_id)
      // Refresh list
      const docs = await listDocuments()
      setDocuments(docs)
      // Auto-index for vector search
      try {
        setIndexingId(result.document_id)
        await indexDocument(result.document_id)
        message.success('已自动建立向量索引')
      } catch { /* indexing failure is non-fatal */ }
      finally { setIndexingId(null) }
    } catch (e: any) {
      message.error(`上传失败: ${e.response?.data?.detail || e.message}`)
    } finally {
      setUploading(false)
    }
    return false // Prevent default upload
  }

  const handleDelete = async (docId: string) => {
    try {
      await deleteDocument(docId)
      message.success('已删除')
      setDocuments(documents.filter(d => d.id !== docId))
    } catch (e: any) {
      message.error('删除失败')
    }
  }

  const handleUrlImport = async () => {
    if (!importUrl.trim()) { message.warning('请输入URL'); return }
    setUrlImporting(true)
    try {
      const resp = await fetch('/api/v1/documents/import-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: importUrl }),
      })
      if (!resp.ok) throw new Error((await resp.json()).detail || '导入失败')
      const result = await resp.json()
      message.success(`URL导入成功: ${result.total_chunks} 个分片`)
      setSelectedDoc(result.document_id)
      setUrlModalOpen(false)
      setImportUrl('')
      const docs = await listDocuments()
      setDocuments(docs)
    } catch (e: any) {
      message.error(`导入失败: ${e.message}`)
    } finally {
      setUrlImporting(false)
    }
  }

  const handleIndex = async (docId: string) => {
    setIndexingId(docId)
    try {
      const result = await indexDocument(docId)
      message.success(`索引完成: ${result.indexed} 个分片`)
    } catch (e: any) {
      message.error('索引失败')
    } finally {
      setIndexingId(null)
    }
  }

  const handleAnalyzeImages = async (docId: string) => {
    setAnalyzingDocId(docId)
    try {
      const result = await analyzeDocumentImages(docId)
      message.success(result.message || `已分析 ${result.images_analyzed} 张图片`)
    } catch (e: any) {
      message.error(`图片分析失败: ${e.response?.data?.detail || e.message}`)
    } finally {
      setAnalyzingDocId(null)
    }
  }

  const handleElectronSelect = async () => {
    const win = window as any
    if (!win.electronAPI?.selectFile) return
    try {
      const filePath = await win.electronAPI.selectFile()
      if (!filePath) return
      const resp = await fetch(`file://${filePath}`)
      const blob = await resp.blob()
      const fileName = filePath.split(/[/\\]/).pop() || 'unknown'
      const file = new File([blob], fileName)
      handleUpload(file)
    } catch (e: any) {
      message.error(`Electron 文件选择失败: ${e.message}`)
    }
  }

  const handleGenerateSummary = async () => {
    if (selectedDocIds.length === 0) {
      message.warning('请先勾选要汇总的资料')
      return
    }
    setGeneratingSummary(true)
    try {
      const result = await generateSummary({ document_ids: selectedDocIds })
      message.success(`知识总纲生成成功！共 ${result.node_count} 个知识点`)
      navigate(`/summary/${result.summary_id}`)
    } catch (e: any) {
      message.error(`生成失败: ${e.response?.data?.detail || e.message}`)
    } finally {
      setGeneratingSummary(false)
    }
  }

  const toggleSelectDoc = (docId: string) => {
    setSelectedDocIds(prev =>
      prev.includes(docId) ? prev.filter(id => id !== docId) : [...prev, docId]
    )
    // Also update legacy single select for backward compatibility
    setSelectedDoc(docId)
  }

  const isElectron = !!(window as any).electronAPI?.isElectron

  const docColumns = [
    {
      title: '类型',
      dataIndex: 'file_type',
      width: 60,
      render: (type: string) => typeIcons[type] || <FileTextOutlined />,
    },
    {
      title: '文件名',
      dataIndex: 'filename',
      ellipsis: true,
    },
    {
      title: '格式',
      dataIndex: 'file_type',
      width: 90,
      render: (type: string) => <Tag>{type.toUpperCase()}</Tag>,
    },
    {
      title: '页数',
      dataIndex: 'page_count',
      width: 70,
      render: (v: number) => v > 0 ? v : '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (status: string) => <Tag color={status === 'ready' ? 'green' : 'orange'}>{status}</Tag>,
    },
    {
      title: '上传日期',
      dataIndex: 'created_at',
      width: 120,
      render: (date: string) => date?.slice(0, 10),
    },
    {
      title: '操作',
      width: 420,
      render: (_: any, doc: any) => (
        <Space wrap>
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => {
              setPreviewDoc({ id: doc.id, type: doc.file_type, name: doc.filename })
              setPreviewVisible(true)
            }}
          >预览</Button>
          <Button
            size="small"
            type={selectedDocIds.includes(doc.id) ? 'primary' : 'default'}
            icon={selectedDocIds.includes(doc.id) ? <CheckSquareOutlined /> : undefined}
            onClick={() => toggleSelectDoc(doc.id)}
          >
            {selectedDocIds.includes(doc.id) ? '已勾选' : '勾选'}
          </Button>
          <Button
            size="small"
            icon={<DatabaseOutlined />}
            loading={indexingId === doc.id}
            onClick={() => handleIndex(doc.id)}
            title="建立向量索引以启用RAG搜索"
          >索引</Button>
          {['pdf', 'docx', 'pptx', 'html'].includes(doc.file_type) && (
            <Button
              size="small"
              icon={<PictureOutlined />}
              loading={analyzingDocId === doc.id}
              onClick={() => handleAnalyzeImages(doc.id)}
              title="使用视觉模型分析文档中的图片"
            >图片</Button>
          )}
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(doc.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Card title="资料导入" extra={
        <Space>
          {isElectron && <Button icon={<UploadOutlined />} onClick={handleElectronSelect}>选择文件</Button>}
          <Button icon={<LinkOutlined />} onClick={() => setUrlModalOpen(true)}>导入URL</Button>
        </Space>
      } style={{ marginBottom: 16 }}>
        <Dragger
          accept=".pdf,.docx,.pptx,.md,.txt,.png,.jpg,.jpeg,.xmind,.py,.js,.ts,.jsx,.tsx,.java,.cpp,.c,.go,.sql,.yaml,.json,.xml,.css,.html"
          showUploadList={false}
          beforeUpload={handleUpload}
          disabled={uploading}
        >
          <p className="ant-upload-drag-icon"><UploadOutlined style={{ fontSize: 48, color: '#4f46e5' }} /></p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持 PDF / Word / PPT / MD / 图片(OCR) / XMind / 代码 / URL · 最大 100MB · 文档100%本地保存
          </p>
        </Dragger>
      </Card>

      <Card title="已上传资料" extra={
        <Button
          icon={<RocketOutlined />}
          type="primary"
          disabled={selectedDocIds.length === 0}
          loading={generatingSummary}
          onClick={handleGenerateSummary}
        >
          生成知识总纲 ({selectedDocIds.length})
        </Button>
      }>
        <Table
          loading={loading}
          dataSource={documents}
          rowKey="id"
          locale={{ emptyText: '暂无资料，请上传你的第一个文档' }}
          columns={docColumns}
          pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
          onRow={(doc) => ({
            style: { background: selectedDoc === doc.id ? '#f0f5ff' : undefined },
          })}
          size="middle"
        />
      </Card>

      <Modal title="导入网页URL" open={urlModalOpen} onCancel={() => setUrlModalOpen(false)}
        onOk={handleUrlImport} confirmLoading={urlImporting} okText="导入">
        <Input placeholder="https://example.com/article" value={importUrl}
          onChange={e => setImportUrl(e.target.value)} prefix={<LinkOutlined />} />
        <div style={{ color: '#999', fontSize: 12, marginTop: 8 }}>
          输入网页URL，系统将自动抓取并提取正文内容
        </div>
      </Modal>

      <Modal
        title={previewDoc?.name || '文件预览'}
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={null}
        width="90vw"
        style={{ top: 20 }}
        styles={{ body: { padding: 0 } }}
        destroyOnHidden
      >
        {previewDoc && (
          <FilePreview
            documentId={previewDoc.id}
            fileType={previewDoc.type}
            fileName={previewDoc.name}
            maxHeight="75vh"
          />
        )}
      </Modal>
    </div>
  )
}
