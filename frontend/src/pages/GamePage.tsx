import { useEffect, useRef, useCallback, useState } from 'react'
import { Card, Button, App, Space, Tag, Alert } from 'antd'
import { TrophyOutlined, ToolOutlined, BulbOutlined } from '@ant-design/icons'
import { useTheme } from '../components/ThemeProvider'
import { useGameStore } from '../game/hooks/useGameState'
import { Board2048 } from '../game/components/Board2048'
import { GameHeader } from '../game/components/GameHeader'
import { GameOverPanel } from '../game/components/GameOverPanel'
import { PauseOverlay } from '../game/components/PauseOverlay'
import type { Direction } from '../game/types'

const GAME_ANIMATION_STYLES = `
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes tileAppear {
  from { opacity: 0; transform: scale(0); }
  to { opacity: 1; transform: scale(1); }
}
@keyframes tilePop {
  0% { transform: scale(1); }
  50% { transform: scale(1.2); }
  100% { transform: scale(1); }
}
`

export default function GamePage() {
  const { isDark } = useTheme()
  const { message } = App.useApp()
  const state = useGameStore(s => s.state)
  const startGame = useGameStore(s => s.startGame)
  const makeMove = useGameStore(s => s.makeMove)
  const pauseGame = useGameStore(s => s.pauseGame)
  const resumeGame = useGameStore(s => s.resumeGame)
  const tickTimer = useGameStore(s => s.tickTimer)
  const resetGame = useGameStore(s => s.resetGame)

  const boardRef = useRef<HTMLDivElement>(null)
  const touchStart = useRef<{ x: number; y: number } | null>(null)
  const [boardSize, setBoardSize] = useState(400)

  const gap = 8
  const cellSize = Math.floor((boardSize - gap * 5) / 4)

  // Calculate board size based on viewport
  useEffect(() => {
    function calc() {
      const maxW = Math.min(window.innerWidth - 48, 500)
      const maxH = Math.min(window.innerHeight - 300, 500)
      setBoardSize(Math.min(maxW, maxH))
    }
    calc()
    window.addEventListener('resize', calc)
    return () => window.removeEventListener('resize', calc)
  }, [])

  // Inject animation styles
  useEffect(() => {
    if (document.getElementById('game-animations')) return
    const style = document.createElement('style')
    style.id = 'game-animations'
    style.textContent = GAME_ANIMATION_STYLES
    document.head.appendChild(style)
    return () => { style.remove() }
  }, [])

  // Game timer tick
  useEffect(() => {
    if (state === 'playing') {
      const interval = setInterval(() => tickTimer(), 1000)
      return () => clearInterval(interval)
    }
  }, [state, tickTimer])

  // Keyboard control
  useEffect(() => {
    if (state !== 'playing') return

    function handleKey(e: KeyboardEvent) {
      let dir: Direction | null = null
      switch (e.key) {
        case 'ArrowUp': dir = 'up'; break
        case 'ArrowDown': dir = 'down'; break
        case 'ArrowLeft': dir = 'left'; break
        case 'ArrowRight': dir = 'right'; break
        case 'Escape':
          pauseGame()
          return
        default: return
      }
      e.preventDefault()
      if (dir) {
        makeMove(dir)
      }
    }

    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [state, makeMove, pauseGame])

  // Touch support
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (state !== 'playing') return
    const t = e.touches[0]
    touchStart.current = { x: t.clientX, y: t.clientY }
  }, [state])

  const handleTouchEnd = useCallback((e: React.TouchEvent) => {
    if (state !== 'playing' || !touchStart.current) return
    const t = e.changedTouches[0]
    const dx = t.clientX - touchStart.current.x
    const dy = t.clientY - touchStart.current.y
    const minSwipe = 30

    let dir: Direction | null = null
    if (Math.abs(dx) > Math.abs(dy)) {
      if (Math.abs(dx) > minSwipe) dir = dx > 0 ? 'right' : 'left'
    } else {
      if (Math.abs(dy) > minSwipe) dir = dy > 0 ? 'down' : 'up'
    }

    touchStart.current = null
    if (dir) {
      makeMove(dir)
    }
  }, [state, makeMove])

  const handleStart = () => {
    startGame()
    boardRef.current?.focus()
  }

  const handleRestart = () => {
    startGame()
    boardRef.current?.focus()
  }

  const handleGoHome = () => {
    resetGame()
  }

  return (
    <div>
      <Card
        title={
          <Space>
            <TrophyOutlined style={{ color: '#faad14' }} />
            <span>2048 知识闯关</span>
            <Tag color="default" style={{ fontSize: 11 }}>
              <ToolOutlined /> 答题系统开发中
            </Tag>
          </Space>
        }
        extra={
          <Space>
            <Tag color="blue" style={{ fontSize: 11 }}>
              <BulbOutlined /> 键盘 ↑↓←→ / 滑动
            </Tag>
          </Space>
        }
      >
        {/* Ready state — start screen */}
        {state === 'ready' && (
          <div style={{ textAlign: 'center', padding: '60px 20px' }}>
            <TrophyOutlined style={{ fontSize: 72, color: '#faad14', marginBottom: 16 }} />
            <h2 style={{ color: isDark ? '#e5e7eb' : '#333', marginBottom: 8 }}>
              2048 知识闯关
            </h2>
            <p style={{ color: '#888', fontSize: 14, maxWidth: 400, margin: '0 auto 24px', lineHeight: 1.8 }}>
              经典 2048 数字合并游戏。使用方向键或滑动屏幕操控瓦片，
              合成更大的数字，挑战 2048！
            </p>

            <Alert
              type="warning"
              showIcon
              icon={<ToolOutlined />}
              message="答题系统开发中"
              description="知识问答门禁功能正在开发，当前版本为纯 2048 游戏体验。敬请期待答题闯关模式上线！"
              style={{ maxWidth: 440, margin: '0 auto 24px', textAlign: 'left' }}
            />

            <Button
              type="primary"
              size="large"
              onClick={handleStart}
              style={{ borderRadius: 10, minWidth: 160, height: 48, fontSize: 16, fontWeight: 600 }}
            >
              <TrophyOutlined /> 开始游戏
            </Button>
          </div>
        )}

        {/* Playing / Paused / Game Over */}
        {state !== 'ready' && (
          <div style={{ maxWidth: boardSize + 32, margin: '0 auto' }}>
            <GameHeader isDark={isDark} />

            <div
              ref={boardRef}
              style={{ position: 'relative' }}
              onTouchStart={handleTouchStart}
              onTouchEnd={handleTouchEnd}
            >
              <Board2048 boardSize={boardSize} cellSize={cellSize} gap={gap} />

              {/* Pause overlay */}
              {state === 'paused' && (
                <PauseOverlay
                  onResume={resumeGame}
                  onQuit={resetGame}
                />
              )}

              {/* Game over panel */}
              {state === 'game_over' && (
                <GameOverPanel
                  isDark={isDark}
                  onRestart={handleRestart}
                  onGoHome={handleGoHome}
                />
              )}
            </div>

            {/* Footer hints */}
            <div style={{
              textAlign: 'center',
              color: '#aaa',
              fontSize: 12,
              marginTop: 12,
            }}>
              {state === 'playing' && (
                <>方向键或滑动屏幕操控 | Esc 暂停</>
              )}
              {state === 'game_over' && (
                <>点击「再来一局」继续挑战</>
              )}
            </div>

            {/* Quiz in development notice */}
            <Alert
              type="warning"
              showIcon
              icon={<ToolOutlined />}
              message="答题系统开发中，敬请期待"
              banner
              style={{ marginTop: 12, borderRadius: 8 }}
            />
          </div>
        )}
      </Card>
    </div>
  )
}
