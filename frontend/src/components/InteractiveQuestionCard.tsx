import { useState, useEffect, useRef } from 'react'
import { Card, Radio, Input, Button, Space, Tag, Typography, Checkbox } from 'antd'
import type { Question } from '../types'

const { TextArea } = Input
const { Text, Title } = Typography

interface Props {
  question: Question
  onSubmit: (answer: string, timeMs: number) => void
  submitting: boolean
  lastResult?: {
    is_correct: boolean
    correct_answer: string
    analysis: string
  } | null
}

export default function InteractiveQuestionCard({ question, onSubmit, submitting, lastResult }: Props) {
  const [answer, setAnswer] = useState('')
  const [checkedOptions, setCheckedOptions] = useState<string[]>([])
  const [startTime, setStartTime] = useState(Date.now())
  const [showResult, setShowResult] = useState(false)
  const inputRef = useRef<any>(null)

  useEffect(() => {
    setAnswer('')
    setCheckedOptions([])
    setShowResult(false)
    setStartTime(Date.now())
    if (inputRef.current) inputRef.current?.focus?.()
  }, [question?.id])

  const handleSubmit = () => {
    const timeMs = Date.now() - startTime
    let finalAnswer = answer

    if (question.question_type === 'multi_choice') {
      finalAnswer = checkedOptions.sort().join(',')
    } else if (question.question_type === 'single_choice' || question.question_type === 'true_false') {
      finalAnswer = answer
    }

    setShowResult(true)
    onSubmit(finalAnswer, timeMs)
  }

  if (!question) return null

  const renderAnswerInput = () => {
    switch (question.question_type) {
      case 'single_choice':
      case 'true_false':
        return (
          <Radio.Group onChange={e => setAnswer(e.target.value)} value={answer}
            style={{ width: '100%' }} disabled={showResult}>
            <Space direction="vertical" style={{ width: '100%' }}>
              {(question.options || []).map((opt: any) => (
                <Radio key={opt.label} value={opt.label}
                  style={{
                    padding: '8px 12px', border: '1px solid #d9d9d9', borderRadius: 6,
                    width: '100%', marginBottom: 4,
                    ...(showResult && opt.label === lastResult?.correct_answer
                      ? { borderColor: '#52c41a', backgroundColor: '#f6ffed' }
                      : {}),
                    ...(showResult && opt.label === answer && !lastResult?.is_correct
                      ? { borderColor: '#ff4d4f', backgroundColor: '#fff2f0' }
                      : {}),
                  }}>
                  {opt.label}. {opt.text}
                </Radio>
              ))}
            </Space>
          </Radio.Group>
        )

      case 'multi_choice':
        return (
          <Checkbox.Group onChange={vals => setCheckedOptions(vals as string[])}
            value={checkedOptions} style={{ width: '100%' }} disabled={showResult}>
            <Space direction="vertical" style={{ width: '100%' }}>
              {(question.options || []).map((opt: any) => (
                <Checkbox key={opt.label} value={opt.label}
                  style={{ padding: '6px 12px', width: '100%' }}>
                  {opt.label}. {opt.text}
                </Checkbox>
              ))}
            </Space>
          </Checkbox.Group>
        )

      case 'fill_blank':
      case 'short_answer':
        return (
          <TextArea ref={inputRef} rows={3} value={answer}
            onChange={e => setAnswer(e.target.value)}
            placeholder="请输入你的答案..."
            disabled={showResult}
            style={{ fontSize: 15 }} />
        )

      default:
        return (
          <TextArea rows={3} value={answer}
            onChange={e => setAnswer(e.target.value)}
            placeholder="请输入答案..."
            disabled={showResult} />
        )
    }
  }

  const canSubmit = question.question_type === 'multi_choice'
    ? checkedOptions.length > 0
    : answer.trim().length > 0

  return (
    <Card>
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Tag color="blue">{question.question_type === 'single_choice' ? '单选题'
            : question.question_type === 'multi_choice' ? '多选题'
            : question.question_type === 'true_false' ? '判断题'
            : question.question_type === 'fill_blank' ? '填空题'
            : '简答题'}</Tag>
          <Tag>{question.difficulty === 'easy' ? '简单' : question.difficulty === 'hard' ? '困难' : '中等'}</Tag>
        </Space>
      </div>

      <div style={{ marginBottom: 20 }}>
        <Text strong style={{ fontSize: 16 }}>{question.question_text}</Text>
      </div>

      {renderAnswerInput()}

      <div style={{ marginTop: 20 }}>
        <Button type="primary" onClick={handleSubmit} loading={submitting}
          disabled={!canSubmit || showResult} size="large">
          提交答案
        </Button>
      </div>

      {showResult && lastResult && (
        <Card size="small" style={{ marginTop: 16, backgroundColor: lastResult.is_correct ? '#f6ffed' : '#fff2f0' }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text strong style={{ color: lastResult.is_correct ? '#52c41a' : '#ff4d4f' }}>
              {lastResult.is_correct ? '✅ 回答正确！' : '❌ 回答错误'}
            </Text>
            {!lastResult.is_correct && (
              <Text>正确答案: {lastResult.correct_answer}</Text>
            )}
            {lastResult.analysis && (
              <Text type="secondary">{lastResult.analysis}</Text>
            )}
          </Space>
        </Card>
      )}
    </Card>
  )
}
