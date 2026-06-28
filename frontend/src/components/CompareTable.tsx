import { Table } from 'antd'

interface CompareTableProps {
  back: string  // Markdown table: | 维度 | A | B |\n|------|---|---|
}

/**
 * Parse a markdown table string into Ant Design Table columns and data.
 */
function parseMarkdownTable(md: string): { columns: any[]; data: any[] } | null {
  const lines = md.trim().split('\n').filter(l => l.trim())
  if (lines.length < 2) return null

  const headerLine = lines[0]
  const separatorLine = lines[1]
  const dataLines = lines.slice(2)

  // Check if second line is a separator (|---|...|)
  if (!/^\|?\s*[-:]+\s*\|/.test(separatorLine)) {
    // Not a table, return raw text
    return null
  }

  // Parse headers
  const headers = headerLine
    .split('|')
    .map(h => h.trim())
    .filter(h => h.length > 0)

  if (headers.length < 2) return null

  // Build columns
  const columns = headers.map((header, i) => ({
    title: header,
    dataIndex: `col${i}`,
    key: `col${i}`,
    render: (text: string) => (
      <span style={{ fontSize: 14, whiteSpace: 'pre-wrap' }}>{text}</span>
    ),
    ...(i === 0 ? { width: 100 } : {}),
  }))

  // Parse data rows
  const data = dataLines.map((line, rowIdx) => {
    const cells = line
      .split('|')
      .map(c => c.trim())
      .filter((c, i, arr) => i > 0 || arr.length > headers.length + 1 ? c : true)
      // Remove leading/trailing empty from pipe splitting
      .filter((c, i, arr) => {
        if (i === 0 && c === '') return false
        if (i === arr.length - 1 && c === '') return false
        return true
      })

    const row: Record<string, string> = { key: String(rowIdx) }
    cells.forEach((cell, ci) => {
      row[`col${ci}`] = cell
    })
    return row
  })

  return { columns, data }
}

export default function CompareTable({ back }: CompareTableProps) {
  const table = parseMarkdownTable(back)

  if (!table) {
    // Render as plain text if parsing fails
    return (
      <div style={{ fontSize: 15, lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
        {back}
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <Table
        columns={table.columns}
        dataSource={table.data}
        pagination={false}
        size="middle"
        bordered
        style={{ fontSize: 14 }}
      />
    </div>
  )
}
