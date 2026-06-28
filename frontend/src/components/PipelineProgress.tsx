import { Progress, Tag, Spin } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, FileTextOutlined } from '@ant-design/icons'

interface PipelineProgressProps {
  stage: string
  progress: number
  message: string
  error?: string | null
}

const stageLabels: Record<string, { label: string; icon: React.ReactNode }> = {
  parse: { label: '解析文档', icon: '📄' },
  knowledge_tree: { label: '生成知识树', icon: '🌳' },
  quiz: { label: '生成题目', icon: '📝' },
  flashcards: { label: '生成闪卡', icon: '🃏' },
  outline: { label: '知识大纲', icon: <FileTextOutlined style={{ color: '#722ed1' }} /> },
  done: { label: '完成', icon: <CheckCircleOutlined style={{ color: '#52c41a' }} /> },
  error: { label: '出错', icon: <CloseCircleOutlined style={{ color: '#ff4d4f' }} /> },
}

export default function PipelineProgress({ stage, progress, message, error }: PipelineProgressProps) {
  const info = stageLabels[stage] || { label: stage, icon: '⏳' }
  const isError = stage === 'error'
  const isDone = stage === 'done'

  return (
    <div style={{
      padding: '24px 32px',
      background: isError ? '#fff2f0' : isDone ? '#f6ffed' : '#f0f5ff',
      borderRadius: 12,
      border: `1px solid ${isError ? '#ffccc7' : isDone ? '#b7eb8f' : '#d6e4ff'}`,
      marginBottom: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <span style={{ fontSize: 20 }}>{info.icon}</span>
        <Tag color={isError ? 'red' : isDone ? 'green' : 'blue'}>{info.label}</Tag>
        {!isDone && !isError && <Spin indicator={<LoadingOutlined />} size="small" />}
      </div>
      <Progress
        percent={progress}
        status={isError ? 'exception' : isDone ? 'success' : 'active'}
        strokeColor={isError ? '#ff4d4f' : '#4f46e5'}
        showInfo={!isDone}
      />
      <div style={{ marginTop: 8, color: isError ? '#ff4d4f' : '#666', fontSize: 13 }}>
        {error || message}
      </div>
    </div>
  )
}
