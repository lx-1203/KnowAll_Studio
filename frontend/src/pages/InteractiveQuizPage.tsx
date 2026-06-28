import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Button, Spin, App, Progress, Space, Typography, Radio, Input, Tag, Result } from 'antd'
import { ArrowLeftOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { startInteractiveQuiz, submitInteractiveAnswer } from '../api'
import type { Question } from '../types'
import InteractiveQuestionCard from '../components/InteractiveQuestionCard'

const { Title, Text } = Typography

export default function InteractiveQuizPage() {
  const { summaryId } = useParams<{ summaryId: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const [sessionId, setSessionId] = useState('')
  const [questions, setQuestions] = useState<Question[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [results, setResults] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [completed, setCompleted] = useState(false)

  useEffect(() => {
    if (!summaryId) return
    startQuiz()
  }, [summaryId])

  const startQuiz = async () => {
    try {
      setLoading(true)
      const data = await startInteractiveQuiz({ summary_id: summaryId, count: 20 })
      setSessionId(data.session_id)
      setQuestions(data.questions || [])
      if (data.questions?.length === 0) {
        message.warning('暂无可用题目，请先运行 Agent 调度生成题目')
      }
    } catch (e: any) {
      message.error('启动答题失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (answer: string, timeMs: number) => {
    if (!sessionId || !questions[currentIndex]) return

    try {
      setSubmitting(true)
      const result = await submitInteractiveAnswer({
        question_id: questions[currentIndex].id,
        user_answer: answer,
        time_spent_ms: timeMs,
      })

      setResults(prev => ({
        ...prev,
        [questions[currentIndex].id]: {
          ...result,
          question: questions[currentIndex],
          user_answer: answer,
          time_spent_ms: timeMs,
        },
      }))

      // Auto-advance after 1.5s
      setTimeout(() => {
        if (currentIndex + 1 < questions.length) {
          setCurrentIndex(prev => prev + 1)
        } else {
          setCompleted(true)
        }
      }, 1500)
    } catch (e: any) {
      message.error('提交失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSubmitting(false)
    }
  }

  const totalAnswered = Object.keys(results).length
  const totalCorrect = Object.values(results).filter((r: any) => r.is_correct).length
  const accuracy = totalAnswered > 0 ? (totalCorrect / totalAnswered * 100).toFixed(1) : '0'

  if (loading) return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>

  if (completed) {
    return (
      <div style={{ maxWidth: 600, margin: '40px auto' }}>
        <Result
          status={totalCorrect / totalAnswered > 0.6 ? 'success' : 'info'}
          title="答题完成！"
          subTitle={`正确率: ${accuracy}% (${totalCorrect}/${totalAnswered})`}
          extra={[
            <Button key="retry" type="primary" onClick={startQuiz}>重新开始</Button>,
            <Button key="back" onClick={() => navigate(-1)}>返回</Button>,
          ]}
        />
        <Card title="答题详情" style={{ marginTop: 16 }}>
          {Object.entries(results).map(([qid, r]: [string, any]) => (
            <Card key={qid} size="small" style={{ marginBottom: 8 }}
              extra={r.is_correct ? <Tag color="success">正确</Tag> : <Tag color="error">错误</Tag>}>
              <Text strong>{r.question?.question_text}</Text>
              {!r.is_correct && (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary">正确答案: {r.correct_answer}</Text>
                  {r.analysis && <div><Text type="secondary">解析: {r.analysis}</Text></div>}
                </div>
              )}
            </Card>
          ))}
        </Card>
      </div>
    )
  }

  if (questions.length === 0) {
    return (
      <div style={{ maxWidth: 500, margin: '100px auto', textAlign: 'center' }}>
        <Title level={4}>暂无可用题目</Title>
        <Text type="secondary">请先在知识点总结页面运行 "并行生成所有内容" 来生成题库</Text>
        <br /><br />
        <Button type="primary" onClick={() => navigate(-1)}>返回</Button>
      </div>
    )
  }

  const currentQuestion = questions[currentIndex]

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} type="text">返回</Button>
          <Title level={4} style={{ margin: 0 }}>交互式答题</Title>
        </Space>
        <Space>
          <Text>{currentIndex + 1} / {questions.length}</Text>
          <Tag color="blue">{accuracy}% 正确率</Tag>
        </Space>
      </div>

      <Progress percent={Math.round((currentIndex / questions.length) * 100)} style={{ marginBottom: 16 }} />

      <InteractiveQuestionCard
        question={currentQuestion}
        onSubmit={handleSubmit}
        submitting={submitting}
        lastResult={results[currentQuestion?.id]}
      />
    </div>
  )
}
