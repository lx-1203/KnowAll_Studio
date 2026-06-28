import { useEffect, useState } from 'react'
import { Card, List, Tag, Button, Space, Typography, Badge, App } from 'antd'
import { ThunderboltOutlined, CheckOutlined, ReloadOutlined } from '@ant-design/icons'
import { getReviewQueue, completeReviewItem, scanFeedback } from '../api'
import type { ReviewQueueItem } from '../types'

const { Text } = Typography

export default function ReviewQueuePanel() {
  const [items, setItems] = useState<ReviewQueueItem[]>([])
  const [loading, setLoading] = useState(false)
  const [scanning, setScanning] = useState(false)

  useEffect(() => {
    loadQueue()
  }, [])

  const loadQueue = async () => {
    try {
      setLoading(true)
      const data = await getReviewQueue(20)
      setItems(data.items || [])
    } catch (e) {
      console.error('Failed to load review queue', e)
    } finally {
      setLoading(false)
    }
  }

  const handleScan = async () => {
    try {
      setScanning(true)
      const result = await scanFeedback({ threshold: 0.7 })
      message.success(`扫描完成：发现 ${result.weak_found} 个薄弱点，推送 ${result.pushed_to_queue} 项到复习队列`)
      await loadQueue()
    } catch (e: any) {
      message.error('扫描失败')
    } finally {
      setScanning(false)
    }
  }

  const handleComplete = async (queueId: string) => {
    try {
      await completeReviewItem(queueId)
      setItems(prev => prev.map(item =>
        item.queue_id === queueId ? { ...item, completed: true } : item
      ))
      message.success('已标记完成')
    } catch (e) {
      message.error('操作失败')
    }
  }

  const pendingItems = items.filter(i => !i.completed)

  return (
    <Card
      title={<Space><ThunderboltOutlined />复习队列<Badge count={pendingItems.length} style={{ marginLeft: 8 }} /></Space>}
      extra={
        <Space>
          <Button size="small" icon={<ReloadOutlined />} onClick={loadQueue} loading={loading}>刷新</Button>
          <Button size="small" type="primary" icon={<ThunderboltOutlined />}
            onClick={handleScan} loading={scanning}>扫描薄弱点</Button>
        </Space>
      }
    >
      {pendingItems.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 24, color: '#999' }}>
          复习队列为空 — 所有知识点掌握良好！
        </div>
      ) : (
        <List
          dataSource={pendingItems}
          renderItem={item => (
            <List.Item
              extra={
                <Button size="small" icon={<CheckOutlined />}
                  onClick={() => handleComplete(item.queue_id)}>完成</Button>
              }
            >
              <List.Item.Meta
                title={
                  <Space>
                    <Tag color={item.resource_type === 'question' ? 'blue' : 'purple'}>
                      {item.resource_type === 'question' ? '题目' : '记忆卡'}
                    </Tag>
                    <Text>{item.knowledge_point_id || item.resource_id}</Text>
                  </Space>
                }
                description={
                  <Space>
                    <Tag color={item.priority >= 7 ? 'red' : item.priority >= 4 ? 'orange' : 'default'}>
                      优先级: {item.priority}
                    </Tag>
                    <Tag>{item.reason === 'low_accuracy' ? '正确率低' : item.reason}</Tag>
                    {item.pushed_at && <Text type="secondary">{item.pushed_at}</Text>}
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      )}
    </Card>
  )
}
