import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../../hooks/useAuth'
import { CourseModal } from './CourseModal'
import { CourseStack } from './CourseStack'
import { LandingNav } from './LandingNav'
import { courses } from './courseData'
import {
  ContactSection,
  CourseIntroSection,
  DeliverablesSection,
  LandingFooter,
  ProductionSection,
} from './Sections'
import { INTRO_UNLOCK_DELAY_MS, PROGRESSIVE_BLOCK_IDS, type Course, type ProgressiveBlockId } from './types'
import { isProgressiveBlockId } from './utils'
import './styles.css'

const SCROLL_HINT_IDLE_MS = 10000
const SCROLL_HINT_SCROLL_STEP_MIN_PX = 360
const SCROLL_HINT_TARGET_OFFSET_PX = 88
const SCROLL_HINT_REARM_MS = 10000
type CourseModalMode = 'single' | 'browse'

export default function LandingPage() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const [activeCourse, setActiveCourse] = useState<Course | null>(null)
  const [courseModalMode, setCourseModalMode] = useState<CourseModalMode>('single')
  const [revealedBlockIds, setRevealedBlockIds] = useState<Set<ProgressiveBlockId>>(() => new Set())
  const [showScrollHint, setShowScrollHint] = useState(false)
  const progressiveBlockRefs = useRef(new Map<ProgressiveBlockId, HTMLElement>())
  const lastScrollYRef = useRef(0)
  const lastScrollActivityAtRef = useRef(Date.now())

  const goToWorkspace = useCallback(() => {
    navigate(isAuthenticated ? '/dashboard' : '/login')
  }, [isAuthenticated, navigate])

  const openSingleCourse = useCallback((course: Course) => {
    setCourseModalMode('single')
    setActiveCourse(course)
  }, [])

  const openCourseBrowser = useCallback(() => {
    setCourseModalMode('browse')
    setActiveCourse(courses[0] ?? null)
  }, [])

  const closeCourseModal = useCallback(() => {
    setActiveCourse(null)
  }, [])

  const scrollToNextViewport = useCallback(() => {
    const currentScrollY = getLandingScrollTop()
    const minimumTargetY = currentScrollY + Math.max(window.innerHeight * 0.72, SCROLL_HINT_SCROLL_STEP_MIN_PX)
    const nextSection = getLandingScrollSections().find((node) => (
      getElementPageTop(node) > currentScrollY + SCROLL_HINT_TARGET_OFFSET_PX
    ))
    const nextTargetY = nextSection ? getElementPageTop(nextSection) - SCROLL_HINT_TARGET_OFFSET_PX : minimumTargetY
    const targetY = Math.max(currentScrollY + SCROLL_HINT_SCROLL_STEP_MIN_PX, Math.min(nextTargetY, minimumTargetY))

    lastScrollActivityAtRef.current = Date.now() + SCROLL_HINT_REARM_MS - SCROLL_HINT_IDLE_MS
    setShowScrollHint(false)
    scrollLandingTo(targetY)
  }, [])

  const revealBlock = useCallback((id: ProgressiveBlockId) => {
    setRevealedBlockIds((current) => {
      if (current.has(id)) return current
      const next = new Set(current)
      next.add(id)
      return next
    })
  }, [])

  const registerProgressiveBlock = useCallback((id: ProgressiveBlockId) => (
    (node: HTMLElement | null) => {
      if (node) {
        progressiveBlockRefs.current.set(id, node)
      } else {
        progressiveBlockRefs.current.delete(id)
      }
    }
  ), [])

  const progressiveClassName = useCallback((id: ProgressiveBlockId, className: string) => (
    `${className} landing-reveal${revealedBlockIds.has(id) ? ' is-revealed' : ''}`
  ), [revealedBlockIds])

  useLayoutEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const unlockDelay = prefersReducedMotion ? 0 : INTRO_UNLOCK_DELAY_MS
    const landingScrollbarClassName = 'pettech-landing-scrollbar'
    const scrollKeys = new Set([' ', 'ArrowDown', 'ArrowUp', 'End', 'Home', 'PageDown', 'PageUp'])
    let scrollLocked = true
    const preventScroll = (event: Event) => {
      if (!scrollLocked) return
      event.preventDefault()
    }
    const preventScrollKeys = (event: KeyboardEvent) => {
      if (!scrollLocked || !scrollKeys.has(event.key)) return
      event.preventDefault()
    }
    const keepIntroAtTop = () => {
      if (!scrollLocked || window.scrollY === 0) return
      window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
    }

    document.documentElement.classList.add(landingScrollbarClassName)
    document.body.classList.add(landingScrollbarClassName)
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
    window.addEventListener('wheel', preventScroll, { passive: false })
    window.addEventListener('touchmove', preventScroll, { passive: false })
    window.addEventListener('keydown', preventScrollKeys)
    window.addEventListener('scroll', keepIntroAtTop, { passive: true })

    const unlockTimer = window.setTimeout(() => {
      scrollLocked = false
      window.removeEventListener('wheel', preventScroll)
      window.removeEventListener('touchmove', preventScroll)
      window.removeEventListener('keydown', preventScrollKeys)
      window.removeEventListener('scroll', keepIntroAtTop)
    }, unlockDelay)

    return () => {
      scrollLocked = false
      window.clearTimeout(unlockTimer)
      window.removeEventListener('wheel', preventScroll)
      window.removeEventListener('touchmove', preventScroll)
      window.removeEventListener('keydown', preventScrollKeys)
      window.removeEventListener('scroll', keepIntroAtTop)
      document.documentElement.classList.remove(landingScrollbarClassName)
      document.body.classList.remove(landingScrollbarClassName)
    }
  }, [])

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (prefersReducedMotion || !('IntersectionObserver' in window)) {
      setRevealedBlockIds(new Set(PROGRESSIVE_BLOCK_IDS))
      return undefined
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return

          const id = entry.target.getAttribute('data-reveal-id')
          if (!isProgressiveBlockId(id)) return

          revealBlock(id)
          observer.unobserve(entry.target)
        })
      },
      {
        rootMargin: '0px 0px -12% 0px',
        threshold: 0.08,
      },
    )

    progressiveBlockRefs.current.forEach((node) => observer.observe(node))

    const frameId = window.requestAnimationFrame(() => {
      progressiveBlockRefs.current.forEach((node, id) => {
        const rect = node.getBoundingClientRect()
        if (rect.top < window.innerHeight * 0.88 && rect.bottom > 0) {
          revealBlock(id)
          observer.unobserve(node)
        }
      })
    })

    return () => {
      window.cancelAnimationFrame(frameId)
      observer.disconnect()
    }
  }, [revealBlock])

  useEffect(() => {
    const isNearPageBottom = () => (
      window.innerHeight + getLandingScrollTop() >= getLandingPageContentBottom() - 24
    )
    const isPageScrollable = () => getLandingPageContentBottom() > window.innerHeight + 24
    const updateScrollHint = () => {
      const hasBeenIdle = Date.now() - lastScrollActivityAtRef.current >= SCROLL_HINT_IDLE_MS
      setShowScrollHint(isPageScrollable() && hasBeenIdle && !isNearPageBottom())
    }
    const recordScrollActivity = () => {
      lastScrollActivityAtRef.current = Date.now()
      setShowScrollHint(false)
    }
    const recordScroll = () => {
      const nextScrollY = getLandingScrollTop()
      if (Math.abs(nextScrollY - lastScrollYRef.current) > 2) {
        recordScrollActivity()
      }
      lastScrollYRef.current = nextScrollY
    }
    const recordScrollKey = (event: KeyboardEvent) => {
      if (![' ', 'ArrowDown', 'ArrowUp', 'End', 'Home', 'PageDown', 'PageUp'].includes(event.key)) return
      recordScrollActivity()
    }

    lastScrollYRef.current = getLandingScrollTop()
    lastScrollActivityAtRef.current = Date.now()
    const intervalId = window.setInterval(updateScrollHint, 250)
    window.addEventListener('scroll', recordScroll, { passive: true })
    window.addEventListener('wheel', recordScrollActivity, { passive: true })
    window.addEventListener('touchmove', recordScrollActivity, { passive: true })
    window.addEventListener('keydown', recordScrollKey)
    window.addEventListener('resize', updateScrollHint)

    return () => {
      window.clearInterval(intervalId)
      window.removeEventListener('scroll', recordScroll)
      window.removeEventListener('wheel', recordScrollActivity)
      window.removeEventListener('touchmove', recordScrollActivity)
      window.removeEventListener('keydown', recordScrollKey)
      window.removeEventListener('resize', updateScrollHint)
    }
  }, [])

  return (
    <main className="landing-page">
      <LandingNav
        isAuthenticated={isAuthenticated}
        onAuthAction={goToWorkspace}
        onCoursesOpen={openCourseBrowser}
      />
      <CourseStack autoPlayEnabled={activeCourse === null} onCourseOpen={openSingleCourse} />
      <CourseIntroSection
        progressiveClassName={progressiveClassName}
        registerProgressiveBlock={registerProgressiveBlock}
        goToWorkspace={goToWorkspace}
        isAuthenticated={isAuthenticated}
      />
      <ProductionSection
        progressiveClassName={progressiveClassName}
        registerProgressiveBlock={registerProgressiveBlock}
        goToWorkspace={goToWorkspace}
        isAuthenticated={isAuthenticated}
      />
      <DeliverablesSection
        progressiveClassName={progressiveClassName}
        registerProgressiveBlock={registerProgressiveBlock}
        goToWorkspace={goToWorkspace}
        isAuthenticated={isAuthenticated}
      />
      <ContactSection
        progressiveClassName={progressiveClassName}
        registerProgressiveBlock={registerProgressiveBlock}
        goToWorkspace={goToWorkspace}
        isAuthenticated={isAuthenticated}
      />
      <LandingFooter
        progressiveClassName={progressiveClassName}
        registerProgressiveBlock={registerProgressiveBlock}
        goToWorkspace={goToWorkspace}
        isAuthenticated={isAuthenticated}
      />
      <button
        className="landing-scroll-hint"
        data-visible={showScrollHint && activeCourse === null}
        type="button"
        onClick={scrollToNextViewport}
        aria-label="向下滚动"
      >
        <ChevronDown size={24} />
      </button>
      <CourseModal
        activeCourse={activeCourse}
        courseItems={courseModalMode === 'browse' ? courses : undefined}
        onClose={closeCourseModal}
        onCourseChange={setActiveCourse}
      />
    </main>
  )
}

