import { useState, useEffect } from 'react'
import { Spin, Empty } from 'antd'
import mammoth from 'mammoth'

interface DocxPreviewProps {
  fileUrl: string
  fileName?: string
  maxHeight?: string
}

export default function DocxPreview({ fileUrl }: DocxPreviewProps) {
  const [html, setHtml] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    fetch(fileUrl)
      .then(r => {
        if (r.status === 204) throw new Error('原始文件暂不可用，可能已被删除')
        if (!r.ok) throw new Error('加载失败')
        return r.arrayBuffer()
      })
      .then(buf => mammoth.convertToHtml({ arrayBuffer: buf }))
      .then(result => { setHtml(result.value); setLoading(false) })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [fileUrl])

  if (loading) return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
  if (error) return <Empty description={`加载失败: ${error}`} />

  return (
    <div
      className="docx-preview"
      style={{
        maxHeight: '65vh', overflow: 'auto', padding: '24px 32px',
        background: '#fff', borderRadius: 8, border: '1px solid #e8e8e8',
        fontFamily: '"Microsoft YaHei", "SimSun", sans-serif',
        fontSize: 15, lineHeight: 1.8, color: '#333',
      }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
