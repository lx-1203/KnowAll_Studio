import { memo } from 'react'
import { Handle, Position } from 'reactflow'
import { Tag } from 'antd'
import { BookOutlined, StarOutlined, WarningOutlined, BulbOutlined } from '@ant-design/icons'

const tagConfig: Record<string, { color: string; icon: React.ReactNode }> = {
  '必考': { color: 'red', icon: <StarOutlined /> },
  '重点': { color: 'orange', icon: <BookOutlined /> },
  '了解': { color: 'blue', icon: <BulbOutlined /> },
  '易错': { color: 'volcano', icon: <WarningOutlined /> },
}

function KnowledgeNode({ data }: { data: any }) {
  const tag = data.tag || ''
  const config = tagConfig[tag] || { color: 'default', icon: null }

  return (
    <div style={{
      padding: '12px 16px',
      background: '#fff',
      border: `2px solid ${data.selected ? '#4f46e5' : '#e8e8e8'}`,
      borderRadius: 10,
      minWidth: 140,
      maxWidth: 220,
      boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      transition: 'all 0.2s',
      cursor: 'pointer',
    }}>
      <Handle type="target" position={Position.Top} style={{ background: '#bbb' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        {config.icon}
        <span style={{ fontWeight: 600, fontSize: 14, color: '#1a1a2e' }}>{data.label}</span>
      </div>
      {tag && <Tag color={config.color} style={{ fontSize: 10, marginBottom: 4 }}>{tag}</Tag>}
      {data.summary && (
        <div style={{ fontSize: 11, color: '#888', lineHeight: 1.4, marginTop: 4 }}>
          {data.summary}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: '#4f46e5' }} />
    </div>
  )
}

export default memo(KnowledgeNode)
