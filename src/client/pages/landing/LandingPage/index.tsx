import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../../hooks/useAuth'
import { CourseModal } from './CourseModal'
import { CourseStack } from './CourseStack'
import { LandingNav } from './LandingNav'
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

export default function LandingPage() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const [activeCourse, setActiveCourse] = useState<Course | null>(null)
  const [revealedBlockIds, setRevealedBlockIds] = useState<Set<ProgressiveBlockId>>(() => new Set())
  const progressiveBlockRefs = useRef(new Map<ProgressiveBlockId, HTMLElement>())

  const goToWorkspace = useCallback(() => {
    navigate(isAuthenticated ? '/dashboard' : '/login')
  }, [isAuthenticated, navigate])

  const goToConsult = useCallback(() => {
    document.getElementById('contact')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
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

  return (
    <main className="landing-page">
      <LandingNav
        isAuthenticated={isAuthenticated}
        onAuthAction={goToWorkspace}
        onConsult={goToConsult}
      />
      <CourseStack autoPlayEnabled={activeCourse === null} onCourseOpen={setActiveCourse} />
      <CourseIntroSection
        progressiveClassName={progressiveClassName}
        registerProgressiveBlock={registerProgressiveBlock}
        goToWorkspace={goToWorkspace}
        goToConsult={goToConsult}
        isAuthenticated={isAuthenticated}
      />
      <ProductionSection
        progressiveClassName={progressiveClassName}
        registerProgressiveBlock={registerProgressiveBlock}
        goToWorkspace={goToWorkspace}
        goToConsult={goToConsult}
        isAuthenticated={isAuthenticated}
      />
      <DeliverablesSection
        progressiveClassName={progressiveClassName}
        registerProgressiveBlock={registerProgressiveBlock}
        goToWorkspace={goToWorkspace}
        goToConsult={goToConsult}
        isAuthenticated={isAuthenticated}
      />
      <ContactSection
        progressiveClassName={progressiveClassName}
        registerProgressiveBlock={registerProgressiveBlock}
        goToWorkspace={goToWorkspace}
        goToConsult={goToConsult}
        isAuthenticated={isAuthenticated}
      />
      <LandingFooter
        progressiveClassName={progressiveClassName}
        registerProgressiveBlock={registerProgressiveBlock}
        goToWorkspace={goToWorkspace}
        goToConsult={goToConsult}
        isAuthenticated={isAuthenticated}
      />
      <CourseModal activeCourse={activeCourse} onClose={() => setActiveCourse(null)} />
    </main>
  )
}
