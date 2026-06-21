import { Suspense, lazy } from 'react'
import { Spin, Result, Button } from 'antd'
import { FilePdfOutlined, FileTextOutlined, FileExcelOutlined, FileMarkdownOutlined, CodeOutlined, FileImageOutlined } from '@ant-design/icons'

interface PreviewComponentProps {
  documentId: string
  fileUrl: string
  fileName?: string
  fileType?: string
  maxHeight?: string
}

const PdfPreview = lazy(() => import('./PdfPreview')) as React.LazyExoticComponent<React.ComponentType<PreviewComponentProps>>
const DocxPreview = lazy(() => import('./DocxPreview')) as React.LazyExoticComponent<React.ComponentType<PreviewComponentProps>>
const XlsxPreview = lazy(() => import('./XlsxPreview')) as React.LazyExoticComponent<React.ComponentType<PreviewComponentProps>>
const PptxPreview = lazy(() => import('./PptxPreview')) as React.LazyExoticComponent<React.ComponentType<PreviewComponentProps>>
const MarkdownPreview = lazy(() => import('./MarkdownPreview')) as React.LazyExoticComponent<React.ComponentType<PreviewComponentProps>>
const CodePreview = lazy(() => import('./CodePreview')) as React.LazyExoticComponent<React.ComponentType<PreviewComponentProps>>
const ImagePreview = lazy(() => import('./ImagePreview')) as React.LazyExoticComponent<React.ComponentType<PreviewComponentProps>>

const apiBase = '/api/v1'

const previewMap: Record<string, React.LazyExoticComponent<React.ComponentType<PreviewComponentProps>>> = {
  pdf: PdfPreview,
  docx: DocxPreview,
  pptx: PptxPreview,
  ppt: PptxPreview,
  xlsx: XlsxPreview,
  xls: XlsxPreview,
  csv: XlsxPreview,
  md: MarkdownPreview,
  markdown: MarkdownPreview,
  py: CodePreview, js: CodePreview, ts: CodePreview, jsx: CodePreview, tsx: CodePreview,
  java: CodePreview, cpp: CodePreview, c: CodePreview, h: CodePreview,
  go: CodePreview, rs: CodePreview, sql: CodePreview,
  yaml: CodePreview, yml: CodePreview, json: CodePreview, xml: CodePreview, css: CodePreview,
  html: CodePreview,
  html_code: CodePreview,
  png: ImagePreview, jpg: ImagePreview, jpeg: ImagePreview,
  gif: ImagePreview, bmp: ImagePreview, webp: ImagePreview,
  txt: MarkdownPreview,  // plain text rendered as markdown
  text: MarkdownPreview,
}

const fileTypeIcons: Record<string, React.ReactNode> = {
  pdf: <FilePdfOutlined style={{ fontSize: 48, color: '#ff4d4f' }} />,
  docx: <FileTextOutlined style={{ fontSize: 48, color: '#1890ff' }} />,
  pptx: <FileTextOutlined style={{ fontSize: 48, color: '#fa8c16' }} />,
  xlsx: <FileExcelOutlined style={{ fontSize: 48, color: '#52c41a' }} />,
  md: <FileMarkdownOutlined style={{ fontSize: 48, color: '#52c41a' }} />,
  code: <CodeOutlined style={{ fontSize: 48, color: '#13c2c2' }} />,
  image: <FileImageOutlined style={{ fontSize: 48, color: '#722ed1' }} />,
}

interface FilePreviewProps {
  documentId: string
  fileType: string
  fileName?: string
  maxHeight?: string
}

export default function FilePreview({ documentId, fileType, fileName, maxHeight }: FilePreviewProps) {
  const type = fileType?.toLowerCase() || ''
  const fileUrl = `${apiBase}/documents/${documentId}/raw`
  const isImage = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'].includes(type)
  const icon = fileTypeIcons[type] || fileTypeIcons.code

  const PreviewComponent = previewMap[type]

  if (!PreviewComponent) {
    return (
      <Result
        icon={icon}
        title="不支持预览"
        subTitle={`文件类型 .${type} 暂不支持在线预览，请下载后使用本地应用查看`}
      />
    )
  }

  return (
    <Suspense fallback={
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center',
        height: maxHeight || '60vh', flexDirection: 'column', gap: 16 }}>
        <Spin size="large" tip="加载预览组件..." />
      </div>
    }>
      <PreviewComponent
        documentId={documentId}
        fileUrl={isImage ? fileUrl : fileUrl}
        fileName={fileName}
        fileType={type}
        maxHeight={maxHeight}
      />
    </Suspense>
  )
}
