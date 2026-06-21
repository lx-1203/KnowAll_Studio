import { Card, Radio, Checkbox, Input, Tag, Space } from 'antd'
import { CheckCircleOutlined } from '@ant-design/icons'
import { RichText } from './LaTeX'

interface QuestionCardProps {
  question: {
    id: string
    question_type: string
    difficulty: string
    tags?: string[]
    question_text: string
    options?: { label: string; text: string }[]
    answer?: string
    analysis?: string
  }
  index: number
  userAnswer: string
  onAnswerChange: (questionId: string, answer: string) => void
  showResults: boolean
  result?: {
    is_correct: boolean
    correct_answer: string
    user_answer: string
    analysis?: string
  }
}

export default function QuestionCard({
  question, index, userAnswer, onAnswerChange, showResults, result,
}: QuestionCardProps) {
  const q = question
  const diffColors: Record<string, string> = { easy: 'green', medium: 'orange', hard: 'red' }
  const diffLabels: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }

  return (
    <Card
      size="small"
      style={{ marginBottom: 12 }}
      title={
        <Space wrap>
          <Tag color="blue">{index + 1}</Tag>
          <Tag color={diffColors[q.difficulty] || 'default'}>{diffLabels[q.difficulty] || q.difficulty}</Tag>
          {q.tags?.map(t => <Tag key={t}>{t}</Tag>)}
          {result && (
            <Tag color={result.is_correct ? 'green' : 'red'}>
              {result.is_correct ? <CheckCircleOutlined /> : '✗'}
              {' '}{result.is_correct ? '正确' : '错误'}
            </Tag>
          )}
        </Space>
      }
    >
      <div style={{ marginBottom: 12, fontWeight: 500, lineHeight: 1.8 }}>
        <RichText text={q.question_text} />
      </div>

      {renderAnswerInput(q, userAnswer, onAnswerChange, showResults)}

      {showResults && result && <ResultPanel result={result} />}
    </Card>
  )
}

function renderAnswerInput(
  q: QuestionCardProps['question'],
  userAnswer: string,
  onAnswerChange: (qid: string, ans: string) => void,
  disabled: boolean,
) {
  switch (q.question_type) {
    case 'single_choice':
    case 'true_false':
      return (
        <Radio.Group value={userAnswer} onChange={e => onAnswerChange(q.id, e.target.value)} disabled={disabled}>
          <Space direction="vertical">
            {q.options?.map(opt => (
              <Radio key={opt.label} value={opt.label}>{opt.label}. {opt.text}</Radio>
            ))}
          </Space>
        </Radio.Group>
      )

    case 'multi_choice':
      return (
        <Checkbox.Group
          value={userAnswer ? userAnswer.split(',') : []}
          onChange={vals => onAnswerChange(q.id, (vals as string[]).join(','))}
          disabled={disabled}
        >
          <Space direction="vertical">
            {q.options?.map(opt => (
              <Checkbox key={opt.label} value={opt.label}>{opt.label}. {opt.text}</Checkbox>
            ))}
          </Space>
        </Checkbox.Group>
      )

    case 'fill_blank':
    case 'short_answer':
      return (
        <Input.TextArea
          value={userAnswer}
          onChange={e => onAnswerChange(q.id, e.target.value)}
          disabled={disabled}
          rows={q.question_type === 'short_answer' ? 4 : 2}
          placeholder="请输入答案..."
        />
      )

    default:
      return (
        <Input.TextArea
          value={userAnswer}
          onChange={e => onAnswerChange(q.id, e.target.value)}
          disabled={disabled}
          rows={3}
          placeholder="请输入答案..."
        />
      )
  }
}

function ResultPanel({ result }: { result: NonNullable<QuestionCardProps['result']> }) {
  return (
    <div style={{
      marginTop: 12, padding: 12,
      background: result.is_correct ? '#f6ffed' : '#fff2f0',
      borderRadius: 8,
    }}>
      <div style={{ fontWeight: 600 }}>
        正确答案: {result.correct_answer}
      </div>
      {!result.is_correct && (
        <div style={{ color: '#ff4d4f' }}>
          你的答案: {result.user_answer || '(未作答)'}
        </div>
      )}
      {result.analysis && (
        <div style={{ marginTop: 8, color: '#666', fontSize: 13, lineHeight: 1.6 }}>
          解析: <RichText text={result.analysis} />
        </div>
      )}
    </div>
  )
}
