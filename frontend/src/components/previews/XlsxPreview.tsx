import { useState, useEffect } from 'react'
import { Spin, Empty, Tabs, Table } from 'antd'
import * as XLSX from 'xlsx'

interface XlsxPreviewProps {
  fileUrl: string
  fileName?: string
  maxHeight?: string
}

export default function XlsxPreview({ fileUrl }: XlsxPreviewProps) {
  const [sheets, setSheets] = useState<{ name: string; data: any[]; columns: any[] }[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeSheet, setActiveSheet] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    fetch(fileUrl)
      .then(r => {
        if (r.status === 204) throw new Error('原始文件暂不可用，可能已被删除')
        if (!r.ok) throw new Error('加载失败')
        return r.arrayBuffer()
      })
      .then(buf => {
        const wb = XLSX.read(buf, { type: 'array' })
        const parsed = wb.SheetNames.map(name => {
          const ws = wb.Sheets[name]
          const json = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' })
          if (!json.length) return { name, data: [], columns: [] }
          const headers = json[0] as string[]
          const rows = json.slice(1).map((row: any, i: number) => {
            const obj: Record<string, any> = { _key: i }
            headers.forEach((h, idx) => { obj[h || `列${idx + 1}`] = row[idx] ?? '' })
            return obj
          })
          const columns = headers.map((h, idx) => ({
            title: h || `列${idx + 1}`,
            dataIndex: h || `列${idx + 1}`,
            key: h || `列${idx + 1}`,
            ellipsis: true,
            width: Math.max(100, Math.min(200, (h?.length || 4) * 16)),
          }))
          return { name, data: rows, columns }
        })
        setSheets(parsed)
        if (parsed.length > 0) setActiveSheet(parsed[0].name)
        setLoading(false)
      })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [fileUrl])

  if (loading) return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
  if (error) return <Empty description={`加载失败: ${error}`} />
  if (!sheets.length) return <Empty description="无数据" />

  const currentSheet = sheets.find(s => s.name === activeSheet) || sheets[0]

  return (
    <Tabs
      activeKey={activeSheet}
      onChange={setActiveSheet}
      size="small"
      items={sheets.map(s => ({
        key: s.name,
        label: s.name,
        children: (
          <Table
            dataSource={s.data}
            columns={s.columns}
            rowKey="_key"
            size="small"
            pagination={s.data.length > 50 ? { pageSize: 50 } : false}
            scroll={{ x: 'max-content', y: '50vh' }}
            bordered
          />
        ),
      }))}
    />
  )
}
