import { ChevronDown, LayoutDashboard, LogIn } from 'lucide-react'
import BrandLogo from '../../../components/brand/BrandLogo'
import { BRAND_NAME } from '../../../lib/brand'
import { navGroups } from './pageData'

type LandingNavProps = {
  isAuthenticated: boolean
  onAuthAction: () => void
  onConsult: () => void
}

export function LandingNav({ isAuthenticated, onAuthAction, onConsult }: LandingNavProps) {
  return (
    <header className="landing-nav">
      <a className="landing-brand" href="#courses" aria-label={`${BRAND_NAME}首页`}>
        <BrandLogo compact size={32} />
        <span>{BRAND_NAME}</span>
      </a>
      <nav className="landing-nav__links" aria-label="主导航">
        {navGroups.map((group) => (
          <div className="landing-nav__item" key={group.label}>
            <a href={group.href}>
              {group.label}
              <ChevronDown size={15} />
            </a>
            <div className="landing-mega">
              {group.items.map(([title, text]) => (
                <a href={group.href} key={title}>
                  <strong>{title}</strong>
                  <span>{text}</span>
                </a>
              ))}
            </div>
          </div>
        ))}
        <a href="#contact">预约咨询</a>
      </nav>
      <div className="landing-nav__actions">
        <button type="button" onClick={onAuthAction}>
          {isAuthenticated ? <LayoutDashboard size={17} /> : <LogIn size={17} />}
          {isAuthenticated ? '进入工作台' : '登录'}
        </button>
        <button className="is-primary" type="button" onClick={onConsult}>
          预约咨询
        </button>
      </div>
    </header>
  )
}
