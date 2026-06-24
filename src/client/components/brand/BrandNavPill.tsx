import { Film, MessageSquareText } from 'lucide-react'
import { Link } from 'react-router-dom'
import { AGENT_TOOL, INTERACTIVE_MOVIE_TOOL } from '../../lib/workflowModes'

type BrandNavPillProps = {
  activeKey: typeof AGENT_TOOL.key | typeof INTERACTIVE_MOVIE_TOOL.key
  className?: string
}

const navItems = [
  {
    key: AGENT_TOOL.key,
    icon: <MessageSquareText size={17} />,
    label: AGENT_TOOL.navLabel,
    path: AGENT_TOOL.path,
  },
  {
    key: INTERACTIVE_MOVIE_TOOL.key,
    icon: <Film size={17} />,
    label: '工作空间',
    path: INTERACTIVE_MOVIE_TOOL.path,
  },
]

export default function BrandNavPill({ activeKey, className = '' }: BrandNavPillProps) {
  return (
    <nav className={`brand-nav-pill ${className}`.trim()} aria-label="主导航">
      {navItems.map((item) => (
        <Link
          className={item.key === activeKey ? 'brand-nav-pill__item is-active' : 'brand-nav-pill__item'}
          key={item.key}
          to={item.path}
        >
          {item.icon}
          <span>{item.label}</span>
        </Link>
      ))}
    </nav>
  )
}
