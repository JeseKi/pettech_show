import { type CSSProperties, useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import type { Course } from './types'

const COURSE_MODAL_EXIT_MS = 280
const COURSE_MODAL_SCROLL_KEYS = new Set([' ', 'ArrowDown', 'ArrowUp', 'End', 'Home', 'PageDown', 'PageUp'])

type CourseModalStyle = CSSProperties & Record<'--course-accent', string>

type CourseModalProps = {
  activeCourse: Course | null
  onClose: () => void
}

export function CourseModal({ activeCourse, onClose }: CourseModalProps) {
  const [displayCourse, setDisplayCourse] = useState<Course | null>(activeCourse)
  const [modalState, setModalState] = useState<'open' | 'closing'>('open')
  const closeTimerRef = useRef(0)
  const panelRef = useRef<HTMLElement | null>(null)
  const touchYRef = useRef(0)

  useEffect(() => {
    if (closeTimerRef.current) {
      window.clearTimeout(closeTimerRef.current)
      closeTimerRef.current = 0
    }

    if (activeCourse) {
      setDisplayCourse(activeCourse)
      setModalState('open')
      return undefined
    }

    if (!displayCourse) return undefined

    setModalState('closing')
    closeTimerRef.current = window.setTimeout(() => {
      setDisplayCourse(null)
      closeTimerRef.current = 0
    }, COURSE_MODAL_EXIT_MS)

    return () => {
      if (closeTimerRef.current) window.clearTimeout(closeTimerRef.current)
    }
  }, [activeCourse, displayCourse])

  useEffect(() => {
    if (!displayCourse) return undefined

    const scrollPanelBy = (deltaY: number) => {
      const panel = panelRef.current
      if (!panel || deltaY === 0) return
      panel.scrollTop += deltaY
    }
    const handleWheel = (event: WheelEvent) => {
      event.preventDefault()
      scrollPanelBy(event.deltaY)
    }
    const handleTouchStart = (event: TouchEvent) => {
      touchYRef.current = event.touches[0]?.clientY ?? 0
    }
    const handleTouchMove = (event: TouchEvent) => {
      const currentY = event.touches[0]?.clientY ?? touchYRef.current
      const deltaY = touchYRef.current - currentY
      touchYRef.current = currentY
      event.preventDefault()
      scrollPanelBy(deltaY)
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!COURSE_MODAL_SCROLL_KEYS.has(event.key)) return
      const panel = panelRef.current
      if (!panel) return

      event.preventDefault()
      const pageStep = Math.max(panel.clientHeight - 80, 120)
      const keyScrollMap: Record<string, number> = {
        ' ': event.shiftKey ? -pageStep : pageStep,
        ArrowDown: 64,
        ArrowUp: -64,
        PageDown: pageStep,
        PageUp: -pageStep,
        End: panel.scrollHeight,
        Home: -panel.scrollHeight,
      }
      scrollPanelBy(keyScrollMap[event.key] ?? 0)
    }

    window.addEventListener('wheel', handleWheel, { capture: true, passive: false })
    window.addEventListener('touchstart', handleTouchStart, { capture: true, passive: true })
    window.addEventListener('touchmove', handleTouchMove, { capture: true, passive: false })
    window.addEventListener('keydown', handleKeyDown, { capture: true })

    return () => {
      window.removeEventListener('wheel', handleWheel, true)
      window.removeEventListener('touchstart', handleTouchStart, true)
      window.removeEventListener('touchmove', handleTouchMove, true)
      window.removeEventListener('keydown', handleKeyDown, true)
    }
  }, [displayCourse])

  if (!displayCourse) return null

  const modalStyle: CourseModalStyle = {
    '--course-accent': displayCourse.accent,
  }
  const resumeSections = [
    { label: '课程介绍', marker: 'Overview', items: [displayCourse.intro] },
    { label: '技术原理', marker: 'Principle', items: displayCourse.principles },
    { label: '技术实现路线', marker: 'Route', items: displayCourse.implementationRoute },
    { label: '优势', marker: 'Value', items: displayCourse.advantages },
  ]
  const evidenceSections = [
    { label: '你会得到', items: displayCourse.gains },
    { label: '今日目标', items: displayCourse.goals },
    { label: '课堂实操', items: displayCourse.practice },
    { label: '验收标准', items: displayCourse.acceptance },
  ]

  return (
    <div
      className="course-modal"
      data-state={modalState}
      role="dialog"
      aria-modal="true"
      aria-label={`${displayCourse.title}详情`}
      style={modalStyle}
    >
      <button className="course-modal__backdrop" type="button" onClick={onClose} aria-label="关闭课程详情" />
      <article className="course-modal__panel" data-lenis-prevent ref={panelRef}>
        <button className="course-modal__close" type="button" onClick={onClose} aria-label="关闭">
          <X size={20} />
        </button>
        <header className="course-modal__hero">
          <div className="course-modal__identity">
            <span>{displayCourse.day} · {displayCourse.capability}</span>
            <h2>{displayCourse.title}</h2>
            <p>{displayCourse.description}</p>
          </div>
          <div className="course-modal__snapshot" aria-label="课程摘要">
            <div>
              <span>交付物</span>
              <strong>{displayCourse.deliverable}</strong>
            </div>
            <div>
              <span>时长</span>
              <strong>{displayCourse.duration}</strong>
            </div>
            <div>
              <span>形式</span>
              <strong>{displayCourse.format}</strong>
            </div>
          </div>
        </header>
        <div className="course-modal__resume">
          <aside className="course-modal__system">
            <span>对应系统能力</span>
            <h3>{displayCourse.capability}</h3>
            <p>课程先讲运营判断，再进入工具化执行。系统能力在工作台中承接课程产物，用于沉淀知识库、生成内容、组织分发和复盘数据。</p>
          </aside>
          <div className="course-modal__story">
            {resumeSections.map((section) => (
              <section className="course-modal__resume-item" key={section.label}>
                <div className="course-modal__resume-label">
                  <span>{section.marker}</span>
                  <strong>{section.label}</strong>
                </div>
                <div className="course-modal__resume-copy">
                  {section.items.map((item) => <p key={item}>{item}</p>)}
                </div>
              </section>
            ))}
          </div>
        </div>
        <div className="course-modal__evidence">
          {evidenceSections.map((section) => (
            <section key={section.label}>
              <h3>{section.label}</h3>
              {section.items.map((item) => <p key={item}>{item}</p>)}
            </section>
          ))}
        </div>
      </article>
    </div>
  )
}
