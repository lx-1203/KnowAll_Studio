import { useState, useEffect, useCallback, useRef } from 'react'
import { App, Modal, Input, Upload, message as antMsg } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import { getReadingArticles, getReadingArticle, convertReadingText, convertReadingStream, uploadReadingArticle, deleteReadingArticle } from '../api'
import { useTheme } from '../components/ThemeProvider'
import './ReadingPage.css'

// ── Types ──
interface Article {
  id: string | number
  title: string
  difficulty: number
  content: string
  tags: string[]
  source?: string
}

interface VocabItem {
  cn: string
  en: string
}

interface WordEntry {
  cn: string
  seen: number
  lastSeen: number
}

interface VocabState {
  words: Record<string, WordEntry>
  totalRead: number
  totalEncountered: number
}

// ── Constants ──
const KNOW_THRESHOLD = 5
const STORAGE_KEY = 'reading_lang_vocab'

function loadVocabState(): VocabState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : { words: {}, totalRead: 0, totalEncountered: 0 }
  } catch { return { words: {}, totalRead: 0, totalEncountered: 0 } }
}

function saveVocabState(state: VocabState) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function getKnownWords(state: VocabState): VocabItem[] {
  return Object.entries(state.words)
    .filter(([, v]) => v.seen >= KNOW_THRESHOLD)
    .map(([en, v]) => ({ cn: v.cn, en }))
}

function getSeenWords(state: VocabState): VocabItem[] {
  return Object.entries(state.words)
    .filter(([, v]) => v.seen > 0 && v.seen < KNOW_THRESHOLD)
    .map(([en, v]) => ({ cn: v.cn, en }))
}

function getLevel(state: VocabState): number {
  const known = Object.values(state.words).filter(v => v.seen >= KNOW_THRESHOLD).length
  if (known >= 150) return 3
  if (known >= 50) return 2
  return 1
}

function wordsToNextLevel(state: VocabState): number {
  const known = Object.values(state.words).filter(v => v.seen >= KNOW_THRESHOLD).length
  if (known >= 150) return 0
  if (known >= 50) return 150 - known
  return 50 - known
}

function updateVocabAfterReading(vocabulary: VocabItem[]): VocabState {
  const state = loadVocabState()
  const now = Date.now()
  vocabulary.forEach(v => {
    const key = v.en.toLowerCase()
    if (state.words[key]) {
      state.words[key].seen += 1
      state.words[key].lastSeen = now
    } else {
      state.words[key] = { cn: v.cn, seen: 1, lastSeen: now }
    }
    state.totalEncountered += 1
  })
  state.totalRead += 1
  saveVocabState(state)
  return state
}

