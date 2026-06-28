import { useEffect, useState } from 'react'
import { Tree } from 'antd'
import type { DataNode } from 'antd/es/tree'

interface Props {
  content: string
}

export default function MarkdownTOC({ content }: Props) {
  const [treeData, setTreeData] = useState<DataNode[]>([])

  useEffect(() => {
    if (!content) return
    const headings = parseHeadings(content)
    const tree = buildTree(headings)
    setTreeData(tree)
  }, [content])

  const onSelect = (selectedKeys: React.Key[]) => {
    if (selectedKeys.length > 0) {
      const id = selectedKeys[0] as string
      const el = document.getElementById(id)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }
  }

  if (treeData.length === 0) {
    return <div style={{ color: '#999', fontSize: 13 }}>无目录结构</div>
  }

  return (
    <Tree
      treeData={treeData}
      onSelect={onSelect}
      defaultExpandAll
      showLine={{ showLeafIcon: false }}
      style={{ fontSize: 13 }}
    />
  )
}

interface Heading {
  id: string
  level: number
  text: string
}

function parseHeadings(md: string): Heading[] {
  const headings: Heading[] = []
  const lines = md.split('\n')
  for (const line of lines) {
    const match = line.match(/^(#{1,3})\s+(.+)/)
    if (match) {
      const level = match[1].length
      const text = match[2].replace(/[🔴🟡🟢🟠]【[^】]*】/, '').trim()
      // 安全编码：过滤所有可能导致 encodeURIComponent 抛出 URIError 的字符
      let safe = text
      try {
        encodeURIComponent(safe)
      } catch {
        // 如果编码失败，逐步移除问题字符
        safe = safe.replace(/[\uD800-\uDFFF]/g, '\uFFFD')
        safe = safe.replace(/[^\u0000-\uD7FF\uE000-\uFFFF]/g, '')
        try { encodeURIComponent(safe) } catch { safe = 'section' }
      }
      const id = 'heading-' + encodeURIComponent(safe)
      headings.push({ id, level, text })
    }
  }
  return headings
}

function buildTree(headings: Heading[]): DataNode[] {
  const root: DataNode[] = []
  const stack: { node: DataNode; level: number }[] = []

  for (const h of headings) {
    const node: DataNode = {
      key: h.id,
      title: h.text,
      isLeaf: h.level === 3,
    }

    while (stack.length > 0 && stack[stack.length - 1].level >= h.level) {
      stack.pop()
    }

    if (stack.length === 0) {
      root.push(node)
    } else {
      const parent = stack[stack.length - 1].node
      if (!parent.children) parent.children = []
      parent.children.push(node)
    }

    stack.push({ node, level: h.level })
  }

  return root
}
