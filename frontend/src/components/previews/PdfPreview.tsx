import { useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { Spin, Button, Space, InputNumber } from 'antd'
import { LeftOutlined, RightOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

// Use bundled worker from react-pdf
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

interface PdfPreviewProps {
  fileUrl: string
  fileName?: string
  maxHeight?: string
}

export default function PdfPreview({ fileUrl, fileName }: PdfPreviewProps) {
  const [numPages, setNumPages] = useState<number>(0)
  const [pageNumber, setPageNumber] = useState(1)
  const [scale, setScale] = useState(1.2)
  const [loading, setLoading] = useState(true)

  const onLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages)
    setLoading(false)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 12 }}>
        <Space>
          <Button icon={<ZoomOutOutlined />} size="small" disabled={scale <= 0.5}
            onClick={() => setScale(s => Math.max(0.5, s - 0.2))} />
          <span style={{ fontSize: 13, color: '#666' }}>{Math.round(scale * 100)}%</span>
          <Button icon={<ZoomInOutlined />} size="small" disabled={scale >= 3}
            onClick={() => setScale(s => Math.min(3, s + 0.2))} />
        </Space>
        <Space>
          <Button icon={<LeftOutlined />} size="small" disabled={pageNumber <= 1}
            onClick={() => setPageNumber(p => Math.max(1, p - 1))} />
          <InputNumber size="small" min={1} max={numPages} value={pageNumber}
            onChange={v => v && setPageNumber(v)} style={{ width: 60 }} />
          <span style={{ fontSize: 13, color: '#666' }}>/ {numPages}</span>
          <Button icon={<RightOutlined />} size="small" disabled={pageNumber >= numPages}
            onClick={() => setPageNumber(p => Math.min(numPages, p + 1))} />
        </Space>
      </div>

      <div style={{ maxHeight: '65vh', overflow: 'auto', background: '#f0f0f0', borderRadius: 8, padding: 16 }}>
        {loading && <Spin style={{ display: 'block', padding: 40 }} />}
        <Document file={fileUrl} onLoadSuccess={onLoadSuccess}
          loading={<Spin style={{ display: 'block', padding: 40 }} />}
          error={<div style={{ padding: 40, color: '#ff4d4f' }}>PDF 加载失败</div>}>
          <Page pageNumber={pageNumber} scale={scale}
            renderTextLayer={true} renderAnnotationLayer={true} />
        </Document>
      </div>
    </div>
  )
}
