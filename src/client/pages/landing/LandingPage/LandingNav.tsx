import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronDown, LayoutDashboard, LogIn, Menu, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import BrandLogo from '../../../components/brand/BrandLogo'
import { BRAND_NAME } from '../../../lib/brand'
import { landingNavGroups } from './pageData'

type LandingNavProps = {
  isAuthenticated: boolean
  onAuthAction: () => void
}

const NAV_MENU_OPEN_DELAY_MS = 120
const NAV_MENU_CLOSE_DELAY_MS = 500

export function LandingNav({ isAuthenticated, onAuthAction }: LandingNavProps) {
  const [activeNavLabel, setActiveNavLabel] = useState<string | null>(null)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [activeMobileGroupLabel, setActiveMobileGroupLabel] = useState(() => landingNavGroups[0]?.label ?? '')
  const openTimerRef = useRef(0)
  const closeTimerRef = useRef(0)

  const clearOpenTimer = useCallback(() => {
    if (!openTimerRef.current) return
    window.clearTimeout(openTimerRef.current)
    openTimerRef.current = 0
  }, [])

  const clearCloseTimer = useCallback(() => {
    if (!closeTimerRef.current) return
    window.clearTimeout(closeTimerRef.current)
    closeTimerRef.current = 0
  }, [])

  const openNavMenu = useCallback((label: string, immediate = false) => {
    clearOpenTimer()
    clearCloseTimer()
    if (immediate || activeNavLabel !== null) {
      setActiveNavLabel(label)
      return
    }
    openTimerRef.current = window.setTimeout(() => {
      setActiveNavLabel(label)
      openTimerRef.current = 0
    }, NAV_MENU_OPEN_DELAY_MS)
  }, [activeNavLabel, clearCloseTimer, clearOpenTimer])

  const scheduleNavMenuClose = useCallback(() => {
    clearOpenTimer()
    clearCloseTimer()
    closeTimerRef.current = window.setTimeout(() => {
      setActiveNavLabel(null)
      closeTimerRef.current = 0
    }, NAV_MENU_CLOSE_DELAY_MS)
  }, [clearCloseTimer, clearOpenTimer])

  const closeNavMenu = useCallback(() => {
    clearOpenTimer()
    clearCloseTimer()
    setActiveNavLabel(null)
  }, [clearCloseTimer, clearOpenTimer])

  const closeAllMenus = useCallback(() => {
    closeNavMenu()
    setMobileMenuOpen(false)
  }, [closeNavMenu])

  useEffect(() => () => {
    clearOpenTimer()
    clearCloseTimer()
  }, [clearCloseTimer, clearOpenTimer])

  useEffect(() => {
    const mobileMenuClassName = 'landing-mobile-menu-open'
    if (!mobileMenuOpen) {
      document.documentElement.classList.remove(mobileMenuClassName)
      document.body.classList.remove(mobileMenuClassName)
      return undefined
    }

    document.documentElement.classList.add(mobileMenuClassName)
    document.body.classList.add(mobileMenuClassName)

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeAllMenus()
    }

    window.addEventListener('keydown', handleKeyDown)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      document.documentElement.classList.remove(mobileMenuClassName)
      document.body.classList.remove(mobileMenuClassName)
    }
  }, [closeAllMenus, mobileMenuOpen])

  return (
    <header className="landing-nav">
      <a className="landing-brand" href="#courses" aria-label={`${BRAND_NAME}首页`}>
        <BrandLogo compact size={32} />
        <span>{BRAND_NAME}</span>
      </a>
      <nav className="landing-nav__links" aria-label="主导航">
        {landingNavGroups.map((group) => {
          const GroupIcon = group.icon
          const menuClassName = group.items.length > 4
            ? `landing-nav__menu landing-nav__menu--wide${activeNavLabel === group.label ? ' is-open' : ''}`
            : `landing-nav__menu${activeNavLabel === group.label ? ' is-open' : ''}`

          return (
            <div
              className={activeNavLabel === group.label ? 'landing-nav__item is-open' : 'landing-nav__item'}
              key={group.label}
              onPointerEnter={() => openNavMenu(group.label)}
              onPointerLeave={scheduleNavMenuClose}
              onFocusCapture={() => openNavMenu(group.label, true)}
              onBlurCapture={(event) => {
                if (event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)) return
                scheduleNavMenuClose()
              }}
            >
              <Link
                className="landing-nav__trigger"
                to={group.path}
                aria-haspopup="true"
                aria-expanded={activeNavLabel === group.label}
                onClick={closeAllMenus}
              >
                <GroupIcon size={16} />
                <span>{group.label}</span>
                <ChevronDown className="landing-nav__chevron" size={14} />
              </Link>
              <div className={menuClassName} aria-label={`${group.label}子菜单`}>
                {group.items.map((item) => {
                  const ItemIcon = item.icon

                  return (
                    <Link className="landing-nav__menu-link" to={item.path} key={item.path} onClick={closeAllMenus}>
                      <span className="landing-nav__menu-icon">
                        <ItemIcon size={17} />
                      </span>
                      <span className="landing-nav__menu-copy">
                        <strong>{item.label}</strong>
                        <span>{item.description}</span>
                      </span>
                    </Link>
                  )
                })}
              </div>
            </div>
          )
        })}
      </nav>
      <button
        className={mobileMenuOpen ? 'landing-nav__mobile-toggle is-open' : 'landing-nav__mobile-toggle'}
        type="button"
        aria-controls="landing-mobile-menu"
        aria-expanded={mobileMenuOpen}
        onClick={() => {
          closeNavMenu()
          setMobileMenuOpen((current) => !current)
        }}
      >
        {mobileMenuOpen ? <X size={17} /> : <Menu size={17} />}
        <span>菜单</span>
      </button>
      <div className="landing-nav__actions">
        <button
          className="is-primary"
          type="button"
          onClick={() => {
            closeAllMenus()
            onAuthAction()
          }}
        >
          {isAuthenticated ? <LayoutDashboard size={17} /> : <LogIn size={17} />}
          <span className="landing-nav__auth-label landing-nav__auth-label--full">
            {isAuthenticated ? '进入工作台' : '登录查看功能'}
          </span>
          <span className="landing-nav__auth-label landing-nav__auth-label--short">
            {isAuthenticated ? '工作台' : '登录'}
          </span>
        </button>
      </div>
      <div
        id="landing-mobile-menu"
        className={mobileMenuOpen ? 'landing-mobile-menu is-open' : 'landing-mobile-menu'}
        aria-hidden={!mobileMenuOpen}
      >
        {landingNavGroups.map((group) => {
          const GroupIcon = group.icon
          const groupOpen = activeMobileGroupLabel === group.label

          return (
            <section className="landing-mobile-menu__group" key={group.label}>
              <button
                className={groupOpen ? 'landing-mobile-menu__group-trigger is-open' : 'landing-mobile-menu__group-trigger'}
                type="button"
                aria-expanded={groupOpen}
                onClick={() => setActiveMobileGroupLabel((current) => (current === group.label ? '' : group.label))}
              >
                <span className="landing-mobile-menu__group-icon">
                  <GroupIcon size={17} />
                </span>
                <span>{group.label}</span>
                <ChevronDown size={15} />
              </button>
              <div className={groupOpen ? 'landing-mobile-menu__items is-open' : 'landing-mobile-menu__items'}>
                <Link className="landing-mobile-menu__primary-link" to={group.path} onClick={closeAllMenus}>
                  进入{group.label}
                </Link>
                {group.items.map((item) => {
                  const ItemIcon = item.icon

                  return (
                    <Link className="landing-mobile-menu__item" to={item.path} key={item.path} onClick={closeAllMenus}>
                      <span className="landing-mobile-menu__item-icon">
                        <ItemIcon size={16} />
                      </span>
                      <span className="landing-mobile-menu__item-copy">
                        <strong>{item.label}</strong>
                        <span>{item.description}</span>
                      </span>
                    </Link>
                  )
                })}
              </div>
            </section>
          )
        })}
      </div>
    </header>
  )
}
