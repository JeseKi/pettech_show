import { useCallback, useEffect, useRef, useState } from 'react'
import { BookOpenText, ChevronDown, LayoutDashboard, LogIn, Menu, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import BrandLogo from '../../../components/brand/BrandLogo'
import { BRAND_NAME } from '../../../lib/brand'
import { useRuntimeConfig } from '../../../hooks/useRuntimeConfig'
import { courseShowcaseTabs, landingNavGroups } from './pageData'
import type { CourseShowcaseTabKey } from './types'

type LandingNavProps = {
  isAuthenticated: boolean
  onAuthAction: () => void
  onCoursesOpen: () => void
  onCourseShowcaseOpen: (tabKey: CourseShowcaseTabKey) => void
}

const NAV_MENU_OPEN_DELAY_MS = 120
const NAV_MENU_CLOSE_DELAY_MS = 500

export function LandingNav({
  isAuthenticated,
  onAuthAction,
  onCoursesOpen,
  onCourseShowcaseOpen,
}: LandingNavProps) {
  const { infoDistribution } = useRuntimeConfig()
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

  const openCourses = useCallback(() => {
    closeAllMenus()
    onCoursesOpen()
  }, [closeAllMenus, onCoursesOpen])

  const openCourseShowcase = useCallback((tabKey: CourseShowcaseTabKey) => {
    closeAllMenus()
    onCourseShowcaseOpen(tabKey)
  }, [closeAllMenus, onCourseShowcaseOpen])

  const resolveItemPath = useCallback((item: { path: string; externalConfigKey?: string }) => {
    if (item.externalConfigKey === 'infoDistributionBaseUrl') {
      return infoDistribution.baseUrl
    }
    return item.path
  }, [infoDistribution.baseUrl])

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
        <div
          className={activeNavLabel === '课程' ? 'landing-nav__item is-open' : 'landing-nav__item'}
          onPointerEnter={() => openNavMenu('课程')}
          onPointerLeave={scheduleNavMenuClose}
          onFocusCapture={() => openNavMenu('课程', true)}
          onBlurCapture={(event) => {
            if (event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)) return
            scheduleNavMenuClose()
          }}
        >
          <button
            className="landing-nav__trigger landing-nav__course-trigger"
            type="button"
            aria-haspopup="true"
            aria-expanded={activeNavLabel === '课程'}
            onClick={() => openNavMenu('课程', true)}
          >
            <BookOpenText size={16} />
            <span>课程</span>
            <ChevronDown className="landing-nav__chevron" size={14} />
          </button>
          <div className={activeNavLabel === '课程' ? 'landing-nav__menu is-open' : 'landing-nav__menu'} aria-label="课程子菜单">
            {courseShowcaseTabs.map((tab) => {
              const ItemIcon = tab.icon

              return (
                <button
                  className="landing-nav__menu-link"
                  type="button"
                  key={tab.key}
                  onClick={() => openCourseShowcase(tab.key)}
                >
                  <span className="landing-nav__menu-icon">
                    <ItemIcon size={17} />
                  </span>
                  <span className="landing-nav__menu-copy">
                    <strong>{tab.label}</strong>
                    <span>{tab.summary}</span>
                  </span>
                </button>
              )
            })}
          </div>
        </div>
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
                  const itemPath = resolveItemPath(item)
                  const isExternal = Boolean(item.externalConfigKey)
                  const content = (
                    <>
                      <span className="landing-nav__menu-icon">
                        <ItemIcon size={17} />
                      </span>
                      <span className="landing-nav__menu-copy">
                        <strong>{item.label}</strong>
                        <span>{item.description}</span>
                      </span>
                    </>
                  )

                  if (!itemPath) {
                    return (
                      <span className="landing-nav__menu-link" key={item.label} title="请先配置 INFO_DISTRIBUTION_BASE_URL">
                        {content}
                      </span>
                    )
                  }

                  return isExternal ? (
                    <a className="landing-nav__menu-link" href={itemPath} key={item.label} target="_blank" rel="noreferrer" onClick={closeAllMenus}>
                      {content}
                    </a>
                  ) : (
                    <Link className="landing-nav__menu-link" to={itemPath} key={itemPath} onClick={closeAllMenus}>
                      {content}
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
        <button className="landing-mobile-menu__course-link" type="button" onClick={openCourses}>
          <span className="landing-mobile-menu__group-icon">
            <BookOpenText size={17} />
          </span>
          <span>
            <strong>课程</strong>
            <span>Day 0 到毕业项目的完整课程详情。</span>
          </span>
        </button>
        <section className="landing-mobile-menu__group">
          <button
            className={activeMobileGroupLabel === '课程' ? 'landing-mobile-menu__group-trigger is-open' : 'landing-mobile-menu__group-trigger'}
            type="button"
            aria-expanded={activeMobileGroupLabel === '课程'}
            onClick={() => setActiveMobileGroupLabel((current) => (current === '课程' ? '' : '课程'))}
          >
            <span className="landing-mobile-menu__group-icon">
              <BookOpenText size={17} />
            </span>
            <span>课程子菜单</span>
            <ChevronDown size={15} />
          </button>
          <div className={activeMobileGroupLabel === '课程' ? 'landing-mobile-menu__items is-open' : 'landing-mobile-menu__items'}>
            {courseShowcaseTabs.map((tab) => {
              const ItemIcon = tab.icon

              return (
                <button
                  className="landing-mobile-menu__item"
                  type="button"
                  key={tab.key}
                  onClick={() => openCourseShowcase(tab.key)}
                >
                  <span className="landing-mobile-menu__item-icon">
                    <ItemIcon size={16} />
                  </span>
                  <span className="landing-mobile-menu__item-copy">
                    <strong>{tab.label}</strong>
                    <span>{tab.summary}</span>
                  </span>
                </button>
              )
            })}
          </div>
        </section>
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
                  const itemPath = resolveItemPath(item)
                  const isExternal = Boolean(item.externalConfigKey)
                  const content = (
                    <>
                      <span className="landing-mobile-menu__item-icon">
                        <ItemIcon size={16} />
                      </span>
                      <span className="landing-mobile-menu__item-copy">
                        <strong>{item.label}</strong>
                        <span>{item.description}</span>
                      </span>
                    </>
                  )

                  if (!itemPath) {
                    return (
                      <span className="landing-mobile-menu__item" key={item.label} title="请先配置 INFO_DISTRIBUTION_BASE_URL">
                        {content}
                      </span>
                    )
                  }

                  return isExternal ? (
                    <a className="landing-mobile-menu__item" href={itemPath} key={item.label} target="_blank" rel="noreferrer" onClick={closeAllMenus}>
                      {content}
                    </a>
                  ) : (
                    <Link className="landing-mobile-menu__item" to={itemPath} key={itemPath} onClick={closeAllMenus}>
                      {content}
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
