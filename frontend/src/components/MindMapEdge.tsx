import { BaseEdge, getBezierPath, EdgeProps } from 'reactflow'

/**
 * 自定义贝塞尔曲线连线组件
 * - 颜色与父节点层级一致
 * - 线条粗细随层级递减
 * - 曲线不穿越节点区域
 */
export default function MindMapEdge({
  id,
  sourceX, sourceY,
  targetX, targetY,
  sourcePosition, targetPosition,
  style = {},
  markerEnd,
  data,
}: EdgeProps) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    curvature: 0.3,
  })

  const level = (data as any)?.level || 1
  const strokeColor = (data as any)?.color || '#64748b'
  const strokeW = (data as any)?.strokeWidth || 1.5

  return (
    <BaseEdge
      id={id}
      path={edgePath}
      style={{
        stroke: strokeColor,
        strokeWidth: strokeW,
        strokeLinecap: 'round',
        ...style,
      }}
      markerEnd={markerEnd}
    />
  )
}
