import { type KeyboardEvent, type PointerEvent, type WheelEvent, useCallback, useEffect, useRef, useState } from 'react'
import {
  COURSE_ORBIT_ANGLE_STEP,
  COURSE_ORBIT_DRAG_SENSITIVITY,
  COURSE_ORBIT_INERTIA_FRICTION,
  COURSE_ORBIT_MIN_VELOCITY,
  COURSE_ORBIT_WHEEL_SENSITIVITY,
  courseOrbitItems,
  getActiveCourseOrbitItem,
  getCourseCardStyle,
  getCourseOrbitAngle,
  getFocusCardStyle,
  getOrbitPose,
} from './courseOrbitModel'
import type { Course, CourseOrbitPointerState, ViewportSize } from './types'
import { clamp, normalizeAngle, smoothstep } from './utils'

type CourseStackProps = {
  onCourseOpen: (course: Course) => void
}

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

const isFocusCardTarget = (target: EventTarget | null) => (
  target instanceof Element && target.closest('.stack-course-card--focus') !== null
)

export function CourseStack({ onCourseOpen }: CourseStackProps) {
  const [orbitPhase, setOrbitPhase] = useState(0)
  const [viewportSize, setViewportSize] = useState<ViewportSize>({ width: 1280, height: 720 })
  const orbitInertiaFrameRef = useRef(0)
  const orbitPointerStateRef = useRef<CourseOrbitPointerState>({
    isDragging: false,
    hasDragged: false,
    startedOnFocusCard: false,
    lastX: 0,
    lastTime: 0,
    velocity: 0,
  })
  const activeOrbitItem = getActiveCourseOrbitItem(orbitPhase)
  const activePose = getOrbitPose(activeOrbitItem, orbitPhase, viewportSize)
  const edgeProgress = clamp(Math.abs(activePose.signed) / COURSE_ORBIT_ANGLE_STEP, 0, 1)
  const focusStrength = 1 - smoothstep(0.08, 1, edgeProgress)
  const orderedCourseOrbitItems = [...courseOrbitItems].sort((left, right) => (
    Math.cos(getCourseOrbitAngle(left, orbitPhase) * Math.PI / 180) -
    Math.cos(getCourseOrbitAngle(right, orbitPhase) * Math.PI / 180)
  ))

  const moveCourseOrbit = useCallback((deltaAngle: number) => {
    setOrbitPhase((currentPhase) => normalizeAngle(currentPhase + deltaAngle))
  }, [])

  const stopCourseOrbitInertia = useCallback(() => {
    if (!orbitInertiaFrameRef.current) return
    window.cancelAnimationFrame(orbitInertiaFrameRef.current)
    orbitInertiaFrameRef.current = 0
  }, [])

  const startCourseOrbitInertia = useCallback(() => {
    stopCourseOrbitInertia()
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    if (Math.abs(orbitPointerStateRef.current.velocity) <= COURSE_ORBIT_MIN_VELOCITY) return

    const animateInertia = () => {
      const pointerState = orbitPointerStateRef.current
      pointerState.velocity *= COURSE_ORBIT_INERTIA_FRICTION
      moveCourseOrbit(pointerState.velocity * 16 * COURSE_ORBIT_DRAG_SENSITIVITY)
      if (Math.abs(pointerState.velocity) > COURSE_ORBIT_MIN_VELOCITY) {
        orbitInertiaFrameRef.current = window.requestAnimationFrame(animateInertia)
      }
    }
    orbitInertiaFrameRef.current = window.requestAnimationFrame(animateInertia)
  }, [moveCourseOrbit, stopCourseOrbitInertia])

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'mouse' && event.button !== 0) return
    const pointerState = orbitPointerStateRef.current
    pointerState.isDragging = true
    pointerState.hasDragged = false
    pointerState.startedOnFocusCard = isFocusCardTarget(event.target)
    pointerState.lastX = event.clientX
    pointerState.lastTime = window.performance.now()
    pointerState.velocity = 0
    stopCourseOrbitInertia()
    event.currentTarget.classList.add('is-dragging')
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const pointerState = orbitPointerStateRef.current
    if (!pointerState.isDragging) return
    const now = window.performance.now()
    const deltaX = event.clientX - pointerState.lastX
    const deltaTime = Math.max(now - pointerState.lastTime, 1)
    pointerState.hasDragged = pointerState.hasDragged || Math.abs(deltaX) > 4
    pointerState.velocity = deltaX / deltaTime
    pointerState.lastX = event.clientX
    pointerState.lastTime = now
    moveCourseOrbit(deltaX * COURSE_ORBIT_DRAG_SENSITIVITY)
  }

  const releasePointer = (event: PointerEvent<HTMLDivElement>, allowFocusCardOpen = true) => {
    const pointerState = orbitPointerStateRef.current
    if (!pointerState.isDragging) return
    const shouldOpenFocusCard = allowFocusCardOpen && pointerState.startedOnFocusCard && !pointerState.hasDragged
    pointerState.isDragging = false
    pointerState.startedOnFocusCard = false
    event.currentTarget.classList.remove('is-dragging')
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    if (shouldOpenFocusCard) {
      pointerState.velocity = 0
      window.setTimeout(() => onCourseOpen(activeOrbitItem), 0)
      return
    }
    startCourseOrbitInertia()
  }

  const handleWheel = (event: WheelEvent<HTMLDivElement>) => {
    if (Math.abs(event.deltaX) <= Math.abs(event.deltaY)) return
    event.preventDefault()
    stopCourseOrbitInertia()
    moveCourseOrbit(-event.deltaX * COURSE_ORBIT_WHEEL_SENSITIVITY)
  }

  const handleSceneKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    stopCourseOrbitInertia()
    moveCourseOrbit(event.key === 'ArrowLeft' ? COURSE_ORBIT_ANGLE_STEP : -COURSE_ORBIT_ANGLE_STEP)
  }

  const handleCourseKeyDown = (event: KeyboardEvent<HTMLElement>, course: Course) => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    onCourseOpen(course)
  }

  useEffect(() => {
    const updateViewportSize = () => {
      setViewportSize({ width: window.innerWidth, height: window.innerHeight })
    }

    updateViewportSize()
    window.addEventListener('resize', updateViewportSize)
    return () => window.removeEventListener('resize', updateViewportSize)
  }, [])

  useEffect(() => () => stopCourseOrbitInertia(), [stopCourseOrbitInertia])

  return (
    <section className="course-stack-section" id="courses">
      <div className="course-stack-stage">
          <div
            className="course-stack-scene"
            onKeyDown={handleSceneKeyDown}
            onPointerCancel={(event) => releasePointer(event, false)}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={releasePointer}
          onWheel={handleWheel}
          tabIndex={0}
        >
          <div className="course-stack-content" aria-label="课程卡片轮盘">
            <div className="course-stack-orbit-ring" aria-hidden="true" />
            <div className="course-stack-cards">
              {orderedCourseOrbitItems.map((course) => (
                <article
                  aria-hidden
                  className="stack-course-card"
                  key={`${course.copyIndex}-${course.day}`}
                  data-course-index={course.courseIndex}
                  data-copy-index={course.copyIndex}
                  data-orbit-index={course.orbitIndex}
                  style={getCourseCardStyle(course, orbitPhase, activeOrbitItem, focusStrength, viewportSize)}
                >
                  {renderCourseCardContent(course)}
                </article>
              ))}
            </div>
          </div>
          <div className="course-stack-focus-layer">
            <article
              aria-current="step"
              aria-label={`${activeOrbitItem.day} ${activeOrbitItem.title} 课程详情`}
              className="stack-course-card stack-course-card--focus is-front"
              onKeyDown={(event) => handleCourseKeyDown(event, activeOrbitItem)}
              role="button"
              data-course-index={activeOrbitItem.courseIndex}
              data-copy-index={activeOrbitItem.copyIndex}
              data-orbit-index={activeOrbitItem.orbitIndex}
              style={getFocusCardStyle(activeOrbitItem, orbitPhase, focusStrength, viewportSize)}
              tabIndex={0}
            >
              {renderCourseCardContent(activeOrbitItem)}
            </article>
          </div>
        </div>
      </div>
    </section>
  )
}
