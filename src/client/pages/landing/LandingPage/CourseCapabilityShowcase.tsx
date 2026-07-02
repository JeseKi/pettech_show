import { useEffect, useMemo, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { courseShowcaseTabs } from './pageData'
import { type CourseShowcaseTabKey, type ProgressiveBlockId } from './types'
import { revealItemStyle } from './utils'

type CourseCapabilityShowcaseProps = {
  activeTabKey: CourseShowcaseTabKey
  onTabChange: (tabKey: CourseShowcaseTabKey) => void
  onCoursesOpen: () => void
  progressiveClassName: (id: ProgressiveBlockId, className: string) => string
  registerProgressiveBlock: (id: ProgressiveBlockId) => (node: HTMLElement | null) => void
}

export function CourseCapabilityShowcase({
  activeTabKey,
  onTabChange,
  onCoursesOpen,
  progressiveClassName,
  registerProgressiveBlock,
}: CourseCapabilityShowcaseProps) {
  const activeTab = useMemo(() => (
    courseShowcaseTabs.find((tab) => tab.key === activeTabKey) ?? courseShowcaseTabs[0]
  ), [activeTabKey])
  const [activeNodeId, setActiveNodeId] = useState(() => activeTab.nodes[0]?.id ?? '')

  useEffect(() => {
    setActiveNodeId(activeTab.nodes[0]?.id ?? '')
  }, [activeTab])

  const activeNode = activeTab.nodes.find((node) => node.id === activeNodeId) ?? activeTab.nodes[0]
  const activeConnectedNodeIds = new Set([
    activeNode?.id ?? '',
    ...activeTab.edges
      .filter((edge) => edge.from === activeNode?.id || edge.to === activeNode?.id)
      .flatMap((edge) => [edge.from, edge.to]),
  ])

  return (
    <section
      className={progressiveClassName('course-capabilities', 'course-capability-showcase')}
      id="course-capabilities"
      aria-labelledby="course-capability-title"
      ref={registerProgressiveBlock('course-capabilities')}
      data-reveal-id="course-capabilities"
    >
      <div className="course-capability-showcase__heading">
        <div>
          <p className="landing-eyebrow">COURSE MENU</p>
          <h2 id="course-capability-title">课程能力不只是一张课表，而是三套可落地的 Agent 工作流</h2>
        </div>
        <p>
          三个子菜单分别对应教学资产生产、行业智能体制作和互动影游导演台。每一项都用流程图说明输入、处理和最终产物。
        </p>
      </div>

      <div className="course-capability-tabs" role="tablist" aria-label="课程子菜单">
        {courseShowcaseTabs.map((tab) => {
          const Icon = tab.icon
          const selected = tab.key === activeTab.key

          return (
            <button
              className={selected ? 'course-capability-tabs__button is-active' : 'course-capability-tabs__button'}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={`course-capability-panel-${tab.key}`}
              id={`course-capability-tab-${tab.key}`}
              key={tab.key}
              onClick={() => onTabChange(tab.key)}
            >
              <Icon size={18} />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>

      <div
        className="course-capability-panel"
        id={`course-capability-panel-${activeTab.key}`}
        role="tabpanel"
        aria-labelledby={`course-capability-tab-${activeTab.key}`}
      >
        <div className="course-capability-panel__copy">
          <span>{activeTab.eyebrow}</span>
          <h3>{activeTab.title}</h3>
          <p>{activeTab.summary}</p>
          <div className="course-capability-panel__rail" aria-label={`${activeTab.label}流程阶段`}>
            {activeTab.rail.map((item) => (
              <strong key={item}>{item}</strong>
            ))}
          </div>
          <button className="landing-button landing-button--primary" type="button" onClick={onCoursesOpen}>
            查看完整课程
            <ArrowRight size={18} />
          </button>
        </div>

        <div className="course-flow-board" aria-label={`${activeTab.label}概念流程图`}>
          <div className="course-flow-map">
            <svg className="course-flow-map__edges" viewBox="0 0 1060 730" preserveAspectRatio="none" aria-hidden="true">
              {activeTab.edges.map((edge) => {
                const connected = edge.from === activeNode?.id || edge.to === activeNode?.id

                return (
                  <g key={edge.id}>
                    <path className="course-flow-map__edge-base" d={edge.path} />
                    <path
                      className={connected ? 'course-flow-map__edge-flow is-active' : 'course-flow-map__edge-flow'}
                      d={edge.path}
                    />
                  </g>
                )
              })}
            </svg>

            {activeTab.nodes.map((node, index) => (
              <button
                className={[
                  'course-flow-node',
                  node.branch ? 'course-flow-node--branch' : '',
                  node.id === activeNode?.id ? 'is-active' : '',
                  activeConnectedNodeIds.has(node.id) ? 'is-connected' : '',
                ].filter(Boolean).join(' ')}
                type="button"
                key={node.id}
                style={{
                  left: `${(node.x / 1060) * 100}%`,
                  top: `${(node.y / 730) * 100}%`,
                  ...revealItemStyle(index),
                }}
                onClick={() => setActiveNodeId(node.id)}
              >
                <i />
                <span className="course-flow-node__label">{node.label}</span>
                <strong>{node.title}</strong>
                <span>{node.subtitle}</span>
              </button>
            ))}
          </div>

          {activeNode && (
            <aside className="course-flow-detail">
              <span>当前节点</span>
              <h3>{activeNode.title}</h3>
              <p>{activeNode.summary}</p>
              <div className="course-flow-detail__stack">
                <section>
                  <strong>输入</strong>
                  <p>{activeNode.input}</p>
                </section>
                <section>
                  <strong>处理</strong>
                  <p>{activeNode.process}</p>
                </section>
                <section>
                  <strong>效果</strong>
                  <p>{activeNode.effect}</p>
                </section>
              </div>
            </aside>
          )}
        </div>
      </div>
    </section>
  )
}
