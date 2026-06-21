import { Skeleton, Card, Space } from 'antd'

export function PageSkeleton() {
  return (
    <div style={{ padding: 24 }}>
      <Skeleton active paragraph={{ rows: 1 }} />
      <Space direction="vertical" style={{ width: '100%', marginTop: 16 }}>
        {[1, 2, 3].map(i => (
          <Card key={i}><Skeleton active paragraph={{ rows: 3 }} /></Card>
        ))}
      </Space>
    </div>
  )
}

export function CardSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <Card style={{ marginBottom: 16 }}>
      <Skeleton active paragraph={{ rows }} />
    </Card>
  )
}

export function MindMapSkeleton() {
  return (
    <div style={{ textAlign: 'center', padding: 80 }}>
      <Skeleton active paragraph={{ rows: 2 }} />
      <div style={{ marginTop: 24, height: 300, background: '#fafafa', borderRadius: 12 }} />
    </div>
  )
}

export function QuizSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div>
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i} style={{ marginBottom: 12 }}>
          <Skeleton active title={{ width: '60%' }} paragraph={{ rows: 3 }} />
        </Card>
      ))}
    </div>
  )
}

export function ChatSkeleton() {
  return (
    <div style={{ padding: 16 }}>
      {[1, 2, 3].map(i => (
        <div key={i} style={{ marginBottom: 24, display: 'flex', gap: 12, flexDirection: i % 2 ? 'row' : 'row-reverse' }}>
          <Skeleton.Avatar active size={36} />
          <Skeleton active paragraph={{ rows: 2 }} style={{ width: '60%' }} />
        </div>
      ))}
    </div>
  )
}
