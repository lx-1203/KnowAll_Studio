import { memo } from 'react'
import { Handle, Position } from 'reactflow'
import { BookOutlined, StarOutlined, WarningOutlined, BulbOutlined, CaretRightOutlined, CaretDownOutlined } from '@ant-design/icons'

const tagConfig: Record<string, { color: string; icon: React.ReactNode; bg: string }> = {
  '必考': { color: '#dc2626', icon: <StarOutlined />, bg: '#fef2f2' },
  '重点': { color: '#ea580c', icon: <BookOutlined />, bg: '#fff7ed' },
  '了解': { color: '#2563eb', icon: <BulbOutlined />, bg: '#eff6ff' },
  '易错': { color: '#c2410c', icon: <WarningOutlined />, bg: '#fff7ed' },
}

/** 层级视觉配置：一级最大最深，逐级变小变浅 */
const levelVisual: Record<number, {
  fontSize: number
  bgColor: string
  borderColor: string
  textColor: string
  badgeBg: string
  nodeMinWidth: number
  nodeMaxWidth: number
  padding: string
  handleSize: number
}> = {
  1: { fontSize: 15, bgColor: '#1e3a5f', borderColor: '#0f2942', textColor: '#ffffff', badgeBg: '#0f2942', nodeMinWidth: 180, nodeMaxWidth: 260, padding: '14px 18px', handleSize: 10 },
  2: { fontSize: 14, bgColor: '#2563eb', borderColor: '#1d4ed8', textColor: '#ffffff', badgeBg: '#1d4ed8', nodeMinWidth: 160, nodeMaxWidth: 230, padding: '11px 15px', handleSize: 8 },
  3: { fontSize: 13, bgColor: '#0891b2', borderColor: '#0e7490', textColor: '#ffffff', badgeBg: '#0e7490', nodeMinWidth: 140, nodeMaxWidth: 210, padding: '9px 13px', handleSize: 7 },
  4: { fontSize: 12, bgColor: '#6d28d9', borderColor: '#5b21b6', textColor: '#ffffff', badgeBg: '#5b21b6', nodeMinWidth: 130, nodeMaxWidth: 200, padding: '8px 12px', handleSize: 6 },
}
const defaultLevelVisual = { fontSize: 11, bgColor: '#64748b', borderColor: '#475569', textColor: '#ffffff', badgeBg: '#475569', nodeMinWidth: 120, nodeMaxWidth: 190, padding: '7px 11px', handleSize: 5 }

/** 连线颜色映射（按层级），供 MindMapPage 引用 */
export const levelEdgeColors: Record<number, string> = {
  1: '#1e3a5f',
  2: '#2563eb',
  3: '#0891b2',
  4: '#6d28d9',
}
export const defaultEdgeColor = '#64748b'

/** 连线粗细映射（按层级递减） */
export const levelEdgeWidths: Record<number, number> = {
  1: 3.0,
  2: 2.2,
  3: 1.6,
  4: 1.2,
}
export const defaultEdgeWidth = 1.0

function KnowledgeNode({ data }: { data: any }) {
  const tag = data.tag || ''
  const config = tagConfig[tag] || { color: '#6b7280', icon: null, bg: '#f9fafb' }
  const level = data.level || 1
  const lv = levelVisual[level] || defaultLevelVisual
  const collapsed = data.collapsed === true
  const hasChildren = (data.childCount || 0) > 0
  const onToggleCollapse = data.onToggleCollapse as (() => void) | undefined

  return (
    <div
      style={{
        padding: lv.padding,
        background: lv.bgColor,
        border: `2px solid ${data.selected ? '#fbbf24' : lv.borderColor}`,
        borderRadius: 10,
        minWidth: lv.nodeMinWidth,
        maxWidth: lv.nodeMaxWidth,
        boxShadow: `0 3px 12px rgba(0,0,0,${level === 1 ? '0.18' : '0.10'})`,
        transition: 'all 0.3s ease',
        cursor: hasChildren ? 'pointer' : 'default',
        position: 'relative',
        color: lv.textColor,
      }}
      onClick={(e) => {
        e.stopPropagation()
        if (hasChildren && onToggleCollapse) onToggleCollapse()
      }}
    >
      {/* 折叠/展开指示器 */}
      {hasChildren && (
        <span style={{
          position: 'absolute',
          top: 6,
          right: 6,
          color: lv.textColor,
          fontSize: 10,
          opacity: 0.8,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
        }}>
          {collapsed ? <CaretRightOutlined /> : <CaretDownOutlined />}
          {collapsed && <span style={{ fontSize: 9 }}>{data.childCount}</span>}
        </span>
      )}

      <Handle type="target" position={Position.Left} style={{ background: lv.textColor, width: lv.handleSize, height: lv.handleSize, border: '2px solid ' + lv.borderColor }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2, paddingRight: hasChildren ? 22 : 0 }}>
        <span style={{ color: 'rgba(255,255,255,0.85)', fontSize: lv.fontSize - 1 }}>{config.icon}</span>
        <span style={{ fontWeight: 700, fontSize: lv.fontSize, lineHeight: 1.3 }}>
          {data.label}
        </span>
      </div>

      {tag && (
        <span style={{
          display: 'inline-block',
          fontSize: lv.fontSize - 4,
          fontWeight: 600,
          color: config.color,
          background: config.bg,
          padding: '1px 7px',
          borderRadius: 4,
          marginBottom: 4,
        }}>{tag}</span>
      )}

      {data.summary && (
        <div style={{ fontSize: lv.fontSize - 3, color: 'rgba(255,255,255,0.7)', lineHeight: 1.4, marginTop: 2 }}>
          {data.summary.length > 60 ? data.summary.slice(0, 60) + '…' : data.summary}
        </div>
      )}

      {/* 折叠状态时显示子节点数量标记 */}
      {collapsed && hasChildren && (
        <div style={{
          marginTop: 6,
          padding: '2px 8px',
          background: 'rgba(255,255,255,0.12)',
          borderRadius: 4,
          fontSize: lv.fontSize - 4,
          textAlign: 'center',
          color: 'rgba(255,255,255,0.8)',
        }}>
          {data.childCount} 个子节点
        </div>
      )}

      <Handle type="source" position={Position.Right} style={{ background: lv.textColor, width: lv.handleSize, height: lv.handleSize, border: '2px solid ' + lv.borderColor }} />
    </div>
  )
}

export default memo(KnowledgeNode)
