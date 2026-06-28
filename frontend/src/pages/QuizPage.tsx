import { useState, useEffect, useCallback } from 'react'
import { Card, Button, Select, Slider, App, Space, Progress, Tag, Spin, Table, List, Tooltip, Row, Col, Checkbox, Popconfirm, Divider, Empty, Badge } from 'antd'
import {
  RobotOutlined, FormOutlined, TrophyOutlined, DownloadOutlined, BugOutlined,
  SyncOutlined, SafetyCertificateOutlined, InboxOutlined, DeleteOutlined,
  CheckSquareOutlined, BorderOutlined, SelectOutlined, PlayCircleOutlined,
} from '@ant-design/icons'
import { generateQuestions, saveToBank, deleteQuestionsBatch, createExam, submitExam, listQuestions, getErrorQuestions, generateVariants } from '../api'
import { useAppStore, useQuizStore } from '../stores'
import QuestionCard from '../components/QuestionCard'
import { COGNITIVE_LEVEL_LABELS, COGNITIVE_LEVEL_COLORS, type CognitiveLevel } from '../types'

const questionTypes = [
  { value: 'single_choice', label: '单选题' },
  { value: 'multi_choice', label: '多选题' },
  { value: 'true_false', label: '判断题' },
  { value: 'fill_blank', label: '填空题' },
  { value: 'short_answer', label: '简答题' },
]

const cognitiveLevels = [
  { value: 'L1_remember', label: 'L1 记忆' },
  { value: 'L2_understand', label: 'L2 理解' },
  { value: 'L3_apply', label: 'L3 应用' },
  { value: 'L4_analyze', label: 'L4 分析' },
  { value: 'L5_evaluate', label: 'L5 评价' },
  { value: 'L6_create', label: 'L6 创造' },
]

function diffLabel(v: number): string {
  if (v <= 0.25) return '很简单'
  if (v <= 0.45) return '偏简单'
  if (v <= 0.60) return '中等'
  if (v <= 0.80) return '偏困难'
  return '困难'
}

const typeLabels: Record<string, string> = {
  single_choice: '单选', multi_choice: '多选', true_false: '判断',
  fill_blank: '填空', short_answer: '简答', calculation: '计算',
  formula: '公式', coding: '编程', material_analysis: '材料分析',
}