function getLandingPage() {
  return document.querySelector<HTMLElement>('.landing-page')
}

function getLandingScrollTop() {
  return Math.max(
    window.scrollY,
    document.documentElement.scrollTop,
    document.body.scrollTop,
  )
}

function getElementPageTop(node: HTMLElement) {
  return node.getBoundingClientRect().top + getLandingScrollTop()
}

function getLandingPageContentBottom() {
  const landingPage = getLandingPage()
  const landingPageBottom = landingPage ? getElementPageTop(landingPage) + landingPage.offsetHeight : 0

  return Math.max(
    document.documentElement.scrollHeight,
    document.body.scrollHeight,
    landingPage?.scrollHeight ?? 0,
    landingPageBottom,
  )
}

function getLandingScrollSections() {
  const landingPage = getLandingPage()
  if (!landingPage) return []

  return Array.from(landingPage.querySelectorAll<HTMLElement>('section[id], footer'))
}

function scrollLandingTo(top: number) {
  const maxTop = Math.max(0, getLandingPageContentBottom() - window.innerHeight)
  const nextTop = Math.min(Math.max(0, top), maxTop)
  const options: ScrollToOptions = { top: nextTop, left: 0, behavior: 'smooth' }

  window.scrollTo(options)
  document.scrollingElement?.scrollTo(options)
  document.documentElement.scrollTo(options)
  document.body.scrollTo(options)
}
