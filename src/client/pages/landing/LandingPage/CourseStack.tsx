import { type CSSProperties, type KeyboardEvent, type PointerEvent, useCallback, useEffect, useRef } from 'react'
import { BRAND_NAME } from '../../../lib/brand'
import { courses } from './courseData'
import type { Course } from './types'

type CourseStackProps = {
  autoPlayEnabled?: boolean
  onCourseOpen: (course: Course) => void
}

const MOBILE_CASSETTE_SPEED_PX_PER_MS = -0.05
const MOBILE_CASSETTE_DRAG_RESPONSE = 1.18
const MOBILE_CASSETTE_INERTIA_FRICTION = 0.93
const MOBILE_CASSETTE_MIN_VELOCITY = 0.015
const MOBILE_CASSETTE_WHEEL_RESPONSE = 0.82
const MOBILE_CASSETTE_WHEEL_VELOCITY_RESPONSE = 0.018

const renderCourseCardContent = (course: Course) => (
  <>
    <div className="stack-course-card__top">
      <span>{course.day}</span>
      <strong>{course.duration}</strong>
    </div>
    <h2>{course.title}</h2>
    <p>{course.description}</p>
    <div className="stack-course-card__meta">
      <strong>得到什么</strong>
      <ul>{course.gains.slice(0, 2).map((gain) => <li key={gain}>{gain}</li>)}</ul>
    </div>
    <footer>{course.deliverable}</footer>
  </>
)

