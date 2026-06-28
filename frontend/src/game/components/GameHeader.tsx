import React from 'react'
import { Button, Space, Tag } from 'antd'
import {
  PauseCircleOutlined,
  PlayCircleOutlined,
  StopOutlined,
  HeartFilled,
  TrophyOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons'
import { useGameStore } from '../hooks/useGameState'

interface GameHeaderProps {
  isDark: boolean
}

export const GameHeader: React.FC<GameHeaderProps> = ({ isDark }) => {
  const state = useGameStore(s => s.state)
  const score = useGameStore(s => s.score)
  const maxTile = useGameStore(s => s.maxTile)
  const lives = useGameStore(s => s.lives)
  const quizTotal = useGameStore(s => s.quizTotal)
  const quizCorrect = useGameStore(s => s.quizCorrect)
  const elapsedTime = useGameStore(s => s.elapsedTime)
  const pauseGame = useGameStore(s => s.pauseGame)
  const resumeGame = useGameStore(s => s.resumeGame)
  const endGame = useGameStore(s => s.endGame)

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  const tagBg = isDark ? 'rgba(255,255,255,0.1)' : '#fff'
  const tagColor = isDark ? '#e5e7eb' : '#333'

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
        marginBottom: 16,
        padding: '12px 16px',
        backgroundColor: isDark ? 'rgba(255,255,255,0.05)' : '#fafafa',
        borderRadius: 10,
      }}
    >
      <Space wrap size={[8, 8]}>
        <Tag icon={<TrophyOutlined />} color="gold" style={{ fontSize: 15, padding: '4px 12px', fontWeight: 700 }}>
          {score}
        </Tag>
        <Tag style={{ background: tagBg, color: tagColor, fontSize: 13 }}>
          最高: {maxTile}
        </Tag>
        <Tag style={{ background: tagBg, color: tagColor, fontSize: 13 }}>
          {formatTime(elapsedTime)}
        </Tag>
        <span>
          {Array.from({ length: 3 }).map((_, i) => (
            <HeartFilled
              key={i}
              style={{
                color: i < lives ? '#ff4d4f' : '#ddd',
                fontSize: 16,
                marginRight: 2,
                transition: 'color 0.3s',
              }}
            />
          ))}
        </span>
      </Space>

      <Space wrap size={[8, 8]}>
        {quizTotal > 0 && (
          <Tag icon={<QuestionCircleOutlined />} color="purple">
            {quizCorrect}/{quizTotal}
          </Tag>
        )}

        {state === 'playing' && (
          <Button
            size="small"
            icon={<PauseCircleOutlined />}
            onClick={pauseGame}
          >
            暂停
          </Button>
        )}
        {state === 'paused' && (
          <Button
            size="small"
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={resumeGame}
          >
            继续
          </Button>
        )}
        {(state === 'playing' || state === 'paused') && (
          <Button
            size="small"
            danger
            icon={<StopOutlined />}
            onClick={endGame}
          >
            结束
          </Button>
        )}
      </Space>
    </div>
  )
}
