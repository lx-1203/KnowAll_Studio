import { useState } from 'react'
import { Spin } from 'antd'

interface ImagePreviewProps {
  fileUrl: string
  fileName?: string
  maxHeight?: string
}

export default function ImagePreview({ fileUrl, fileName }: ImagePreviewProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: 200, background: '#f0f0f0', borderRadius: 8,
      overflow: 'auto', maxHeight: '70vh',
    }}>
      {loading && !error && <Spin style={{ padding: 40 }} />}
      {error ? (
        <div style={{ padding: 40, color: '#ff4d4f' }}>图片加载失败</div>
      ) : (
        <img
          src={fileUrl}
          alt={fileName || '图片预览'}
          onLoad={() => setLoading(false)}
          onError={() => { setLoading(false); setError(true) }}
          style={{ maxWidth: '100%', maxHeight: '65vh', objectFit: 'contain' }}
        />
      )}
    </div>
  )
}
