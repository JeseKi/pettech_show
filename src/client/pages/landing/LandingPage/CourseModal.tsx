import { X } from 'lucide-react'
import type { Course } from './types'

type CourseModalProps = {
  activeCourse: Course | null
  onClose: () => void
}

export function CourseModal({ activeCourse, onClose }: CourseModalProps) {
  if (!activeCourse) return null

  return (
    <div className="course-modal" role="dialog" aria-modal="true" aria-label={`${activeCourse.title}详情`}>
      <button className="course-modal__backdrop" type="button" onClick={onClose} aria-label="关闭课程详情" />
      <article className="course-modal__panel" data-lenis-prevent>
        <button className="course-modal__close" type="button" onClick={onClose} aria-label="关闭">
          <X size={20} />
        </button>
        <span>{activeCourse.day} · {activeCourse.capability}</span>
        <h2>{activeCourse.title}</h2>
        <p>{activeCourse.description}</p>
        <div className="course-modal__meta">
          <strong>{activeCourse.deliverable}</strong>
          <strong>{activeCourse.duration}</strong>
          <strong>{activeCourse.format}</strong>
        </div>
        <div className="course-modal__columns">
          <section>
            <h3>你会得到</h3>
            {activeCourse.gains.map((item) => <p key={item}>{item}</p>)}
          </section>
          <section>
            <h3>今日目标</h3>
            {activeCourse.goals.map((item) => <p key={item}>{item}</p>)}
          </section>
          <section>
            <h3>课堂实操</h3>
            {activeCourse.practice.map((item) => <p key={item}>{item}</p>)}
          </section>
          <section>
            <h3>验收标准</h3>
            {activeCourse.acceptance.map((item) => <p key={item}>{item}</p>)}
          </section>
          <section>
            <h3>对应系统能力</h3>
            <p>{activeCourse.capability}</p>
            <p>课程先讲运营判断，再进入工具化执行，功能需要登录后在工作台查看。</p>
          </section>
        </div>
      </article>
    </div>
  )
}
