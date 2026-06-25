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

  useEffect(() => {
    if (!displayCourse) return undefined
    document.documentElement.classList.add('course-modal-open')
    document.body.classList.add('course-modal-open')

    return () => {
      document.documentElement.classList.remove('course-modal-open')
      document.body.classList.remove('course-modal-open')
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
      <article className="course-modal__panel" data-lenis-prevent>
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
