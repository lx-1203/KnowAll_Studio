import { useState, useRef, useEffect, useCallback } from 'react'
import { Card, Radio, Checkbox, Input, Tag, Space, Tooltip, Progress, Button } from 'antd'
import type { InputRef } from 'antd'
import { CheckCircleOutlined } from '@ant-design/icons'
import { RichText } from './LaTeX'
import VoiceInput from './VoiceInput'
import { COGNITIVE_LEVEL_LABELS, COGNITIVE_LEVEL_COLORS, type CognitiveLevel } from '../types'

interface QuestionCardProps {
  question: {
    id: string
    question_type: string
    difficulty: string
    difficulty_score?: number
    cognitive_level?: string
    tags?: string[]
    question_text: string
    options?: { label: string; text: string }[]
    answer?: string | string[]
    analysis?: string
    blanks?: { index: number; answer: string; hint?: string }[]
    scoring_points?: { point: string; keywords: string[]; score: number }[]
    term?: string
    review_total?: number
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
    grading_method?: 'semantic' | 'local'
    semantic_scores?: { correctness: number; completeness: number; clarity: number }
    semantic_total?: number
    feedback?: { strengths: string[]; weaknesses: string[]; suggestion: string }
    key_points_matched?: string[]
    key_points_missed?: string[]
    partial_score?: number
    blank_details?: { blank_index: number; expected: string; user_answer: string; is_correct: boolean; hint?: string }[]
    point_details?: { point: string; max_score: number; earned: number; keywords_matched: string[]; keywords_expected: string[] }[]
    earned_score?: number
    score_total?: number
  }
  marked?: boolean
  onToggleMark?: (questionId: string) => void
}

function diffLabel(v: number): string {
  if (v <= 0.25) return '很简单'; if (v <= 0.45) return '偏简单'
  if (v <= 0.60) return '中等'; if (v <= 0.80) return '偏困难'; return '困难'
}

export default function QuestionCard({
  question, index, userAnswer, onAnswerChange, showResults, result, marked, onToggleMark,
}: QuestionCardProps) {
  const q = question
  const diffColors: Record<string, string> = { easy: 'green', medium: 'orange', hard: 'red' }
  const diffLabels: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }

  return (
    <Card
      size="small"
      style={{ marginBottom: 12, borderLeft: marked ? '3px solid #faad14' : undefined }}
      title={
        <Space wrap>
          <Tag color="blue">{index + 1}</Tag>
          {q.cognitive_level && (
            <Tag color={COGNITIVE_LEVEL_COLORS[q.cognitive_level as CognitiveLevel] || 'default'}>
              {COGNITIVE_LEVEL_LABELS[q.cognitive_level as CognitiveLevel] || q.cognitive_level}
            </Tag>
          )}
          {q.difficulty_score != null ? (
            <Tooltip title={`难度: ${q.difficulty_score.toFixed(2)}`}>
              <Progress percent={Math.round(q.difficulty_score * 100)} size="small" style={{ width: 70, minWidth: 70 }}
                strokeColor={q.difficulty_score <= 0.35 ? '#52c41a' : q.difficulty_score <= 0.65 ? '#faad14' : '#ff4d4f'}
                format={() => diffLabel(q.difficulty_score!)} />
            </Tooltip>
          ) : (
            <Tag color={diffColors[q.difficulty] || 'default'}>{diffLabels[q.difficulty] || q.difficulty}</Tag>
          )}
          {q.review_total != null && (
            <Tooltip title={`AI审核: ${q.review_total.toFixed(1)}/4.0`}>
              <Tag color={q.review_total >= 3.2 ? 'green' : q.review_total >= 2.4 ? 'orange' : 'red'}>
                质量{q.review_total.toFixed(1)}
              </Tag>
            </Tooltip>
          )}
          {q.tags?.map(t => <Tag key={t}>{t}</Tag>)}
          {result && (
            <Tag color={result.is_correct ? 'green' : 'red'}>
              {result.is_correct ? <CheckCircleOutlined /> : '✗'} {result.is_correct ? '正确' : '错误'}
            </Tag>
          )}
          {onToggleMark && (
            <Button size="small" type={marked ? 'primary' : 'text'} danger={marked}
              onClick={(e) => { e.stopPropagation(); onToggleMark(q.id) }}>
              {marked ? '★ 已标记' : '☆ 标记'}
            </Button>
          )}
        </Space>
      }
    >
      {/* Question text */}
      <div style={{ marginBottom: 12, fontWeight: 500, lineHeight: 1.8 }}>
        <RichText text={q.question_text} />
      </div>

      {/* Answer input area */}
      {renderAnswerInput(q, userAnswer, onAnswerChange, showResults)}

      {/* Word count for text-based answers */}
      {(q.question_type === 'short_answer' || q.question_type === 'term_definition') && (
        <div style={{ textAlign: 'right', color: '#999', fontSize: 12, marginTop: 4 }}>
          字数: {userAnswer.length}
        </div>
      )}

      {/* Results */}
      {showResults && result && <ResultPanel result={result} questionType={q.question_type} />}
    </Card>
  )
}

