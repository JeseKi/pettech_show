import { Tooltip } from 'antd'
import { Home } from 'lucide-react'
import { Link } from 'react-router-dom'

type WorkbenchHomeButtonProps = {
  className?: string
}

export default function WorkbenchHomeButton({ className = '' }: WorkbenchHomeButtonProps) {
  return (
    <Tooltip title="返回工作台首页">
      <Link
        aria-label="返回工作台首页"
        className={`workbench-home-button ${className}`.trim()}
        to="/dashboard"
      >
        <Home size={18} strokeWidth={2.2} />
      </Link>
    </Tooltip>
  )
}
