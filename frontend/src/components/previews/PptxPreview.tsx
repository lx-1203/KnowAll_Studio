import { useState, useEffect } from 'react'
import { Spin, Empty, Carousel } from 'antd'
import { LeftOutlined, RightOutlined } from '@ant-design/icons'

const apiBase = '/api/v1'

interface PptxPreviewProps {
  documentId: string
  fileName?: string
  maxHeight?: string
}

export default function PptxPreview({ documentId }: PptxPreviewProps) {
  const [slides, setSlides] = useState<{ index: number; image_url: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    setLoading(true)
    setError('')
    fetch(`${apiBase}/documents/${documentId}/slides`)
      .then(r => {
        if (!r.ok) throw new Error(r.status === 400 ? '仅支持 PPTX 格式' : '加载失败')
        return r.json()
      })
      .then(data => {
        setSlides(data.slides || [])
        setLoading(false)
      })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [documentId])

  if (loading) return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
  if (error) return <Empty description={`加载失败: ${error}`} />
  if (!slides.length) return <Empty description="无幻灯片" />

  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ marginBottom: 8, fontSize: 13, color: '#666' }}>
        {current + 1} / {slides.length}
      </div>
      <div style={{
        maxHeight: '62vh', overflow: 'hidden', display: 'flex',
        justifyContent: 'center', alignItems: 'center',
        background: '#f0f0f0', borderRadius: 8,
      }}>
        <img
          src={slides[current]?.image_url}
          alt={`幻灯片 ${current + 1}`}
          style={{ maxWidth: '100%', maxHeight: '60vh', objectFit: 'contain' }}
        />
      </div>
      <div style={{ marginTop: 12, display: 'flex', justifyContent: 'center', gap: 16 }}>
        <button onClick={() => setCurrent(c => Math.max(0, c - 1))}
          disabled={current === 0}
          style={{ background: 'none', border: '1px solid #d9d9d9', borderRadius: 4,
            padding: '4px 16px', cursor: current === 0 ? 'not-allowed' : 'pointer' }}>
          上一页
        </button>
        <span style={{ lineHeight: '32px', fontSize: 13 }}>
          {current + 1} / {slides.length}
        </span>
        <button onClick={() => setCurrent(c => Math.min(slides.length - 1, c + 1))}
          disabled={current >= slides.length - 1}
          style={{ background: 'none', border: '1px solid #d9d9d9', borderRadius: 4,
            padding: '4px 16px', cursor: current >= slides.length - 1 ? 'not-allowed' : 'pointer' }}>
          下一页
        </button>
      </div>
    </div>
  )
}
