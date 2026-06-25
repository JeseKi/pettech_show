import { type CSSProperties, useCallback, useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import type { Course } from './types'

const COURSE_MODAL_EXIT_MS = 280
const COURSE_MODAL_SWITCH_MS = 620

type CourseModalStyle = CSSProperties & Record<'--course-accent', string>
type CourseSwitchDirection = 'none' | 'previous' | 'next'

type CourseModalProps = {
  activeCourse: Course | null
  courseItems?: Course[]
  onClose: () => void
  onCourseChange?: (course: Course) => void
}

export function CourseModal({ activeCourse, courseItems = [], onClose, onCourseChange }: CourseModalProps) {
  const [displayCourse, setDisplayCourse] = useState<Course | null>(activeCourse)
  const [modalState, setModalState] = useState<'open' | 'closing'>('open')
  const [switchDirection, setSwitchDirection] = useState<CourseSwitchDirection>('none')
  const closeTimerRef = useRef(0)
  const switchTimerRef = useRef(0)
  const panelRef = useRef<HTMLElement | null>(null)

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

  useEffect(() => () => {
    if (switchTimerRef.current) window.clearTimeout(switchTimerRef.current)
  }, [])

  useEffect(() => {
    if (!displayCourse) return undefined
    document.documentElement.classList.add('course-modal-open')
    document.body.classList.add('course-modal-open')

    return () => {
      document.documentElement.classList.remove('course-modal-open')
      document.body.classList.remove('course-modal-open')
    }
  }, [displayCourse])

  useEffect(() => {
    if (!displayCourse) return
    panelRef.current?.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [displayCourse])

  const currentCourseIndex = displayCourse
    ? courseItems.findIndex((course) => (
      course === displayCourse || (course.day === displayCourse.day && course.title === displayCourse.title)
    ))
    : -1
  const normalizedCourseIndex = currentCourseIndex >= 0 ? currentCourseIndex : 0
  const canBrowseCourses = Boolean(displayCourse && courseItems.length > 1 && onCourseChange)

  const switchCourse = useCallback((direction: Exclude<CourseSwitchDirection, 'none'>) => {
    if (!displayCourse || !courseItems.length || !onCourseChange) return

    const currentIndex = currentCourseIndex >= 0 ? currentCourseIndex : 0
    const offset = direction === 'next' ? 1 : -1
    const nextIndex = (currentIndex + offset + courseItems.length) % courseItems.length

    setSwitchDirection(direction)
    if (switchTimerRef.current) window.clearTimeout(switchTimerRef.current)
    switchTimerRef.current = window.setTimeout(() => {
      setSwitchDirection('none')
      switchTimerRef.current = 0
    }, COURSE_MODAL_SWITCH_MS)
    onCourseChange(courseItems[nextIndex])
  }, [courseItems, currentCourseIndex, displayCourse, onCourseChange])

  useEffect(() => {
    if (!canBrowseCourses) return undefined

    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target
      if (
        target instanceof HTMLElement &&
        (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
      ) return

      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        switchCourse('previous')
      }
      if (event.key === 'ArrowRight') {
        event.preventDefault()
        switchCourse('next')
      }
    }

    window.addEventListener('keydown', handleKeyDown)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [canBrowseCourses, switchCourse])

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
      aria-label={canBrowseCourses ? '课程详情浏览' : `${displayCourse.title}详情`}
      style={modalStyle}
    >
      <button className="course-modal__backdrop" type="button" onClick={onClose} aria-label="关闭课程详情" />
      <article className="course-modal__panel" data-lenis-prevent ref={panelRef}>
        <button className="course-modal__close" type="button" onClick={onClose} aria-label="关闭">
          <X size={20} />
        </button>
        {canBrowseCourses ? (
          <div className="course-modal__browser-bar" aria-label="课程切换">
            <button
              className="course-modal__step"
              type="button"
              onClick={() => switchCourse('previous')}
              aria-label="上一节课程"
            >
              <ChevronLeft size={21} />
            </button>
            <div className="course-modal__browser-current" aria-live="polite">
              <span>{normalizedCourseIndex + 1} / {courseItems.length}</span>
              <strong>{displayCourse.day}</strong>
            </div>
            <button
              className="course-modal__step"
              type="button"
              onClick={() => switchCourse('next')}
              aria-label="下一节课程"
            >
              <ChevronRight size={21} />
            </button>
          </div>
        ) : null}
        <div
          className="course-modal__content"
          data-switch-direction={switchDirection}
          key={`${displayCourse.day}-${displayCourse.title}`}
        >
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
        </div>
      </article>
    </div>
  )
}