export function CourseStack({ autoPlayEnabled = true, onCourseOpen }: CourseStackProps) {
  const mobileCassetteFrameRef = useRef(0)
  const mobileCassetteLastTimeRef = useRef(0)
  const mobileCassetteViewportRef = useRef<HTMLDivElement | null>(null)
  const mobileCassetteTrackRef = useRef<HTMLDivElement | null>(null)
  const mobileCassetteGroupRef = useRef<HTMLDivElement | null>(null)
  const mobileClickSuppressedRef = useRef(false)
  const mobileCassetteStateRef = useRef({
    groupWidth: 0,
    hasDragged: false,
    isDragging: false,
    lastX: 0,
    lastTime: 0,
    offset: 0,
    startedCourseIndex: null as number | null,
    velocity: 0,
  })

  const handleCourseKeyDown = (event: KeyboardEvent<HTMLElement>, course: Course) => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    onCourseOpen(course)
  }

  const normalizeMobileCassetteOffset = useCallback((offset: number) => {
    const groupWidth = mobileCassetteStateRef.current.groupWidth
    if (groupWidth <= 0) return offset
    return ((offset % groupWidth) + groupWidth) % groupWidth - groupWidth
  }, [])

  const applyMobileCassetteOffset = useCallback((offset: number) => {
    const normalizedOffset = normalizeMobileCassetteOffset(offset)
    mobileCassetteStateRef.current.offset = normalizedOffset
    if (mobileCassetteTrackRef.current) {
      mobileCassetteTrackRef.current.style.transform = `translate3d(${normalizedOffset}px, 0, 0)`
    }
  }, [normalizeMobileCassetteOffset])

  const handleMobileCassettePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'mouse' && event.button !== 0) return
    const cassetteState = mobileCassetteStateRef.current
    const courseElement = event.target instanceof Element
      ? event.target.closest<HTMLElement>('.mobile-course-card')
      : null
    const startedCourseIndex = courseElement?.dataset.courseIndex
    cassetteState.isDragging = true
    cassetteState.hasDragged = false
    cassetteState.lastX = event.clientX
    cassetteState.lastTime = window.performance.now()
    cassetteState.startedCourseIndex = startedCourseIndex === undefined ? null : Number(startedCourseIndex)
    cassetteState.velocity = 0
    event.currentTarget.classList.add('is-dragging')
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const handleMobileCassettePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const cassetteState = mobileCassetteStateRef.current
    if (!cassetteState.isDragging) return
    const now = window.performance.now()
    const deltaX = event.clientX - cassetteState.lastX
    const deltaTime = Math.max(now - cassetteState.lastTime, 1)
    cassetteState.lastX = event.clientX
    cassetteState.lastTime = now
    cassetteState.velocity = deltaX / deltaTime
    cassetteState.hasDragged = cassetteState.hasDragged || Math.abs(deltaX) > 4
    applyMobileCassetteOffset(cassetteState.offset + deltaX * MOBILE_CASSETTE_DRAG_RESPONSE)
  }

  const releaseMobileCassettePointer = (event: PointerEvent<HTMLDivElement>, allowCourseOpen = true) => {
    const cassetteState = mobileCassetteStateRef.current
    if (!cassetteState.isDragging) return
    const shouldOpenCourse = allowCourseOpen && !cassetteState.hasDragged && cassetteState.startedCourseIndex !== null
    const courseToOpen = shouldOpenCourse ? courses[cassetteState.startedCourseIndex ?? -1] : undefined
    cassetteState.isDragging = false
    mobileClickSuppressedRef.current = cassetteState.hasDragged
    cassetteState.startedCourseIndex = null
    event.currentTarget.classList.remove('is-dragging')
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    if (courseToOpen) {
      window.setTimeout(() => onCourseOpen(courseToOpen), 0)
      return
    }
    if (cassetteState.hasDragged) {
      window.setTimeout(() => {
        mobileClickSuppressedRef.current = false
      }, 0)
    }
  }

  const handleMobileCourseOpen = (course: Course) => {
    if (mobileClickSuppressedRef.current) {
      mobileClickSuppressedRef.current = false
      return
    }
    onCourseOpen(course)
  }

  const handleMobileCassetteWheel = useCallback((event: WheelEvent) => {
    if (Math.abs(event.deltaX) <= Math.abs(event.deltaY)) return
    event.preventDefault()
    const cassetteState = mobileCassetteStateRef.current
    cassetteState.velocity = -event.deltaX * MOBILE_CASSETTE_WHEEL_VELOCITY_RESPONSE
    applyMobileCassetteOffset(
      cassetteState.offset - event.deltaX * MOBILE_CASSETTE_WHEEL_RESPONSE,
    )
  }, [applyMobileCassetteOffset])

  useEffect(() => {
    const viewportElement = mobileCassetteViewportRef.current
    if (!viewportElement) return undefined

    viewportElement.addEventListener('wheel', handleMobileCassetteWheel, { passive: false })
    return () => viewportElement.removeEventListener('wheel', handleMobileCassetteWheel)
  }, [handleMobileCassetteWheel])

  useEffect(() => {
    const updateMobileCassetteWidth = () => {
      const groupWidth = mobileCassetteGroupRef.current?.scrollWidth ?? 0
      mobileCassetteStateRef.current.groupWidth = groupWidth
      applyMobileCassetteOffset(mobileCassetteStateRef.current.offset)
    }

    updateMobileCassetteWidth()
    window.addEventListener('resize', updateMobileCassetteWidth)
    return () => window.removeEventListener('resize', updateMobileCassetteWidth)
  }, [applyMobileCassetteOffset])

  useEffect(() => {
    if (!autoPlayEnabled) return undefined
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined

    const animateMobileCassette = (timestamp: number) => {
      const previousTimestamp = mobileCassetteLastTimeRef.current || timestamp
      const deltaTime = Math.min(timestamp - previousTimestamp, 48)
      mobileCassetteLastTimeRef.current = timestamp

      const cassetteState = mobileCassetteStateRef.current
      if (!cassetteState.isDragging) {
        if (Math.abs(cassetteState.velocity) > MOBILE_CASSETTE_MIN_VELOCITY) {
          applyMobileCassetteOffset(cassetteState.offset + deltaTime * cassetteState.velocity)
          cassetteState.velocity *= MOBILE_CASSETTE_INERTIA_FRICTION ** (deltaTime / 16)
        } else {
          cassetteState.velocity = 0
          applyMobileCassetteOffset(
            cassetteState.offset + deltaTime * MOBILE_CASSETTE_SPEED_PX_PER_MS,
          )
        }
      }

      mobileCassetteFrameRef.current = window.requestAnimationFrame(animateMobileCassette)
    }

    mobileCassetteFrameRef.current = window.requestAnimationFrame(animateMobileCassette)
    return () => {
      if (mobileCassetteFrameRef.current) window.cancelAnimationFrame(mobileCassetteFrameRef.current)
      mobileCassetteFrameRef.current = 0
      mobileCassetteLastTimeRef.current = 0
    }
  }, [applyMobileCassetteOffset, autoPlayEnabled])

  const mobileCourseRows = [courses, courses]

  return (
    <section className="course-stack-section" id="courses">
      <div className="course-stack-stage">
        <div className="course-stack-mobile" aria-label="课程卡片">
          <div className="course-stack-mobile__summary" aria-label="课程路径概览">
            <span>{BRAND_NAME}</span>
            <h1>
              <span>宠物行业 AI 内容增长</span>
              <span>工作台</span>
            </h1>
            <p>把竞品素材、用户问题和业务目标整理成内容资产，再生成选题策略、稿件和多平台内容包。</p>
            <div className="course-stack-mobile__stats">
              <strong>内容资产库</strong>
              <strong>选题策略</strong>
              <strong>稿件生产</strong>
            </div>
            <div className="course-stack-mobile__flow" aria-label="课程流程">
              <span>对标入库</span>
              <span>知识沉淀</span>
              <span>选题规划</span>
              <span>内容分发</span>
            </div>
          </div>
          <div
            className="course-stack-mobile__viewport"
            ref={mobileCassetteViewportRef}
            onPointerCancel={(event) => releaseMobileCassettePointer(event, false)}
            onPointerDown={handleMobileCassettePointerDown}
            onPointerMove={handleMobileCassettePointerMove}
            onPointerUp={releaseMobileCassettePointer}
          >
            <div className="course-stack-mobile__track" ref={mobileCassetteTrackRef}>
              {mobileCourseRows.map((row, rowIndex) => (
                <div
                  className="course-stack-mobile__group"
                  key={rowIndex}
                  aria-hidden={rowIndex > 0}
                  ref={rowIndex === 0 ? mobileCassetteGroupRef : undefined}
                >
                  {row.map((course) => (
                    <article
                      className="mobile-course-card"
                      key={`${rowIndex}-${course.day}`}
                      data-course-index={courses.indexOf(course)}
                      onClick={() => handleMobileCourseOpen(course)}
                      onKeyDown={(event) => handleCourseKeyDown(event, course)}
                      role="button"
                      style={{ '--course-accent': course.accent } as CSSProperties}
                      tabIndex={rowIndex === 0 ? 0 : -1}
                    >
                      {renderCourseCardContent(course)}
                    </article>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
