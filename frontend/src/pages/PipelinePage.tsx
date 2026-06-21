import { useState } from 'react'
import { Card, Button, Select, message, Space, InputNumber, Steps, Tag } from 'antd'
import { ThunderboltOutlined, RocketOutlined } from '@ant-design/icons'
import PipelineProgress from '../components/PipelineProgress'
import { useAppStore } from '../stores'

const apiBase = '/api/v1'

interface PipelineState {
  stage: string
  progress: number
  message: string
  error: string | null
  result: any | null
}

export default function PipelinePage() {
  const { selectedDoc } = useAppStore()
  const [running, setRunning] = useState(false)
  const [state, setState] = useState<PipelineState | null>(null)
  const [config, setConfig] = useState({
    question_count: 15,
    question_type: 'single_choice',
    difficulty: 'medium',
    card_count: 20,
    card_type: 'qa',
  })

  const handleRun = async () => {
    if (!selectedDoc) { message.warning('请先在"资料导入"页面选择一份文档'); return }
    setRunning(true)
    setState({ stage: 'parse', progress: 0, message: '启动全链路生成...', error: null, result: null })

    try {
      const response = await fetch(`${apiBase}/pipeline/run/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_id: selectedDoc, ...config }),
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('No reader')

      let buffer = ''
      let finalState: PipelineState | null = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              finalState = {
                stage: data.stage,
                progress: data.progress,
                message: data.message,
                error: data.error || null,
                result: data.result || null,
              }
              setState(finalState)
            } catch {}
          }
        }
      }

      if (finalState?.error) {
        message.error(finalState.error)
      } else if (finalState?.result) {
        message.success('全链路生成完成！知识树、题目、闪卡已全部就绪')
      }
    } catch (e: any) {
      message.error(`流水线执行失败: ${e.message}`)
      setState(s => s ? { ...s, stage: 'error', error: e.message } : null)
    } finally {
      setRunning(false)
    }
  }

  const stages = [
    { title: '解析分片', stage: 'parse' },
    { title: '知识树', stage: 'knowledge_tree' },
    { title: '生成题目', stage: 'quiz' },
    { title: '生成闪卡', stage: 'flashcards' },
    { title: '完成', stage: 'done' },
  ]
  const currentStageIdx = stages.findIndex(s => s.stage === state?.stage)

  return (
    <div>
      <Card title={<Space><ThunderboltOutlined /> 一键全链路生成</Space>} extra={
        <Space>
          <Select value={config.question_type} onChange={v => setConfig(c => ({ ...c, question_type: v }))}
            options={[
              { value: 'single_choice', label: '单选题' },
              { value: 'multi_choice', label: '多选题' },
              { value: 'true_false', label: '判断题' },
            ]} style={{ width: 100 }} />
          <InputNumber value={config.question_count} onChange={v => setConfig(c => ({ ...c, question_count: v || 10 }))}
            min={5} max={50} addonAfter="题" style={{ width: 100 }} />
          <Select value={config.card_type} onChange={v => setConfig(c => ({ ...c, card_type: v }))}
            options={[
              { value: 'qa', label: '问答卡' },
              { value: 'cloze', label: '填空卡' },
            ]} style={{ width: 100 }} />
          <InputNumber value={config.card_count} onChange={v => setConfig(c => ({ ...c, card_count: v || 10 }))}
            min={5} max={100} addonAfter="张" style={{ width: 100 }} />
          <Button icon={<RocketOutlined />} type="primary" loading={running} onClick={handleRun} size="large">
            一键生成全部
          </Button>
        </Space>
      }>
        <Steps current={currentStageIdx >= 0 ? currentStageIdx : 0} size="small" style={{ marginBottom: 24 }}
          items={stages.map(s => ({ title: s.title }))}
          status={state?.error ? 'error' : state?.stage === 'done' ? 'finish' : undefined}
        />

        {!state && !running && (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <RocketOutlined style={{ fontSize: 64, marginBottom: 16 }} />
            <p style={{ fontSize: 16, fontWeight: 500 }}>文档 → 知识树 → 题库 → 闪卡，一键串联</p>
            <p style={{ fontSize: 13 }}>
              先在「资料导入」上传文档并选中，然后回到此页面点击「一键生成全部」
            </p>
            <Space style={{ marginTop: 16 }}>
              {['quality', 'speed', 'cost'].map(t => <Tag key={t} color="blue">
                {t === 'quality' ? 'AI质量保证' : t === 'speed' ? '全自动流水线' : '缓存复用节约Token'}
              </Tag>)}
            </Space>
          </div>
        )}

        {state && <PipelineProgress
          stage={state.stage}
          progress={state.progress}
          message={state.message}
          error={state.error}
        />}

        {state?.result && (
          <Card size="small" style={{ background: '#f6ffed', marginTop: 16 }}>
            <Space direction="vertical">
              <Tag color="green">生成结果</Tag>
              <div>知识树 ID: {state.result.tree_id}</div>
              <div>题目数量: {state.result.question_count} 道</div>
              <div>闪卡牌组 ID: {state.result.deck_id}</div>
            </Space>
          </Card>
        )}
      </Card>
    </div>
  )
}
