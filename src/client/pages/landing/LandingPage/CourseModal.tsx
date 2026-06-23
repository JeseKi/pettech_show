import { type CSSProperties, useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import type { Course } from './types'

const COURSE_MODAL_EXIT_MS = 280

type CourseModalStyle = CSSProperties & Record<'--course-accent', string>

type CourseModalProps = {
  activeCourse: Course | null
  onClose: () => void
}

export function CourseModal({ activeCourse, onClose }: CourseModalProps) {
  const [displayCourse, setDisplayCourse] = useState<Course | null>(activeCourse)
  const [modalState, setModalState] = useState<'open' | 'closing'>('open')
  const closeTimerRef = useRef(0)

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

  if (!displayCourse) return null

  const modalStyle: CourseModalStyle = {
    '--course-accent': displayCourse.accent,
  }

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
      <article className="course-modal__panel" data-lenis-prevent>
        <button className="course-modal__close" type="button" onClick={onClose} aria-label="关闭">
          <X size={20} />
        </button>
        <span>{displayCourse.day} · {displayCourse.capability}</span>
        <h2>{displayCourse.title}</h2>
        <p>{displayCourse.description}</p>
        <div className="course-modal__meta">
          <strong>{displayCourse.deliverable}</strong>
          <strong>{displayCourse.duration}</strong>
          <strong>{displayCourse.format}</strong>
        </div>
        <div className="course-modal__columns">
          <section>
            <h3>你会得到</h3>
            {displayCourse.gains.map((item) => <p key={item}>{item}</p>)}
          </section>
          <section>
            <h3>今日目标</h3>
            {displayCourse.goals.map((item) => <p key={item}>{item}</p>)}
          </section>
          <section>
            <h3>课堂实操</h3>
            {displayCourse.practice.map((item) => <p key={item}>{item}</p>)}
          </section>
          <section>
            <h3>验收标准</h3>
            {displayCourse.acceptance.map((item) => <p key={item}>{item}</p>)}
          </section>
          <section>
            <h3>对应系统能力</h3>
            <p>{displayCourse.capability}</p>
            <p>课程先讲运营判断，再进入工具化执行，功能需要登录后在工作台查看。</p>
          </section>
        </div>
      </article>
    </div>
  )
}
