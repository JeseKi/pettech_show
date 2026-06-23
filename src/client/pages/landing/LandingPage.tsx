import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Archive,
  ArrowRight,
  BookOpenCheck,
  CalendarDays,
  ChevronDown,
  Database,
  FileText,
  Layers3,
  LayoutDashboard,
  LogIn,
  Network,
  PackageCheck,
  PenLine,
  Route,
  Target,
  UploadCloud,
  Wand2,
  X,
} from 'lucide-react'
import BrandLogo from '../../components/brand/BrandLogo'
import { useAuth } from '../../hooks/useAuth'
import { BRAND_NAME } from '../../lib/brand'
import SandTableHero from './SandTableHero'
import './LandingPage.css'

type Course = {
  day: string
  title: string
  question: string
  deliverable: string
  capability: string
  goals: string[]
  practice: string[]
  acceptance: string[]
}

const INTRO_UNLOCK_DELAY_MS = 3900

const navGroups = [
  {
    label: '课程介绍',
    href: '#course-intro',
    items: [
      ['7 天训练营', '每天围绕一个真实宠物行业运营场景，产出可交付业务资产。'],
      ['适合对象', '宠物医院、门店、美容洗护、品牌、博主达人和供应链团队。'],
      ['交付结果', '带走选题池、内容包、分发计划、转化路径和资产库。'],
    ],
  },
  {
    label: '内容生产系统',
    href: '#production',
    items: [
      ['知识库生成', '把对标素材、课程资料和运营素材沉淀为可检索资产。'],
      ['选题矩阵', '从素材库生成 30 天选题规划，保留痛点、方案和承接动作。'],
      ['主稿与变体', '从一个 seed 生成主内容，再拆成多平台内容包。'],
    ],
  },
  {
    label: '7天课程',
    href: '#courses',
    items: [
      ['业务诊断', '先明确账号身份、目标用户和首轮内容方向。'],
      ['内容生产', '把选题写成主稿、短视频旁白、图文卡和标题封面。'],
      ['分发转化', '设计推荐流、搜索流、私域承接和复盘沉淀。'],
    ],
  },
  {
    label: '交付成果',
    href: '#deliverables',
    items: [
      ['内容增长场景表', '明确每个业务最该解决的内容增长问题。'],
      ['30 天选题矩阵', '每条选题都有痛点、解决方案和转化策略。'],
      ['内容资产库', '把做完的内容回写到下一轮可复用资产中。'],
    ],
  },
]

const audience = [
  '宠物医院 / 诊所',
  '宠物门店 / 美容洗护 / 寄养',
  '宠物训练师',
  '宠物食品 / 用品品牌',
  '宠物博主 / 达人',
  '宠物供应链企业的老板、运营、市场负责人',
]

const productionSteps = [
  {
    icon: UploadCloud,
    title: '对标内容入库',
    text: '把竞品账号、爆款内容、评论区问题和人工备注整理成可复用原始素材。',
  },
  {
    icon: Database,
    title: '知识库生成',
    text: '从素材中提取痛点、热点、解决方案、选题、搜索入口和 Wiki 条目。',
  },
  {
    icon: Network,
    title: '选题矩阵生成',
    text: '生成 30 天选题矩阵，包含选题、痛点、方案、钩子、承接动作和发布提醒。',
  },
  {
    icon: FileText,
    title: '主内容生成',
    text: '围绕选题 seed 生成长文/主稿，保留来源矩阵、metadata 和内容产物路径。',
  },
  {
    icon: Wand2,
    title: '内容变体改写',
    text: '把主内容改写成不同角度、平台语气、账号定位和用户场景的变体。',
  },
  {
    icon: PenLine,
    title: '标题与封面方向',
    text: '围绕搜索、点击、收藏、转化和封面短标题形成可选方案。',
  },
  {
    icon: Layers3,
    title: '图文卡与短视频化',
    text: '从主内容拆出小红书图文、短视频旁白、轮播视频和公众号长文结构。',
  },
  {
    icon: Route,
    title: '多平台分发',
    text: '适配抖音、视频号、小红书、公众号、社群和私域的发布与承接逻辑。',
  },
  {
    icon: Target,
    title: '转化路径设计',
    text: '让内容导向咨询、到店、预约、下单、私域沉淀和下一轮复盘。',
  },
  {
    icon: Archive,
    title: '内容资产沉淀',
    text: '把素材库、选题库、内容资产库和复盘表接回下一轮内容生产。',
  },
]

