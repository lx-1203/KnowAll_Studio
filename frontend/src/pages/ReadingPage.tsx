import { useState, useEffect, useCallback, useRef } from 'react'
import { App } from 'antd'
import { getReadingArticles, getReadingArticle, convertReadingText } from '../api'
import { useTheme } from '../components/ThemeProvider'
import './ReadingPage.css'

interface Article {
  id: number
  title: string
  difficulty: number
  content: string
  tags: string[]
}

interface VocabItem {
  cn: string
  en: string
}

interface ConvertResult {
  result: string
  vocabulary: VocabItem[]
  level: number
  ratio: string
  word_count: number
  source: string
}

interface SavedWord {
  cn: string
  en: string
  time: number
}

interface ReadStats {
  totalRead: number
  totalWords: number
}

const STORAGE_SAVED = 'reading_lang_saved'
const STORAGE_STATS = 'reading_lang_stats'

function loadSavedWords(): Record<string, SavedWord> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_SAVED) || '{}')
  } catch {
    return {}
  }
}

function loadReadStats(): ReadStats {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_STATS) || '{"totalRead":0,"totalWords":0}')
  } catch {
    return { totalRead: 0, totalWords: 0 }
  }
}

function renderMixedText(result: string, vocabulary: VocabItem[], revealMode: boolean): string {
  const enToCn: Record<string, string[]> = {}
  vocabulary.forEach(v => {
    const key = v.en.toLowerCase()
    if (!enToCn[key]) enToCn[key] = []
    enToCn[key].push(v.cn)
  })

  const used: Record<string, number> = {}
  const parts: string[] = []
  const regex = /([a-zA-Z]+(?:'[a-zA-Z]+)?|\s+|[^a-zA-Z\s]+)/g
  let match
  while ((match = regex.exec(result)) !== null) {
    const token = match[0]
    const key = token.toLowerCase()
    if (/^[a-zA-Z]/.test(token) && enToCn[key]) {
      const idx = used[key] || 0
      used[key] = idx + 1
      const cnList = enToCn[key]
      const cn = cnList[idx] || cnList[0] || ''
      const escaped = token.replace(/</g, '&lt;').replace(/>/g, '&gt;')
      parts.push(
        `<span class="en-word ${revealMode ? 'revealed' : ''}" data-cn="${cn.replace(/"/g, '&quot;')}">${escaped}<span class="cn-tip">${revealMode ? cn : '?'}</span></span>`
      )
    } else {
      parts.push(token.replace(/</g, '&lt;').replace(/>/g, '&gt;'))
    }
  }
  return parts.join('')
}

export default function ReadingPage() {
  const { message } = App.useApp()
  const { isDark } = useTheme()

  const [currentLevel, setCurrentLevel] = useState(1)
  const [activeTab, setActiveTab] = useState<'articles' | 'custom'>('articles')
  const [articles, setArticles] = useState<Article[]>([])
  const [currentArticle, setCurrentArticle] = useState<Article | null>(null)
  const [currentVocab, setCurrentVocab] = useState<VocabItem[]>([])
  const [revealMode, setRevealMode] = useState(true)
  const [savedWords, setSavedWords] = useState<Record<string, SavedWord>>(loadSavedWords)
  const [customText, setCustomText] = useState('')
  const [loading, setLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [panelOpen, setPanelOpen] = useState(false)
  const [renderedHtml, setRenderedHtml] = useState('')
  const [showStats, setShowStats] = useState(false)
  const [statLevel, setStatLevel] = useState('-')
  const [statRatio, setStatRatio] = useState('-')
  const [statWords, setStatWords] = useState('-')
  const [titleText, setTitleText] = useState('选择一篇文章开始阅读')
  const customTextRef = useRef<HTMLTextAreaElement>(null)
  const currentLevelRef = useRef(currentLevel)
  currentLevelRef.current = currentLevel

  // Load articles
  const loadArticles = useCallback(async () => {
    try {
      const data = await getReadingArticles()
      setArticles(data)
    } catch {
      // silent
    }
  }, [])

  useEffect(() => {
    loadArticles()
  }, [loadArticles])

  // Core conversion logic - accepts explicit level to avoid stale closures
  const doConvert = useCallback(async (text: string, level: number, title: string, article: Article | null) => {
    setTitleText(title)
    setShowStats(true)
    setLoading(true)
    try {
      const data: ConvertResult = await convertReadingText(text, level)
      if ((data as any).error) {
        message.error((data as any).error)
        return
      }
      setCurrentVocab(data.vocabulary)
      setCurrentArticle(article)
      setStatLevel('L' + data.level)
      setStatRatio(data.ratio)
      setStatWords(String(data.word_count))
      const finalTitle = data.source === 'dictionary' ? title + ' [离线模式]' : title
      setTitleText(finalTitle)
      const html = renderMixedText(data.result, data.vocabulary, revealMode)
      setRenderedHtml(html)

      // Persist reading stats
      try {
        const prev = JSON.parse(localStorage.getItem(STORAGE_STATS) || '{"totalRead":0,"totalWords":0}')
        prev.totalRead += 1
        prev.totalWords += data.word_count
        localStorage.setItem(STORAGE_STATS, JSON.stringify(prev))
      } catch { /* ignore */ }
    } catch {
      message.error('请求失败，请检查服务是否运行')
    } finally {
      setLoading(false)
    }
  }, [message, revealMode])

  // Select article
  const selectArticle = useCallback(async (id: number) => {
    try {
      const article = await getReadingArticle(id)
      if ((article as any).error) return
      await loadArticles()
      await doConvert(article.content, currentLevelRef.current, article.title, article)
      setSidebarOpen(false)
    } catch {
      // silent
    }
  }, [loadArticles, doConvert])

  // Re-convert when level changes
  useEffect(() => {
    if (currentArticle) {
      doConvert(currentArticle.content, currentLevel, currentArticle.title, currentArticle)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentLevel])

  // Convert custom text
  const convertCustom = useCallback(async () => {
    const text = customText.trim()
    if (!text) {
      message.warning('请输入文本')
      return
    }
    await doConvert(text, currentLevel, '自定义文本', null)
  }, [customText, currentLevel, doConvert, message])

  // Click handler for word toggling (delegated via the reading area)
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

  // Global toggle reveal
  const toggleReveal = useCallback(() => {
    setRevealMode(prev => !prev)
  }, [])

  // Apply reveal mode to all word elements when revealMode or renderedHtml changes
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

  // Refresh reading
  const refreshReading = useCallback(() => {
    if (currentArticle) {
      doConvert(currentArticle.content, currentLevel, currentArticle.title, currentArticle)
    }
  }, [currentArticle, currentLevel, doConvert])

  // Save/unsave word
  const toggleSaveWord = useCallback((key: string, cn: string, en: string) => {
    setSavedWords(prev => {
      const next = { ...prev }
      if (next[key]) {
        delete next[key]
        message.success(`已取消收藏 "${en}"`)
      } else {
        next[key] = { cn, en, time: Date.now() }
        message.success(`已收藏 "${en}" ← "${cn}"`)
      }
      localStorage.setItem(STORAGE_SAVED, JSON.stringify(next))
      return next
    })
  }, [message])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (activeTab === 'custom') {
          e.preventDefault()
          convertCustom()
        }
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault()
        refreshReading()
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
        e.preventDefault()
        toggleReveal()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [activeTab, convertCustom, refreshReading, toggleReveal])

  const savedCount = Object.keys(savedWords).length
  const levelLabels: Record<number, string> = { 1: '10-25%英文', 2: '25-50%英文', 3: '50-80%英文' }
  const levelNames: Record<number, string> = { 1: '初级', 2: '中级', 3: '高级' }

  return (
    <div className={`reading-app${isDark ? ' dark' : ''}`}>
      {/* Left Sidebar */}
      <aside className={`reading-sidebar${sidebarOpen ? ' mobile-open' : ''}`}>
        <div className="reading-sidebar-header">
          <div className="reading-logo">阅读语言</div>
          <div className="reading-logo-sub">渐进式语言学习工具</div>
        </div>

        <div className="reading-level-selector">
          {[1, 2, 3].map(level => (
            <button
              key={level}
              className={`reading-level-btn${currentLevel === level ? ` active l${level}` : ''}`}
              onClick={() => setCurrentLevel(level)}
            >
              {levelNames[level]}
              <span className="reading-level-label">{levelLabels[level]}</span>
            </button>
          ))}
        </div>

        <div className="reading-sidebar-nav">
          <button
            className={activeTab === 'articles' ? 'active' : ''}
            onClick={() => setActiveTab('articles')}
          >
            文章库
          </button>
          <button
            className={activeTab === 'custom' ? 'active' : ''}
            onClick={() => setActiveTab('custom')}
          >
            自定义
          </button>
        </div>

        <div className="reading-sidebar-content">
          {activeTab === 'articles' ? (
            <div>
              {articles.map(a => (
                <div
                  key={a.id}
                  className={`reading-article-item${currentArticle?.id === a.id ? ' active' : ''}`}
                  onClick={() => selectArticle(a.id)}
                >
                  <div className="reading-article-title">
                    {a.title}
                    <span className={`reading-diff-badge d${a.difficulty}`}>L{a.difficulty}</span>
                  </div>
                  <div className="reading-article-meta">
                    {a.tags.map(t => (
                      <span key={t} className="reading-tag">{t}</span>
                    ))}
                    <span>{a.content.length}字</span>
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
              <button className="reading-btn-convert" onClick={convertCustom} disabled={loading}>
                开始阅读
              </button>
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
              {revealMode ? '显示中文' : '隐藏中文'}
            </button>
            <button className="reading-btn-icon" onClick={refreshReading} disabled={loading}>
              刷新
            </button>
            <button className="reading-btn-icon" onClick={() => setSidebarOpen(v => !v)}>
              菜单
            </button>
            <button className="reading-btn-icon" onClick={() => setPanelOpen(v => !v)}>
              单词本
            </button>
          </div>
        </div>

        {showStats && (
          <div className="reading-stats-bar">
            <div className="reading-stat-item">
              等级: <span className="reading-stat-value">{statLevel}</span>
            </div>
            <div className="reading-stat-item">
              替换率: <span className="reading-stat-value">{statRatio}</span>
            </div>
            <div className="reading-stat-item">
              生词: <span className="reading-stat-value">{statWords}</span>
            </div>
            <div className="reading-stat-item">
              已收藏: <span className="reading-stat-value">{savedCount}</span>
            </div>
          </div>
        )}

        <div className="reading-area">
          <div className="reading-content">
            {!showStats ? (
              <div className="reading-empty">
                <h3>欢迎使用阅读语言</h3>
                <p>
                  从左侧选择一篇文章，或输入自定义文本<br />
                  开始您的渐进式英语学习之旅
                </p>
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
          正在阅读的生词 <span className="reading-panel-badge">{currentVocab.length}</span>
        </div>
        <div className="reading-panel-content">
          {currentVocab.length === 0 ? (
            <div className="reading-panel-empty">
              {showStats ? '当前文本无可替换词汇' : '选择文章后，这里会显示当前文本中的生词'}
            </div>
          ) : (
            currentVocab.map((v, i) => {
              const key = `${v.cn}_${v.en}`
              const saved = savedWords[key]
              return (
                <div key={i} className={`reading-vocab-card${saved ? ' saved' : ''}`}>
                  <div>
                    <span className="reading-vocab-en">{v.en}</span>
                    <span className="reading-vocab-cn"> ← {v.cn}</span>
                  </div>
                  <button
                    className={`reading-vocab-save-btn${saved ? ' saved' : ''}`}
                    onClick={() => toggleSaveWord(key, v.cn, v.en)}
                  >
                    {saved ? '✓' : '+'}
                  </button>
                </div>
              )
            })
          )}
        </div>
      </aside>
    </div>
  )
}