// ===== Answer Input Renderers =====

function renderAnswerInput(
  q: QuestionCardProps['question'],
  userAnswer: string,
  onAnswerChange: (qid: string, ans: string) => void,
  disabled: boolean,
) {
  switch (q.question_type) {
    case 'single_choice':
    case 'true_false':
      return <ChoiceInput q={q} userAnswer={userAnswer} onAnswerChange={onAnswerChange} disabled={disabled} multi={false} />

    case 'multi_choice':
      return <ChoiceInput q={q} userAnswer={userAnswer} onAnswerChange={onAnswerChange} disabled={disabled} multi={true} />

    case 'fill_blank':
      return <FillBlankInput q={q} userAnswer={userAnswer} onAnswerChange={onAnswerChange} disabled={disabled} />

    case 'short_answer':
    case 'term_definition':
      return <TextAnswerInput q={q} userAnswer={userAnswer} onAnswerChange={onAnswerChange} disabled={disabled} />

    default:
      return (
        <Input.TextArea value={userAnswer} onChange={e => onAnswerChange(q.id, e.target.value)}
          disabled={disabled} rows={3} placeholder="请输入答案..." />
      )
  }
}

// ---- Choice (radio/checkbox) ----
function ChoiceInput({ q, userAnswer, onAnswerChange, disabled, multi }: {
  q: QuestionCardProps['question']
  userAnswer: string; onAnswerChange: (qid: string, ans: string) => void; disabled: boolean; multi: boolean
}) {
  if (multi) {
    const values = userAnswer ? userAnswer.split(',').filter(Boolean) : []
    return (
      <Checkbox.Group value={values} onChange={vals => onAnswerChange(q.id, (vals as string[]).join(','))} disabled={disabled}>
        <Space direction="vertical">
          {q.options?.map(opt => <Checkbox key={opt.label} value={opt.label}>{opt.label}. {opt.text}</Checkbox>)}
        </Space>
      </Checkbox.Group>
    )
  }
  return (
    <Radio.Group value={userAnswer} onChange={e => onAnswerChange(q.id, e.target.value)} disabled={disabled}>
      <Space direction="vertical">
        {q.options?.map(opt => <Radio key={opt.label} value={opt.label}>{opt.label}. {opt.text}</Radio>)}
      </Space>
    </Radio.Group>
  )
}