const productionFlow = [
  ['从素材到选题', '对标内容、评论需求和业务目标进入知识库，生成可生产的选题 seed。'],
  ['从选题到内容包', '一个 seed 生成主稿，再拆出标题、图文卡、短视频旁白和封面方向。'],
  ['从发布到转化', '按平台重写表达，设计评论、私信、到店、预约和购买承接动作。'],
  ['从复盘到资产库', '把表现数据、用户问题和新素材回写，下一轮继续复用。'],
]

const deliverables = [
  '内容增长场景表',
  '账号 / 品牌内容诊断表',
  '对标账号原始素材和结构化素材',
  '30 天选题矩阵',
  '3 个优先选题的主内容和短视频旁白',
  '标题、图文卡、封面和视频化内容包',
  '多平台分发计划',
  '转化路径设计表',
  '轻量内容资产库和复盘计划',
]

const courses: Course[] = [
  {
    day: 'Day 0',
    title: '课程导入',
    question: '内容增长到底要解决哪些运营问题？',
    deliverable: '内容增长场景表',
    capability: '增长链路认知',
    goals: [
      '理解宠物行业为什么适合内容增长',
      '明确 8 个运营场景分别解决什么问题',
      '知道 AI 和工具只在场景落地时出现',
    ],
    practice: [
      '填写自己的内容增长场景表',
      '标出最关注的 3 个场景',
      '描述课程结束后希望拿到的业务结果',
    ],
    acceptance: [
      '能说清自己的业务目标',
      '能选出最重要的 3 个内容增长场景',
      '能描述最终想获得的业务产物',
    ],
  },
  {
    day: 'Day 1',
    title: '业务诊断',
    question: '我适合做什么内容？',
    deliverable: '内容诊断表',
    capability: '账号定位与内容方向',
    goals: [
      '明确业务身份、目标用户和业务目标',
      '识别内容资源和内容禁区',
      '收束首轮 30 天内容方向',
    ],
    practice: ['填写 Day 1 内容诊断表', '选择主目标和副目标', '写出一句账号定位表达'],
    acceptance: ['主业务目标只选 1 个', '账号定位能说清用户和问题', '内容方向能接上自己的资源'],
  },
  {
    day: 'Day 2',
    title: '竞品洞察',
    question: '我该对标谁，从哪里切入？',
    deliverable: '对标内容素材包',
    capability: '对标内容入库 / 知识库生成',
    goals: [
      '找到 3-5 个对标账号',
      '整理 10 条对标内容原始记录',
      '提炼高频痛点、搜索入口和差异化切入点',
    ],
    practice: ['记录竞品账号和高表现内容', '整理原始素材 Markdown', '生成结构化素材并抽查选题和搜索入口'],
    acceptance: ['至少 3 个竞品账号', '至少 10 条原始素材', '每条结构化素材都有选题和搜索入口'],
  },
  {
    day: 'Day 3',
    title: '选题生成',
    question: '我今天到底发什么？',
    deliverable: '30 天选题矩阵',
    capability: '选题矩阵生成',
    goals: [
      '从素材和知识库生成可复用选题 seed',
      '让每个选题都有痛点、解决方案和承接动作',
      '筛出优先生产的 Top 选题',
    ],
    practice: ['生成 30 条以上选题矩阵', '标出 Top 10 选题', '选择 Day 4 要生产的 3 个选题'],
    acceptance: [
      '至少 30 个选题',
      '每个选题都有痛点、方案和承接动作',
      '能追溯到素材或选题资产库',
    ],
  },
  {
    day: 'Day 4',
    title: '主内容与脚本',
    question: '选题怎么写成能拍的内容？',
    deliverable: '主内容与短视频旁白',
    capability: '主内容生成 / 内容变体改写',
    goals: [
      '把优先选题写成完整主内容',
      '改出短视频旁白和小红书图文结构',
      '检查专业判断、口语感和合规风险',
    ],
    practice: ['选择 3 个优先选题', '生成至少 1 篇主内容', '改写短视频旁白、图文结构和评论私信引导'],
    acceptance: ['主内容保留痛点、方案和承接动作', '开头 3 秒能进入痛点', '医疗、功效、食品相关表达已复核'],
  },
  {
    day: 'Day 5',
    title: '内容生产',
    question: '脚本怎么变成图文、封面和标题？',
    deliverable: '一题多发内容包',
    capability: '标题 / 图文卡 / 封面方向',
    goals: ['生成标题候选和图文卡内容', '形成封面与正文视觉方向', '把一个选题拆成多平台内容包'],
    practice: ['选择一个主内容目录', '生成标题池和图文卡', '规划封面、短视频成片和公众号长文结构'],
    acceptance: ['标题匹配平台和业务目标', '图文卡可发布', '封面和正文视觉没有文字溢出或误导表达'],
  },
  {
    day: 'Day 6',
    title: '分发获客',
    question: '内容做完，怎么发到不同平台？',
    deliverable: '多平台变体与视频化产物',
    capability: '多平台分发 / 图文卡视频化',
    goals: [
      '理解推荐流、搜索流和私域承接',
      '为不同平台生成内容变体',
      '把图文卡组织成可发布视频化内容',
    ],
    practice: ['生成多平台变体', '规划发布节奏和平台适配', '制作图文卡视频化脚本或轮播方案'],
    acceptance: ['每个平台都有适配理由', '搜索词和推荐流逻辑清楚', '内容能导向后续转化动作'],
  },
  {
    day: 'Day 7',
    title: '转化与资产沉淀',
    question: '内容怎么带来咨询、到店，并沉淀资产？',
    deliverable: '转化路径 + 内容资产库',
    capability: '转化路径设计 / 内容资产沉淀',
    goals: [
      '设计咨询、到店、下单和私域承接路径',
      '把内容、素材、数据和复盘沉淀为资产',
      '为下一轮内容生产准备输入',
    ],
    practice: ['填写转化路径设计表', '整理内容资产库', '制定复盘计划和下一轮内容方向'],
    acceptance: [
      '转化动作与业务目标匹配',
      '内容资产能复用',
      '复盘不只看播放量，也看咨询、收藏和搜索入口',
    ],
  },
]

