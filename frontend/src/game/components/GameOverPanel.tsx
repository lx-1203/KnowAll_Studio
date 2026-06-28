import React from 'react'
import { Button, Card, Space, Tag } from 'antd'
import { TrophyOutlined, ReloadOutlined, HomeOutlined } from '@ant-design/icons'
import { useGameStore, getGameStats } from '../hooks/useGameState'

interface GameOverPanelProps {
  isDark: boolean
  onRestart: () => void
  onGoHome: () => void
}

export const GameOverPanel: React.FC<GameOverPanelProps> = ({ isDark, onRestart, onGoHome }) => {
  const stats = getGameStats()
  const quizCorrect = useGameStore(s => s.quizCorrect)
  const quizTotal = useGameStore(s => s.quizTotal)
  const maxTile = useGameStore(s => s.maxTile)

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  const isWin = maxTile >= 2048

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(255,255,255,0.85)',
        zIndex: 100,
        borderRadius: 10,
        backdropFilter: 'blur(4px)',
      }}
    >
      <Card
        style={{
          width: '90%',
          maxWidth: 360,
          borderRadius: 14,
          textAlign: 'center',
          boxShadow: '0 4px 24px rgba(0,0,0,0.12)',
        }}
      >
        <TrophyOutlined style={{ fontSize: 56, color: isWin ? '#faad14' : '#8c8c8c', marginBottom: 12 }} />

        <h2 style={{ margin: '0 0 8px', color: isDark ? '#e5e7eb' : '#1f2937' }}>
          {isWin ? '恭喜通关！' : '游戏结束'}
        </h2>

        <div style={{ marginBottom: 16, color: '#666', fontSize: 13 }}>
          {isWin ? '你成功合成 2048 瓦片！' : '生命值耗尽或无法继续移动'}
        </div>

        {/* Stats grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 8,
          marginBottom: 20,
          textAlign: 'left',
        }}>
          <StatItem label="最终得分" value={stats.score} />
          <StatItem label="最大瓦片" value={stats.maxTile} />
          <StatItem label="移动步数" value={stats.moves} />
          <StatItem label="游戏时长" value={formatTime(stats.elapsedTime)} />
          <StatItem label="答题正确" value={`${quizCorrect}/${quizTotal}`} />
          <StatItem label="答题准确率" value={quizTotal > 0 ? `${Math.round((quizCorrect / quizTotal) * 100)}%` : '-'} />
        </div>

        <Space size={12}>
          <Button
            type="primary"
            size="large"
            icon={<ReloadOutlined />}
            onClick={onRestart}
            style={{ borderRadius: 8 }}
          >
            再来一局
          </Button>
          <Button
            size="large"
            icon={<HomeOutlined />}
            onClick={onGoHome}
            style={{ borderRadius: 8 }}
          >
            返回
          </Button>
        </Space>
      </Card>
    </div>
  )
}

function StatItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{
      padding: '8px 12px',
      backgroundColor: '#fafafa',
      borderRadius: 8,
    }}>
      <div style={{ fontSize: 11, color: '#999', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: '#333' }}>{value}</div>
    </div>
  )
}