// ---- Multi-blank fill-in ----
function FillBlankInput({ q, userAnswer, onAnswerChange, disabled }: {
  q: QuestionCardProps['question']
  userAnswer: string; onAnswerChange: (qid: string, ans: string) => void; disabled: boolean
}) {
  const blanks = q.blanks || []
  const inputRefs = useRef<(InputRef | null)[]>([])

  // Parse existing answers (delimited by ;)
  const answers = userAnswer ? userAnswer.split(';').map(s => s.trim()) : []

  const updateBlank = (index: number, value: string) => {
    const newAnswers = [...answers]
    newAnswers[index] = value
    // Pad array to blanks length
    while (newAnswers.length < blanks.length) newAnswers.push('')
    onAnswerChange(q.id, newAnswers.join(';'))
  }

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Tab' && !e.shiftKey && index < blanks.length - 1) {
      e.preventDefault()
      inputRefs.current[index + 1]?.focus()
    }
  }

  // Voice command handler
  const handleVoiceCommand = (command: string) => {
    if (command === '下一空' || command === '下一个' || command === 'next') {
      // Find current focused input and move to next
      const focusedIdx = inputRefs.current.findIndex(ref => {
        try { return document.activeElement === (ref as any)?.input || document.activeElement === (ref as any)?.resizableTextArea?.textArea }
        catch { return false }
      })
      if (focusedIdx >= 0 && focusedIdx < blanks.length - 1) {
        inputRefs.current[focusedIdx + 1]?.focus()
      }
    }
  }

  // Single blank
  if (blanks.length <= 1) {
    return (
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space>
          <Input
            value={userAnswer}
            onChange={e => onAnswerChange(q.id, e.target.value)}
            disabled={disabled}
            placeholder={blanks[0]?.hint || '请输入答案...'}
            style={{ width: 300 }}
            allowClear
          />
          <VoiceInput
            onResult={(text) => onAnswerChange(q.id, text)}
            onCommand={handleVoiceCommand}
            disabled={disabled} />
        </Space>
      </Space>
    )
  }

  // Multi-blank
  return (
    <Space direction="vertical" style={{ width: '100%' }} size={8}>
      {blanks.map((blank, i) => (
        <Space key={i}>
          <Tag color="processing">空{i + 1}</Tag>
          <Input
            ref={el => { inputRefs.current[i] = el }}
            value={answers[i] || ''}
            onChange={e => updateBlank(i, e.target.value)}
            onKeyDown={e => handleKeyDown(i, e)}
            disabled={disabled}
            placeholder={blank.hint || `第${i + 1}空`}
            style={{ width: 280 }}
            allowClear
          />
          {i === 0 && (
            <VoiceInput
              onResult={(text) => {
                if (blanks.length > 1) {
                  updateBlank(i, text)
                } else {
                  onAnswerChange(q.id, text)
                }
              }}
              onCommand={handleVoiceCommand}
              disabled={disabled} />
          )}
        </Space>
      ))}
      {blanks.length > 1 && (
        <span style={{ fontSize: 11, color: '#999' }}>提示：用 Tab 键快速切换空位，答案以分号分隔</span>
      )}
    </Space>
  )
}

// ---- Text-based answer (short answer / term definition) ----
function TextAnswerInput({ q, userAnswer, onAnswerChange, disabled }: {
  q: QuestionCardProps['question']
  userAnswer: string; onAnswerChange: (qid: string, ans: string) => void; disabled: boolean
}) {
  const isTerm = q.question_type === 'term_definition'
  const scoringPoints = q.scoring_points || []

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space align="start" style={{ width: '100%' }}>
        <Input.TextArea
          value={userAnswer}
          onChange={e => onAnswerChange(q.id, e.target.value)}
          disabled={disabled}
          rows={isTerm ? 6 : 4}
          placeholder={isTerm ? '请详细解释该术语的含义...' : '请输入答案...'}
          maxLength={isTerm ? 2000 : 1000}
          showCount
          style={{ flex: 1 }}
        />
        <VoiceInput
          onResult={(text) => onAnswerChange(q.id, text)}
          disabled={disabled} />
      </Space>
      {/* Scoring point hints for term definition */}
      {isTerm && scoringPoints.length > 0 && !disabled && (
        <div style={{ fontSize: 12, color: '#888', background: '#fafafa', padding: 6, borderRadius: 4 }}>
          提示：本题按要点评分，共 {scoringPoints.reduce((s, p) => s + p.score, 0)} 分。
          {scoringPoints.map((p, i) => (
            <Tag key={i} style={{ margin: '2px 4px', fontSize: 11 }}>{p.point}({p.score}分)</Tag>
          ))}
        </div>
      )}
    </Space>
  )
}