// ── Render helpers ──
function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function renderMixedText(result: string, vocabulary: VocabItem[], revealMode: boolean): string {
  const enToData: Record<string, { cn: string }> = {}
  vocabulary.forEach(v => {
    enToData[v.en.toLowerCase()] = { cn: v.cn }
  })

  function findMatch(token: string) {
    const lower = token.toLowerCase()
    if (enToData[lower]) return enToData[lower]
    const stripped = lower.replace(/(ing|ed|s|es|ly|ment|tion|ness|ful|less|er|est)$/, '')
    if (stripped !== lower && enToData[stripped]) return enToData[stripped]
    return null
  }

  // Handle multi-word phrases by replacing with placeholders first
  const multiWords = Object.keys(enToData).filter(k => k.includes(' ')).sort((a, b) => b.length - a.length)
  const placeholders: Record<string, string> = {}
  let workText = result
  multiWords.forEach((phrase, i) => {
    const ph = `__PH_${i}__`
    const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const re = new RegExp(escaped, 'gi')
    workText = workText.replace(re, ph)
    placeholders[ph] = phrase
  })

  const regex = /__PH_\d+__|([a-zA-Z]+(?:'[a-z]+)?)/g
  const parts: string[] = []
  let lastIdx = 0
  let match
  while ((match = regex.exec(workText)) !== null) {
    if (match.index > lastIdx) {
      parts.push(escapeHtml(workText.substring(lastIdx, match.index)))
    }
    const token = match[0]
    if (token.startsWith('__PH_') && placeholders[token]) {
      const phrase = placeholders[token]
      const data = enToData[phrase.toLowerCase()]
      if (data) {
        parts.push(
          `<span class="en-word ${revealMode ? 'revealed' : ''}" data-cn="${data.cn.replace(/"/g, '&quot;')}">${phrase}<span class="cn-tip">${revealMode ? data.cn : '?'}</span></span>`
        )
      } else {
        parts.push(phrase)
      }
    } else {
      const data = findMatch(token)
      if (data) {
        parts.push(
          `<span class="en-word ${revealMode ? 'revealed' : ''}" data-cn="${data.cn.replace(/"/g, '&quot;')}">${token}<span class="cn-tip">${revealMode ? data.cn : '?'}</span></span>`
        )
      } else {
        parts.push(token)
      }
    }
    lastIdx = match.index + match[0].length
  }
  if (lastIdx < workText.length) {
    parts.push(escapeHtml(workText.substring(lastIdx)))
  }
  return parts.join('')
}

// ── Component ──
export default function ReadingPage() {
  const { message } = App.useApp()
  const { isDark } = useTheme()

  // Core state
  const [activeTab, setActiveTab] = useState<'articles' | 'custom'>('articles')
  const [articles, setArticles] = useState<Article[]>([])
  const [currentArticle, setCurrentArticle] = useState<Article | null>(null)
  const [currentVocab, setCurrentVocab] = useState<VocabItem[]>([])
  const [revealMode, setRevealMode] = useState(true)
  const [vocabState, setVocabState] = useState<VocabState>(loadVocabState)
  const [customText, setCustomText] = useState('')
  const [loading, setLoading] = useState(false)
  const [renderedHtml, setRenderedHtml] = useState('')
  const [titleText, setTitleText] = useState('📚 选择一篇文章开始')
  const [showStats, setShowStats] = useState(false)
  const [statKnownCount, setStatKnownCount] = useState('-')
  const [statTotalVocab, setStatTotalVocab] = useState('-')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [panelOpen, setPanelOpen] = useState(false)
  const [panelTab, setPanelTab] = useState<'current' | 'known' | 'learning'>('current')
  const [streamingToken, setStreamingToken] = useState('')

  // Upload modal state
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [uploadTitle, setUploadTitle] = useState('')
  const [uploadContent, setUploadContent] = useState('')
  const [fileHint, setFileHint] = useState('')

  const customTextRef = useRef<HTMLTextAreaElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Auto-level
  const level = getLevel(vocabState)
  const toNext = wordsToNextLevel(vocabState)
  const knownCount = Object.values(vocabState.words).filter(v => v.seen >= KNOW_THRESHOLD).length
  const learningCount = Object.values(vocabState.words).filter(v => v.seen > 0 && v.seen < KNOW_THRESHOLD).length
  const totalWords = Object.keys(vocabState.words).length

  const levelNames: Record<number, string> = { 1: '初学者', 2: '进阶者', 3: '掌握者' }
  const levelIcons: Record<number, string> = { 1: '🌱', 2: '🌿', 3: '🌳' }

  // ── Load articles ──
  const loadArticles = useCallback(async () => {
    try {
      const data = await getReadingArticles()
      setArticles(Array.isArray(data) ? data : [])
    } catch { /* silent */ }
  }, [])

  useEffect(() => { loadArticles() }, [loadArticles])

  // ── Core: reading (uses non-streaming API for reliability with offline fallback) ──
  const doRead = useCallback(async (text: string, skipCache = false) => {
    setShowStats(true)
    setLoading(true)
    setStreamingToken('')
    setRenderedHtml('')

    const state = loadVocabState()
    setVocabState(state)
    const known = getKnownWords(state)
    const seen = getSeenWords(state)

    // Try streaming first if API key is likely configured, otherwise use non-streaming
    let usedStreaming = false
    try {
      // Use non-streaming convertText — reliable, always works with offline dictionary
      const data = await convertReadingText(
        text,
        getLevel(state),
        known,
        seen,
      )
      if ((data as any).error) {
        message.error((data as any).error)
        setShowStats(false)
        setLoading(false)
        return
      }
      setCurrentVocab(data.vocabulary || [])
      const newState = updateVocabAfterReading(data.vocabulary || [])
      setVocabState(newState)
      setStatKnownCount(String(getKnownWords(newState).length))
      setStatTotalVocab(String(Object.keys(newState.words).length))
      const html = renderMixedText(data.result, data.vocabulary || [], revealMode)
      setRenderedHtml(html)
    } catch (e: any) {
      message.error('请求失败，请检查服务是否运行: ' + (e.message || '未知错误'))
      setShowStats(false)
      setRenderedHtml('')
    } finally {
      setLoading(false)
      setStreamingToken('')
    }
  }, [message, revealMode])

  // ── Select article ──
  const selectArticle = useCallback(async (id: string | number) => {
    try {
      const article = await getReadingArticle(String(id))
      if (article.error) return
      setCurrentArticle(article)
      setTitleText('📖 ' + article.title)
      await doRead(article.content)
      setSidebarOpen(false)
    } catch { /* silent */ }
  }, [doRead])

  // ── Convert custom text ──
  const convertCustom = useCallback(async () => {
    const text = customText.trim()
    if (!text) { message.warning('请输入文本'); return }
    setCurrentArticle(null)
    setTitleText('✏️ 自定义文本')
    await doRead(text)
  }, [customText, doRead, message])

  // ── Refresh reading ──
  const refreshReading = useCallback(() => {
    if (currentArticle) {
      doRead(currentArticle.content, true)
    } else if (customText.trim()) {
      doRead(customText.trim(), true)
    }
  }, [currentArticle, customText, doRead])

  // ── Toggle reveal ──
  const toggleReveal = useCallback(() => {
    setRevealMode(prev => !prev)
  }, [])

  useEffect(() => {
    document.querySelectorAll('.reading-text .en-word').forEach(el => {
      const htmlEl = el as HTMLElement
      const tip = htmlEl.querySelector('.cn-tip') as HTMLElement | null
      if (revealMode) {
        htmlEl.classList.add('revealed')
        if (tip) tip.textContent = htmlEl.dataset.cn || '?'
      } else {
        htmlEl.classList.remove('revealed')
        if (tip) tip.textContent = '?'
      }
    })
  }, [revealMode, renderedHtml])

  // ── Handle word click ──
  const handleReadingClick = useCallback((e: React.MouseEvent) => {
    const target = e.target as HTMLElement
    const wordEl = target.closest('.en-word') as HTMLElement | null
    if (!wordEl) return
    e.stopPropagation()
    const tip = wordEl.querySelector('.cn-tip') as HTMLElement | null
    wordEl.classList.toggle('revealed')
    if (wordEl.classList.contains('revealed')) {
      if (tip) tip.textContent = wordEl.dataset.cn || '?'
    } else {
      if (tip) tip.textContent = '?'
    }
  }, [])

  // ── Upload article ──
  const handleUploadArticle = useCallback(async () => {
    if (!uploadTitle.trim() || !uploadContent.trim()) {
      message.warning('请输入标题和内容')
      return
    }
    try {
      const data = await uploadReadingArticle(uploadTitle.trim(), uploadContent.trim())
      if ((data as any).error) { message.error((data as any).error); return }
      message.success('文章已保存！')
      setUploadModalOpen(false)
      setUploadTitle('')
      setUploadContent('')
      await loadArticles()
      if (data.article) {
        setCurrentArticle(data.article)
        setTitleText('📖 ' + data.article.title)
        await doRead(data.article.content)
      }
    } catch (e: any) {
      message.error('上传失败: ' + (e.response?.data?.detail || e.message))
    }
  }, [uploadTitle, uploadContent, message, loadArticles, doRead])

  // Handle file upload for reading
  const handleFileUpload = useCallback(async (file: File) => {
    try {
      const text = await file.text()
      const lines = text.trim().split('\n')
      const title = lines[0].trim().slice(0, 200)
      const content = lines.slice(1).join('\n').trim()
      if (!content) {
        message.warning('文件内容不足（需首行标题 + 正文）')
        return false
      }
      setUploadTitle(title)
      setUploadContent(text)
      setFileHint(`已加载: ${title} (${content.length}字)`)
    } catch {
      message.error('文件读取失败')
    }
    return false // Prevent upload (we handle it manually)
  }, [message])

  // ── Delete article ──
  const handleDeleteArticle = useCallback(async (id: string) => {
    Modal.confirm({
      title: '确定删除这篇文章？',
      content: '删除后无法恢复',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteReadingArticle(id)
          message.success('已删除')
          if (currentArticle && String(currentArticle.id) === id) {
            setCurrentArticle(null)
            setShowStats(false)
            setRenderedHtml('')
            setCurrentVocab([])
            setTitleText('📚 选择一篇文章开始')
          }
          await loadArticles()
        } catch (e: any) {
          message.error('删除失败: ' + (e.response?.data?.detail || e.message))
        }
      },
    })
  }, [currentArticle, message, loadArticles])

  // ── Keyboard shortcuts ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (activeTab === 'custom') { e.preventDefault(); convertCustom() }
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault(); refreshReading()
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
        e.preventDefault(); toggleReveal()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [activeTab, convertCustom, refreshReading, toggleReveal])

  // ── Render ──
  return (
    <div className={`reading-app${isDark ? ' dark' : ''}`}>
      {/* Left Sidebar */}
      <aside className={`reading-sidebar${sidebarOpen ? ' mobile-open' : ''}`}>
        <div className="reading-sidebar-header">
          <div className="reading-logo">📖 阅读语言</div>
          <div className="reading-logo-sub">自适应渐进式英语学习</div>
        </div>

        {/* Auto-level display */}
        <div className="reading-level-auto">
          <div className="reading-level-info">
            <span className={`reading-level-badge l${level}`}>{levelIcons[level]} L{level}</span>
            <span className="reading-level-name">{levelNames[level]}</span>
          </div>
          <div className="reading-level-progress-bg">
            <div className={`reading-level-progress-fill l${level}`}
              style={{ width: `${level >= 3 ? 100 : Math.min(100, (knownCount / (level === 1 ? 50 : 150)) * 100)}%` }} />
          </div>
          <div className="reading-level-detail">
            <span>{knownCount}</span> 已知词 · <span>{learningCount}</span> 学习中 · 升L{Math.min(level + 1, 3)}还需 <span>{toNext}</span> 词
          </div>
        </div>

        {/* Manual level selector (for reference) */}
        <div className="reading-level-selector" style={{ margin: '8px 12px', padding: '8px', fontSize: '0.75em' }}>
          {[1, 2, 3].map(lv => (
            <button
              key={lv}
              className={`reading-level-btn${level === lv ? ` active l${lv}` : ''}`}
              disabled
              style={{ cursor: 'default', opacity: level === lv ? 1 : 0.7 }}
            >
              {levelNames[lv]}
              <span className="reading-level-label">{lv === 1 ? '掌握50词' : lv === 2 ? '掌握150词' : '已达成'}</span>
            </button>
          ))}
        </div>

        <div className="reading-sidebar-nav">
          <button className={activeTab === 'articles' ? 'active' : ''} onClick={() => setActiveTab('articles')}>
            📚 文章库
          </button>
          <button className={activeTab === 'custom' ? 'active' : ''} onClick={() => setActiveTab('custom')}>
            ✏️ 自定义
          </button>
        </div>

        <div className="reading-sidebar-content">
          {activeTab === 'articles' ? (
            <div>
              <button
                className="reading-btn-upload"
                onClick={() => setUploadModalOpen(true)}
                style={{
                  width: '100%', padding: '8px', border: '2px dashed #e2e8f0', borderRadius: '8px',
                  background: 'none', cursor: 'pointer', fontSize: '0.85em', color: '#6366f1',
                  fontWeight: 600, marginBottom: 12, transition: 'all 0.2s',
                }}
                onMouseEnter={e => (e.currentTarget.style.borderColor = '#6366f1')}
                onMouseLeave={e => (e.currentTarget.style.borderColor = '#e2e8f0')}
              >
                + 上传文章
              </button>
              {articles.map(a => (
                <div
                  key={a.id}
                  className={`reading-article-item${currentArticle && String(currentArticle.id) === String(a.id) ? ' active' : ''}`}
                  onClick={() => selectArticle(a.id)}
                >
                  <div className="reading-article-title">
                    {a.title}
                    <span className={`reading-diff-badge d${a.difficulty || 0}`}>
                      {a.difficulty ? `L${a.difficulty}` : 'U'}
                    </span>
                  </div>
                  <div className="reading-article-meta">
                    {a.tags && a.tags.map(t => <span key={t} className="reading-tag">{t}</span>)}
                    <span>{a.content.length}字</span>
                    {a.source === 'upload' && (
                      <span
                        className="reading-tag"
                        style={{ cursor: 'pointer', color: '#ef4444', marginLeft: 'auto' }}
                        onClick={(e) => { e.stopPropagation(); handleDeleteArticle(String(a.id)) }}
                        title="删除"
                      >
                        🗑️
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="reading-custom-area">
              <textarea
                ref={customTextRef}
                value={customText}
                onChange={e => setCustomText(e.target.value)}
                placeholder={"在此粘贴中文文本...\n\n例如：我们的世界很大，让我们去看看"}
              />
              <div className="reading-custom-actions">
                <button className="reading-btn-secondary" onClick={() => setUploadModalOpen(true)}>
                  📁 上传文件
                </button>
                <button className="reading-btn-convert" onClick={convertCustom} disabled={loading}>
                  🔄 开始阅读
                </button>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="reading-main">
        <div className="reading-main-header">
          <h2>{titleText}</h2>
          <div className="reading-header-actions">
            <button
              className={`reading-reveal-toggle${!revealMode ? ' active' : ''}`}
              onClick={toggleReveal}
              title="切换显示/隐藏中文"
            >
              {revealMode ? '👁️ 显示中文' : '🙈 隐藏中文'}
            </button>
            <button className="reading-btn-icon" onClick={refreshReading} disabled={loading}>
              🔄 换一批词
            </button>
            <button className="reading-btn-icon" onClick={() => setSidebarOpen(v => !v)}>
              ☰
            </button>
            <button className="reading-btn-icon" onClick={() => setPanelOpen(v => !v)}>
              📝 单词本
            </button>
          </div>
        </div>

        {showStats && (
          <div className="reading-stats-bar">
            <div className="reading-stat-item">
              累计词汇: <span className="reading-stat-value">{statTotalVocab}</span>
            </div>
            <div className="reading-stat-item">
              已知词: <span className="reading-stat-value">{statKnownCount}</span>
            </div>
            <div className="reading-stat-item">
              当前生词: <span className="reading-stat-value">{currentVocab.length}</span>
            </div>
          </div>
        )}

        <div className="reading-area">
          <div className="reading-content">
            {!showStats && !loading ? (
              <div className="reading-empty">
                <div className="reading-empty-icon" style={{ fontSize: '3em', marginBottom: 16 }}>📖</div>
                <h3>自适应渐进式学习</h3>
                <p>
                  系统会根据你的词汇量自动调整难度<br />
                  每千字最多引入适量新词<br />
                  见过的词会在后续文章里反复出现
                </p>
              </div>
            ) : loading && !streamingToken ? (
              <div className="reading-empty">
                <p>⏳ 正在生成...</p>
              </div>
            ) : streamingToken && !renderedHtml ? (
              <div className="reading-text" style={{ whiteSpace: 'pre-wrap' }}>
                {streamingToken.startsWith('⚡') ? streamingToken : streamingToken}
              </div>
            ) : (
              <div
                className="reading-text"
                onClick={handleReadingClick}
                dangerouslySetInnerHTML={{ __html: renderedHtml }}
              />
            )}
          </div>
        </div>
      </main>

      {/* Right Panel */}
      <aside className={`reading-right-panel${panelOpen ? ' mobile-open' : ''}`}>
        <div className="reading-panel-header">
          单词本
          <span className="reading-panel-badge">{currentVocab.length}</span>
        </div>
        <div className="reading-panel-tabs">
          <button
            className={`reading-panel-tab${panelTab === 'current' ? ' active' : ''}`}
            onClick={() => setPanelTab('current')}
          >
            📋 本文
          </button>
          <button
            className={`reading-panel-tab${panelTab === 'known' ? ' active' : ''}`}
            onClick={() => setPanelTab('known')}
          >
            ✅ 已知
          </button>
          <button
            className={`reading-panel-tab${panelTab === 'learning' ? ' active' : ''}`}
            onClick={() => setPanelTab('learning')}
          >
            🔄 学习中
          </button>
        </div>
        <div className="reading-panel-content">
          {panelTab === 'current' && (
            currentVocab.length === 0 ? (
              <div className="reading-panel-empty">请先选择一篇文章</div>
            ) : (
              currentVocab.map((v, i) => (
                <div key={i} className="reading-vocab-card">
                  <div>
                    <span className="reading-vocab-en">{v.en}</span>
                    <span className="reading-vocab-cn"> ← {v.cn}</span>
                  </div>
                </div>
              ))
            )
          )}
          {panelTab === 'known' && (
            (() => {
              const known = getKnownWords(vocabState)
              return known.length === 0 ? (
                <div className="reading-panel-empty">暂无已掌握词汇<br />阅读几篇文章后这里会逐渐积累</div>
              ) : (
                known.sort((a, b) => {
                  const sa = vocabState.words[a.en.toLowerCase()]?.seen || 0
                  const sb = vocabState.words[b.en.toLowerCase()]?.seen || 0
                  return sb - sa
                }).map((v, i) => (
                  <div key={i} className="reading-vocab-card known">
                    <div>
                      <span className="reading-vocab-en">{v.en}</span>
                      <span className="reading-vocab-cn"> ← {v.cn}</span>
                    </div>
                    <span className="reading-seen-count">
                      ×{vocabState.words[v.en.toLowerCase()]?.seen || 0}
                    </span>
                  </div>
                ))
              )
            })()
          )}
          {panelTab === 'learning' && (
            (() => {
              const learning = getSeenWords(vocabState)
              return learning.length === 0 ? (
                <div className="reading-panel-empty">暂无可复习词汇</div>
              ) : (
                learning.sort((a, b) => {
                  const sa = vocabState.words[a.en.toLowerCase()]?.seen || 0
                  const sb = vocabState.words[b.en.toLowerCase()]?.seen || 0
                  return sb - sa
                }).map((v, i) => (
                  <div key={i} className="reading-vocab-card learning">
                    <div>
                      <span className="reading-vocab-en">{v.en}</span>
                      <span className="reading-vocab-cn"> ← {v.cn}</span>
                    </div>
                    <span className="reading-seen-count">
                      {vocabState.words[v.en.toLowerCase()]?.seen || 0}/{KNOW_THRESHOLD}
                    </span>
                  </div>
                ))
              )
            })()
          )}
        </div>
      </aside>

      {/* Upload Modal */}
      <Modal
        title="上传文章"
        open={uploadModalOpen}
        onCancel={() => { setUploadModalOpen(false); setFileHint('') }}
        footer={[
          <button key="cancel" className="reading-btn-icon" onClick={() => { setUploadModalOpen(false); setFileHint('') }}>
            取消
          </button>,
          <button key="upload" className="reading-btn-convert" style={{ width: 'auto', padding: '6px 24px' }}
            onClick={handleUploadArticle}>
            保存
          </button>,
        ]}
      >
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontWeight: 600, fontSize: '0.9em' }}>标题</label>
          <Input
            value={uploadTitle}
            onChange={e => setUploadTitle(e.target.value)}
            placeholder="文章标题（必填）"
            maxLength={200}
            style={{ marginTop: 4 }}
          />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontWeight: 600, fontSize: '0.9em' }}>内容</label>
          <Input.TextArea
            value={uploadContent}
            onChange={e => setUploadContent(e.target.value)}
            placeholder="文章正文..."
            rows={6}
            style={{ marginTop: 4 }}
          />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontWeight: 600, fontSize: '0.9em', display: 'block', marginBottom: 4 }}>
            或上传 .txt 文件（首行为标题）
          </label>
          <input
            type="file"
            accept=".txt"
            onChange={async (e) => {
              const file = e.target.files?.[0]
              if (file) await handleFileUpload(file)
            }}
            style={{ fontSize: '0.85em' }}
          />
          {fileHint && <div style={{ color: '#059669', fontSize: '0.8em', marginTop: 4 }}>{fileHint}</div>}
        </div>
      </Modal>
    </div>
  )
}
