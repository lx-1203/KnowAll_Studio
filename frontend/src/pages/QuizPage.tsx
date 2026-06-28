import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, Button, Select, Slider, App, Space, Progress, Tag, Spin, Table, List, Tooltip, Row, Col, Checkbox, Popconfirm, Tabs, Badge, Modal, Drawer, Segmented, Statistic, Typography } from 'antd'
import {
  RobotOutlined, FormOutlined, TrophyOutlined, BugOutlined, SyncOutlined,
  SafetyCertificateOutlined, InboxOutlined, DeleteOutlined, CheckSquareOutlined,
  BorderOutlined, SelectOutlined, PlayCircleOutlined, ThunderboltOutlined,
  FileTextOutlined, ReloadOutlined, OrderedListOutlined, SaveOutlined, StarOutlined,
  BarChartOutlined, HistoryOutlined, EyeOutlined,
} from '@ant-design/icons'
import {
  generateQuestions, saveToBank, deleteQuestionsBatch, createExam,
  submitExam, listQuestions, getErrorQuestions, generateVariants, listDocuments,
  getMasteryAnalysis, getAnswerHistory, getReviewStats, getReviewKnowledgePoints,
} from '../api'
import { useAppStore, useQuizStore } from '../stores'
import QuestionCard from '../components/QuestionCard'
import MasteryOverview from '../components/MasteryOverview'
import ReviewRecommendation from '../components/ReviewRecommendation'
import { COGNITIVE_LEVEL_LABELS, COGNITIVE_LEVEL_COLORS, type CognitiveLevel } from '../types'

// ---- Constants ----
const questionTypes = [
  { value: 'single_choice', label: '单选题' },
  { value: 'multi_choice', label: '多选题' },
  { value: 'true_false', label: '判断题' },
  { value: 'fill_blank', label: '填空题' },
  { value: 'short_answer', label: '简答题' },
  { value: 'term_definition', label: '名词解释' },
]
const cognitiveLevels = [
  { value: 'L1_remember', label: 'L1 记忆' },
  { value: 'L2_understand', label: 'L2 理解' },
  { value: 'L3_apply', label: 'L3 应用' },
  { value: 'L4_analyze', label: 'L4 分析' },
  { value: 'L5_evaluate', label: 'L5 评价' },
  { value: 'L6_create', label: 'L6 创造' },
]
const typeLabels: Record<string, string> = {
  single_choice: '单选', multi_choice: '多选', true_false: '判断',
  fill_blank: '填空', short_answer: '简答', calculation: '计算',
  formula: '公式', coding: '编程', material_analysis: '材料分析',
  term_definition: '名词解释',
}
function diffLabel(v: number): string {
  if (v <= 0.25) return '很简单'
  if (v <= 0.45) return '偏简单'
  if (v <= 0.60) return '中等'
  if (v <= 0.80) return '偏困难'
  return '困难'
}