// ===== Result Panel =====
function ResultPanel({ result, questionType }: {
  result: NonNullable<QuestionCardProps['result']>
  questionType: string
}) {
  const isSemantic = result.grading_method === 'semantic'
  const isPartial = questionType === 'fill_blank' || questionType === 'term_definition'

  return (
    <div style={{ marginTop: 12, padding: 12, background: result.is_correct ? '#f6ffed' : '#fff2f0', borderRadius: 8 }}>
      <div style={{ fontWeight: 600 }}>
        正确答案: {result.correct_answer}
        {isSemantic && <Tag color="purple" style={{ marginLeft: 8 }}>AI语义评分</Tag>}
        {isPartial && result.partial_score != null && (
          <Tag color={result.partial_score >= 0.6 ? 'green' : 'orange'}>
            部分得分: {((result.partial_score) * 100).toFixed(0)}%
          </Tag>
        )}
      </div>

      {!result.is_correct && (
        <div style={{ color: '#ff4d4f', marginTop: 4 }}>
          你的答案: {result.user_answer || '(未作答)'}
        </div>
      )}

      {/* Multi-blank details */}
      {result.blank_details && result.blank_details.length > 0 && (
        <div style={{ marginTop: 8, padding: 8, background: '#fafafa', borderRadius: 4 }}>
          {result.blank_details.map((bd, i) => (
            <div key={i} style={{ marginBottom: 4 }}>
              <Tag color={bd.is_correct ? 'green' : 'red'}>空{bd.blank_index}</Tag>
              期望: <Tag color="blue">{bd.expected}</Tag>
              {bd.user_answer && <span>你的: <Tag color={bd.is_correct ? 'green' : 'red'}>{bd.user_answer}</Tag></span>}
              {bd.hint && <span style={{ color: '#888', fontSize: 12 }}> ({bd.hint})</span>}
            </div>
          ))}
        </div>
      )}

      {/* Term definition scoring details */}
      {result.point_details && result.point_details.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontWeight: 500, marginBottom: 4 }}>
            要点得分: {result.earned_score}/{result.score_total}
          </div>
          {result.point_details.map((pd, i) => (
            <div key={i} style={{ marginBottom: 6, padding: '4px 8px', background: '#fafafa', borderRadius: 4, fontSize: 13 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{pd.point}</span>
                <Tag color={pd.earned >= pd.max_score * 0.5 ? 'green' : 'red'}>
                  {pd.earned}/{pd.max_score}分
                </Tag>
              </div>
              <div style={{ marginTop: 2 }}>
                {pd.keywords_matched.map((kw, j) => (
                  <Tag key={j} color="green" style={{ fontSize: 11 }}>{kw}</Tag>
                ))}
                {pd.keywords_expected.filter(kw => !pd.keywords_matched.includes(kw)).map((kw, j) => (
                  <Tag key={j} color="default" style={{ fontSize: 11, textDecoration: 'line-through' }}>{kw}</Tag>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Semantic grading panel */}
      {isSemantic && result.semantic_scores && <SemanticPanel result={result} />}

      {result.analysis && (
        <div style={{ marginTop: 8, color: '#666', fontSize: 13, lineHeight: 1.6 }}>
          解析: <RichText text={result.analysis} />
        </div>
      )}
    </div>
  )
}

function SemanticPanel({ result }: { result: NonNullable<QuestionCardProps['result']> }) {
  const ss = result.semantic_scores!
  const fb = result.feedback
  return (
    <div style={{ marginTop: 10, padding: 10, background: '#fafafa', borderRadius: 6 }}>
      <Space wrap size={[8, 4]}>
        <Tooltip title="核心观点正确性"><Tag color="blue">正确性: {ss.correctness}/10</Tag></Tooltip>
        <Tooltip title="要点覆盖完整度"><Tag color="cyan">完整性: {ss.completeness}/10</Tag></Tooltip>
        <Tooltip title="表述逻辑清晰度"><Tag color="geekblue">清晰度: {ss.clarity}/10</Tag></Tooltip>
        <Tag color={(result.semantic_total ?? 0) >= 6 ? 'green' : 'red'}>
          总分: {(result.semantic_total ?? 0).toFixed(1)}/10
        </Tag>
      </Space>
      {fb && (
        <div style={{ marginTop: 8, fontSize: 13 }}>
          {fb.strengths?.length > 0 && <div style={{ color: '#52c41a' }}>优点: {fb.strengths.join('；')}</div>}
          {fb.weaknesses?.length > 0 && <div style={{ color: '#ff4d4f' }}>不足: {fb.weaknesses.join('；')}</div>}
          {fb.suggestion && <div style={{ color: '#666', fontStyle: 'italic' }}>建议: {fb.suggestion}</div>}
        </div>
      )}
      {result.key_points_matched?.length > 0 && (
        <div style={{ marginTop: 6, fontSize: 12 }}>
          <span style={{ color: '#52c41a' }}>匹配: </span>
          {result.key_points_matched.map((kp, i) => <Tag key={i} color="green" style={{ fontSize: 11 }}>{kp}</Tag>)}
        </div>
      )}
      {result.key_points_missed?.length > 0 && (
        <div style={{ marginTop: 4, fontSize: 12 }}>
          <span style={{ color: '#ff4d4f' }}>遗漏: </span>
          {result.key_points_missed.map((kp, i) => <Tag key={i} color="red" style={{ fontSize: 11 }}>{kp}</Tag>)}
        </div>
      )}
    </div>
  )
}
