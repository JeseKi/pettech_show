import { ArrowRight, PackageCheck, Target } from 'lucide-react'
import { BRAND_NAME } from '../../../lib/brand'
import { audience, deliverables, productionFlow, productionSteps } from './pageData'
import type { ProgressiveBlockId } from './types'
import { revealItemStyle } from './utils'

type LandingSectionProps = {
  progressiveClassName: (id: ProgressiveBlockId, className: string) => string
  registerProgressiveBlock: (id: ProgressiveBlockId) => (node: HTMLElement | null) => void
  goToWorkspace: () => void
  isAuthenticated: boolean
}

export function CourseIntroSection({ progressiveClassName, registerProgressiveBlock }: LandingSectionProps) {
  return (
    <section
      className={progressiveClassName('course-intro', 'landing-section landing-section--intro')}
      id="course-intro"
      ref={registerProgressiveBlock('course-intro')}
      data-reveal-id="course-intro"
    >
      <div className="landing-section__heading">
        <p className="landing-eyebrow">WORKBENCH POSITIONING</p>
        <h2>不是临时写几段文案，而是跑完一轮内容获客闭环</h2>
      </div>
      <div className="result-strip">
        {productionFlow.map(([title, text], index) => (
          <article key={title} style={revealItemStyle(index)}>
            <span>{title.slice(1, 3)}</span>
            <h3>{title}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
      <div className="capability-grid">
        {audience.map((item, index) => (
          <article key={item} style={revealItemStyle(index + productionFlow.length)}>
            <Target size={24} />
            <h3>{item}</h3>
            <p>围绕真实业务目标，设计适合自己的内容方向、转化动作和资产沉淀方式。</p>
          </article>
        ))}
      </div>
    </section>
  )
}

export function ProductionSection({
  progressiveClassName,
  registerProgressiveBlock,
  goToWorkspace,
  isAuthenticated,
}: LandingSectionProps) {
  return (
    <section
      className={progressiveClassName('production', 'landing-section tool-flow')}
      id="production"
      ref={registerProgressiveBlock('production')}
      data-reveal-id="production"
    >
      <div className="landing-section__heading">
        <p className="landing-eyebrow">CONTENT PRODUCTION</p>
        <h2>内容生产系统在工作台里使用，公开页只展示能力链路</h2>
      </div>
      <div className="tool-flow__body">
        <div className="tool-flow__rail">
          <span>素材</span>
          <span>知识库</span>
          <span>选题</span>
          <span>内容包</span>
        </div>
        <div className="tool-flow__items">
          {productionSteps.map((item, index) => {
            const Icon = item.icon
            return (
              <article key={item.title} style={revealItemStyle(index)}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <Icon size={26} />
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            )
          })}
        </div>
      </div>
      <div className="landing-section__heading" style={{ marginTop: 34, marginBottom: 0 }}>
        <p className="landing-eyebrow">LOGIN REQUIRED</p>
        <h2>实际功能需要登录后进入工作台查看和使用</h2>
      </div>
      <div className="landing-actions" style={{ marginTop: 24 }}>
        <button className="landing-button landing-button--primary" type="button" onClick={goToWorkspace}>
          {isAuthenticated ? '进入内容生产工作台' : '登录查看功能'}
          <ArrowRight size={18} />
        </button>
      </div>
    </section>
  )
}

export function DeliverablesSection({
  progressiveClassName,
  registerProgressiveBlock,
  goToWorkspace,
  isAuthenticated,
}: LandingSectionProps) {
  return (
    <section
      className={progressiveClassName('deliverables', 'landing-section demo-section')}
      id="deliverables"
      ref={registerProgressiveBlock('deliverables')}
      data-reveal-id="deliverables"
    >
      <div className="demo-section__copy">
        <p className="landing-eyebrow">DELIVERABLES</p>
        <h2>课程结束，带走的是自己的内容增长资产</h2>
        <p>
          从业务诊断、竞品素材、知识库、选题矩阵，到主内容、图文短视频、多平台分发和转化复盘，
          每一步都对应真实可检查的业务产物。
        </p>
        <div className="landing-actions">
          <button className="landing-button landing-button--primary" type="button" onClick={goToWorkspace}>
            {isAuthenticated ? '进入工作台查看功能' : '登录查看功能'}
            <ArrowRight size={18} />
          </button>
        </div>
      </div>
      <div className="tool-flow__items">
        {deliverables.map((item, index) => (
          <article key={item} style={revealItemStyle(index)}>
            <span>{String(index + 1).padStart(2, '0')}</span>
            <PackageCheck size={24} />
            <h3>{item}</h3>
            <p>围绕企业真实运营和获客场景交付，能直接进入下一轮内容生产和复盘。</p>
          </article>
        ))}
      </div>
    </section>
  )
}

export function ContactSection({
  progressiveClassName,
  registerProgressiveBlock,
  goToWorkspace,
  isAuthenticated,
}: LandingSectionProps) {
  return (
    <section
      className={progressiveClassName('contact', 'landing-section final-cta')}
      id="contact"
      ref={registerProgressiveBlock('contact')}
      data-reveal-id="contact"
    >
      <h2>把企业内容增长放进同一个工作台</h2>
      <p>登录后查看内容生产系统、课程训练路径和可复用的业务资产。</p>
      <div>
        <button type="button" onClick={goToWorkspace}>
          {isAuthenticated ? '进入工作台' : '登录查看功能'}
          <ArrowRight size={18} />
        </button>
      </div>
    </section>
  )
}

export function LandingFooter({ registerProgressiveBlock }: LandingSectionProps) {
  return (
    <footer
      className="landing-footer"
      ref={registerProgressiveBlock('footer')}
      data-reveal-id="footer"
    >
      <span>{BRAND_NAME}</span>
      <span>企业AI内容增长与内容生产工作台</span>
    </footer>
  )
}