export default function LandingPage() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const [activeCourse, setActiveCourse] = useState<Course | null>(null)
  const [introComplete, setIntroComplete] = useState(false)

  const featuredCourse = useMemo(() => courses[3], [])

  const goToWorkspace = () => {
    navigate(isAuthenticated ? '/aiwiki' : '/login')
  }

  const goToConsult = () => {
    navigate(isAuthenticated ? '/dashboard' : '/register')
  }

  useEffect(() => {
    const previousHtmlOverflowY = document.documentElement.style.overflowY
    const previousBodyOverflowY = document.body.style.overflowY
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const unlockDelay = prefersReducedMotion ? 0 : INTRO_UNLOCK_DELAY_MS

    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
    document.documentElement.style.overflowY = 'hidden'
    document.body.style.overflowY = 'hidden'

    const unlockTimer = window.setTimeout(() => {
      setIntroComplete(true)
      document.documentElement.style.overflowY = previousHtmlOverflowY
      document.body.style.overflowY = previousBodyOverflowY
    }, unlockDelay)

    return () => {
      window.clearTimeout(unlockTimer)
      document.documentElement.style.overflowY = previousHtmlOverflowY
      document.body.style.overflowY = previousBodyOverflowY
    }
  }, [])

  return (
    <main className={`landing-page${introComplete ? ' is-intro-complete' : ''}`}>
      <header className="landing-nav">
        <a className="landing-brand" href="#hero" aria-label={`${BRAND_NAME}首页`}>
          <BrandLogo compact size={32} />
          <span>{BRAND_NAME}</span>
        </a>
        <nav className="landing-nav__links" aria-label="主导航">
          {navGroups.map((group) => (
            <div className="landing-nav__item" key={group.label}>
              <a href={group.href}>
                {group.label}
                <ChevronDown size={15} />
              </a>
              <div className="landing-mega">
                {group.items.map(([title, text]) => (
                  <a href={group.href} key={title}>
                    <strong>{title}</strong>
                    <span>{text}</span>
                  </a>
                ))}
              </div>
            </div>
          ))}
          <a href="#contact">预约咨询</a>
        </nav>
        <div className="landing-nav__actions">
          <button type="button" onClick={() => navigate(isAuthenticated ? '/dashboard' : '/login')}>
            {isAuthenticated ? <LayoutDashboard size={17} /> : <LogIn size={17} />}
            {isAuthenticated ? '进入工作台' : '登录'}
          </button>
          <button className="is-primary" type="button" onClick={goToConsult}>
            预约咨询
          </button>
        </div>
      </header>

      <section className="landing-hero" id="hero">
        <SandTableHero />
        <div className="landing-hero__content">
          <p className="landing-eyebrow">PET CONTENT GROWTH SYSTEM</p>
          <h1>宠物行业 AI 内容增长与内容生产系统</h1>
          <p>
            面向宠物医院、门店、品牌和达人，把对标素材、知识库、选题矩阵、主内容、
            图文短视频、多平台分发和转化资产串成一套可持续运行的内容生产流程。
          </p>
          <div className="landing-hero__actions">
            <a className="landing-button landing-button--primary" href="#contact">
              预约咨询
              <ArrowRight size={18} />
            </a>
            <a className="landing-button" href="#courses">
              <BookOpenCheck size={17} />
              查看 7 天课程
            </a>
          </div>
        </div>
        <div className="landing-hero__metrics" aria-label="课程与系统数据">
          <div><strong>8</strong><span>运营场景</span></div>
          <div><strong>30</strong><span>天选题矩阵</span></div>
          <div><strong>7</strong><span>天训练营</span></div>
        </div>
      </section>

      <section className="landing-section landing-section--intro" id="course-intro">
        <div className="landing-section__heading">
          <p className="landing-eyebrow">COURSE POSITIONING</p>
          <h2>不是临时写几段文案，而是跑完一轮内容获客闭环</h2>
        </div>
        <div className="result-strip">
          {productionFlow.map(([title, text]) => (
            <article key={title}>
              <span>{title.slice(1, 3)}</span>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
        <div className="capability-grid">
          {audience.map((item) => (
            <article key={item}>
              <Target size={24} />
              <h3>{item}</h3>
              <p>围绕真实业务目标，设计适合自己的内容方向、转化动作和资产沉淀方式。</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section tool-flow" id="production">
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
                <article key={item.title}>
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
        <div className="landing-hero__actions" style={{ marginTop: 24 }}>
          <button className="landing-button landing-button--primary" type="button" onClick={goToWorkspace}>
            {isAuthenticated ? '进入内容生产工作台' : '登录查看功能'}
            <ArrowRight size={18} />
          </button>
        </div>
      </section>

      <section className="landing-section course-section" id="courses">
        <div className="landing-section__heading">
          <p className="landing-eyebrow">7-DAY BOOTCAMP</p>
          <h2>宠物行业 AI 内容增长实战课 · 7 天训练营</h2>
        </div>
        <div className="course-layout">
          <button className="course-feature" type="button" onClick={() => setActiveCourse(featuredCourse)}>
            <span>{featuredCourse.day} · {featuredCourse.capability}</span>
            <h3>{featuredCourse.title}</h3>
            <p>{featuredCourse.question}</p>
            <strong>{featuredCourse.deliverable}</strong>
          </button>
          <div className="course-grid">
            {courses.map((course) => (
              <button key={course.day} type="button" onClick={() => setActiveCourse(course)}>
                <span>{course.day} · {course.capability}</span>
                <h3>{course.title}</h3>
                <p>{course.question}</p>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-section demo-section" id="deliverables">
        <div className="demo-section__copy">
          <p className="landing-eyebrow">DELIVERABLES</p>
          <h2>课程结束，带走的是自己的内容增长资产</h2>
          <p>
            从业务诊断、竞品素材、知识库、选题矩阵，到主内容、图文短视频、多平台分发和转化复盘，
            每一步都对应真实可检查的业务产物。
          </p>
          <div className="landing-hero__actions">
            <button className="landing-button landing-button--primary" type="button" onClick={goToWorkspace}>
              {isAuthenticated ? '进入工作台查看功能' : '登录查看功能'}
              <ArrowRight size={18} />
            </button>
          </div>
        </div>
        <div className="tool-flow__items">
          {deliverables.map((item, index) => (
            <article key={item}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <PackageCheck size={24} />
              <h3>{item}</h3>
              <p>围绕宠物行业真实运营场景交付，能直接进入下一轮内容生产和复盘。</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section final-cta" id="contact">
        <CalendarDays size={34} />
        <h2>想把宠物行业内容生产做成可持续系统？</h2>
        <p>预约咨询，了解内容生产系统、7 天训练营和适合你业务的落地方式。</p>
        <div>
          <button type="button" onClick={goToConsult}>
            预约咨询
            <ArrowRight size={18} />
          </button>
          <button type="button" onClick={goToWorkspace}>
            {isAuthenticated ? '进入工作台' : '登录查看功能'}
          </button>
        </div>
      </section>

      <footer className="landing-footer">
        <span>{BRAND_NAME}</span>
        <span>宠物行业 AI 内容增长与内容生产系统</span>
      </footer>

      {activeCourse && (
        <div className="course-modal" role="dialog" aria-modal="true" aria-label={`${activeCourse.title}详情`}>
          <button
            className="course-modal__backdrop"
            type="button"
            onClick={() => setActiveCourse(null)}
            aria-label="关闭课程详情"
          />
          <article className="course-modal__panel">
            <button className="course-modal__close" type="button" onClick={() => setActiveCourse(null)} aria-label="关闭">
              <X size={20} />
            </button>
            <span>{activeCourse.day} · {activeCourse.capability}</span>
            <h2>{activeCourse.title}</h2>
            <p>{activeCourse.question}</p>
            <div className="course-modal__meta">
              <strong>{activeCourse.deliverable}</strong>
              <strong>宠物行业真实运营场景</strong>
            </div>
            <div className="course-modal__columns">
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
      )}
    </main>
  )
}
