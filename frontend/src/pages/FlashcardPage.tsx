import { useState, useEffect, useCallback } from 'react'
import { Card, Button, Space, App, Spin, Tag, Select, Input, Modal, Dropdown, Table, Progress } from 'antd'
import { RobotOutlined, SwapOutlined, RightOutlined, IdcardOutlined, DownloadOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { getDueCards, reviewCard, generateCards, listDecks, searchCards, getRelatedCards, generateDeckSummary } from '../api'
import { useAppStore, useFlashcardStore } from '../stores'
import ClozeRenderer from '../components/ClozeRenderer'
import CompareTable from '../components/CompareTable'

export default function FlashcardPage() {
  const { selectedDoc } = useAppStore()
  const { dueCards, currentIndex, isFlipped, reviewLimit, setDueCards, flip, next, prev, setReviewLimit } = useFlashcardStore()
  const { message } = App.useApp()
  const [loading, setLoading] = useState(false)
  const [decks, setDecks] = useState<any[]>([])
  const [genConfig, setGenConfig] = useState({ card_type: 'qa', count: 20, deck_name: '默认牌组' })
  const [genModalVisible, setGenModalVisible] = useState(false)
  const [genInput, setGenInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searching, setSearching] = useState(false)

  const loadDueCards = async () => {
    setLoading(true)
    try {
      const result = await getDueCards(20)
      setDueCards(result.cards || [])
    } catch (e: any) {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadDueCards(); listDecks().then(setDecks).catch(console.error) }, [])

  // ── Keyboard shortcuts ──────────────────────────────────────

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (genModalVisible) return  // Don't intercept when modal is open

      const card = dueCards[currentIndex]
      if (!card) return

      switch (e.key) {
        case ' ':
          e.preventDefault()
          flip()
          break
        case 'ArrowRight':
          e.preventDefault()
          if (currentIndex < dueCards.length - 1) next()
          break
        case 'ArrowLeft':
          e.preventDefault()
          prev()
          break
        case '1':
          if (isFlipped) { e.preventDefault(); handleReview(1) }
          break
        case '2':
          if (isFlipped) { e.preventDefault(); handleReview(2) }
          break
        case '3':
          if (isFlipped) { e.preventDefault(); handleReview(3) }
          break
        case '4':
          if (isFlipped) { e.preventDefault(); handleReview(4) }
          break
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [dueCards, currentIndex, isFlipped, genModalVisible])

  const handleExportAnki = async (deckId: string) => {
    try {
      const resp = await fetch(`/api/v1/flashcards/export/anki/${deckId}`)
      if (!resp.ok) throw new Error('Export failed')
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `deck_${deckId.slice(0, 8)}.apkg`; a.click()
      URL.revokeObjectURL(url)
      message.success('Anki 导出成功')
    } catch { message.error('导出失败') }
  }

  const handleReview = async (rating: number) => {
    const card = dueCards[currentIndex]
    if (!card) return
    try {
      const result = await reviewCard(card.id, rating)
      const ratingLabel = { 1: '完全忘记', 2: '困难想起', 3: '正常回忆', 4: '轻松想起' }[rating]
      message.success(`${ratingLabel} — 下次复习: ${result.next_review_at?.slice(0, 10) || '待定'}`)
      next()
    } catch (e: any) {
      message.error('提交失败')
    }
  }

  const handleGenerate = async () => {
    if (!genInput.trim()) { message.warning('请输入知识点文本'); return }
    setLoading(true)
    try {
      const result = await generateCards({
        knowledge_text: genInput,
        card_type: genConfig.card_type,
        count: genConfig.count,
        deck_name: genConfig.deck_name,
      })
      message.success(`已生成 ${result.generated_count} 张卡片`)
      setGenModalVisible(false)
      loadDueCards()
    } catch (e: any) {
      message.error('生成失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const result = await searchCards(searchQuery, 10)
      setSearchResults(result.results || [])
    } catch { message.error('搜索失败') }
    finally { setSearching(false) }
  }

  const card = dueCards[currentIndex]
  const ratingLabels = [
    { value: 1, label: '完全忘记', color: '#ff4d4f', key: '1' },
    { value: 2, label: '困难想起', color: '#faad14', key: '2' },
    { value: 3, label: '正常回忆', color: '#52c41a', key: '3' },
    { value: 4, label: '轻松想起', color: '#1890ff', key: '4' },
  ]

  // ── Render card content based on type ────────────────────────

  const renderCardContent = () => {
    if (!card) return null

    // Cloze: interactive fill-in-the-blanks
    if (card.card_type === 'cloze' && isFlipped) {
      return <ClozeRenderer front={card.front} back={card.back} hints={card.hints} />
    }

    // Compare: table rendering
    if (card.card_type === 'compare' && isFlipped) {
      return <CompareTable back={card.back} />
    }

    // Default QA and fallback
    return (
      <div>
        <div style={{ color: '#999', fontSize: 12, marginBottom: 8 }}>
          {isFlipped ? '背面 (答案)' : '正面 (问题)'}
        </div>
        <div style={{ fontWeight: 600, lineHeight: 1.8 }}>
          {isFlipped ? card.back : card.front}
        </div>
        {card.hints && !isFlipped && (
          <div style={{ marginTop: 16, color: '#aaa', fontSize: 13 }}>
            提示: {card.hints}
          </div>
        )}
      </div>
    )
  }

  return (
    <div>
      <Card title="记忆闪卡" extra={
        <Space>
          <Input.Search
            placeholder="搜索卡片..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onSearch={handleSearch}
            loading={searching}
            style={{ width: 200 }}
            enterButton={<SearchOutlined />}
          />
          <Button icon={<RobotOutlined />} type="primary" onClick={() => setGenModalVisible(true)}>
            AI 生成卡片
          </Button>
          <Dropdown menu={{ items: decks.map(d => ({ key: d.id, label: `导出 ${d.name} (${d.card_count}张)` })), onClick: ({ key }) => handleExportAnki(key) }}>
            <Button icon={<DownloadOutlined />}>导出Anki</Button>
          </Dropdown>
          <Button icon={<ReloadOutlined />} onClick={loadDueCards}>刷新</Button>
        </Space>
      }>
        {/* Search Results */}
        {searchResults.length > 0 && (
          <div style={{ marginBottom: 16, padding: 12, background: '#f6f8fa', borderRadius: 8 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>搜索结果 ({searchResults.length})</div>
            {searchResults.map(r => (
              <div key={r.id} style={{ padding: '8px 0', borderBottom: '1px solid #eee', cursor: 'pointer' }}
                onClick={() => setSearchResults([])}>
                <Tag>{r.card_type}</Tag>
                <strong>{r.front?.slice(0, 80)}</strong>
                <div style={{ color: '#666', fontSize: 13 }}>{r.back?.slice(0, 120)}</div>
              </div>
            ))}
            <Button size="small" style={{ marginTop: 8 }} onClick={() => setSearchResults([])}>清除结果</Button>
          </div>
        )}

        {loading && <div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /></div>}

        {!loading && dueCards.length === 0 && (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <IdcardOutlined style={{ fontSize: 64, marginBottom: 16 }} />
            <p>暂无待复习卡片</p>
            <p style={{ fontSize: 12 }}>点击「AI 生成卡片」创建新的记忆卡片</p>
          </div>
        )}

        {!loading && card && (
          <div style={{ maxWidth: 650, margin: '0 auto' }}>
            {/* Progress bar */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 13, color: '#999' }}>
                  第 {currentIndex + 1} / {dueCards.length} 张
                  <Tag style={{ marginLeft: 8 }}>{card.card_type}</Tag>
                </span>
                <span style={{ fontSize: 13, color: '#999' }}>
                  今日剩余 {dueCards.length - currentIndex - 1} 张
                </span>
              </div>
              <Progress
                percent={Math.round(((currentIndex + 1) / dueCards.length) * 100)}
                showInfo={false}
                strokeColor="#4f46e5"
                trailColor="#e8eaed"
                size="small"
              />
            </div>

            {/* Card face */}
            <div
              className="flashcard-flip"
              style={{ minHeight: 200, cursor: card.card_type === 'cloze' && !isFlipped ? 'default' : 'pointer' }}
              onClick={() => {
                if (card.card_type === 'qa' || card.card_type === 'compare') flip()
              }}
            >
              <div
                style={{
                  minHeight: 200, background: '#fff', border: '2px solid #4f46e5',
                  borderRadius: 16, padding: 32, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', textAlign: 'center', fontSize: 18,
                }}
              >
                {renderCardContent()}
              </div>
            </div>

            {/* Cloze doesn't need flip button */}
            {!isFlipped && card.card_type !== 'cloze' && (
              <div style={{ textAlign: 'center', marginTop: 12 }}>
                <Tag color="blue">点击卡片翻转 | 空格键翻转</Tag>
              </div>
            )}

            {/* Rating buttons (for QA/Compare when flipped, for Cloze always) */}
            {(isFlipped || card.card_type === 'cloze') && (
              <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                {ratingLabels.map(r => (
                  <Button key={r.value} block onClick={() => handleReview(r.value)}
                    style={{ borderColor: r.color, color: r.color }}>
                    {r.label} ({r.key})
                  </Button>
                ))}
              </div>
            )}

            {/* Navigation */}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12 }}>
              <Button
                icon={<RightOutlined style={{ transform: 'rotate(180deg)' }} />}
                onClick={prev}
                disabled={currentIndex <= 0}
                size="small"
              >
                上一张
              </Button>
              <span style={{ fontSize: 12, color: '#999', lineHeight: '32px' }}>
                快捷键: 空格翻转 | 1-4 评分 | ← → 导航
              </span>
              <Button
                icon={<RightOutlined />}
                onClick={next}
                disabled={currentIndex >= dueCards.length - 1}
                size="small"
              >
                下一张 (跳过)
              </Button>
            </div>
          </div>
        )}
      </Card>

      <Card title="牌组列表" style={{ marginTop: 16 }}>
        <Table
          dataSource={decks}
          rowKey="id"
          locale={{ emptyText: '暂无牌组' }}
          columns={[
            { title: '名称', dataIndex: 'name', ellipsis: true },
            { title: '卡片数', dataIndex: 'card_count', width: 100 },
            { title: '创建时间', dataIndex: 'created_at', width: 140, render: (v: string) => v?.slice(0, 10) },
            { title: '操作', width: 200, render: (_: any, record: any) => (
              <Space>
                <Button size="small" icon={<RobotOutlined />}
                  onClick={async () => {
                    try {
                      const summary = await generateDeckSummary(record.id)
                      Modal.info({
                        title: `牌组摘要: ${summary.deck_name}`,
                        content: (
                          <div>
                            <p>{summary.summary}</p>
                            <p>核心主题: {(summary.core_topics || []).join(', ')}</p>
                            <p>难度: {summary.difficulty_level} | 预计学习时间: {summary.estimated_study_time_minutes} 分钟</p>
                            <p style={{ color: '#4f46e5' }}>{summary.learning_tips}</p>
                          </div>
                        ),
                        width: 500,
                      })
                    } catch { message.error('生成摘要失败') }
                  }}
                >摘要</Button>
                <Button size="small" icon={<DownloadOutlined />} onClick={() => handleExportAnki(record.id)}>导出Anki</Button>
              </Space>
            )},
          ]}
          pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total) => `共 ${total} 个牌组` }}
          size="middle"
        />
      </Card>

      <Modal title="AI 生成闪卡" open={genModalVisible} onCancel={() => setGenModalVisible(false)}
        onOk={handleGenerate} confirmLoading={loading} width={600}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <label>知识点文本:</label>
          <Input.TextArea rows={5} value={genInput} onChange={e => setGenInput(e.target.value)}
            placeholder="粘贴知识点内容，AI 将据此生成问答/填空/对比卡片..." />
          <Space>
            <Select value={genConfig.card_type} onChange={v => setGenConfig(g => ({ ...g, card_type: v }))}
              options={[
                { value: 'qa', label: '问答卡' },
                { value: 'cloze', label: '填空卡' },
                { value: 'compare', label: '对比辨析卡' },
              ]} />
            <Select value={genConfig.count} onChange={v => setGenConfig(g => ({ ...g, count: v }))}
              options={[10, 20, 30, 50].map(n => ({ value: n, label: `${n}张` }))} />
          </Space>
        </Space>
      </Modal>
    </div>
  )
}
