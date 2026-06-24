import { useState, useEffect } from 'react'
import { Spin, Empty } from 'antd'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'

interface MarkdownPreviewProps {
  fileUrl: string
  fileName?: string
  maxHeight?: string
}

export default function MarkdownPreview({ fileUrl, fileName }: MarkdownPreviewProps) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    fetch(fileUrl)
      .then(r => {
        if (r.status === 204) throw new Error('原始文件暂不可用，可能已被删除')
        if (!r.ok) throw new Error('加载失败')
        return r.text()
      })
      .then(text => { setContent(text); setLoading(false) })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [fileUrl])

  if (loading) return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
  if (error) return <Empty description={`加载失败: ${error}`} />

  const isMarkdown = fileName?.match(/\.(md|markdown)$/i)
  const displayContent = content.length > 100000 ? content.slice(0, 100000) + '\n\n*(内容过长，仅显示前100KB)*' : content

  return (
    <div style={{
      maxHeight: '65vh', overflow: 'auto', padding: '24px 32px',
      background: '#fff', borderRadius: 8, border: '1px solid #e8e8e8',
      fontFamily: '"Microsoft YaHei", "SimSun", sans-serif',
      fontSize: 15, lineHeight: 1.8, color: '#333',
    }}
      className="markdown-preview">
      {isMarkdown ? (
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeKatex]}>
          {displayContent}
        </ReactMarkdown>
      ) : (
        <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit' }}>
          {displayContent}
        </pre>
      )}
    </div>
  )
}
