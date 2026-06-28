import React from 'react'
import { Button, Space } from 'antd'
import { PlayCircleOutlined, HomeOutlined } from '@ant-design/icons'

interface PauseOverlayProps {
  onResume: () => void
  onQuit: () => void
}

export const PauseOverlay: React.FC<PauseOverlayProps> = ({ onResume, onQuit }) => {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0,0,0,0.55)',
        zIndex: 90,
        borderRadius: 10,
        backdropFilter: 'blur(3px)',
        animation: 'fadeIn 0.2s ease',
      }}
    >
      <div
        style={{
          fontSize: 36,
          fontWeight: 700,
          color: '#fff',
          marginBottom: 4,
          letterSpacing: 4,
        }}
      >
        暂停中
      </div>
      <div style={{ fontSize: 14, color: 'rgba(255,255,255,0.7)', marginBottom: 28 }}>
        休息一下，马上回来
      </div>

      <Space direction="vertical" size={12}>
        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          onClick={onResume}
          style={{ borderRadius: 10, minWidth: 180, height: 44 }}
        >
          继续游戏
        </Button>
        <Button
          size="large"
          icon={<HomeOutlined />}
          onClick={onQuit}
          style={{ borderRadius: 10, minWidth: 180, height: 44 }}
        >
          退出游戏
        </Button>
      </Space>
    </div>
  )
}
