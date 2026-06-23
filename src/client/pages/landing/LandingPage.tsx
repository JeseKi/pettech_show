import { type CSSProperties, useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Lenis from 'lenis'
import 'lenis/dist/lenis.css'
import {
  Archive,
  ArrowRight,
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
import './LandingPage.css'

type Course = {
  day: string
  title: string
  description: string
  duration: string
  format: string
  deliverable: string
  capability: string
  accent: string
  gains: string[]
  goals: string[]
  practice: string[]
  acceptance: string[]
}

const PROGRESSIVE_BLOCK_IDS = ['course-intro', 'production', 'deliverables', 'contact', 'footer'] as const
const INTRO_UNLOCK_DELAY_MS = 1900
const STACK_INTRO_DELAY_MS = 480
const STACK_INTRO_DURATION_MS = 1420
const STACK_PROGRESS_OFFSET = 0.55
const STACK_PROGRESS_RANGE = 0.15
const STACK_SMOOTH_SCROLL_LERP = 0.07

type ProgressiveBlockId = (typeof PROGRESSIVE_BLOCK_IDS)[number]
type RevealStyle = CSSProperties & Record<'--reveal-delay', string>
type CourseStackSectionStyle = CSSProperties & Record<'--course-scroll-height', string>
type CourseCardStyle = CSSProperties & Record<
  | '--course-accent'
  | '--stack-z'
  | '--stack-rotate-y'
  | '--stack-rotate-z'
  | '--stack-opacity'
  | '--stack-brightness',
  string
>
type ViewportSize = {
  width: number
  height: number
}

const revealItemStyle = (index: number): RevealStyle => ({
  '--reveal-delay': `${index * 48}ms`,
})

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

const isProgressiveBlockId = (id: string | null): id is ProgressiveBlockId => (
  id !== null && PROGRESSIVE_BLOCK_IDS.includes(id as ProgressiveBlockId)
)

const navGroups = [
  {
    label: '7天课程',
    href: '#courses',
    items: [
      ['课程卡片堆叠', '滚动浏览 Day 0 到毕业项目，每张卡展示内容、收获、时间和交付物。'],
      ['业务诊断', '先明确账号身份、目标用户和首轮内容方向。'],
      ['分发转化', '设计推荐流、搜索流、私域承接和复盘沉淀。'],
    ],
  },
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
    description: '把工具学习切回真实运营场景，先理解宠物行业内容增长为什么是前置销售系统。',
    duration: '约 150 分钟',
    format: '场景导入 + 链路认知',
    deliverable: '内容增长场景表',
    capability: '增长链路认知',
    accent: '#b8ff67',
    gains: ['看清 8 个运营场景', '标出最关注的 3 个问题', '明确最终想拿到的业务产物'],
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
    description: '从身份、目标用户、业务目标、资源优势和内容禁区出发，收束首轮内容方向。',
    duration: '约 150 分钟',
    format: '定位判断 + 诊断表实操',
    deliverable: '内容诊断表',
    capability: '账号定位与内容方向',
    accent: '#6ee7f9',
    gains: ['账号 / 品牌定位表达', '主目标与副目标', '首轮 30 天内容方向'],
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
    description: '把对标账号和高表现内容变成可复用素材，而不是只停留在看同行、抄标题。',
    duration: '约 150 分钟',
    format: '案例拆解 + 素材入库',
    deliverable: '对标内容素材包',
    capability: '对标内容入库 / 知识库生成',
    accent: '#facc15',
    gains: ['3-5 个对标账号', '10 条原始素材记录', '高频痛点和搜索入口'],
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
    description: '从素材库、用户问题、搜索入口和业务目标里生成选题矩阵，让每天发什么有依据。',
    duration: '约 150 分钟',
    format: '矩阵生成 + Top 选题筛选',
    deliverable: '30 天选题矩阵',
    capability: '选题矩阵生成',
    accent: '#fb7185',
    gains: ['30 条以上选题 seed', 'Top 10 优先选题', '痛点、方案和承接动作'],
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
    description: '把优先选题写成主内容，再改成短视频旁白、小红书图文结构和承接话术。',
    duration: '约 150 分钟',
    format: '主稿生成 + 脚本改写',
    deliverable: '主内容与短视频旁白',
    capability: '主内容生成 / 内容变体改写',
    accent: '#a78bfa',
    gains: ['3 个优先选题', '至少 1 篇主内容', '短视频旁白与图文结构'],
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
    description: '把一条主内容拆成标题、图文卡、封面方向、短视频和公众号结构，形成一题多发内容包。',
    duration: '约 150 分钟',
    format: '标题封面 + 图文卡实操',
    deliverable: '一题多发内容包',
    capability: '标题 / 图文卡 / 封面方向',
    accent: '#f97316',
    gains: ['标题候选池', '一组图文卡', '封面与视频化方向'],
    goals: ['生成标题候选和图文卡内容', '形成封面与正文视觉方向', '把一个选题拆成多平台内容包'],
    practice: ['选择一个主内容目录', '生成标题池和图文卡', '规划封面、短视频成片和公众号长文结构'],
    acceptance: ['标题匹配平台和业务目标', '图文卡可发布', '封面和正文视觉没有文字溢出或误导表达'],
  },
  {
    day: 'Day 6',
    title: '分发获客',
    description: '理解推荐流、搜索流和私域承接，把内容改写成抖音、视频号、小红书、公众号等平台版本。',
    duration: '约 150 分钟',
    format: '平台适配 + 视频化组织',
    deliverable: '多平台变体与视频化产物',
    capability: '多平台分发 / 图文卡视频化',
    accent: '#38bdf8',
    gains: ['3-5 个平台版本', '发布节奏规划', '图文卡视频化方案'],
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
    description: '把内容后的咨询、到店、下单和私域路径设计清楚，再把素材、数据和复盘沉淀为资产。',
    duration: '约 150 分钟',
    format: '转化路径 + 复盘资产库',
    deliverable: '转化路径 + 内容资产库',
    capability: '转化路径设计 / 内容资产沉淀',
    accent: '#2dd4bf',
    gains: ['转化路径设计表', '轻量内容资产库', '下一轮复盘计划'],
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
  {
    day: '毕业项目',
    title: '闭环实战',
    description: '把定位、素材、选题、主内容、视觉卡、分发、转化和资产沉淀串成一份完整增长方案。',
    duration: '结课项目',
    format: '方案提交 + 复盘计划',
    deliverable: '完整内容增长方案',
    capability: '内容增长闭环',
    accent: '#f0abfc',
    gains: ['30 天选题矩阵', '3 个优先选题主内容', '分发、转化和下一轮复盘方案'],
    goals: [
      '完成一轮从定位到资产沉淀的完整闭环',
      '明确接下来 30 天选题和 3 个优先生产主题',
      '知道数据怎么复盘、下一轮内容从哪里来',
    ],
    practice: [
      '提交账号 / 品牌定位与目标用户',
      '整理素材、选题矩阵、主内容和内容包',
      '完成多平台分发计划、转化路径和复盘记录',
    ],
    acceptance: [
      '定位、素材、选题和内容产物完整',
      '分发与转化匹配平台和业务目标',
      '资产沉淀能指导下一轮内容生产',
    ],
  },
]

const courseStackSectionStyle: CourseStackSectionStyle = {
  '--course-scroll-height': `${courses.length * 70}svh`,
}

const getCourseCardStyle = (
  index: number,
  progress: number,
  course: Course,
  viewportSize: ViewportSize,
): CourseCardStyle => {
  const staggeredProgress = clamp(progress * 1.05 - index * 0.006, 0, 1)
  const startZ = -2.65 * viewportSize.width - index * 0.03 * viewportSize.width
  const endZ = 1.4 * viewportSize.width + (courses.length - index - 1) * 0.03 * viewportSize.width
  const z = startZ + (endZ - startZ) * progress
  const rotateY = -30 * staggeredProgress
  const rotateZ = -220 + 340 * staggeredProgress
  const visibleDepth = Math.abs(z) / Math.max(viewportSize.width, 1)
  const opacity = clamp(1 - Math.max(visibleDepth - 1.9, 0) * 0.34, 0, 1)
  const brightness = clamp(1.08 - visibleDepth * 0.08, 0.68, 1.08)

  return {
    '--course-accent': course.accent,
    '--stack-z': `${z}px`,
    '--stack-rotate-y': `${rotateY}deg`,
    '--stack-rotate-z': `${rotateZ}deg`,
    '--stack-opacity': `${opacity}`,
    '--stack-brightness': `${brightness}`,
    zIndex: courses.length - index,
  }
}

export default function LandingPage() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const [activeCourse, setActiveCourse] = useState<Course | null>(null)
  const [introComplete, setIntroComplete] = useState(false)
  const [revealedBlockIds, setRevealedBlockIds] = useState<Set<ProgressiveBlockId>>(() => new Set())
  const [stackProgress, setStackProgress] = useState(0)
  const [stackIntroProgress, setStackIntroProgress] = useState(0)
  const [viewportSize, setViewportSize] = useState<ViewportSize>({ width: 1280, height: 720 })
  const progressiveBlockRefs = useRef(new Map<ProgressiveBlockId, HTMLElement>())
  const courseStackRef = useRef<HTMLElement | null>(null)

  const motionProgress = STACK_PROGRESS_OFFSET * stackIntroProgress + stackProgress * STACK_PROGRESS_RANGE
  const activeStackIndex = clamp(Math.round(stackProgress * (courses.length - 1)), 0, courses.length - 1)

  const revealBlock = useCallback((id: ProgressiveBlockId) => {
    setRevealedBlockIds((current) => {
      if (current.has(id)) return current

      const next = new Set(current)
      const targetIndex = PROGRESSIVE_BLOCK_IDS.indexOf(id)
      PROGRESSIVE_BLOCK_IDS.slice(0, targetIndex + 1).forEach((blockId) => next.add(blockId))
      return next
    })
  }, [])

  const registerProgressiveBlock = useCallback((id: ProgressiveBlockId) => (node: HTMLElement | null) => {
    if (node) {
      progressiveBlockRefs.current.set(id, node)
      return
    }

    progressiveBlockRefs.current.delete(id)
  }, [])

  const progressiveClassName = (id: ProgressiveBlockId, className: string) => (
    `${className} landing-reveal${revealedBlockIds.has(id) ? ' is-revealed' : ''}`
  )

  const goToWorkspace = () => {
    navigate(isAuthenticated ? '/aiwiki' : '/login')
  }

  const goToConsult = () => {
    navigate(isAuthenticated ? '/dashboard' : '/register')
  }

  const openCourse = (course: Course) => {
    setActiveCourse(course)
  }

  const handleCourseKeyDown = (event: React.KeyboardEvent<HTMLElement>, course: Course) => {
    if (event.key !== 'Enter' && event.key !== ' ') return

    event.preventDefault()
    openCourse(course)
  }

  const handleStackSceneClick = (event: React.MouseEvent<HTMLDivElement>) => {
    const cardElements = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('.stack-course-card'))
    const matchingCard = cardElements
      .map((cardElement) => {
        const rect = cardElement.getBoundingClientRect()
        const opacity = Number(window.getComputedStyle(cardElement).opacity)
        const courseIndex = Number(cardElement.dataset.courseIndex)

        return {
          courseIndex,
          isHit:
            opacity > 0.1
            && event.clientX >= rect.left
            && event.clientX <= rect.right
            && event.clientY >= rect.top
            && event.clientY <= rect.bottom,
          zIndex: Number(window.getComputedStyle(cardElement).zIndex) || 0,
        }
      })
      .filter((card) => card.isHit && Number.isInteger(card.courseIndex))
      .sort((left, right) => right.zIndex - left.zIndex)[0]

    if (!matchingCard) return

    openCourse(courses[matchingCard.courseIndex])
  }

  useEffect(() => {
    const updateStackProgress = () => {
      const section = courseStackRef.current
      if (!section) return

      const scrollable = Math.max(section.offsetHeight - window.innerHeight, 1)
      const progress = clamp(-section.getBoundingClientRect().top / scrollable, 0, 1)

      setStackProgress((current) => (Math.abs(current - progress) < 0.0001 ? current : progress))
    }

    const updateViewportSize = () => {
      setViewportSize({
        width: window.innerWidth,
        height: window.innerHeight,
      })
    }

    let frameId = 0
    const requestUpdate = () => {
      window.cancelAnimationFrame(frameId)
      frameId = window.requestAnimationFrame(updateStackProgress)
    }

    updateViewportSize()
    updateStackProgress()
    window.addEventListener('scroll', requestUpdate, { passive: true })
    window.addEventListener('resize', updateViewportSize)
    window.addEventListener('resize', requestUpdate)

    return () => {
      window.cancelAnimationFrame(frameId)
      window.removeEventListener('scroll', requestUpdate)
      window.removeEventListener('resize', updateViewportSize)
      window.removeEventListener('resize', requestUpdate)
    }
  }, [])

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (prefersReducedMotion) {
      setStackIntroProgress(1)
      return undefined
    }

    let frameId = 0
    const startTime = window.performance.now() + STACK_INTRO_DELAY_MS

    const animateIntro = (timestamp: number) => {
      const linearProgress = clamp((timestamp - startTime) / STACK_INTRO_DURATION_MS, 0, 1)
      const easedProgress = 1 - ((1 - linearProgress) ** 3)

      setStackIntroProgress((current) => (
        Math.abs(current - easedProgress) < 0.0001 ? current : easedProgress
      ))

      if (linearProgress < 1) {
        frameId = window.requestAnimationFrame(animateIntro)
      }
    }

    frameId = window.requestAnimationFrame(animateIntro)

    return () => {
      window.cancelAnimationFrame(frameId)
    }
  }, [])

  useEffect(() => {
    if (!introComplete) return undefined

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (prefersReducedMotion) return undefined

    const lenis = new Lenis({
      lerp: STACK_SMOOTH_SCROLL_LERP,
      smoothWheel: true,
      syncTouch: true,
      prevent: (node) => Boolean(node.closest('.course-modal__panel')),
    })

    let frameId = 0
    const animateSmoothScroll = (time: number) => {
      lenis.raf(time)
      frameId = window.requestAnimationFrame(animateSmoothScroll)
    }

    frameId = window.requestAnimationFrame(animateSmoothScroll)

    return () => {
      window.cancelAnimationFrame(frameId)
      lenis.destroy()
    }
  }, [introComplete])

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

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (prefersReducedMotion || !('IntersectionObserver' in window)) {
      setRevealedBlockIds(new Set(PROGRESSIVE_BLOCK_IDS))
      return undefined
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return

          const id = entry.target.getAttribute('data-reveal-id')
          if (!isProgressiveBlockId(id)) return

          revealBlock(id)
          observer.unobserve(entry.target)
        })
      },
      {
        rootMargin: '0px 0px -12% 0px',
        threshold: 0.08,
      },
    )

    progressiveBlockRefs.current.forEach((node) => observer.observe(node))

    const frameId = window.requestAnimationFrame(() => {
      progressiveBlockRefs.current.forEach((node, id) => {
        const rect = node.getBoundingClientRect()
        if (rect.top < window.innerHeight * 0.88 && rect.bottom > 0) {
          revealBlock(id)
          observer.unobserve(node)
        }
      })
    })

    return () => {
      window.cancelAnimationFrame(frameId)
      observer.disconnect()
    }
  }, [revealBlock])

  return (
    <main className="landing-page">
      <header className="landing-nav">
        <a className="landing-brand" href="#courses" aria-label={`${BRAND_NAME}首页`}>
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

      <section
        className="course-stack-section"
        id="courses"
        ref={courseStackRef}
        style={courseStackSectionStyle}
      >
        <div className="course-stack-stage">
          <div className="course-stack-scene" onClick={handleStackSceneClick}>
            <div className="course-stack-content" aria-label="课程卡片堆叠">
              {courses.map((course, index) => {
                const cardDistance = Math.abs(index - activeStackIndex)

                return (
                  <article
                    aria-current={activeStackIndex === index ? 'step' : undefined}
                    aria-label={`${course.day} ${course.title} 课程详情`}
                    className="stack-course-card"
                    key={course.day}
                    onClick={() => openCourse(course)}
                    onKeyDown={(event) => handleCourseKeyDown(event, course)}
                    role="button"
                    data-course-index={index}
                    style={getCourseCardStyle(index, motionProgress, course, viewportSize)}
                    tabIndex={cardDistance < 2 ? 0 : -1}
                  >
                    <div className="stack-course-card__top">
                      <span>{course.day}</span>
                      <strong>{course.duration}</strong>
                    </div>

                    <h2>{course.title}</h2>
                    <p>{course.description}</p>

                    <div className="stack-course-card__meta">
                      <strong>得到什么</strong>
                      <ul>
                        {course.gains.slice(0, 2).map((gain) => (
                          <li key={gain}>{gain}</li>
                        ))}
                      </ul>
                    </div>

                    <footer>{course.deliverable}</footer>
                  </article>
                )
              })}
            </div>
          </div>
        </div>
      </section>

      <section
        className={progressiveClassName('course-intro', 'landing-section landing-section--intro')}
        id="course-intro"
        ref={registerProgressiveBlock('course-intro')}
        data-reveal-id="course-intro"
      >
        <div className="landing-section__heading">
          <p className="landing-eyebrow">COURSE POSITIONING</p>
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
              <p>围绕宠物行业真实运营场景交付，能直接进入下一轮内容生产和复盘。</p>
            </article>
          ))}
        </div>
      </section>

      <section
        className={progressiveClassName('contact', 'landing-section final-cta')}
        id="contact"
        ref={registerProgressiveBlock('contact')}
        data-reveal-id="contact"
      >
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

      <footer
        className={progressiveClassName('footer', 'landing-footer')}
        ref={registerProgressiveBlock('footer')}
        data-reveal-id="footer"
      >
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
          <article className="course-modal__panel" data-lenis-prevent>
            <button className="course-modal__close" type="button" onClick={() => setActiveCourse(null)} aria-label="关闭">
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
      )}
    </main>
  )
}
