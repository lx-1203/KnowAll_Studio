import type { SVGProps } from 'react'

const base: SVGProps<SVGSVGElement> = {
  viewBox: '0 0 24 24',
  width: '1em',
  height: '1em',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: '2',
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

/** 学习仪表盘 — 四格仪表盘，一格里含折线增长 */
export function DashboardIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...p}>
      <rect x="3" y="3" width="8" height="8" rx="1.5" />
      <rect x="13" y="3" width="8" height="8" rx="1.5" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" />
      <polyline points="15,19 17,15 21,17" />
    </svg>
  )
}

/** 题库练习 — 剪贴板 + 勾选 */
export function QuizIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...p}>
      <path d="M8 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V5a2 2 0 00-2-2h-1" />
      <rect x="9" y="3" width="6" height="3" rx="1" />
      <polyline points="9 12 11 14 15 10" />
    </svg>
  )
}

/** 记忆闪卡 — 两张层叠卡片 + 记忆波纹 */
export function FlashcardIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...p}>
      <rect x="3" y="5" width="16" height="13" rx="2" />
      <rect x="5" y="2" width="16" height="13" rx="2" />
      <line x1="7" y1="9" x2="17" y2="9" />
      <line x1="7" y1="12" x2="14" y2="12" />
    </svg>
  )
}

/** 学习计划 — 日历本 + 标记点 */
export function StudyPlanIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...p}>
      <rect x="4" y="4" width="16" height="17" rx="2" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="4" y1="10" x2="20" y2="10" />
      <circle cx="9" cy="14" r="1" fill="currentColor" stroke="none" />
      <circle cx="9" cy="18" r="1" fill="currentColor" stroke="none" />
      <line x1="11" y1="14" x2="16" y2="14" />
      <line x1="11" y1="18" x2="14" y2="18" />
    </svg>
  )
}

/** 思维导图 — 中心节点放射连接四角 */
export function MindMapIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...p}>
      <circle cx="12" cy="12" r="3" />
      <circle cx="4" cy="6" r="2" />
      <circle cx="20" cy="6" r="2" />
      <circle cx="4" cy="18" r="2" />
      <circle cx="20" cy="18" r="2" />
      <line x1="10" y1="10.5" x2="5.5" y2="7" />
      <line x1="14" y1="10.5" x2="18.5" y2="7" />
      <line x1="10" y1="13.5" x2="5.5" y2="17" />
      <line x1="14" y1="13.5" x2="18.5" y2="17" />
    </svg>
  )
}

/** 资料导入 — 收件盒 + 下箭头 */
export function UploadIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...p}>
      <path d="M20 14v3a2 2 0 01-2 2H6a2 2 0 01-2-2v-3" />
      <polyline points="8 10 12 6 16 10" />
      <line x1="12" y1="6" x2="12" y2="17" />
    </svg>
  )
}

/** 全局搜索 — 放大镜 + 十字线 */
export function SearchIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...p}>
      <circle cx="11" cy="11" r="7" />
      <line x1="16.5" y1="16.5" x2="21" y2="21" />
      <line x1="8" y1="11" x2="14" y2="11" />
      <line x1="11" y1="8" x2="11" y2="14" />
    </svg>
  )
}

/** AI助手 — 四角星光 */
export function AIIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...p}>
      <path d="M12 2.5L13.8 8.2 20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8z" />
      <circle cx="19" cy="5" r="1" fill="currentColor" stroke="none" />
      <circle cx="5" cy="19" r="0.8" fill="currentColor" stroke="none" />
    </svg>
  )
}

/** 答题回顾 — 眼睛 + 趋势折线 */
export function ReviewIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...p}>
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

/** 互动游戏 — 游戏手柄 */
export function GameIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...p}>
      <path d="M6.5 10h11a3.5 3.5 0 013.5 3.5v1a3.5 3.5 0 01-3.5 3.5h-11a3.5 3.5 0 01-3.5-3.5v-1a3.5 3.5 0 013.5-3.5z" />
      <line x1="8" y1="12.5" x2="8" y2="15.5" />
      <line x1="6.5" y1="14" x2="9.5" y2="14" />
      <circle cx="14.5" cy="14" r="1.3" />
      <circle cx="17.5" cy="12.5" r="1.3" />
    </svg>
  )
}

/** 个人中心 — 人物半身 */
export function UserIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...p}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0-4 4-7 8-7s8 3 8 7" />
    </svg>
  )
}

/** 协作分享 — 三节点拓扑 */
export function ShareIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...p}>
      <circle cx="6" cy="12" r="2.5" />
      <circle cx="18" cy="6" r="2.5" />
      <circle cx="18" cy="18" r="2.5" />
      <line x1="8.5" y1="12" x2="15.5" y2="7" />
      <line x1="8.5" y1="12" x2="15.5" y2="17" />
      <line x1="15.5" y1="8.5" x2="15.5" y2="16.5" />
    </svg>
  )
}

/** 系统设置 — 齿轮 */
export function SettingsIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...p}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  )
}
