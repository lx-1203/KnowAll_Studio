import { useState, useEffect, useMemo, useCallback } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { App, Card, Table, Tag, Button, Select, Input, Space, Progress, Modal, Spin, Empty, Tooltip, Typography } from 'antd'
import { BookOutlined, SearchOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { getVocabulary, generateVocabulary, markVocabularyMastered, getDocumentDetail } from '../api'
import type { LanguageVocabulary } from '../types'
import type { ColumnsType } from 'antd/es/table'

const { Title, Text } = Typography

const PART_OF_SPEECH_OPTIONS = [
  { value: '', label: '全部词性' },
  { value: 'noun', label: '名词' },
  { value: 'verb', label: '动词' },
  { value: 'adjective', label: '形容词' },
  { value: 'adverb', label: '副词' },
  { value: 'other', label: '其他' },
]

const DIFFICULTY_OPTIONS = [
  { value: '', label: '全部难度' },
  { value: 'easy', label: '容易' },
  { value: 'medium', label: '中等' },
  { value: 'hard', label: '困难' },
]

const DIFFICULTY_COLORS: Record<string, string> = {
  easy: 'green',
  medium: 'orange',
  hard: 'red',
}

const DIFFICULTY_LABELS: Record<string, string> = {
  easy: '容易',
  medium: '中等',
  hard: '困难',
}

const POS_COLORS: Record<string, string> = {
  noun: 'blue',
  verb: 'cyan',
  adjective: 'geekblue',
  adverb: 'purple',
  other: 'default',
}

const POS_LABELS: Record<string, string> = {
  noun: '名词',
  verb: '动词',
  adjective: '形容词',
  adverb: '副词',
  other: '其他',
}

export default function LanguageLearningPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const params = useParams<{ docId?: string }>()
  const [searchParams] = useSearchParams()

  const docId = params.docId || searchParams.get('docId') || ''

  const [documentName, setDocumentName] = useState('')
  const [vocabulary, setVocabulary] = useState<LanguageVocabulary[]>([])
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [partOfSpeechFilter, setPartOfSpeechFilter] = useState('')
  const [difficultyFilter, setDifficultyFilter] = useState('')
  const [keywordFilter, setKeywordFilter] = useState('')
  const [summaryModalOpen, setSummaryModalOpen] = useState(false)
  const [summaryIdInput, setSummaryIdInput] = useState('')
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({})

  // Load document info to display the document name
  useEffect(() => {
    if (!docId) return
    getDocumentDetail(docId)
      .then((data: any) => {
        setDocumentName(data.filename || data.name || docId)
      })
      .catch(() => setDocumentName(docId))
  }, [docId])

  // Load vocabulary on mount and whenever docId changes
  useEffect(() => {
    if (!docId) return
    loadVocabulary()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docId])

  const loadVocabulary = useCallback(async () => {
    if (!docId) return
    setLoading(true)
    try {
      const data = await getVocabulary({ document_id: docId })
      const list = data.vocabularies || data.vocabulary || data.items || data || []
      setVocabulary(Array.isArray(list) ? list : [])
    } catch (e: any) {
      message.error('获取生词表失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }, [docId, message])

  // Client-side filtering
  const filteredVocab = useMemo(() => {
    let result = vocabulary
    if (partOfSpeechFilter) {
      result = result.filter(v => v.part_of_speech === partOfSpeechFilter)
    }
    if (difficultyFilter) {
      result = result.filter(v => v.difficulty === difficultyFilter)
    }
    if (keywordFilter.trim()) {
      const kw = keywordFilter.trim().toLowerCase()
      result = result.filter(v =>
        v.word.toLowerCase().includes(kw) ||
        v.definition.toLowerCase().includes(kw) ||
        (v.phonetic && v.phonetic.toLowerCase().includes(kw))
      )
    }
    return result
  }, [vocabulary, partOfSpeechFilter, difficultyFilter, keywordFilter])

  const masteredCount = vocabulary.filter(v => v.mastered).length
  const masteryPercent = vocabulary.length > 0
    ? Math.round((masteredCount / vocabulary.length) * 100)
    : 0

  // Open the generate modal
  const handleGenerate = () => {
    setSummaryModalOpen(true)
  }

  // Confirm generating vocabulary
  const confirmGenerate = async () => {
    setSummaryModalOpen(false)
    setGenerating(true)
    try {
      await generateVocabulary({
        document_id: docId,
        ...(summaryIdInput.trim() ? { summary_id: summaryIdInput.trim() } : {}),
      })
      message.success('生词表生成成功！')
      setSummaryIdInput('')
      await loadVocabulary()
    } catch (e: any) {
      message.error('生成生词表失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setGenerating(false)
    }
  }

  // Toggle mastered status for a word
  const handleMarkMastered = async (vocabId: string, currentMastered: boolean) => {
    setActionLoading(prev => ({ ...prev, [vocabId]: true }))
    try {
      await markVocabularyMastered(vocabId, !currentMastered)
      setVocabulary(prev =>
        prev.map(v => (v.id === vocabId ? { ...v, mastered: !currentMastered } : v))
      )
      message.success(!currentMastered ? '已标记为掌握' : '已取消掌握')
    } catch (e: any) {
      message.error('操作失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setActionLoading(prev => ({ ...prev, [vocabId]: false }))
    }
  }

  // Table column definitions
  const columns: ColumnsType<LanguageVocabulary> = [
    {
      title: '单词',
      dataIndex: 'word',
      key: 'word',
      width: 140,
      render: (text, record) => (
        <Text
          style={{
            fontWeight: 600,
            textDecoration: record.mastered ? 'line-through' : 'none',
            color: record.mastered ? '#999' : undefined,
          }}
        >
          {text}
        </Text>
      ),
    },
    {
      title: '音标',
      dataIndex: 'phonetic',
      key: 'phonetic',
      width: 140,
      render: (text) =>
        text ? (
          <Text type="secondary" style={{ fontFamily: 'monospace' }}>
            {text}
          </Text>
        ) : (
          <Text type="secondary">-</Text>
        ),
    },
    {
      title: '释义',
      dataIndex: 'definition',
      key: 'definition',
      ellipsis: { showTitle: false },
      render: (text) => (
        <Tooltip placement="topLeft" title={text}>
          <Text>{text}</Text>
        </Tooltip>
      ),
    },
    {
      title: '词性',
      dataIndex: 'part_of_speech',
      key: 'part_of_speech',
      width: 100,
      render: (pos) =>
        pos ? (
          <Tag color={POS_COLORS[pos] || 'default'}>{POS_LABELS[pos] || pos}</Tag>
        ) : (
          <Text type="secondary">-</Text>
        ),
    },
    {
      title: '难度',
      dataIndex: 'difficulty',
      key: 'difficulty',
      width: 80,
      render: (diff) => (
        <Tag color={DIFFICULTY_COLORS[diff] || 'default'}>
          {DIFFICULTY_LABELS[diff] || diff}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 110,
      render: (_, record) => (
        <Button
          size="small"
          type={record.mastered ? 'default' : 'primary'}
          disabled={record.mastered}
          loading={actionLoading[record.id]}
          onClick={() => handleMarkMastered(record.id, record.mastered)}
          style={
            record.mastered
              ? { borderColor: '#d9d9d9', color: '#999' }
              : { background: '#4f46e5', borderColor: '#4f46e5' }
          }
        >
          {record.mastered ? '已掌握' : '标记已掌握'}
        </Button>
      ),
    },
  ]

  // ── No docId: prompt user to select a document ──
  if (!docId) {
    return (
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 24px 0' }}>
        <Title level={3}>
          <BookOutlined style={{ marginRight: 8, color: '#4f46e5' }} />
          词汇学习
        </Title>
        <Card>
          <Empty description="未选择文档">
            <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
              请从资料库或知识总纲跳转到词汇学习页面
            </Text>
            <Button type="primary" onClick={() => navigate('/upload')}>
              前往资料库
            </Button>
          </Empty>
        </Card>
      </div>
    )
  }

  // ── Normal page with docId ──
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px 24px' }}>
      {/* Page header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          <BookOutlined style={{ marginRight: 8, color: '#4f46e5' }} />
          词汇学习 — {documentName || '加载中...'}
        </Title>
        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          loading={generating}
          onClick={handleGenerate}
          style={{ background: '#4f46e5', borderColor: '#4f46e5' }}
        >
          生成生词表
        </Button>
      </div>

      {/* Filter bar */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap size="middle">
          <Select
            value={partOfSpeechFilter}
            onChange={setPartOfSpeechFilter}
            options={PART_OF_SPEECH_OPTIONS}
            style={{ width: 130 }}
            placeholder="词性筛选"
          />
          <Select
            value={difficultyFilter}
            onChange={setDifficultyFilter}
            options={DIFFICULTY_OPTIONS}
            style={{ width: 130 }}
            placeholder="难度筛选"
          />
          <Input.Search
            placeholder="搜索单词..."
            value={keywordFilter}
            onChange={e => setKeywordFilter(e.target.value)}
            onSearch={setKeywordFilter}
            style={{ width: 240 }}
            allowClear
            prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
          />
          <Button
            icon={<ReloadOutlined />}
            onClick={loadVocabulary}
            loading={loading}
          >
            刷新
          </Button>
        </Space>
      </Card>

      {/* Main content: vocabulary table or empty state */}
      <Spin spinning={loading}>
        {vocabulary.length === 0 && !loading ? (
          <Card>
            <Empty description="该文档暂无生词表，请先生成">
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={handleGenerate}
                loading={generating}
              >
                生成生词表
              </Button>
            </Empty>
          </Card>
        ) : (
          <Card>
            <Table
              columns={columns}
              dataSource={filteredVocab}
              rowKey="id"
              pagination={{
                pageSize: 20,
                showSizeChanger: true,
                pageSizeOptions: ['10', '20', '50', '100'],
                showTotal: (total, range) =>
                  `${range[0]}-${range[1]} / ${total} 个单词`,
              }}
              size="middle"
              locale={{
                emptyText:
                  partOfSpeechFilter || difficultyFilter || keywordFilter
                    ? '筛选结果为空，请调整筛选条件'
                    : '暂无数据',
              }}
            />
          </Card>
        )}
      </Spin>

      {/* Statistics bar */}
      {vocabulary.length > 0 && (
        <Card size="small" style={{ marginTop: 16 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 16,
            }}
          >
            <Space size="large" wrap>
              <span>
                <Text type="secondary">共 </Text>
                <Text strong style={{ fontSize: 16 }}>
                  {vocabulary.length}
                </Text>
                <Text type="secondary"> 个单词</Text>
              </span>
              <span>
                <Text type="secondary">已掌握: </Text>
                <Text strong style={{ fontSize: 16, color: '#22c55e' }}>
                  {masteredCount}
                </Text>
              </span>
              <span>
                <Text type="secondary">掌握率: </Text>
                <Text strong style={{ fontSize: 16, color: '#4f46e5' }}>
                  {masteryPercent}%
                </Text>
              </span>
            </Space>
            <Progress
              percent={masteryPercent}
              size="small"
              style={{ minWidth: 200, maxWidth: 300 }}
              strokeColor="#4f46e5"
              trailColor="#e5e7eb"
            />
          </div>
        </Card>
      )}

      {/* Modal for optional summary_id input before generating */}
      <Modal
        title="生成生词表"
        open={summaryModalOpen}
        onOk={confirmGenerate}
        onCancel={() => {
          setSummaryModalOpen(false)
          setSummaryIdInput('')
        }}
        okText="开始生成"
        cancelText="取消"
        confirmLoading={generating}
      >
        <div style={{ marginBottom: 12 }}>
          <Text>
            将从文档 <Text strong>{documentName}</Text> 中提取生词并生成词汇表。
          </Text>
        </div>
        <div>
          <Text type="secondary">Summary ID（可选，如有知识总纲请填写）：</Text>
          <Input
            placeholder="输入 summary_id（可选）"
            value={summaryIdInput}
            onChange={e => setSummaryIdInput(e.target.value)}
            style={{ marginTop: 8 }}
            allowClear
          />
        </div>
      </Modal>
    </div>
  )
}
