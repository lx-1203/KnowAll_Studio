import React, { useEffect } from 'react'
import { Button, Card, Radio, Checkbox, Space, Tag } from 'antd'
import { CloseOutlined } from '@ant-design/icons'
import { QuizTimer } from './QuizTimer'
import type { QuizGateState } from '../types'
import { DEFAULT_GAME_CONFIG } from '../config'
import { useQuizGate } from '../hooks/useQuizGate'

interface QuizGateModalProps {
  isDark: boolean
}

export const QuizGateModal: React.FC<QuizGateModalProps> = ({ isDark }) => {
  const { quizState, selectAnswer, submitAnswer, dismissFeedback } = useQuizGate()
  const { question, userAnswer, timeLeft, isSubmitted, result, showFeedback } = quizState

  // 超时自动提交
  useEffect(() => {
    if (timeLeft <= 0 && !isSubmitted) {
      submitAnswer()
    }
  }, [timeLeft, isSubmitted, submitAnswer])

  // 反馈1.5秒后自动关闭
  useEffect(() => {
    if (showFeedback && result) {
      const timer = setTimeout(() => {
        dismissFeedback()
      }, 1500)
      return () => clearTimeout(timer)
    }
  }, [showFeedback, result, dismissFeedback])

  if (!question) return null

  const isWarning = timeLeft <= 10
  const diffLabels: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }
  const diffColors: Record<string, string> = { easy: 'green', medium: 'orange', hard: 'red' }
  const typeLabels: Record<string, string> = {
    single_choice: '单选题',
    multi_choice: '多选题',
    true_false: '判断题',
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0,0,0,0.6)',
        backdropFilter: 'blur(4px)',
        padding: 16,
        animation: 'fadeIn 0.25s ease',
      }}
    >
      <Card
        style={{
          width: '100%',
          maxWidth: 480,
          maxHeight: '90vh',
          overflow: 'auto',
          borderRadius: 16,
          boxShadow: '0 8px 40px rgba(0,0,0,0.3)',
        }}
        styles={{ body: { padding: 24 } }}
      >
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 13, color: '#888', marginBottom: 4 }}>
            答题门禁 — 回答正确方可继续
          </div>
          <Space size={8}>
            <Tag color={diffColors[question.difficulty]}>
              {diffLabels[question.difficulty]}
            </Tag>
            <Tag>{typeLabels[question.question_type] || question.question_type}</Tag>
          </Space>
        </div>

        {/* Timer */}
        {!isSubmitted && (
          <div style={{ marginBottom: 16 }}>
            <QuizTimer
              timeLeft={timeLeft}
              totalTime={DEFAULT_GAME_CONFIG.quiz.timeLimit}
              isWarning={isWarning}
            />
          </div>
        )}

        {/* Question text */}
        <div
          style={{
            fontSize: 15,
            fontWeight: 600,
            lineHeight: 1.8,
            marginBottom: 20,
            color: isDark ? '#e5e7eb' : '#1f2937',
          }}
        >
          {question.question_text}
        </div>

        {/* Options */}
        <div style={{ marginBottom: 20 }}>
          {question.question_type === 'multi_choice' ? (
            <Checkbox.Group
              value={userAnswer ? userAnswer.split(',').filter(Boolean) : []}
              onChange={(vals) => {
                selectAnswer((vals as string[]).join(','))
              }}
              disabled={isSubmitted}
              style={{ width: '100%' }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                {question.options.map(opt => {
                  const isCorrect = result && question.answer.includes(opt.label)
                  const isUser = userAnswer?.includes(opt.label)
                  let bgColor = ''
                  if (result) {
                    if (isCorrect) bgColor = '#f6ffed'
                    else if (isUser && !isCorrect) bgColor = '#fff2f0'
                  }
                  return (
                    <div
                      key={opt.label}
                      style={{
                        padding: '8px 12px',
                        borderRadius: 8,
                        border: isUser && !result ? '2px solid #4f46e5' : '1px solid #e8e8e8',
                        backgroundColor: bgColor || '#fff',
                        transition: 'all 0.2s',
                        cursor: isSubmitted ? 'default' : 'pointer',
                      }}
                    >
                      <Checkbox value={opt.label} disabled={isSubmitted}>
                        <strong>{opt.label}.</strong> {opt.text}
                      </Checkbox>
                    </div>
                  )
                })}
              </Space>
            </Checkbox.Group>
          ) : (
            <Radio.Group
              value={userAnswer}
              onChange={e => selectAnswer(e.target.value)}
              disabled={isSubmitted}
              style={{ width: '100%' }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                {question.options.map(opt => {
                  const isCorrect = result && question.answer === opt.label
                  const isUser = userAnswer === opt.label
                  let bgColor = ''
                  if (result) {
                    if (isCorrect) bgColor = '#f6ffed'
                    else if (isUser && !isCorrect) bgColor = '#fff2f0'
                  }
                  return (
                    <div
                      key={opt.label}
                      style={{
                        padding: '8px 12px',
                        borderRadius: 8,
                        border: isUser && !result ? '2px solid #4f46e5' : '1px solid #e8e8e8',
                        backgroundColor: bgColor || '#fff',
                        transition: 'all 0.2s',
                      }}
                    >
                      <Radio value={opt.label} disabled={isSubmitted}>
                        <strong>{opt.label}.</strong> {opt.text}
                      </Radio>
                    </div>
                  )
                })}
              </Space>
            </Radio.Group>
          )}
        </div>

        {/* Submit button */}
        {!isSubmitted ? (
          <Button
            type="primary"
            block
            size="large"
            disabled={!userAnswer}
            onClick={submitAnswer}
            style={{ borderRadius: 10, height: 44, fontWeight: 600 }}
          >
            提交答案
          </Button>
        ) : (
          <div
            style={{
              textAlign: 'center',
              padding: 16,
              borderRadius: 10,
              backgroundColor: result?.isCorrect ? '#f6ffed' : '#fff2f0',
              animation: 'fadeIn 0.3s ease',
            }}
          >
            <div
              style={{
                fontSize: 28,
                fontWeight: 700,
                marginBottom: 4,
                color: result?.isCorrect ? '#52c41a' : '#ff4d4f',
              }}
            >
              {result?.isCorrect ? '✓ 回答正确！' : '✗ 回答错误'}
            </div>
            {!result?.isCorrect && (
              <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>
                正确答案: {result?.correctAnswer}
              </div>
            )}
            {question.analysis && (
              <div style={{ fontSize: 12, color: '#888', marginTop: 8, lineHeight: 1.6 }}>
                {question.analysis}
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}
