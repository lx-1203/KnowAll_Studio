import { memo } from 'react'
import { Handle, Position } from 'reactflow'
import { Tag } from 'antd'
import { BookOutlined, StarOutlined, WarningOutlined, BulbOutlined } from '@ant-design/icons'

const tagConfig: Record<string, { color: string; icon: React.ReactNode; bg: string }> = {
  '必考': { color: '#dc2626', icon: <StarOutlined />, bg: '#fef2f2' },
  '重点': { color: '#ea580c', icon: <BookOutlined />, bg: '#fff7ed' },
  '了解': { color: '#2563eb', icon: <BulbOutlined />, bg: '#eff6ff' },
  '易错': { color: '#c2410c', icon: <WarningOutlined />, bg: '#fff7ed' },
}

const levelBadgeColors: Record<number, string> = {
  1: '#4f46e5',
  2: '#0891b2',
  3: '#059669',
  4: '#7c3aed',
}

function KnowledgeNode({ data }: { data: any }) {
  const tag = data.tag || ''
  const config = tagConfig[tag] || { color: '#6b7280', icon: null, bg: '#f9fafb' }
  const level = data.level || 1
  const levelColor = levelBadgeColors[level] || '#6b7280'

  return (
    <div style={{
      padding: '10px 14px',
      background: '#fff',
      border: `2px solid ${data.selected ? '#4f46e5' : config.color}20`,
      borderLeft: `4px solid ${config.color}`,
      borderRadius: 8,
      minWidth: 150,
      maxWidth: 220,
      boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      transition: 'all 0.2s',
      cursor: 'pointer',
      position: 'relative',
    }}>
      {/* 层级角标 */}
      <span style={{
        position: 'absolute',
        top: -1,
        right: -1,
        background: levelColor,
        color: '#fff',
        fontSize: 10,
        fontWeight: 700,
        padding: '1px 6px',
        borderRadius: '0 8px 0 6px',
      }}>L{level}</span>

      <Handle type="target" position={Position.Left} style={{ background: '#94a3b8', width: 8, height: 8 }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2, paddingRight: 22 }}>
        <span style={{ color: config.color, fontSize: 14 }}>{config.icon}</span>
        <span style={{ fontWeight: 600, fontSize: 13, color: '#1e293b', lineHeight: 1.3 }}>
          {data.label}
        </span>
      </div>

      {tag && (
        <span style={{
          display: 'inline-block',
          fontSize: 10,
          fontWeight: 600,
          color: config.color,
          background: config.bg,
          padding: '1px 7px',
          borderRadius: 4,
          marginBottom: 4,
        }}>{tag}</span>
      )}

      {data.summary && (
        <div style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.4, marginTop: 2 }}>
          {data.summary.length > 60 ? data.summary.slice(0, 60) + '…' : data.summary}
        </div>
      )}

      <Handle type="source" position={Position.Right} style={{ background: '#6366f1', width: 8, height: 8 }} />
    </div>
  )
}

export default memo(KnowledgeNode)
