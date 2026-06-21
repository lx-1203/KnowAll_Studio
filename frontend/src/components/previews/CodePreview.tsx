import { useState, useEffect } from 'react'
import { Spin, Empty } from 'antd'
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vs2015 } from 'react-syntax-highlighter/dist/esm/styles/hljs'

const langMap: Record<string, string> = {
  py: 'python', js: 'javascript', ts: 'typescript', jsx: 'javascript', tsx: 'typescript',
  java: 'java', cpp: 'cpp', c: 'c', h: 'c', go: 'go', rs: 'rust',
  sql: 'sql', yaml: 'yaml', yml: 'yaml', json: 'json', xml: 'xml', css: 'css',
  html: 'html', markdown: 'markdown', md: 'markdown',
}

interface CodePreviewProps {
  fileUrl: string
  fileName?: string
  fileType?: string
  maxHeight?: string
}

export default function CodePreview({ fileUrl, fileName, fileType }: CodePreviewProps) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    fetch(fileUrl)
      .then(r => { if (!r.ok) throw new Error('加载失败'); return r.text() })
      .then(text => { setContent(text); setLoading(false) })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [fileUrl])

  if (loading) return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
  if (error) return <Empty description={`加载失败: ${error}`} />

  const ext = fileType || fileName?.split('.').pop() || ''
  const lang = langMap[ext.toLowerCase()] || ext.toLowerCase() || 'plaintext'
  const displayContent = content.length > 200000 ? content.slice(0, 200000) + '\n\n// 内容过长，仅显示前200KB' : content

  return (
    <div style={{ maxHeight: '65vh', overflow: 'auto', borderRadius: 8, border: '1px solid #1e1e1e' }}>
      <div style={{
        background: '#2d2d2d', color: '#ccc', padding: '4px 16px',
        fontSize: 12, fontFamily: 'monospace',
        display: 'flex', justifyContent: 'space-between',
      }}>
        <span>{fileName || `代码文件`}</span>
        <span>{lang}</span>
      </div>
      <SyntaxHighlighter
        language={lang}
        style={vs2015}
        showLineNumbers
        customStyle={{ margin: 0, borderRadius: '0 0 8px 8px', fontSize: 13 }}
        lineNumberStyle={{ color: '#666', fontSize: 11 }}
      >
        {displayContent}
      </SyntaxHighlighter>
    </div>
  )
}
