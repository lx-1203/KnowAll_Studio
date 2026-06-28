import React, { useEffect, useState } from 'react'

interface FeedbackOverlayProps {
  isCorrect: boolean
  message?: string
  visible: boolean
  onDone?: () => void
}

export const FeedbackOverlay: React.FC<FeedbackOverlayProps> = ({
  isCorrect,
  message,
  visible,
  onDone,
}) => {
  const [show, setShow] = useState(false)

  useEffect(() => {
    if (visible) {
      setShow(true)
      const timer = setTimeout(() => {
        setShow(false)
        onDone?.()
      }, 1200)
      return () => clearTimeout(timer)
    }
    return undefined
  }, [visible, onDone])

  if (!show) return null

  return (
    <div
      style={{
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 2000,
        pointerEvents: 'none',
        animation: 'feedbackPopIn 0.3s ease-out',
      }}
    >
      <div
        style={{
          fontSize: 42,
          fontWeight: 800,
          color: isCorrect ? '#52c41a' : '#ff4d4f',
          textShadow: '0 4px 20px rgba(0,0,0,0.2)',
          textAlign: 'center',
          lineHeight: 1.2,
        }}
      >
        {isCorrect ? '✓' : '✗'}
      </div>
      <div
        style={{
          fontSize: 18,
          fontWeight: 600,
          color: isCorrect ? '#52c41a' : '#ff4d4f',
          textAlign: 'center',
          textShadow: '0 2px 10px rgba(0,0,0,0.15)',
        }}
      >
        {message || (isCorrect ? '回答正确！' : '回答错误！')}
      </div>
    </div>
  )
}
