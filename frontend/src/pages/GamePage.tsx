import { useState, useEffect } from 'react'
import { Card, Button, Select, App, Space, Tag, InputNumber, Progress, Input, Table } from 'antd'
import { PlayCircleOutlined, CheckCircleOutlined, TrophyOutlined, ArrowRightOutlined, HistoryOutlined } from '@ant-design/icons'
import { useAppStore } from '../stores'
import { saveGameProgress, getGameProgress } from '../api'

const apiBase = '/api/v1'

interface MatchPair {
  id: string
  concept: string
  definition: string
  difficulty: string
}

export default function GamePage() {
  const { selectedDoc } = useAppStore()
  const { message } = App.useApp()
  const [gameType, setGameType] = useState('matching')
  const [count, setCount] = useState(8)
  const [loading, setLoading] = useState(false)
  const [pairs, setPairs] = useState<MatchPair[]>([])
  const [clozeLevels, setClozeLevels] = useState<any[]>([])
  const [clozeIdx, setClozeIdx] = useState(0)
  const [clozeAnswer, setClozeAnswer] = useState('')
  const [clozeRevealed, setClozeRevealed] = useState(false)
  const [selected, setSelected] = useState<string[]>([])
  const [matched, setMatched] = useState<Set<string>>(new Set())
  const [gameStarted, setGameStarted] = useState(false)
  const [score, setScore] = useState(0)
  const [attempts, setAttempts] = useState(0)
  const [progressHistory, setProgressHistory] = useState<any[]>([])
  // Fix game state
  const [fixItems, setFixItems] = useState<any[]>([])
  const [fixIdx, setFixIdx] = useState(0)
  const [fixAnswer, setFixAnswer] = useState('')
  const [fixRevealed, setFixRevealed] = useState(false)
  // Coding game state
  const [codingItems, setCodingItems] = useState<any[]>([])
  const [codingIdx, setCodingIdx] = useState(0)
  const [codingAnswer, setCodingAnswer] = useState('')
  const [codingRevealed, setCodingRevealed] = useState(false)

  useEffect(() => { getGameProgress().then(setProgressHistory).catch(console.error) }, [])

  const handleGenerate = async () => {
    if (!selectedDoc) { message.warning('请先在资料导入页面选择文档'); return }
    setLoading(true)
    try {
      const chunksResp = await fetch(`${apiBase}/documents/${selectedDoc}/chunks`)
      const chunks = await chunksResp.json()
      const knowledgeText = (Array.isArray(chunks) ? chunks : []).map((c: any) => c.text).join('\n\n').slice(0, 3000)

      const resp = await fetch(`${apiBase}/generate/game-levels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ knowledge_text: knowledgeText, game_type: 'matching', count }),
      })
      if (!resp.ok) throw new Error('生成失败')
      const data = await resp.json()

      if (gameType === 'matching') {
        const rawPairs = data.pairs || data
        const gamePairs = Array.isArray(rawPairs) ? rawPairs.map((p: any, i: number) => ({
          id: p.id || `p_${i}`,
          concept: p.concept || p.label || p.term || '',
          definition: p.definition || p.text || p.description || '',
          difficulty: p.difficulty || 'medium',
        })) : []
        if (gamePairs.length === 0) { message.warning('未生成匹配对，请重试'); return }
        setPairs(gamePairs)
      } else if (gameType === 'fix') {
        const rawPairs = data.pairs || data
        const items = Array.isArray(rawPairs) ? rawPairs.map((p: any, i: number) => ({
          id: p.id || `f_${i}`,
          incorrect: p.incorrect || p.wrong || p.text || p.passage || '',
          correct: p.correct || p.answer || p.fixed || '',
          hint: p.hint || '',
        })) : []
        if (items.length === 0) { message.warning('未生成修正题目，请重试'); return }
        setFixItems(items)
        setFixIdx(0)
        setFixRevealed(false)
        setFixAnswer('')
      } else if (gameType === 'coding') {
        const rawPairs = data.pairs || data
        const items = Array.isArray(rawPairs) ? rawPairs.map((p: any, i: number) => ({
          id: p.id || `c_${i}`,
          question: p.question || p.problem || p.description || '',
          answer: p.answer || p.solution || p.code || '',
          hint: p.hint || p.test_cases || '',
        })) : []
        if (items.length === 0) { message.warning('未生成编程题，请重试'); return }
        setCodingItems(items)
        setCodingIdx(0)
        setCodingRevealed(false)
        setCodingAnswer('')
      } else {
        const levels = data.levels || data
        if (!levels.length) { message.warning('未生成关卡，请重试'); return }
        setClozeLevels(levels)
        setClozeIdx(0)
        setClozeRevealed(false)
        setClozeAnswer('')
      }
      setMatched(new Set())
      setSelected([])
      setScore(0)
      setAttempts(0)
      setGameStarted(true)
      message.success(gameType === 'matching' ? `已生成 ${data.count} 组匹配对` : `已生成 ${data.count} 个填空关卡`)
    } catch (e: any) {
      message.error(`生成失败: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleSelect = (id: string) => {
    if (matched.has(id)) return
    const newSelected = selected.includes(id)
      ? selected.filter(s => s !== id)
      : [...selected, id].slice(0, 2)

    setSelected(newSelected)

    if (newSelected.length === 2) {
      setAttempts(a => a + 1)
      const [a, b] = newSelected
      // IDs are like c_p_0 (concept of pair 0) and d_p_0 (definition of pair 0)
      const aPairId = a.split('_').slice(1).join('_') // "p_0" from "c_p_0"
      const bPairId = b.split('_').slice(1).join('_') // "p_0" from "d_p_0"
      const aType = a.startsWith('c_') ? 'concept' : 'definition'
      const bType = b.startsWith('c_') ? 'concept' : 'definition'

      // Match if: different types (concept+definition) AND same pairId
      const isMatch = aType !== bType && aPairId === bPairId

      if (isMatch) {
        setMatched(m => new Set([...m, a, b]))
        setScore(s => s + 1)
        message.success('匹配正确！')
      } else {
        message.error('不匹配，请再试！')
      }

      setTimeout(() => setSelected([]), 600)
    }
  }

  const getShuffledItems = () => {
    const concepts = pairs.map(p => ({ id: `c_${p.id}`, text: p.concept, type: 'concept', pairId: p.id }))
    const defs = pairs.map(p => ({ id: `d_${p.id}`, text: p.definition, type: 'definition', pairId: p.id }))
    return [...concepts, ...defs].sort(() => Math.random() - 0.5)
  }

  const items = getShuffledItems()
  const isComplete = matched.size === pairs.length * 2

  return (
    <div>
      <Card title="互动游戏" extra={
        <Space>
          <Select value={gameType} onChange={setGameType}
            options={[
              { value: 'matching', label: '概念匹配' },
              { value: 'cloze_ladder', label: '填空闯关' },
              { value: 'fix', label: '错误修正' },
              { value: 'coding', label: '编程挑战' },
            ]} />
          <Space.Compact>
            <InputNumber value={count} onChange={v => setCount(v || 8)} min={4} max={20} />
            <span style={{ display: 'inline-flex', alignItems: 'center', padding: '0 8px', backgroundColor: '#fafafa', border: '1px solid #d9d9d9', borderLeft: 0, borderRadius: '0 6px 6px 0', fontSize: 14 }}>对</span>
          </Space.Compact>
          <Button icon={<PlayCircleOutlined />} type="primary" loading={loading} onClick={handleGenerate}>
            {gameStarted ? '重新生成' : '开始游戏'}
          </Button>
        </Space>
      }>
        {!gameStarted && (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <TrophyOutlined style={{ fontSize: 64, marginBottom: 16 }} />
            <p>选择题型和数量，点击「开始游戏」</p>
            <p style={{ fontSize: 12 }}>游戏素材由 AI 根据文档内容生成，100% 本地运行</p>
          </div>
        )}

        {gameStarted && gameType === 'matching' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
              <Space>
                <Tag color="blue">已匹配: {matched.size / 2}/{pairs.length}</Tag>
                <Tag color="orange">尝试次数: {attempts}</Tag>
                <Tag color="green">得分: {score}</Tag>
              </Space>
              <Progress percent={Math.round((matched.size / (pairs.length * 2)) * 100)} style={{ width: 200 }} />
            </div>

            {isComplete && (
              <Card size="small" style={{ background: '#f6ffed', marginBottom: 16, textAlign: 'center' }}>
                <TrophyOutlined style={{ fontSize: 32, color: '#faad14' }} />
                <h3>恭喜完成！</h3>
                <p>尝试 {attempts} 次，得分 {score} 分</p>
                <Space>
                  <Button type="primary" onClick={handleGenerate}>再来一局</Button>
                  <Button onClick={() => {
                    saveGameProgress({ game_type: 'matching', level_id: 'default', best_score: score, stars: Math.min(3, Math.ceil(score / pairs.length * 3)), completed: true })
                      .then(() => getGameProgress().then(setProgressHistory))
                    message.success('成绩已保存')
                  }}>保存成绩</Button>
                </Space>
              </Card>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
              {items.map(item => {
                const isMatched = matched.has(item.id)
                const isSelected = selected.includes(item.id)
                const isConcept = item.type === 'concept'

                return (
                  <Card
                    key={item.id}
                    size="small"
                    hoverable={!isMatched}
                    onClick={() => !isMatched && handleSelect(item.id)}
                    style={{
                      cursor: isMatched ? 'default' : 'pointer',
                      opacity: isMatched ? 0.5 : 1,
                      border: isSelected ? '2px solid #4f46e5' : isMatched ? '2px solid #52c41a' : '1px solid #e8e8e8',
                      background: isSelected ? '#f0f5ff' : isMatched ? '#f6ffed' : '#fff',
                      transition: 'all 0.2s',
                    }}
                  >
                    <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>
                      {isConcept ? '📘 概念' : '📝 定义'}
                    </div>
                    <div style={{ fontSize: 14, lineHeight: 1.5 }}>
                      {item.text}
                    </div>
                    {isMatched && <CheckCircleOutlined style={{ position: 'absolute', top: 8, right: 8, color: '#52c41a' }} />}
                  </Card>
                )
              })}
            </div>
          </div>
        )}

        {gameStarted && gameType === 'cloze_ladder' && clozeLevels.length > 0 && (() => {
          const level = clozeLevels[clozeIdx] || {}
          const passage = level.passage || level.text || level.question || ''
          const answer = level.answer || level.correct || ''
          const isLast = clozeIdx >= clozeLevels.length - 1

          const handleClozeSubmit = () => {
            setAttempts(a => a + 1)
            const correct = clozeAnswer.trim().toLowerCase() === answer.trim().toLowerCase()
            if (correct || clozeRevealed) {
              if (correct) setScore(s => s + 1)
              if (isLast) {
                setClozeRevealed(true)
              } else {
                setClozeIdx(i => i + 1)
                setClozeAnswer('')
                setClozeRevealed(false)
              }
            } else {
              setClozeRevealed(true)
              message.warning('回答错误，已显示答案')
            }
          }

          return (
            <div style={{ maxWidth: 700, margin: '0 auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
                <Space>
                  <Tag color="blue">关卡: {clozeIdx + 1}/{clozeLevels.length}</Tag>
                  <Tag color="orange">尝试次数: {attempts}</Tag>
                  <Tag color="green">得分: {score}</Tag>
                </Space>
                <Progress percent={Math.round(((clozeIdx + 1) / clozeLevels.length) * 100)} style={{ width: 200 }} />
              </div>
              <Card style={{ background: '#fafafa', marginBottom: 16 }}>
                <div style={{ fontSize: 16, lineHeight: 2, whiteSpace: 'pre-wrap' }}>{passage}</div>
              </Card>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Input value={clozeAnswer} onChange={e => setClozeAnswer(e.target.value)}
                  placeholder="请输入答案..." disabled={clozeRevealed}
                  onKeyDown={e => { if (e.key === 'Enter') handleClozeSubmit() }} />
                {clozeRevealed && (
                  <Card size="small" style={{ background: '#f6ffed' }}>
                    <div style={{ fontWeight: 600 }}>答案: {answer}</div>
                    {level.hint && <div style={{ color: '#666', marginTop: 4 }}>提示: {level.hint}</div>}
                  </Card>
                )}
                <Button type="primary" block onClick={handleClozeSubmit}>
                  {clozeRevealed ? (isLast ? '完成' : '下一关') : '提交'}
                </Button>
                {isLast && clozeRevealed && (
                  <Button onClick={() => {
                    saveGameProgress({ game_type: 'cloze_ladder', level_id: 'default', best_score: score, stars: Math.min(3, Math.ceil(score / clozeLevels.length * 3)), completed: true })
                      .then(() => getGameProgress().then(setProgressHistory))
                    message.success('成绩已保存')
                  }}>保存成绩</Button>
                )}
              </Space>
            </div>
          )
        })()}

        {gameStarted && gameType === 'fix' && fixItems.length > 0 && (() => {
          const item = fixItems[fixIdx] || {}
          const incorrectText = item.incorrect || ''
          const correctText = item.correct || ''
          const isLast = fixIdx >= fixItems.length - 1

          const handleFixSubmit = () => {
            setAttempts(a => a + 1)
            const correct = fixAnswer.trim().toLowerCase() === correctText.trim().toLowerCase()
            if (correct || fixRevealed) {
              if (correct) setScore(s => s + 1)
              if (isLast) {
                setFixRevealed(true)
              } else {
                setFixIdx(i => i + 1)
                setFixAnswer('')
                setFixRevealed(false)
              }
            } else {
              setFixRevealed(true)
              message.warning('修正不正确，已显示答案')
            }
          }

          return (
            <div style={{ maxWidth: 700, margin: '0 auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
                <Space>
                  <Tag color="red">错误修正: {fixIdx + 1}/{fixItems.length}</Tag>
                  <Tag color="orange">尝试: {attempts}</Tag>
                  <Tag color="green">得分: {score}</Tag>
                </Space>
                <Progress percent={Math.round(((fixIdx + 1) / fixItems.length) * 100)} style={{ width: 200 }} />
              </div>
              <Card style={{ background: '#fff2f0', marginBottom: 16, border: '1px solid #ffccc7' }}>
                <Tag color="red" style={{ marginBottom: 8 }}>找出并修正错误:</Tag>
                <div style={{ fontSize: 16, lineHeight: 2, whiteSpace: 'pre-wrap' }}>{incorrectText}</div>
              </Card>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Input.TextArea rows={3} value={fixAnswer} onChange={e => setFixAnswer(e.target.value)}
                  placeholder="请输入修正后的正确内容..." disabled={fixRevealed} />
                {fixRevealed && (
                  <Card size="small" style={{ background: '#f6ffed' }}>
                    <div style={{ fontWeight: 600 }}>正确答案: {correctText}</div>
                    {item.hint && <div style={{ color: '#666', marginTop: 4 }}>提示: {item.hint}</div>}
                  </Card>
                )}
                <Button type="primary" block onClick={handleFixSubmit}>
                  {fixRevealed ? (isLast ? '完成' : '下一题') : '提交'}
                </Button>
                {isLast && fixRevealed && (
                  <Button onClick={() => {
                    saveGameProgress({ game_type: 'fix', level_id: 'default', best_score: score, stars: Math.min(3, Math.ceil(score / fixItems.length * 3)), completed: true })
                      .then(() => getGameProgress().then(setProgressHistory))
                    message.success('成绩已保存')
                  }}>保存成绩</Button>
                )}
              </Space>
            </div>
          )
        })()}

        {gameStarted && gameType === 'coding' && codingItems.length > 0 && (() => {
          const item = codingItems[codingIdx] || {}
          const questionText = item.question || ''
          const answerCode = item.answer || ''
          const isLast = codingIdx >= codingItems.length - 1

          const handleCodingSubmit = () => {
            setAttempts(a => a + 1)
            setCodingRevealed(true)
            setScore(s => s + 1)
          }

          return (
            <div style={{ maxWidth: 700, margin: '0 auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
                <Space>
                  <Tag color="purple">编程挑战: {codingIdx + 1}/{codingItems.length}</Tag>
                  <Tag color="orange">尝试: {attempts}</Tag>
                  <Tag color="green">完成: {score}</Tag>
                </Space>
                <Progress percent={Math.round(((codingIdx + 1) / codingItems.length) * 100)} style={{ width: 200 }} />
              </div>
              <Card style={{ background: '#f0f5ff', marginBottom: 16, border: '1px solid #d6e4ff' }}>
                <Tag color="purple" style={{ marginBottom: 8 }}>编程题目:</Tag>
                <div style={{ fontSize: 16, lineHeight: 2, whiteSpace: 'pre-wrap' }}>{questionText}</div>
              </Card>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Input.TextArea rows={6} value={codingAnswer} onChange={e => setCodingAnswer(e.target.value)}
                  placeholder="请输入代码..." disabled={codingRevealed}
                  style={{ fontFamily: 'monospace', fontSize: 13 }} />
                {codingRevealed && (
                  <Card size="small" style={{ background: '#f6ffed' }}>
                    <div style={{ fontWeight: 600, marginBottom: 4 }}>参考答案:</div>
                    <pre style={{ background: '#000', color: '#0f0', padding: 12, borderRadius: 6, fontSize: 12, overflow: 'auto', maxHeight: 200 }}>{answerCode}</pre>
                    {item.hint && <div style={{ color: '#666', marginTop: 4 }}>提示: {item.hint}</div>}
                  </Card>
                )}
                {!codingRevealed ? (
                  <Button type="primary" block onClick={handleCodingSubmit}>提交并查看答案</Button>
                ) : (
                  <Button type="primary" block onClick={() => {
                    if (isLast) {
                      saveGameProgress({ game_type: 'coding', level_id: 'default', best_score: score, stars: Math.min(3, Math.ceil(score / codingItems.length * 3)), completed: true })
                        .then(() => getGameProgress().then(setProgressHistory))
                      message.success('成绩已保存')
                    } else {
                      setCodingIdx(i => i + 1)
                      setCodingAnswer('')
                      setCodingRevealed(false)
                    }
                  }}>
                    {isLast ? '完成' : '下一题'}
                  </Button>
                )}
              </Space>
            </div>
          )
        })()}
      </Card>

      {progressHistory.length > 0 && (
        <Card title={<Space><HistoryOutlined /> 历史成绩</Space>} style={{ marginTop: 16 }}>
          <Table
            dataSource={progressHistory}
            rowKey="id"
            size="small"
            pagination={false}
            columns={[
              { title: '游戏类型', dataIndex: 'game_type', width: 100, render: (v: string) => {
                const labels: Record<string, string> = { matching: '概念匹配', cloze_ladder: '填空闯关', fix: '错误修正', coding: '编程挑战' }
                return <Tag>{labels[v] || v}</Tag>
              }},
              { title: '最高分', dataIndex: 'best_score', width: 80 },
              { title: '星级', dataIndex: 'stars', width: 80, render: (v: number) => '★'.repeat(v || 0) + '☆'.repeat(3 - (v || 0)) },
              { title: '状态', dataIndex: 'completed', width: 80, render: (v: boolean) => v ? <Tag color="green">已完成</Tag> : <Tag>进行中</Tag> },
              { title: '更新时间', dataIndex: 'updated_at', width: 120, render: (v: string) => v?.slice(0, 10) },
            ]}
          />
        </Card>
      )}
    </div>
  )
}
