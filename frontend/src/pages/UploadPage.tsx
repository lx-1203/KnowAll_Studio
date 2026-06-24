import { useState, useEffect } from 'react'
import { Upload, Button, Card, List, App, Tag, Space, Popconfirm, Modal, Input } from 'antd'
import { UploadOutlined, FilePdfOutlined, FileTextOutlined, FileMarkdownOutlined, DeleteOutlined, FileImageOutlined, BranchesOutlined, LinkOutlined, CodeOutlined, EyeOutlined } from '@ant-design/icons'
import { uploadDocument, listDocuments, deleteDocument } from '../api'
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
  const { documents, setDocuments, setSelectedDoc, selectedDoc, loading, setLoading } = useAppStore()
  const { message } = App.useApp()
  const [uploading, setUploading] = useState(false)
  const [urlModalOpen, setUrlModalOpen] = useState(false)
  const [importUrl, setImportUrl] = useState('')
  const [urlImporting, setUrlImporting] = useState(false)
  const [previewVisible, setPreviewVisible] = useState(false)
  const [previewDoc, setPreviewDoc] = useState<{ id: string; type: string; name: string } | null>(null)

  useEffect(() => {
    listDocuments().then(setDocuments).catch(console.error)
  }, [])

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      const result = await uploadDocument(file)
      message.success(`上传成功: ${result.filename} (${result.total_chunks} 个分片)`)
      setSelectedDoc(result.document_id)
      // Refresh list
      const docs = await listDocuments()
      setDocuments(docs)
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

  return (
    <div>
      <Card title="资料导入" extra={
        <Button icon={<LinkOutlined />} onClick={() => setUrlModalOpen(true)}>导入URL</Button>
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

      <Card title="已上传资料">
        <List
          loading={loading}
          dataSource={documents}
          locale={{ emptyText: '暂无资料，请上传你的第一个文档' }}
          renderItem={doc => (
            <List.Item
              key={doc.id}
              style={{ background: selectedDoc === doc.id ? '#f0f5ff' : undefined }}
              actions={[
                <Button
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => {
                    setPreviewDoc({ id: doc.id, type: doc.file_type, name: doc.filename })
                    setPreviewVisible(true)
                  }}
                >预览</Button>,
                <Button
                  size="small"
                  type={selectedDoc === doc.id ? 'primary' : 'default'}
                  onClick={() => setSelectedDoc(selectedDoc === doc.id ? null : doc.id)}
                >
                  {selectedDoc === doc.id ? '已选择' : '选择'}
                </Button>,
                <Popconfirm title="确定删除？" onConfirm={() => handleDelete(doc.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>,
              ]}
            >
              <List.Item.Meta
                avatar={typeIcons[doc.file_type] || <FileTextOutlined />}
                title={doc.filename}
                description={
                  <Space>
                    <Tag>{doc.file_type.toUpperCase()}</Tag>
                    {doc.page_count > 0 && <span>{doc.page_count} 页</span>}
                    <Tag color={doc.status === 'ready' ? 'green' : 'orange'}>{doc.status}</Tag>
                    <span style={{ color: '#999', fontSize: 12 }}>{doc.created_at?.slice(0, 10)}</span>
                  </Space>
                }
              />
            </List.Item>
          )}
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
