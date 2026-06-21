import { useState, useEffect } from 'react'
import { Card, Button, Space, message, Spin, Tag, Select, Input, Modal, Dropdown } from 'antd'
import { RobotOutlined, SwapOutlined, RightOutlined, IdcardOutlined, DownloadOutlined, ReloadOutlined } from '@ant-design/icons'
import { getDueCards, reviewCard, generateCards, listDecks } from '../api'
import { useAppStore, useFlashcardStore } from '../stores'

export default function FlashcardPage() {
  const { selectedDoc } = useAppStore()
  const { dueCards, currentIndex, isFlipped, setDueCards, flip, next } = useFlashcardStore()
  const [loading, setLoading] = useState(false)
  const [decks, setDecks] = useState<any[]>([])
  const [genConfig, setGenConfig] = useState({ card_type: 'qa', count: 20, deck_name: '默认牌组' })
  const [genModalVisible, setGenModalVisible] = useState(false)
  const [genInput, setGenInput] = useState('')

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
      message.success(`已记录 (下次复习: ${result.next_review_at?.slice(0, 10) || '待定'})`)
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

  const card = dueCards[currentIndex]
  const ratingLabels = [
    { value: 1, label: '完全忘记', color: '#ff4d4f' },
    { value: 2, label: '困难想起', color: '#faad14' },
    { value: 3, label: '正常回忆', color: '#52c41a' },
    { value: 4, label: '轻松想起', color: '#1890ff' },
  ]

  return (
    <div>
      <Card title="记忆闪卡" extra={
        <Space>
          <Button icon={<RobotOutlined />} type="primary" onClick={() => setGenModalVisible(true)}>
            AI 生成卡片
          </Button>
          <Dropdown menu={{ items: decks.map(d => ({ key: d.id, label: `导出 ${d.name} (${d.card_count}张)` })), onClick: ({ key }) => handleExportAnki(key) }}>
            <Button icon={<DownloadOutlined />}>导出Anki</Button>
          </Dropdown>
          <Button icon={<ReloadOutlined />} onClick={loadDueCards}>刷新</Button>
        </Space>
      }>
        {loading && <div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /></div>}
        {!loading && dueCards.length === 0 && (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <IdcardOutlined style={{ fontSize: 64, marginBottom: 16 }} />
            <p>暂无待复习卡片</p>
            <p style={{ fontSize: 12 }}>点击「AI 生成卡片」创建新的记忆卡片</p>
          </div>
        )}
        {!loading && card && (
          <div style={{ maxWidth: 600, margin: '0 auto' }}>
            <div style={{ textAlign: 'center', marginBottom: 12, color: '#999' }}>
              {currentIndex + 1} / {dueCards.length}
              <Tag style={{ marginLeft: 8 }}>{card.card_type}</Tag>
            </div>

            <div
              className="flashcard-flip"
              style={{ height: 280, cursor: 'pointer' }}
              onClick={flip}
            >
              <div className={`flashcard-inner ${isFlipped ? 'flipped' : ''}`}
                style={{
                  height: '100%', background: '#fff', border: '2px solid #4f46e5',
                  borderRadius: 16, padding: 32, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', textAlign: 'center', fontSize: 18,
                }}>
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
              </div>
            </div>

            <div style={{ textAlign: 'center', marginTop: 12 }}>
              <Tag color="blue">点击卡片翻转</Tag>
            </div>

            {isFlipped && (
              <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                {ratingLabels.map(r => (
                  <Button key={r.value} block onClick={() => handleReview(r.value)}
                    style={{ borderColor: r.color, color: r.color }}>
                    {r.label} ({r.value})
                  </Button>
                ))}
              </div>
            )}

            {!isFlipped && (
              <div style={{ textAlign: 'center', marginTop: 16 }}>
                <Button icon={<SwapOutlined />} onClick={flip}>显示答案</Button>
                <Button icon={<RightOutlined />} onClick={next} style={{ marginLeft: 8 }}
                  disabled={currentIndex >= dueCards.length - 1}>跳过</Button>
              </div>
            )}
          </div>
        )}
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