export default function QuizPage() {
  const { Text } = Typography
  const { selectedDoc, setSelectedDoc } = useAppStore()
  const { currentExam, userAnswers, results, setCurrentExam, setAnswer, setResults, reset } = useQuizStore()
  const { message, modal } = App.useApp()
  const [activeTab, setActiveTab] = useState('generate')

  // ---- Shared state ----
  const [docs, setDocs] = useState<any[]>([])
  const [docId, setDocId] = useState<string>(selectedDoc || '')

  // Load docs on mount
  useEffect(() => {
    listDocuments(50).then((data: any) => {
      const items = data?.documents || data?.items || data || []
      setDocs(Array.isArray(items) ? items : [])
    }).catch(() => {})
  }, [])

  // Sync docId with global store
  useEffect(() => {
    if (selectedDoc && !docId) setDocId(selectedDoc)
  }, [selectedDoc])

  // ---- Generation ----
  const [genConfig, setGenConfig] = useState({
    question_type: 'single_choice', count: 5, difficulty: 'medium' as string,
    difficulty_score: 0.5, cognitive_level: 'L2_understand' as string, enable_review: true,
  })
  const [generating, setGenerating] = useState(false)
  const [previewQuestions, setPreviewQuestions] = useState<any[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [saving, setSaving] = useState(false)

  // ---- Bank ----
  const [allQuestions, setAllQuestions] = useState<any[]>([])
  const [questionsLoading, setQuestionsLoading] = useState(false)
  const [bankSelected, setBankSelected] = useState<Set<string>>(new Set())
  const [bankFilter, setBankFilter] = useState<{ type?: string; cognitive?: string }>({})

  // ---- Errors ----
  const [errorQuestions, setErrorQuestions] = useState<any[]>([])
  const [errorsLoading, setErrorsLoading] = useState(false)
  const [variantGenerating, setVariantGenerating] = useState<string | null>(null)

  // ---- Review mode ----
  const [reviewMode, setReviewMode] = useState<'all' | 'review'>('all')
  const [reviewFilter, setReviewFilter] = useState<'all' | 'wrong'>('all')

  // ---- Review analysis (global) ----
  const [mastery, setMastery] = useState<any>(null)
  const [masteryLoading, setMasteryLoading] = useState(false)
  const [reviewStats, setReviewStats] = useState<any>(null)
  const [reviewStatsLoading, setReviewStatsLoading] = useState(false)
  const [answerHistory, setAnswerHistory] = useState<any[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyPage, setHistoryPage] = useState(1)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [filterCorrect, setFilterCorrect] = useState<boolean | undefined>(undefined)
  const [filterKpId, setFilterKpId] = useState<string | undefined>(undefined)
  const [kpList, setKpList] = useState<any[]>([])
  const [reviewSubTab, setReviewSubTab] = useState('mastery')

  // ---- Exam state ----
  const [markedQuestions, setMarkedQuestions] = useState<Set<string>>(new Set())
  const [answerSheetOpen, setAnswerSheetOpen] = useState(false)
  const autoSaveTimer = useRef<ReturnType<typeof setInterval> | null>(null)
  const toggleMark = (qid: string) => setMarkedQuestions(prev => {
    const next = new Set(prev)
    next.has(qid) ? next.delete(qid) : next.add(qid)
    return next
  })

  // ---- Load bank ----
  useEffect(() => { refreshBank() }, [bankFilter])
  const refreshBank = useCallback(() => {
    setQuestionsLoading(true)
    const params: any = { limit: 200 }
    if (bankFilter.type) params.question_type = bankFilter.type
    if (bankFilter.cognitive) params.cognitive_level = bankFilter.cognitive
    listQuestions(params).then(setAllQuestions).catch(console.error).finally(() => setQuestionsLoading(false))
  }, [bankFilter])

  // ===== GENERATION =====
  const handleGenerate = async () => {
    const effectiveDocId = docId || selectedDoc
    if (!effectiveDocId) { message.warning('请先选择一份文档作为出题素材'); return }
    setGenerating(true)
    setPreviewQuestions([])
    setSelectedIds(new Set())
    try {
      const result = await generateQuestions({
        document_id: effectiveDocId,
        question_type: genConfig.question_type,
        count: genConfig.count,
        difficulty: genConfig.difficulty,
        difficulty_score: genConfig.difficulty_score,
        cognitive_level: genConfig.cognitive_level,
        enable_review: genConfig.enable_review,
        preview: true,
      })
      const qs = result.questions || []
      setPreviewQuestions(qs)
      setSelectedIds(new Set(qs.map((_: any, i: number) => i)))
      const reviewed = result.reviewed_count || 0
      message.success(`已生成 ${qs.length} 题${reviewed > 0 ? `（${reviewed} 道通过AI审核）` : ''}`)
    } catch (e: any) {
      message.error(`生成失败: ${e.response?.data?.detail || e.message}`)
    } finally { setGenerating(false) }
  }

  // Quick quiz: generate → auto-save → create exam → switch to exam tab
  const handleQuickQuiz = async () => {
    const effectiveDocId = docId || selectedDoc
    if (!effectiveDocId) { message.warning('请先选择一份文档'); return }
    setGenerating(true)
    try {
      const result = await generateQuestions({
        document_id: effectiveDocId,
        question_type: genConfig.question_type,
        count: genConfig.count,
        difficulty: genConfig.difficulty,
        difficulty_score: genConfig.difficulty_score,
        cognitive_level: genConfig.cognitive_level,
        enable_review: genConfig.enable_review,
        preview: true,
      })
      const qs = result.questions || []
      if (qs.length === 0) { message.warning('未能生成题目，请重试'); return }

      // Auto-save all to bank
      const saveResult = await saveToBank({ questions: qs })
      const ids = saveResult.question_ids || []

      // Create exam
      const exam = await createExam({ title: `快速测验-${new Date().toLocaleDateString()}`, question_ids: ids })
      setCurrentExam(exam)
      setResults(null as any)
      reset()
      setPreviewQuestions([])
      refreshBank()
      setActiveTab('exam')
      message.success(`快速测验已就绪: ${exam.question_count} 题`)
    } catch (e: any) {
      message.error(`快速测验失败: ${e.response?.data?.detail || e.message}`)
    } finally { setGenerating(false) }
  }

  // ---- Selection helpers ----
  const toggleSelect = (idx: number) => setSelectedIds(prev => { const n = new Set(prev); n.has(idx) ? n.delete(idx) : n.add(idx); return n })
  const selectAll = () => setSelectedIds(new Set(previewQuestions.map((_, i) => i)))
  const deselectAll = () => setSelectedIds(new Set())
  const invertSelect = () => setSelectedIds(prev => { const n = new Set<number>(); previewQuestions.forEach((_, i) => { if (!prev.has(i)) n.add(i) }); return n })

  // ---- Save to bank ----
  const handleSaveToBank = async () => {
    const selected = previewQuestions.filter((_, i) => selectedIds.has(i))
    if (!selected.length) { message.warning('请勾选题目'); return }
    setSaving(true)
    try {
      const result = await saveToBank({ questions: selected })
      message.success(`已入库 ${result.saved_count} 题`)
      setPreviewQuestions([])
      setSelectedIds(new Set())
      refreshBank()
    } catch (e: any) { message.error('入库失败') }
    finally { setSaving(false) }
  }

  // ---- Create exam from preview ----
  const handleCreateExam = async () => {
    const selected = previewQuestions.filter((_, i) => selectedIds.has(i))
    if (!selected.length) { message.warning('请勾选题目'); return }
    setSaving(true)
    try {
      const saveResult = await saveToBank({ questions: selected })
      const exam = await createExam({ title: `测验-${new Date().toLocaleDateString()}`, question_ids: saveResult.question_ids || [] })
      setCurrentExam(exam)
      setResults(null as any)
      reset()
      setPreviewQuestions([])
      setSelectedIds(new Set())
      refreshBank()
      setActiveTab('exam')
      message.success(`试卷已创建: ${exam.question_count} 题`)
    } catch (e: any) { message.error('创建失败') }
    finally { setSaving(false) }
  }

  // ---- Create exam from bank ----
  const handleCreateExamFromBank = async () => {
    if (!bankSelected.size) { message.warning('请勾选题目'); return }
    try {
      const exam = await createExam({ title: `测验-${new Date().toLocaleDateString()}`, question_ids: Array.from(bankSelected) })
      setCurrentExam(exam)
      setResults(null as any)
      reset()
      setBankSelected(new Set())
      setActiveTab('exam')
      message.success(`试卷已创建: ${exam.question_count} 题`)
    } catch (e: any) { message.error('创建失败') }
  }

  // ---- 一键刷题 (all filtered questions) ----
  const handleStartPractice = async () => {
    if (!allQuestions.length) { message.warning('题库为空，请先生成题目'); return }
    const ids = allQuestions.map((q: any) => q.id)
    try {
      const exam = await createExam({ title: `刷题练习-${new Date().toLocaleDateString()}`, question_ids: ids })
      setCurrentExam(exam)
      setResults(null as any)
      reset()
      setActiveTab('exam')
      message.success(`已加载 ${exam.question_count} 题，开始刷题！`)
    } catch (e: any) { message.error('创建失败') }
  }

  // ---- 随机刷题 ----
  const handleRandomPractice = async (count: number = 10) => {
    if (!allQuestions.length) { message.warning('题库为空，请先生成题目'); return }
    const shuffled = [...allQuestions].sort(() => Math.random() - 0.5)
    const picked = shuffled.slice(0, Math.min(count, shuffled.length))
    const ids = picked.map((q: any) => q.id)
    try {
      const exam = await createExam({ title: `随机刷题-${new Date().toLocaleDateString()}`, question_ids: ids })
      setCurrentExam(exam)
      setResults(null as any)
      reset()
      setActiveTab('exam')
      message.success(`随机抽取 ${exam.question_count} 题，开始刷题！`)
    } catch (e: any) { message.error('创建失败') }
  }

  // ---- 单题练习 ----
  const handlePracticeSingle = async (qid: string) => {
    try {
      const exam = await createExam({ title: `单题练习-${new Date().toLocaleDateString()}`, question_ids: [qid] })
      setCurrentExam(exam)
      setResults(null as any)
      reset()
      setActiveTab('exam')
      message.success('开始单题练习')
    } catch (e: any) { message.error('创建失败') }
  }

  // ---- Bank ops ----
  const handleBankDelete = async () => {
    if (!bankSelected.size) return
    Modal.confirm({
      title: `确认删除 ${bankSelected.size} 道题目？`, content: '删除后不可恢复，关联的错题记录也会失效。',
      okText: '确认删除', okType: 'danger', cancelText: '取消',
      onOk: async () => {
        await deleteQuestionsBatch(Array.from(bankSelected))
        message.success(`已删除 ${bankSelected.size} 题`)
        setBankSelected(new Set())
        refreshBank()
      },
    })
  }

  // ---- Submit exam ----
  const handleSubmit = async () => {
    if (!currentExam) return
    try {
      const result = await submitExam({ paper_id: currentExam.paper_id, answers: userAnswers })
      setResults(result)
      // Clean up auto-save after successful submit
      localStorage.removeItem(`exam_progress_${currentExam.paper_id}`)
      if (autoSaveTimer.current) clearInterval(autoSaveTimer.current)
      message.success(`得分: ${result.score}/${result.total * 5} (${result.percentage}%)`)
    } catch (e: any) { message.error('提交失败') }
  }

  // ---- Errors ----
  const loadErrors = async () => {
    setErrorsLoading(true)
    try { setErrorQuestions((await getErrorQuestions()) || []) }
    catch { message.error('加载错题失败') }
    finally { setErrorsLoading(false) }
  }
  const handleGenerateVariants = async (errorId: string) => {
    // Confirm before replacing current exam
    if (currentExam) {
      Modal.confirm({
        title: '生成变式题将替换当前试卷', content: '当前进行中的试卷将被替换，是否继续？',
        okText: '继续', cancelText: '取消',
        onOk: async () => {
          setVariantGenerating(errorId)
          try {
            const result = await generateVariants(errorId, 3)
            const variants = result.questions || []
            if (variants.length > 0) {
              const exam = await createExam({ title: `变式练习-${new Date().toLocaleDateString()}`, question_ids: variants.map((q: any) => q.id) })
              setCurrentExam(exam); setResults(null as any); reset(); setActiveTab('exam')
              message.success(`已生成 ${variants.length} 道变式题`)
            }
          } catch { message.error('变式题生成失败') }
          finally { setVariantGenerating(null) }
        },
      })
      return
    }
    setVariantGenerating(errorId)
    try {
      const result = await generateVariants(errorId, 3)
      const variants = result.questions || []
      if (variants.length > 0) {
        const exam = await createExam({ title: `变式练习-${new Date().toLocaleDateString()}`, question_ids: variants.map((q: any) => q.id) })
        setCurrentExam(exam); setResults(null as any); reset(); setActiveTab('exam')
        message.success(`已生成 ${variants.length} 道变式题`)
      }
    } catch { message.error('变式题生成失败') }
    finally { setVariantGenerating(null) }
  }

  // ---- Review analysis loaders ----
  const loadMastery = async () => {
    setMasteryLoading(true)
    try { setMastery(await getMasteryAnalysis()) }
    catch { message.error('加载掌握度分析失败') }
    finally { setMasteryLoading(false) }
  }
  const loadReviewStats = async () => {
    setReviewStatsLoading(true)
    try { setReviewStats(await getReviewStats()) }
    catch { message.error('加载统计数据失败') }
    finally { setReviewStatsLoading(false) }
  }
  const loadKpList = async () => {
    try { const data = await getReviewKnowledgePoints(); setKpList(data.items || []) }
    catch { /* silent */ }
  }
  const loadHistory = useCallback(async (page?: number, correct?: boolean, kpId?: string) => {
    setHistoryLoading(true)
    try {
      const p = page || historyPage
      const data = await getAnswerHistory({
        page: p, page_size: 20,
        is_correct: correct !== undefined ? correct : filterCorrect,
        kp_id: kpId || filterKpId,
      })
      setAnswerHistory(data.items || [])
      setHistoryTotal(data.total || 0)
      setHistoryPage(p)
    } catch { message.error('加载答题历史失败') }
    finally { setHistoryLoading(false) }
  }, [historyPage, filterCorrect, filterKpId])
  const handleHistoryFilter = (type: 'correct' | 'kp', value: any) => {
    if (type === 'correct') { setFilterCorrect(value); loadHistory(1, value, undefined) }
    else { setFilterKpId(value); loadHistory(1, undefined, value) }
  }

  // ---- Review view component ----
  const ReviewView = ({ questions, results, filter }: { questions: any[]; results: any; filter: 'all' | 'wrong' }) => {
    const filteredDetails = results.details.filter((d: any) => filter === 'all' || !d.is_correct)
    const wrongCount = results.total - results.correct

    if (filteredDetails.length === 0) {
      return (
        <Card style={{ textAlign: 'center', padding: 40 }}>
          <TrophyOutlined style={{ fontSize: 48, color: '#52c41a', marginBottom: 16 }} />
          <p style={{ fontSize: 16, color: '#52c41a' }}>全部正确，太棒了！</p>
        </Card>
      )
    }

    return (
      <div>
        {/* Quick-jump question number buttons */}
        <Card size="small" style={{ marginBottom: 16, background: '#fafafa' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 13, color: '#666', whiteSpace: 'nowrap' }}>跳转:</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {filteredDetails.map((d: any, idx: number) => {
                const q = questions.find((q: any) => q.id === d.question_id)
                const qIdx = questions.indexOf(q)
                return (
                  <Tooltip key={d.question_id} title={`第${qIdx + 1}题 ${d.is_correct ? '✓' : '✗'}`}>
                    <Button
                      size="small"
                      style={{
                        width: 32, height: 28, padding: 0, fontSize: 12,
                        background: d.is_correct ? '#f6ffed' : '#fff2f0',
                        borderColor: d.is_correct ? '#b7eb8f' : '#ffa39e',
                      }}
                      onClick={() => {
                        const el = document.getElementById(`review-${d.question_id}`)
                        el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
                      }}
                    >
                      {qIdx + 1}
                    </Button>
                  </Tooltip>
                )
              })}
            </div>
          </div>
          <div style={{ fontSize: 12, color: '#888' }}>
            <Tag color="green">✓ 正确</Tag> <Tag color="red">✗ 错误</Tag> 点击题号快速跳转
            {filter === 'wrong' && <Tag color="red" style={{ marginLeft: 8 }}>仅显示错题 ({wrongCount})</Tag>}
          </div>
        </Card>

        {/* Review cards */}
        {filteredDetails.map((d: any, idx: number) => {
          const q = questions.find((q: any) => q.id === d.question_id)
          if (!q) return null
          const qIdx = questions.indexOf(q)
          const isCorrect = d.is_correct

          return (
            <Card
              id={`review-${d.question_id}`}
              key={d.question_id}
              size="small"
              style={{ marginBottom: 12 }}
              title={
                <Space>
                  <Tag color={isCorrect ? 'green' : 'red'} style={{ fontWeight: 600 }}>
                    {isCorrect ? '✓' : '✗'} 第{qIdx + 1}题
                  </Tag>
                  <Tag>{typeLabels[q.question_type] || q.question_type}</Tag>
                  {q.cognitive_level && (
                    <Tag color={COGNITIVE_LEVEL_COLORS[q.cognitive_level as CognitiveLevel] || 'default'}>
                      {COGNITIVE_LEVEL_LABELS[q.cognitive_level as CognitiveLevel] || q.cognitive_level}
                    </Tag>
                  )}
                </Space>
              }
            >
              <div style={{ fontWeight: 500, marginBottom: 12, fontSize: 15 }}>{q.question_text}</div>

              {/* User answer vs correct answer */}
              <Row gutter={[16, 8]}>
                <Col xs={24} sm={12}>
                  <div style={{ padding: '8px 12px', borderRadius: 6, background: isCorrect ? '#f6ffed' : '#fff2f0', border: `1px solid ${isCorrect ? '#b7eb8f' : '#ffa39e'}` }}>
                    <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>你的答案</div>
                    <div style={{ fontWeight: 500, wordBreak: 'break-all' }}>{d.user_answer || '(未作答)'}</div>
                  </div>
                </Col>
                {!isCorrect && (
                  <Col xs={24} sm={12}>
                    <div style={{ padding: '8px 12px', borderRadius: 6, background: '#f6ffed', border: '1px solid #b7eb8f' }}>
                      <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>正确答案</div>
                      <div style={{ fontWeight: 500, color: '#52c41a', wordBreak: 'break-all' }}>{d.correct_answer}</div>
                    </div>
                  </Col>
                )}
              </Row>

              {/* Analysis */}
              {(q.analysis || d.analysis) && (
                <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 6, background: '#fafafa', fontSize: 13, color: '#555', lineHeight: 1.6 }}>
                  <span style={{ fontWeight: 500, color: '#333' }}>解析: </span>
                  {d.analysis || q.analysis}
                </div>
              )}
            </Card>
          )
        })}
      </div>
    )
  }

  // ---- Render question card ----
  const renderQuestion = (q: any, index: number) => (
    <div id={`question-${q.id}`} key={q.id}>
      <QuestionCard question={q} index={index}
        userAnswer={userAnswers[q.id] || ''}
        onAnswerChange={(qid, ans) => setAnswer(qid, ans)}
        showResults={!!results}
        result={results?.details?.find((d: any) => d.question_id === q.id)}
        marked={markedQuestions.has(q.id)}
        onToggleMark={toggleMark} />
    </div>
  )

  // ===== TAB: 出题 =====
  const generateTab = (
    <div>
      <Card title="出题配置" size="small" style={{ marginBottom: 16 }}>
        <Space wrap size={[12, 8]} style={{ width: '100%' }}>
          <Select
            placeholder="选择出题素材文档"
            value={docId || undefined}
            onChange={(v) => { setDocId(v); setSelectedDoc(v) }}
            options={docs.map((d: any) => ({ value: d.id, label: d.filename || d.id }))}
            style={{ minWidth: 200 }}
            showSearch
            filterOption={(input, option) => (option?.label as string || '').toLowerCase().includes(input.toLowerCase())}
            notFoundContent="暂无文档，请先上传"
            allowClear
          />
          <Select value={genConfig.question_type} onChange={v => setGenConfig(g => ({ ...g, question_type: v }))}
            options={questionTypes} style={{ width: 90 }} />
          <Select value={genConfig.cognitive_level} onChange={v => setGenConfig(g => ({ ...g, cognitive_level: v }))}
            options={cognitiveLevels} style={{ width: 105 }} />
          <Tooltip title={`难度: ${genConfig.difficulty_score.toFixed(2)}`}>
            <Slider value={genConfig.difficulty_score} onChange={v => {
              const val = v as number
              setGenConfig(g => ({ ...g, difficulty_score: val, difficulty: val <= 0.35 ? 'easy' : val <= 0.65 ? 'medium' : 'hard' }))
            }} min={0.05} max={1.0} step={0.05} style={{ width: 80, margin: 0 }}
              tooltip={{ formatter: v => `${(v as number).toFixed(2)}` }} />
          </Tooltip>
          <Select value={genConfig.count} onChange={v => setGenConfig(g => ({ ...g, count: v }))}
            options={[3, 5, 10, 15].map(n => ({ value: n, label: `${n}题` }))} />
          <Button size="small" icon={<SafetyCertificateOutlined />}
            type={genConfig.enable_review ? 'primary' : 'default'} ghost={!genConfig.enable_review}
            onClick={() => setGenConfig(g => ({ ...g, enable_review: !g.enable_review }))}>
            AI审核
          </Button>
          <Button icon={<RobotOutlined />} type="default" loading={generating} onClick={handleGenerate}>
            生成预览
          </Button>
          <Button icon={<ThunderboltOutlined />} type="primary" loading={generating} onClick={handleQuickQuiz}>
            快速测验
          </Button>
        </Space>
        <div style={{ marginTop: 8, color: '#999', fontSize: 12 }}>
          「生成预览」先看题目再决定入库 ｜ 「快速测验」生成后直接开始答题
        </div>
      </Card>

      {generating && (
        <div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /><p style={{ marginTop: 12 }}>AI 正在出题...</p></div>
      )}

      {!generating && previewQuestions.length > 0 && (
        <Card title={<Space><Badge count={selectedIds.size} style={{ backgroundColor: '#1677ff' }}><Tag color="blue">预览结果</Tag></Badge><Tag>{previewQuestions.length} 题</Tag></Space>}
          extra={
            <Space>
              <Button size="small" onClick={selectAll} icon={<CheckSquareOutlined />}>全选</Button>
              <Button size="small" onClick={deselectAll} icon={<BorderOutlined />}>取消</Button>
              <Button size="small" onClick={invertSelect} icon={<SelectOutlined />}>反选</Button>
              <Button size="small" type="primary" icon={<InboxOutlined />} loading={saving} onClick={handleSaveToBank}>
                入库 ({selectedIds.size})
              </Button>
              <Button size="small" icon={<PlayCircleOutlined />} loading={saving} onClick={handleCreateExam}>
                组卷答题
              </Button>
            </Space>
          }>
          <List size="small" bordered dataSource={previewQuestions} style={{ maxHeight: 520, overflow: 'auto' }}
            renderItem={(q: any, i: number) => (
              <List.Item key={i} style={{ cursor: 'pointer', background: selectedIds.has(i) ? '#f0f5ff' : undefined }}
                onClick={() => toggleSelect(i)}>
                <Space align="start" style={{ width: '100%' }}>
                  <Checkbox checked={selectedIds.has(i)} onChange={() => toggleSelect(i)} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500, marginBottom: 4 }}>{q.question_text}</div>
                    <Space size={4} wrap>
                      <Tag color="blue">{typeLabels[q.question_type] || q.question_type}</Tag>
                      <Tag color={COGNITIVE_LEVEL_COLORS[q.cognitive_level as CognitiveLevel] || 'default'}>
                        {COGNITIVE_LEVEL_LABELS[q.cognitive_level as CognitiveLevel] || q.cognitive_level}
                      </Tag>
                      <Progress percent={Math.round((q.difficulty_score ?? 0.5) * 100)} size="small" style={{ width: 60 }}
                        strokeColor={(q.difficulty_score ?? 0.5) <= 0.35 ? '#52c41a' : (q.difficulty_score ?? 0.5) <= 0.65 ? '#faad14' : '#ff4d4f'}
                        format={() => diffLabel(q.difficulty_score ?? 0.5)} />
                      {q.reviewed && (
                        <Tag color={q.review_total >= 3.2 ? 'green' : q.review_total >= 2.4 ? 'orange' : 'red'}>
                          质量{q.review_total?.toFixed(1)}
                        </Tag>
                      )}
                    </Space>
                  </div>
                </Space>
              </List.Item>
            )} />
        </Card>
      )}
    </div>
  )

  // ===== TAB: 答题 =====
  const questionCount = currentExam?.questions?.length || 0
  const answeredCount = Object.keys(userAnswers).length

  const examTab = (
    <div>
      {!currentExam ? (
        <Card>
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <FormOutlined style={{ fontSize: 64, marginBottom: 16 }} />
            <p>暂无进行中的试卷</p>
            <p>请先在「出题」Tab生成题目并组卷，或在「题库」中选择题目组卷</p>
            <Button type="primary" onClick={() => setActiveTab('generate')}>去出题</Button>
          </div>
        </Card>
      ) : (
        <Row gutter={16}>
          {/* Main exam area */}
          <Col flex="1" style={{ minWidth: 0 }}>
            <Card
              title={currentExam.title || '当前试卷'}
              extra={
                <Space>
                  {/* Answer sheet button */}
                  <Button icon={<OrderedListOutlined />} onClick={() => setAnswerSheetOpen(true)}>
                    答题卡 ({answeredCount}/{questionCount})
                  </Button>
                  {!results ? (
                    <Tooltip title={answeredCount < questionCount / 2
                      ? `请至少回答 ${Math.ceil(questionCount / 2)} 题` : '提交试卷'}>
                      <Button type="primary" size="large" onClick={handleSubmit}
                        disabled={answeredCount < questionCount / 2}>
                        提交 ({answeredCount}/{questionCount})
                      </Button>
                    </Tooltip>
                  ) : (
                    <Space>
                      <Button onClick={() => {
                        setCurrentExam(null as any); setResults(null as any); reset()
                        setMarkedQuestions(new Set())
                        setReviewMode('all'); setReviewFilter('all')
                        localStorage.removeItem(`exam_progress_${currentExam.paper_id}`)
                      }} icon={<ReloadOutlined />}>返回</Button>
                      <Button icon={<BugOutlined />} onClick={() => { loadErrors(); setActiveTab('errors') }}>错题</Button>
                      <Button icon={<SaveOutlined />} onClick={() => {
                        const saveKey = `exam_progress_${currentExam.paper_id}`
                        const progress = { answers: useQuizStore.getState().userAnswers, marked: Array.from(markedQuestions), savedAt: new Date().toISOString() }
                        localStorage.setItem(saveKey, JSON.stringify(progress))
                        message.success('进度已保存')
                      }}>保存进度</Button>
                    </Space>
                  )}
                </Space>
              }>
              {results && (
                <>
                  <Card size="small" style={{ marginBottom: 16, background: '#f0f5ff' }}>
                    <Space wrap>
                      <TrophyOutlined style={{ fontSize: 24, color: '#faad14' }} />
                      <span style={{ fontSize: 18, fontWeight: 600 }}>{results.score}/{results.total * 5} ({results.percentage}%)</span>
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
                              <div style={{ fontSize: 12, color: stats.accuracy >= 70 ? '#52c41a' : '#ff4d4f' }}>{stats.accuracy}%</div>
                            </Card>
                          </Col>
                        ))}
                      </Row>
                    </Card>
                  )}

                  {/* View toggle: 全部题目 / 答题回顾 */}
                  <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                    <Segmented
                      value={reviewMode}
                      onChange={v => setReviewMode(v as 'all' | 'review')}
                      options={[
                        { label: '全部题目', value: 'all' },
                        { label: '答题回顾', value: 'review' },
                      ]}
                    />
                    {reviewMode === 'review' && (
                      <Space>
                        <Segmented
                          size="small"
                          value={reviewFilter}
                          onChange={v => setReviewFilter(v as 'all' | 'wrong')}
                          options={[
                            { label: `全部(${results.total})`, value: 'all' },
                            { label: `仅错题(${results.total - results.correct})`, value: 'wrong' },
                          ]}
                        />
                        {results.total - results.correct > 0 && (
                          <Button size="small" type="primary" danger icon={<ReloadOutlined />}
                            onClick={() => {
                              const wrongIds = results.details
                                .filter((d: any) => !d.is_correct)
                                .map((d: any) => d.question_id)
                              if (!wrongIds.length) { message.warning('没有错题'); return }
                              Modal.confirm({
                                title: '错题重练', content: `将用 ${wrongIds.length} 道错题创建新试卷，是否继续？`,
                                okText: '开始重练', cancelText: '取消',
                                onOk: async () => {
                                  try {
                                    const exam = await createExam({ title: `错题重练-${new Date().toLocaleDateString()}`, question_ids: wrongIds })
                                    setCurrentExam(exam); setResults(null as any); reset()
                                    setMarkedQuestions(new Set()); setReviewMode('all'); setReviewFilter('all')
                                    message.success(`错题重练已就绪: ${exam.question_count} 题`)
                                  } catch (e: any) { message.error('创建失败') }
                                },
                              })
                            }}>
                            错题重练
                          </Button>
                        )}
                      </Space>
                    )}
                  </div>
                </>
              )}

              {/* Question list / Review view */}
              {reviewMode === 'review' && results ? (
                <ReviewView
                  questions={currentExam?.questions || []}
                  results={results}
                  filter={reviewFilter}
                />
              ) : (
                currentExam?.questions?.map((q: any, i: number) => renderQuestion(q, i))
              )}
            </Card>
          </Col>

          {/* Answer sheet drawer */}
          <Drawer
            title={<Space><OrderedListOutlined /> 答题卡 <Tag>{answeredCount}/{questionCount} 已答</Tag><Tag color="orange">{markedQuestions.size} 标记</Tag></Space>}
            placement="right"
            width={280}
            open={answerSheetOpen}
            onClose={() => setAnswerSheetOpen(false)}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {currentExam?.questions?.map((q: any, i: number) => {
                const answered = !!userAnswers[q.id]
                const isMarked = markedQuestions.has(q.id)
                const isCorrect = results?.details?.find((d: any) => d.question_id === q.id)?.is_correct
                let bgColor = '#f0f0f0' // unanswered
                if (answered && !results) bgColor = '#e6f7ff' // answered, not yet graded
                if (isMarked) bgColor = '#fff7e6' // marked
                if (results && isCorrect) bgColor = '#f6ffed' // correct
                if (results && !isCorrect) bgColor = '#fff2f0' // wrong

                return (
                  <Tooltip key={q.id} title={`${i + 1}. ${(q.question_text || '').slice(0, 40)}...`}>
                    <Button
                      size="small"
                      style={{ width: 36, height: 36, background: bgColor, borderColor: isMarked ? '#faad14' : undefined }}
                      onClick={() => {
                        setAnswerSheetOpen(false)
                        // Scroll to question
                        const el = document.getElementById(`question-${q.id}`)
                        el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
                      }}
                    >
                      {isMarked ? <StarOutlined style={{ color: '#faad14', fontSize: 12 }} /> : i + 1}
                    </Button>
                  </Tooltip>
                )
              })}
            </div>
            <div style={{ marginTop: 16, fontSize: 12, color: '#888' }}>
              <div><Tag color="blue">已答</Tag> <Tag>未答</Tag> <Tag color="orange">标记</Tag></div>
              <div style={{ marginTop: 8 }}>点击题号快速跳转</div>
            </div>
          </Drawer>
        </Row>
      )}
    </div>
  )

  // ===== TAB: 题库 =====
  const bankTab = (
    <Card title={<Space><InboxOutlined /> 题库 <Badge count={allQuestions.length} style={{ backgroundColor: '#1677ff' }} /></Space>}
      extra={
        <Space wrap>
          <Select allowClear placeholder="题型" style={{ width: 90 }} value={bankFilter.type}
            onChange={v => setBankFilter(f => ({ ...f, type: v }))} options={questionTypes} />
          <Select allowClear placeholder="认知层次" style={{ width: 105 }} value={bankFilter.cognitive}
            onChange={v => setBankFilter(f => ({ ...f, cognitive: v }))} options={cognitiveLevels} />
          <Button icon={<PlayCircleOutlined />} disabled={!bankSelected.size} onClick={handleCreateExamFromBank}>
            组卷 ({bankSelected.size})
          </Button>
          <Button danger icon={<DeleteOutlined />} disabled={!bankSelected.size} onClick={handleBankDelete}>
            删除 ({bankSelected.size})
          </Button>
        </Space>
      }>
      {/* 刷题快捷操作栏 */}
      <Card size="small" style={{ marginBottom: 16, background: '#f6ffed', borderColor: '#b7eb8f' }}>
        <Space wrap>
          <Button type="primary" icon={<ThunderboltOutlined />} size="large"
            disabled={!allQuestions.length}
            onClick={handleStartPractice}>
            一键刷题 ({allQuestions.length}题)
          </Button>
          <Tooltip title="从题库中随机抽题练习">
            <Button icon={<SyncOutlined />} disabled={!allQuestions.length}
              onClick={() => handleRandomPractice(10)}>
              随机10题
            </Button>
          </Tooltip>
          <Button icon={<SyncOutlined />} disabled={!allQuestions.length}
            onClick={() => handleRandomPractice(5)}>
            随机5题
          </Button>
          <Button icon={<SyncOutlined />} disabled={!allQuestions.length}
            onClick={() => handleRandomPractice(20)}>
            随机20题
          </Button>
          <span style={{ fontSize: 12, color: '#888' }}>
            无需勾选，直接刷题；筛选条件对「一键刷题」和「随机刷题」生效
          </span>
        </Space>
      </Card>

      <Table loading={questionsLoading} dataSource={allQuestions} rowKey="id" size="middle"
        locale={{ emptyText: '暂无题目，去「出题」Tab生成' }}
        rowSelection={{ selectedRowKeys: Array.from(bankSelected), onChange: (keys) => setBankSelected(new Set(keys as string[])) }}
        columns={[
          { title: '题目', dataIndex: 'question_text', ellipsis: true,
            render: (v: string) => v || '(无文本)' },
          { title: '题型', dataIndex: 'question_type', width: 65,
            render: (v: string) => <Tag>{typeLabels[v] || v}</Tag> },
          { title: '认知', dataIndex: 'cognitive_level', width: 65,
            render: (v: string) => v ? <Tag color={COGNITIVE_LEVEL_COLORS[v as CognitiveLevel] || 'default'}>
              {COGNITIVE_LEVEL_LABELS[v as CognitiveLevel] || v}</Tag> : <span style={{ color: '#ccc' }}>—</span> },
          { title: '难度', dataIndex: 'difficulty_score', width: 75,
            render: (v: number, r: any) => {
              if (v != null) return <Progress percent={Math.round(v * 100)} size="small"
                strokeColor={v <= 0.35 ? '#52c41a' : v <= 0.65 ? '#faad14' : '#ff4d4f'} format={() => diffLabel(v)} />
              return <Tag color={r.difficulty === 'easy' ? 'green' : r.difficulty === 'hard' ? 'red' : 'orange'}>
                {r.difficulty === 'easy' ? '简单' : r.difficulty === 'hard' ? '困难' : '中等'}</Tag>
            } },
          { title: '操作', width: 80, fixed: 'right' as const,
            render: (_: any, record: any) => (
              <Button size="small" type="link" icon={<PlayCircleOutlined />}
                onClick={() => handlePracticeSingle(record.id)}>
                练习
              </Button>
            ) },
        ]}
        pagination={{ pageSize: 15, showSizeChanger: true, showTotal: t => `共 ${t} 题` }} />
    </Card>
  )

  // ===== TAB: 错题 =====
  const errorsTab = (
    <Card title={<Space><BugOutlined /> 错题本 ({errorQuestions.length})</Space>}
      extra={<Button onClick={loadErrors} loading={errorsLoading} icon={<ReloadOutlined />}>刷新</Button>}>
      {!errorQuestions.length && !errorsLoading ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
          <TrophyOutlined style={{ fontSize: 48, marginBottom: 16, color: '#52c41a' }} />
          <p>暂无错题</p>
          <Button type="primary" onClick={() => setActiveTab('exam')}>去答题</Button>
        </div>
      ) : (
        <List loading={errorsLoading} dataSource={errorQuestions}
          renderItem={(item: any) => (
            <List.Item key={item.error_id} actions={[
              <Button key="variant" type="primary" size="small" icon={<SyncOutlined />}
                loading={variantGenerating === item.error_id}
                onClick={() => handleGenerateVariants(item.error_id)}>
                变式题
              </Button>,
            ]}>
              <List.Item.Meta
                avatar={<Space direction="vertical" size={2} align="center">
                  <Tag color="red">错{item.error_count}次</Tag>
                  {item.question?.cognitive_level && (
                    <Tag color={COGNITIVE_LEVEL_COLORS[item.question.cognitive_level as CognitiveLevel] || 'default'} style={{ fontSize: 10 }}>
                      {COGNITIVE_LEVEL_LABELS[item.question.cognitive_level as CognitiveLevel] || item.question.cognitive_level}
                    </Tag>
                  )}
                </Space>}
                title={<div style={{ fontSize: 14 }}>{item.question?.question_text || '(无文本)'}</div>}
                description={
                  <Space direction="vertical" size={4}>
                    <Tag color="green">答案: {item.question?.answer}</Tag>
                    {item.question?.analysis && (
                      <div style={{ color: '#666', fontSize: 12 }}>解析: {item.question.analysis.slice(0, 150)}</div>
                    )}
                  </Space>
                } />
            </List.Item>
          )} />
      )}
    </Card>
  )

  // ===== TAB: 回顾分析 =====
  const reviewAnalysisTab = (
    <div>
      <Tabs activeKey={reviewSubTab} onChange={setReviewSubTab} size="small"
        tabBarStyle={{ marginBottom: 16 }}
        items={[
          {
            key: 'mastery',
            label: <span><TrophyOutlined /> 掌握度总览</span>,
            children: (
              <div>
                <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'flex-end' }}>
                  <Button icon={<ReloadOutlined />} onClick={loadMastery} loading={masteryLoading} size="small">刷新</Button>
                </div>
                <MasteryOverview analysis={mastery} loading={masteryLoading} />
                {!mastery && !masteryLoading && (
                  <Card size="small" style={{ textAlign: 'center', marginTop: 16 }}>
                    <Button type="primary" onClick={() => { loadMastery(); loadKpList(); loadReviewStats() }}>加载分析数据</Button>
                  </Card>
                )}
              </div>
            ),
          },
          {
            key: 'stats',
            label: <span><BarChartOutlined /> 数据统计</span>,
            children: (
              <div>
                {reviewStatsLoading ? (
                  <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
                ) : reviewStats ? (
                  <div>
                    <Row gutter={16} style={{ marginBottom: 24 }}>
                      <Col xs={12} sm={6}>
                        <Card size="small"><Statistic title="总答题数" value={reviewStats.total_answers} prefix={<FormOutlined />} /></Card>
                      </Col>
                      <Col xs={12} sm={6}>
                        <Card size="small"><Statistic title="正确数" value={reviewStats.correct_answers}
                          prefix={<CheckSquareOutlined />} valueStyle={{ color: '#52c41a' }} /></Card>
                      </Col>
                      <Col xs={12} sm={6}>
                        <Card size="small"><Statistic title="错误数" value={reviewStats.total_answers - reviewStats.correct_answers}
                          prefix={<BugOutlined />} valueStyle={{ color: '#ff4d4f' }} /></Card>
                      </Col>
                      <Col xs={12} sm={6}>
                        <Card size="small"><Statistic title="总正确率" value={reviewStats.overall_accuracy * 100}
                          suffix="%" precision={1} valueStyle={{ color: reviewStats.overall_accuracy >= 0.8 ? '#52c41a' : reviewStats.overall_accuracy >= 0.6 ? '#faad14' : '#ff4d4f' }} /></Card>
                      </Col>
                    </Row>
                    {reviewStats.recent_7_days?.length > 0 && (
                      <Card size="small" title="近7天答题趋势" style={{ marginBottom: 16 }}>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          {reviewStats.recent_7_days.map((day: any) => (
                            <Card key={day.date} size="small" style={{ flex: '1 1 100px', minWidth: 100, textAlign: 'center' }} bodyStyle={{ padding: '8px' }}>
                              <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>
                                {new Date(day.date).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })}
                              </div>
                              <div style={{ fontSize: 20, fontWeight: 600 }}>
                                {day.total > 0 ? `${Math.round((day.correct / day.total) * 100)}%` : '-'}
                              </div>
                              <div style={{ fontSize: 10, color: '#888' }}>{day.correct}/{day.total}</div>
                            </Card>
                          ))}
                        </div>
                      </Card>
                    )}
                    {Object.keys(reviewStats.cognitive_breakdown || {}).length > 0 && (
                      <Card size="small" title="认知层次分析">
                        <Row gutter={[12, 8]}>
                          {Object.entries(reviewStats.cognitive_breakdown).map(([level, data]: [string, any]) => (
                            <Col key={level} xs={12} sm={8} md={4}>
                              <Card size="small" style={{ textAlign: 'center' }} bodyStyle={{ padding: '10px 8px' }}>
                                <Tag color={COGNITIVE_LEVEL_COLORS[level as CognitiveLevel] || 'default'}>
                                  {COGNITIVE_LEVEL_LABELS[level as CognitiveLevel] || level}
                                </Tag>
                                <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4 }}>{data.correct}/{data.total}</div>
                                <Progress percent={Math.round(data.accuracy * 100)} size="small"
                                  strokeColor={data.accuracy >= 0.7 ? '#52c41a' : '#ff4d4f'} />
                              </Card>
                            </Col>
                          ))}
                        </Row>
                      </Card>
                    )}
                    <div style={{ marginTop: 12, textAlign: 'right' }}>
                      <Button icon={<ReloadOutlined />} onClick={loadReviewStats} loading={reviewStatsLoading} size="small">刷新</Button>
                    </div>
                  </div>
                ) : (
                  <Card size="small" style={{ textAlign: 'center', padding: 40 }}>
                    <Button type="primary" onClick={loadReviewStats}>加载统计数据</Button>
                  </Card>
                )}
              </div>
            ),
          },
          {
            key: 'history',
            label: <span><HistoryOutlined /> 答题历史</span>,
            children: (
              <Card>
                <Space wrap style={{ marginBottom: 16 }}>
                  <Select allowClear placeholder="按结果筛选" value={filterCorrect}
                    onChange={(v) => handleHistoryFilter('correct', v)} style={{ minWidth: 120 }}
                    options={[{ value: true, label: '正确' }, { value: false, label: '错误' }]} />
                  <Select allowClear showSearch placeholder="按知识点筛选" value={filterKpId}
                    onChange={(v) => handleHistoryFilter('kp', v)} style={{ minWidth: 200 }}
                    options={kpList.map((kp: any) => ({
                      value: kp.id,
                      label: `${kp.title}${kp.mastery != null ? ` (${(kp.mastery * 100).toFixed(0)}%)` : ''}`,
                    }))}
                    filterOption={(input: any, option: any) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())} />
                  <Button icon={<ReloadOutlined />} onClick={() => loadHistory(1)}>刷新</Button>
                  <Text style={{ fontSize: 12, color: '#888' }}>共 {historyTotal} 条记录</Text>
                </Space>
                <Table loading={historyLoading} dataSource={answerHistory} rowKey="record_id" size="small"
                  columns={[
                    { title: '题目', dataIndex: 'question_text', ellipsis: true, width: 260,
                      render: (v: string) => <Tooltip title={v}><Text style={{ fontSize: 13 }}>{v}</Text></Tooltip> },
                    { title: '类型', dataIndex: 'question_type', width: 65,
                      render: (v: string) => <Tag style={{ fontSize: 11 }}>{typeLabels[v] || v}</Tag> },
                    { title: '认知', dataIndex: 'cognitive_level', width: 65,
                      render: (v: string) => v ? <Tag color={COGNITIVE_LEVEL_COLORS[v as CognitiveLevel] || 'default'} style={{ fontSize: 10 }}>{COGNITIVE_LEVEL_LABELS[v as CognitiveLevel] || v}</Tag> : <span style={{ color: '#ccc' }}>-</span> },
                    { title: '结果', dataIndex: 'is_correct', width: 60,
                      render: (v: boolean) => v ? <Tag color="green">正确</Tag> : <Tag color="red">错误</Tag> },
                    { title: '用时', dataIndex: 'time_spent_ms', width: 65,
                      render: (v: number) => <Text style={{ fontSize: 12 }}>{v > 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}ms`}</Text> },
                    { title: '时间', dataIndex: 'answered_at', width: 90,
                      render: (v: string | null) => v ? new Date(v).toLocaleDateString() : '-' },
                  ]}
                  pagination={{
                    current: historyPage, pageSize: 20, total: historyTotal,
                    onChange: (page) => loadHistory(page),
                    showSizeChanger: true, pageSizeOptions: ['10', '20', '50'],
                    showTotal: (total) => `共 ${total} 条`,
                  }}
                  scroll={{ x: 700 }}
                  locale={{ emptyText: '暂无答题记录' }}
                />
              </Card>
            ),
          },
          {
            key: 'recommend',
            label: <span><RobotOutlined /> AI复习推荐</span>,
            children: <ReviewRecommendation onRefresh={loadMastery} />,
          },
        ]}
      />
    </div>
  )

  return (
    <Tabs activeKey={activeTab} onChange={setActiveTab}
      items={[
        { key: 'generate', label: <span><RobotOutlined /> 出题</span>, children: generateTab },
        { key: 'exam', label: <span><FormOutlined /> 答题{currentExam ? <Badge dot style={{ marginLeft: 4 }} /> : ''}</span>, children: examTab },
        { key: 'bank', label: <span><InboxOutlined /> 题库<Badge count={allQuestions.length} style={{ backgroundColor: '#1677ff', marginLeft: 4 }} overflowCount={999} /></span>, children: bankTab },
        { key: 'errors', label: <span><BugOutlined /> 错题{errorQuestions.length > 0 ? <Badge count={errorQuestions.length} style={{ backgroundColor: '#ff4d4f', marginLeft: 4 }} /> : ''}</span>, children: errorsTab },
        { key: 'review', label: <span><EyeOutlined /> 回顾分析</span>, children: reviewAnalysisTab },
      ]}
      style={{ minHeight: 'calc(100vh - 200px)' }}
    />
  )
}
