import { useState, useRef, useCallback, useEffect } from 'react'
import { Button, Tooltip, Tag } from 'antd'
import { AudioOutlined, AudioMutedOutlined, LoadingOutlined } from '@ant-design/icons'

interface VoiceInputProps {
  onResult: (text: string, isFinal: boolean) => void
  onCommand?: (command: string) => void  // voice commands like "下一空"
  disabled?: boolean
  lang?: string
}

type VoiceState = 'idle' | 'listening' | 'recognizing' | 'error' | 'unsupported'

export default function VoiceInput({ onResult, onCommand, disabled, lang = 'zh-CN' }: VoiceInputProps) {
  const [state, setState] = useState<VoiceState>('idle')
  const [interimText, setInterimText] = useState('')
  const recognitionRef = useRef<any>(null)
  const finalTranscriptRef = useRef('')

  // Check support
  const isSupported = !!(window as any).SpeechRecognition || !!(window as any).webkitSpeechRecognition

  useEffect(() => {
    if (!isSupported) {
      setState('unsupported')
      return
    }
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort()
      }
    }
  }, [isSupported])

  const startListening = useCallback(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRecognition) return

    const recognition = new SpeechRecognition()
    recognition.lang = lang
    recognition.interimResults = true
    recognition.continuous = true
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setState('listening')
      setInterimText('')
      finalTranscriptRef.current = ''
    }

    recognition.onspeechstart = () => {
      setState('recognizing')
    }

    recognition.onresult = (event: any) => {
      let interim = ''
      let final = ''

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) {
          final += result[0].transcript
        } else {
          interim += result[0].transcript
        }
      }

      if (interim) {
        setInterimText(interim)
        onResult(interim, false)
      }

      if (final) {
        finalTranscriptRef.current += final

        // Check for voice commands
        const cmd = final.toLowerCase().trim()
        if (['下一空', '下一个', 'next', '下一题'].includes(cmd) && onCommand) {
          onCommand(cmd)
          setInterimText('')
          return
        }

        onResult(finalTranscriptRef.current, true)
        setInterimText('')
      }
    }

    recognition.onerror = (event: any) => {
      console.warn('Voice recognition error:', event.error)
      if (event.error === 'not-allowed') {
        setState('error')
      } else if (event.error !== 'aborted') {
        // Auto-restart on non-critical errors
        try { recognition.start() } catch {}
      }
    }

    recognition.onend = () => {
      setState('idle')
      setInterimText('')
    }

    recognitionRef.current = recognition
    try {
      recognition.start()
    } catch {}
  }, [lang, onResult, onCommand])

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
    }
    setState('idle')
    setInterimText('')
  }, [])

  if (!isSupported) {
    return (
      <Tooltip title="您的浏览器不支持语音识别，请使用 Chrome 或 Edge">
        <Button size="small" icon={<AudioMutedOutlined />} disabled>
          语音不可用
        </Button>
      </Tooltip>
    )
  }

  const isActive = state === 'listening' || state === 'recognizing'

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <Tooltip title={
        state === 'idle' ? '点击开始语音输入' :
        state === 'listening' ? '正在监听...' :
        state === 'recognizing' ? '正在识别...' :
        state === 'error' ? '麦克风权限未授权，请在浏览器设置中允许' :
        '语音输入'
      }>
        <Button
          size="small"
          type={isActive ? 'primary' : 'default'}
          danger={isActive}
          icon={isActive ? <LoadingOutlined spin /> : <AudioOutlined />}
          onClick={isActive ? stopListening : startListening}
          disabled={disabled || state === 'error' || state === 'unsupported'}
        />
      </Tooltip>
      {isActive && (
        <Tag color="red" style={{ fontSize: 11, margin: 0 }}>
          {state === 'listening' ? '监听中' : '识别中'}
        </Tag>
      )}
      {interimText && (
        <span style={{ color: '#999', fontSize: 12, fontStyle: 'italic', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {interimText}
        </span>
      )}
    </span>
  )
}
