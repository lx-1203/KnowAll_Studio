import { useEffect, useRef } from 'react'

// Lazy-load KaTeX
let katex: any = null
async function loadKatex() {
  if (!katex) {
    const mod = await import('katex')
    katex = mod.default || mod
  }
  return katex
}

interface LaTeXProps {
  text: string
  displayMode?: boolean
}

export default function LaTeX({ text, displayMode = false }: LaTeXProps) {
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    let cancelled = false
    loadKatex().then(ktx => {
      if (cancelled || !ref.current) return
      try {
        ktx.render(text, ref.current, {
          displayMode,
          throwOnError: false,
          trust: true,
        })
      } catch {
        ref.current.textContent = text
      }
    })
    return () => { cancelled = true }
  }, [text, displayMode])

  return <span ref={ref} style={{ display: displayMode ? 'block' : 'inline' }} />
}

/**
 * Render text containing inline LaTeX ($...$ and $$...$$).
 */
export function renderMixedText(text: string): (string | { latex: string; display: boolean })[] {
  const parts: (string | { latex: string; display: boolean })[] = []
  const regex = /\$\$([\s\S]*?)\$\$|\$(.*?)\$/g
  let last = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(text.slice(last, match.index))
    }
    if (match[1] !== undefined) {
      parts.push({ latex: match[1], display: true })
    } else if (match[2] !== undefined) {
      parts.push({ latex: match[2], display: false })
    }
    last = regex.lastIndex
  }

  if (last < text.length) {
    parts.push(text.slice(last))
  }

  return parts
}

export function RichText({ text }: { text: string }) {
  const parts = renderMixedText(text)
  return (
    <span>
      {parts.map((part, i) =>
        typeof part === 'string' ? (
          <span key={i}>{part}</span>
        ) : (
          <LaTeX key={i} text={part.latex} displayMode={part.display} />
        )
      )}
    </span>
  )
}
