import React from 'react'

interface QuizTimerProps {
  timeLeft: number
  totalTime: number
  isWarning: boolean
}

export const QuizTimer: React.FC<QuizTimerProps> = ({ timeLeft, totalTime, isWarning }) => {
  const pct = (timeLeft / totalTime) * 100
  const radius = 28
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference * (1 - pct / 100)

  return (
    <div style={{ position: 'relative', width: 72, height: 72, margin: '0 auto' }}>
      <svg width="72" height="72" style={{ transform: 'rotate(-90deg)' }}>
        <circle
          cx="36" cy="36" r={radius}
          fill="none"
          stroke="#eee"
          strokeWidth="4"
        />
        <circle
          cx="36" cy="36" r={radius}
          fill="none"
          stroke={isWarning ? '#ff4d4f' : '#4f46e5'}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          style={{ transition: 'stroke-dashoffset 1s linear, stroke 0.3s' }}
        />
      </svg>
      <div
        style={{
          position: 'absolute',
          top: 0, left: 0, right: 0, bottom: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 22,
          fontWeight: 700,
          color: isWarning ? '#ff4d4f' : '#333',
          transition: 'color 0.3s',
        }}
      >
        {timeLeft}
      </div>
    </div>
  )
}