export default function QuizPage() {
  const { selectedDoc } = useAppStore()
  const { currentExam, userAnswers, results, setCurrentExam, setAnswer, setResults, reset } = useQuizStore()
  const { message } = App.useApp()

  // Generation config
  const [genConfig, setGenConfig] = useState({
    question_type: 'single_choice',
    count: 5,
    difficulty: 'medium' as string,
    difficulty_score: 0.5,
    cognitive_level: 'L2_understand' as string,
    enable_review: true,
  })
  const [generating, setGenerating] = useState(false)

  // Preview questions (not yet saved to bank)
  const [previewQuestions, setPreviewQuestions] = useState<any[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [saving, setSaving] = useState(false)

  // Question bank
  const [allQuestions, setAllQuestions] = useState<any[]>([])
  const [questionsLoading, setQuestionsLoading] = useState(false)
  const [bankSelected, setBankSelected] = useState<Set<string>>(new Set())
  const [bankFilter, setBankFilter] = useState<{ type?: string; cognitive?: string }>({})

  // Exam
  const [showResults, setShowResults] = useState(false)

  // Error panel
  const [errorQuestions, setErrorQuestions] = useState<any[]>([])
  const [errorsLoading, setErrorsLoading] = useState(false)
  const [showErrors, setShowErrors] = useState(false)
  const [variantGenerating, setVariantGenerating] = useState<string | null>(null)

  // Load bank on mount
  useEffect(() => { refreshBank() }, [])
  const refreshBank = useCallback(() => {
    setQuestionsLoading(true)
    const params: any = { limit: 200 }
    if (bankFilter.type) params.question_type = bankFilter.type
    if (bankFilter.cognitive) params.cognitive_level = bankFilter.cognitive
    listQuestions(params).then(setAllQuestions).catch(console.error).finally(() => setQuestionsLoading(false))
  }, [bankFilter])

  // ===== Generate =====
  const handleGenerate = async () => {
    if (!selectedDoc) { message.warning('请先在"资料导入"页面选择文档'); return }
    setGenerating(true)
    setPreviewQuestions([])
    setSelectedIds(new Set())
    try {
      const result = await generateQuestions({
        document_id: selectedDoc,
        question_type: genConfig.question_type,
        count: genConfig.count,
        difficulty: genConfig.difficulty,
        difficulty_score: genConfig.difficulty_score,
        cognitive_level: genConfig.cognitive_level,
        enable_review: genConfig.enable_review,
        preview: true,  // preview mode: don't auto-save
      })
      const qs = result.questions || []
      setPreviewQuestions(qs)
      setSelectedIds(new Set(qs.map((_: any, i: number) => i)))
      const reviewed = result.reviewed_count || 0
      message.success(`已生成 ${qs.length} 道题目${reviewed > 0 ? `（${reviewed} 道通过AI审核）` : ''}，请勾选要入库的题目`)
    } catch (e: any) {
      message.error(`生成失败: ${e.response?.data?.detail || e.message}`)
    } finally {
      setGenerating(false)
    }
  }

  // ===== Selection Helpers =====
  const toggleSelect = (idx: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx); else next.add(idx)
      return next
    })
  }
  const selectAll = () => setSelectedIds(new Set(previewQuestions.map((_, i) => i)))
  const deselectAll = () => setSelectedIds(new Set())
  const invertSelect = () => {
    setSelectedIds(prev => {
      const next = new Set<number>()
      previewQuestions.forEach((_, i) => { if (!prev.has(i)) next.add(i) })
      return next
    })
  }

  // ===== Save to Bank =====
  const handleSaveToBank = async () => {
    const selected = previewQuestions.filter((_, i) => selectedIds.has(i))
    if (selected.length === 0) { message.warning('请至少勾选一道题目'); return }
    setSaving(true)
    try {
      const result = await saveToBank({ questions: selected })
      message.success(`已存入题库 ${result.saved_count} 道题目`)
      setPreviewQuestions([])
      setSelectedIds(new Set())
      refreshBank()
    } catch (e: any) {
      message.error(`入库失败: ${e.response?.data?.detail || e.message}`)
    } finally {
      setSaving(false)
    }
  }

  // ===== Create Exam from Selected Preview =====
  const handleCreateExamFromPreview = async () => {
    const selected = previewQuestions.filter((_, i) => selectedIds.has(i))
    if (selected.length === 0) { message.warning('请至少勾选一道题目'); return }
    // First save to bank, then create exam
    setSaving(true)
    try {
      const saveResult = await saveToBank({ questions: selected })
      const ids = saveResult.question_ids || []
      const exam = await createExam({
        title: `测验-${new Date().toLocaleDateString()}`,
        question_ids: ids,
      })
      setCurrentExam(exam)
      setPreviewQuestions([])
      setSelectedIds(new Set())
      setShowResults(false)
      reset()
      refreshBank()
      message.success(`已创建试卷: ${exam.question_count} 题`)
    } catch (e: any) {
      message.error(`操作失败: ${e.response?.data?.detail || e.message}`)
    } finally {
      setSaving(false)
    }
  }

  // ===== Bank Management =====
  const handleBankSelect = (qid: string) => {
    setBankSelected(prev => {
      const next = new Set(prev)
      if (next.has(qid)) next.delete(qid); else next.add(qid)
      return next
    })
  }
  const handleBankDelete = async () => {
    if (bankSelected.size === 0) { message.warning('请勾选要删除的题目'); return }
    try {
      await deleteQuestionsBatch(Array.from(bankSelected))
      message.success(`已删除 ${bankSelected.size} 道题目`)
      setBankSelected(new Set())
      refreshBank()
    } catch (e: any) {
      message.error('删除失败')
    }
  }
  const handleCreateExamFromBank = async () => {
    if (bankSelected.size === 0) { message.warning('请勾选题目'); return }
    try {
      const exam = await createExam({
        title: `测验-${new Date().toLocaleDateString()}`,
        question_ids: Array.from(bankSelected),
      })
      setCurrentExam(exam)
      setShowResults(false)
      reset()
      setBankSelected(new Set())
      message.success(`已创建试卷: ${exam.question_count} 题`)
    } catch (e: any) {
      message.error('创建试卷失败')
    }
  }

  // ===== Submit Exam =====
  const handleSubmit = async () => {
    if (!currentExam) return
    try {
      const result = await submitExam({ paper_id: currentExam.paper_id, answers: userAnswers })
      setResults(result)
      setShowResults(true)
      message.success(`得分: ${result.score}/${result.total * 5} (${result.percentage}%)`)
    } catch (e: any) {
      message.error('提交失败')
    }
  }

  // ===== Error Questions =====
  const handleViewErrors = async () => {
    setErrorsLoading(true); setShowErrors(true)
    try { setErrorQuestions((await getErrorQuestions()) || []) }
    catch (e: any) { message.error('获取错题失败') }
    finally { setErrorsLoading(false) }
  }
  const handleGenerateVariants = async (errorId: string) => {
    setVariantGenerating(errorId)
    try {
      const result = await generateVariants(errorId, 3)
      const variants = result.questions || []
      message.success(`已生成 ${variants.length} 道变式题`)
      if (variants.length > 0) {
        const exam = await createExam({ title: `变式练习-${new Date().toLocaleDateString()}`, question_ids: variants.map((q: any) => q.id) })
        setCurrentExam(exam); setShowResults(false); setShowErrors(false); reset()
      }
    } catch (e: any) { message.error('变式题生成失败') }
    finally { setVariantGenerating(null) }
  }

  // ===== Render =====
  const renderQuestion = (q: any, index: number) => (
    <QuestionCard
      key={q.id}
      question={q}
      index={index}
      userAnswer={userAnswers[q.id] || ''}
      onAnswerChange={(qid, ans) => setAnswer(qid, ans)}
      showResults={showResults}
      result={results?.details?.find((d: any) => d.question_id === q.id)}
    />
  )

  return (
    <div>
      {/* ===== Generation Panel ===== */}
      <Card title="AI 出题" extra={
        <Space wrap>
          <Select value={genConfig.question_type} onChange={v => setGenConfig(g => ({ ...g, question_type: v }))}
            options={questionTypes} style={{ minWidth: 90 }} />
          <Select value={genConfig.cognitive_level} onChange={v => setGenConfig(g => ({ ...g, cognitive_level: v }))}
            options={cognitiveLevels} style={{ minWidth: 105 }} />
          <Tooltip title={`难度: ${genConfig.difficulty_score.toFixed(2)} (${diffLabel(genConfig.difficulty_score)})`}>
            <Slider value={genConfig.difficulty_score} onChange={v => {
              const val = v as number
              setGenConfig(g => ({ ...g, difficulty_score: val, difficulty: val <= 0.35 ? 'easy' : val <= 0.65 ? 'medium' : 'hard' }))
            }} min={0.05} max={1.0} step={0.05} style={{ width: 80, margin: 0 }}
              tooltip={{ formatter: v => `${(v as number).toFixed(2)}` }} />
          </Tooltip>
          <Select value={genConfig.count} onChange={v => setGenConfig(g => ({ ...g, count: v }))}
            options={[3, 5, 10, 15].map(n => ({ value: n, label: `${n}题` }))} />
          <Button size="small" icon={<SafetyCertificateOutlined />}
            type={genConfig.enable_review ? 'primary' : 'default'}
            ghost={!genConfig.enable_review}
            onClick={() => setGenConfig(g => ({ ...g, enable_review: !g.enable_review }))}>
            AI审核{genConfig.enable_review ? '开' : '关'}
          </Button>
          <Button icon={<RobotOutlined />} type="primary" loading={generating} onClick={handleGenerate}>
            生成题目
          </Button>
        </Space>
      }>
        {generating && (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" />
            <p style={{ marginTop: 12 }}>AI 正在出题{genConfig.enable_review ? '并审核质量' : ''}...</p>
          </div>
        )}

        {/* Preview Results */}
        {!generating && previewQuestions.length > 0 && (
          <div>
            <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space>
                <Badge count={selectedIds.size} style={{ backgroundColor: '#1677ff' }} overflowCount={99}>
                  <Tag color="blue" style={{ fontSize: 14, padding: '2px 12px' }}>生成结果</Tag>
                </Badge>
                <Tag color="purple">{previewQuestions.length} 题</Tag>
                {previewQuestions.some(q => q.reviewed) && (
                  <Tag color="green">AI已审核</Tag>
                )}
              </Space>
              <Space>
                <Button size="small" onClick={selectAll} icon={<CheckSquareOutlined />}>全选</Button>
                <Button size="small" onClick={deselectAll} icon={<BorderOutlined />}>取消</Button>
                <Button size="small" onClick={invertSelect} icon={<SelectOutlined />}>反选</Button>
                <Button size="small" type="primary" icon={<InboxOutlined />} loading={saving} onClick={handleSaveToBank}>
                  存入题库 ({selectedIds.size})
                </Button>
                <Button size="small" icon={<PlayCircleOutlined />} loading={saving} onClick={handleCreateExamFromPreview}>
                  直接组卷
                </Button>
              </Space>
            </div>
            <List
              size="small"
              bordered
              dataSource={previewQuestions}
              style={{ maxHeight: 500, overflow: 'auto' }}
              renderItem={(q: any, i: number) => (
                <List.Item
                  key={i}
                  style={{ cursor: 'pointer', background: selectedIds.has(i) ? '#f0f5ff' : undefined }}
                  onClick={() => toggleSelect(i)}
                >
                  <Space align="start" style={{ width: '100%' }}>
                    <Checkbox checked={selectedIds.has(i)} onChange={() => toggleSelect(i)} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 500, marginBottom: 4 }}>{q.question_text}</div>
                      <Space size={4} wrap>
                        <Tag color="blue">{typeLabels[q.question_type] || q.question_type}</Tag>
                        <Tag color={COGNITIVE_LEVEL_COLORS[q.cognitive_level as CognitiveLevel] || 'default'}>
                          {COGNITIVE_LEVEL_LABELS[q.cognitive_level as CognitiveLevel] || q.cognitive_level}
                        </Tag>
                        <Tooltip title={`难度: ${(q.difficulty_score ?? 0.5).toFixed(2)}`}>
                          <Progress percent={Math.round((q.difficulty_score ?? 0.5) * 100)} size="small"
                            style={{ width: 60, minWidth: 60 }}
                            strokeColor={(q.difficulty_score ?? 0.5) <= 0.35 ? '#52c41a' : (q.difficulty_score ?? 0.5) <= 0.65 ? '#faad14' : '#ff4d4f'}
                            format={() => diffLabel(q.difficulty_score ?? 0.5)} />
                        </Tooltip>
                        {q.reviewed && (
                          <Tooltip title={`AI审核: ${q.review_decision} (${q.review_total?.toFixed(1)}/4.0)`}>
                            <Tag color={q.review_total >= 3.2 ? 'green' : q.review_total >= 2.4 ? 'orange' : 'red'}>
                              质量{q.review_total?.toFixed(1)}
                            </Tag>
                          </Tooltip>
                        )}
                      </Space>
                    </div>
                  </Space>
                </List.Item>
              )}
            />
          </div>
        )}

        {!generating && previewQuestions.length === 0 && !currentExam && (
          <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
            <FormOutlined style={{ fontSize: 48, marginBottom: 12 }} />
            <p>配置参数后点击「生成题目」，勾选满意的题目存入题库</p>
          </div>
        )}
      </Card>

      {/* ===== Exam Section ===== */}
      {currentExam && (
        <Card title="当前试卷" style={{ marginTop: 16 }}
          extra={!showResults ? (
            <Button type="primary" size="large" onClick={handleSubmit}
              disabled={Object.keys(userAnswers).length < (currentExam.questions?.length || 0) / 2}>
              提交 ({Object.keys(userAnswers).length}/{currentExam.questions?.length || 0})
            </Button>
          ) : (
            <Space>
              <Button onClick={() => { reset(); setShowResults(false); setCurrentExam(null as any) }}>返回题库</Button>
              <Button icon={<BugOutlined />} onClick={handleViewErrors}>错题</Button>
            </Space>
          )}>
          {showResults && results && (
            <>
              <Card size="small" style={{ marginBottom: 16, background: '#f0f5ff' }}>
                <Space wrap>
                  <TrophyOutlined style={{ fontSize: 24, color: '#faad14' }} />
                  <span style={{ fontSize: 18, fontWeight: 600 }}>
                    {results.score}/{results.total * 5} ({results.percentage}%)
                  </span>
                  <Progress percent={results.percentage} style={{ width: 200 }} />
                  <Tag color="green">正确: {results.correct}</Tag>
                  <Tag color="red">错误: {results.total - results.correct}</Tag>
                </Space>
              </Card>
              {results.cognitive_breakdown && (
                <Card size="small" title="认知层次分析" style={{ marginBottom: 16, background: '#fafafa' }}>
                  <Row gutter={[12, 8]}>
                    {Object.entries(results.cognitive_breakdown).map(([level, stats]: [string, any]) => (
                      <Col key={level} xs={12} sm={8} md={4}>
                        <Card size="small" style={{ textAlign: 'center' }} bodyStyle={{ padding: '10px 8px' }}>
                          <Tag color={COGNITIVE_LEVEL_COLORS[level as CognitiveLevel] || 'default'}>
                            {COGNITIVE_LEVEL_LABELS[level as CognitiveLevel] || level}
                          </Tag>
                          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4 }}>{stats.correct}/{stats.total}</div>
                          <div style={{ fontSize: 12, color: stats.accuracy >= 70 ? '#52c41a' : '#ff4d4f' }}>
                            {stats.accuracy}%
                          </div>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                </Card>
              )}
            </>
          )}
          {currentExam?.questions?.map((q: any, i: number) => renderQuestion(q, i))}
        </Card>
      )}

      {/* ===== Error Panel ===== */}
      {showErrors && (
        <Card title={<Space><BugOutlined /> 错题本 ({errorQuestions.length})</Space>}
          extra={<Button onClick={() => setShowErrors(false)}>关闭</Button>} style={{ marginTop: 16 }}>
          {errorsLoading ? <div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /></div>
            : errorQuestions.length === 0 ? (
              <Empty description="暂无错题，继续加油！" />
            ) : (
              <List dataSource={errorQuestions} renderItem={(item: any) => (
                <List.Item key={item.error_id} actions={[
                  <Button key="variant" type="primary" size="small" icon={<SyncOutlined />}
                    loading={variantGenerating === item.error_id}
                    onClick={() => handleGenerateVariants(item.error_id)}>变式题</Button>,
                ]}>
                  <List.Item.Meta
                    avatar={<Space direction="vertical" size={2}><Tag color="red">错{item.error_count}次</Tag></Space>}
                    title={item.question?.question_text || '(无文本)'}
                    description={
                      <Space direction="vertical" size={2}>
                        <Tag color="green">答案: {item.question?.answer}</Tag>
                        {item.question?.analysis && (
                          <div style={{ color: '#666', fontSize: 12 }}>解析: {item.question.analysis.slice(0, 100)}</div>
                        )}
                      </Space>
                    } />
                </List.Item>
              )} />
            )}
        </Card>
      )}

      {/* ===== Question Bank ===== */}
      <Card title={
        <Space>
          <InboxOutlined /> 题库
          <Badge count={allQuestions.length} style={{ backgroundColor: '#1677ff' }} overflowCount={999} />
        </Space>
      }
        style={{ marginTop: 16 }}
        extra={
          <Space wrap>
            <Select allowClear placeholder="题型筛选" style={{ width: 100 }}
              value={bankFilter.type} onChange={v => setBankFilter(f => ({ ...f, type: v }))}
              options={questionTypes} />
            <Select allowClear placeholder="认知层次" style={{ width: 110 }}
              value={bankFilter.cognitive} onChange={v => setBankFilter(f => ({ ...f, cognitive: v }))}
              options={cognitiveLevels} />
            <Button icon={<PlayCircleOutlined />} disabled={bankSelected.size === 0} onClick={handleCreateExamFromBank}>
              组卷 ({bankSelected.size})
            </Button>
            <Popconfirm title={`确认删除 ${bankSelected.size} 道题目？`} onConfirm={handleBankDelete} disabled={bankSelected.size === 0}>
              <Button danger icon={<DeleteOutlined />} disabled={bankSelected.size === 0}>
                删除 ({bankSelected.size})
              </Button>
            </Popconfirm>
          </Space>
        }>
        <Table
          loading={questionsLoading}
          dataSource={allQuestions}
          rowKey="id"
          size="middle"
          locale={{ emptyText: '暂无题目，先生成题目并入库' }}
          rowSelection={{
            selectedRowKeys: Array.from(bankSelected),
            onChange: (keys) => setBankSelected(new Set(keys as string[])),
          }}
          columns={[
            { title: '题目', dataIndex: 'question_text', ellipsis: true, width: 300,
              render: (v: string) => v || '(无文本)' },
            { title: '题型', dataIndex: 'question_type', width: 70,
              render: (v: string) => <Tag>{typeLabels[v] || v}</Tag> },
            { title: '认知', dataIndex: 'cognitive_level', width: 70,
              render: (v: string) => v ? <Tag color={COGNITIVE_LEVEL_COLORS[v as CognitiveLevel] || 'default'}>
                {COGNITIVE_LEVEL_LABELS[v as CognitiveLevel] || v}</Tag> : <span style={{ color: '#ccc' }}>—</span> },
            { title: '难度', dataIndex: 'difficulty_score', width: 80,
              render: (v: number, r: any) => {
                if (v != null) return <Progress percent={Math.round(v * 100)} size="small"
                  strokeColor={v <= 0.35 ? '#52c41a' : v <= 0.65 ? '#faad14' : '#ff4d4f'}
                  format={() => diffLabel(v)} />
                const d = r.difficulty
                return <Tag color={d === 'easy' ? 'green' : d === 'hard' ? 'red' : 'orange'}>
                  {d === 'easy' ? '简单' : d === 'hard' ? '困难' : '中等'}</Tag>
              } },
            { title: '操作', width: 50, render: (_: any, r: any) => (
              <Popconfirm title="确认删除？" onConfirm={async () => {
                await deleteQuestionsBatch([r.id]); refreshBank(); setBankSelected(new Set())
              }}>
                <Button size="small" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            )},
          ]}
          pagination={{ pageSize: 15, showSizeChanger: true, showTotal: (t) => `共 ${t} 道` }}
        />
      </Card>
    </div>
  )
}
