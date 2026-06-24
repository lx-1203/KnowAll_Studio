import { useState } from 'react'
import { Card, Button, Select, App, Space, Progress, Tag, Spin } from 'antd'
import { RobotOutlined, FormOutlined, TrophyOutlined, DownloadOutlined } from '@ant-design/icons'
import { generateQuestions, createExam, submitExam } from '../api'
import { useAppStore, useQuizStore } from '../stores'
import QuestionCard from '../components/QuestionCard'
import { QuizSkeleton } from '../components/SkeletonLoader'

const questionTypes = [
  { value: 'single_choice', label: '单选题' },
  { value: 'multi_choice', label: '多选题' },
  { value: 'true_false', label: '判断题' },
  { value: 'fill_blank', label: '填空题' },
  { value: 'short_answer', label: '简答题' },
]

export default function QuizPage() {
  const { selectedDoc } = useAppStore()
  const { currentExam, userAnswers, results, setCurrentExam, setAnswer, setResults, reset } = useQuizStore()
  const { message } = App.useApp()
  const [generating, setGenerating] = useState(false)
  const [genConfig, setGenConfig] = useState({ question_type: 'single_choice', count: 10, difficulty: 'medium' })
  const [showResults, setShowResults] = useState(false)

  const handleGenerate = async () => {
    if (!selectedDoc) { message.warning('请先在"资料导入"页面选择文档'); return }
    setGenerating(true)
    try {
      // Generate questions
      const qResult = await generateQuestions({
        document_id: selectedDoc,
        question_type: genConfig.question_type,
        count: genConfig.count,
        difficulty: genConfig.difficulty,
      })
      message.success(`已生成 ${qResult.generated_count} 道题目`)

      // Create exam paper
      const questionIds = (qResult.questions || []).map((q: any) => q.id)
      const exam = await createExam({
        title: `测验-${new Date().toLocaleDateString()}`,
        question_ids: questionIds,
      })
      setCurrentExam(exam)
    } catch (e: any) {
      message.error(`生成失败: ${e.response?.data?.detail || e.message}`)
    } finally {
      setGenerating(false)
      setShowResults(false)
    }
  }

  const handleSubmit = async () => {
    if (!currentExam) return
    try {
      const result = await submitExam({
        paper_id: currentExam.paper_id,
        answers: userAnswers,
      })
      setResults(result)
      setShowResults(true)
      message.success(`得分: ${result.score}/${result.total * 5} (${result.percentage}%)`)
    } catch (e: any) {
      message.error('提交失败')
    }
  }

  const renderQuestion = (q: any, index: number) => {
    const userAnswer = userAnswers[q.id] || ''
    const result = results?.details?.find((d: any) => d.question_id === q.id)
    return (
      <QuestionCard
        key={q.id}
        question={q}
        index={index}
        userAnswer={userAnswer}
        onAnswerChange={(qid, ans) => setAnswer(qid, ans)}
        showResults={showResults}
        result={result}
      />
    )
  }

  return (
    <div>
      <Card title="题库测评" extra={
        <Space>
          <Select value={genConfig.question_type} onChange={v => setGenConfig(g => ({ ...g, question_type: v }))} options={questionTypes} />
          <Select value={genConfig.count} onChange={v => setGenConfig(g => ({ ...g, count: v }))}
            options={[5, 10, 15, 20].map(n => ({ value: n, label: `${n}题` }))} />
          <Select value={genConfig.difficulty} onChange={v => setGenConfig(g => ({ ...g, difficulty: v }))}
            options={['easy', 'medium', 'hard'].map(d => ({ value: d, label: d === 'easy' ? '简单' : d === 'medium' ? '中等' : '困难' }))} />
          <Button icon={<RobotOutlined />} type="primary" loading={generating} onClick={handleGenerate}>
            AI 生成试卷
          </Button>
        </Space>
      }>
        {!currentExam && !generating && (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <FormOutlined style={{ fontSize: 64, marginBottom: 16 }} />
            <p>选择题型和数量，点击「AI 生成试卷」开始测评</p>
          </div>
        )}
        {generating && (
          <div style={{ textAlign: 'center', padding: 60 }}>
            <Spin size="large" />
            <p style={{ marginTop: 16 }}>AI 正在出题...</p>
          </div>
        )}
        {showResults && results && (
          <Card size="small" style={{ marginBottom: 16, background: '#f0f5ff' }}>
            <Space>
              <TrophyOutlined style={{ fontSize: 24, color: '#faad14' }} />
              <span style={{ fontSize: 18, fontWeight: 600 }}>
                得分: {results.score}/{results.total * 5} ({results.percentage}%)
              </span>
              <Progress percent={results.percentage} style={{ width: 200 }} />
              <Tag color="green">正确: {results.correct}</Tag>
              <Tag color="red">错误: {results.total - results.correct}</Tag>
            </Space>
          </Card>
        )}
        {currentExam?.questions?.map((q: any, i: number) => renderQuestion(q, i))}
        {currentExam && !showResults && (
          <Button type="primary" size="large" block onClick={handleSubmit}
            disabled={Object.keys(userAnswers).length < (currentExam.questions?.length || 0) / 2}>
            提交试卷 ({Object.keys(userAnswers).length}/{currentExam.questions?.length || 0})
          </Button>
        )}
        {showResults && (
          <Space style={{ marginTop: 16 }}>
            <Button icon={<DownloadOutlined />} onClick={() => {
              const data = JSON.stringify({ exam: currentExam, results }, null, 2)
              const blob = new Blob([data], { type: 'application/json' })
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url; a.download = `exam_result_${Date.now()}.json`; a.click()
              URL.revokeObjectURL(url)
              message.success('结果已导出')
            }}>导出结果</Button>
            <Button onClick={() => { reset(); setShowResults(false) }}>重新作答</Button>
            <Button type="primary" onClick={() => { setShowResults(false) }}>查看错题</Button>
          </Space>
        )}
      </Card>
    </div>
  )
}
