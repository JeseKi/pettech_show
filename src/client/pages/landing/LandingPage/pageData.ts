import {
  Archive,
  BarChart3,
  Bot,
  CalendarDays,
  Database,
  FileText,
  Film,
  Flame,
  GraduationCap,
  Hand,
  Layers3,
  Lightbulb,
  MessageCircle,
  MessageCircleWarning,
  Network,
  NotebookText,
  PenLine,
  PenTool,
  Puzzle,
  Route,
  ScrollText,
  Search,
  Sparkles,
  Target,
  TrendingUp,
  UploadCloud,
  Wand2,
  Wrench,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import {
  AGENT_TOOL,
  CAPABILITY_GROUP_META,
  CONTENT_GROWTH_TOOL,
  GESTURE_CONTROL_TOOL,
  INFO_DISTRIBUTION_TOOL,
  INTERACTIVE_MOVIE_TOOL,
  PERSONAL_AIWIKI_TOOL,
  WECHAT_AUTOMATION_FLOW_TOOL,
  WECOM_MOMENTS_PUBLISH_TOOL,
  VISIBLE_CAPABILITY_ENTRIES,
  type WorkflowExternalConfigKey,
} from '../../../lib/workflowModes'
import type { CourseShowcaseTabKey } from './types'

type LandingNavMenuItem = {
  label: string
  path: string
  description: string
  icon: LucideIcon
  externalConfigKey?: WorkflowExternalConfigKey
}

export type LandingNavGroup = {
  label: string
  path: string
  icon: LucideIcon
  items: LandingNavMenuItem[]
}

export type CourseShowcaseNode = {
  id: string
  label: string
  title: string
  subtitle: string
  x: number
  y: number
  branch?: boolean
  summary: string
  input: string
  process: string
  effect: string
}

export type CourseShowcaseEdge = {
  id: string
  path: string
  from: string
  to: string
}

export type CourseShowcaseTab = {
  key: CourseShowcaseTabKey
  label: string
  eyebrow: string
  title: string
  summary: string
  icon: LucideIcon
  rail: string[]
  nodes: CourseShowcaseNode[]
  edges: CourseShowcaseEdge[]
}

export const courseShowcaseTabs: CourseShowcaseTab[] = [
  {
    key: 'teaching-assets',
    label: '教学资产',
    eyebrow: 'AI TEACHING ASSETS',
    title: '把课程目标变成可授课、可测评、可复用的教学资产包',
    summary: '参考教育内容 Agent 的常见能力，把教案、PPT、课件、试题、讲义和复盘数据组织成教师可确认的资产生产链路，并接入我们的完整课程路径。',
    icon: GraduationCap,
    rail: ['目标', '教案', '课件', '题库', '课程'],
    nodes: [
      {
        id: 'goal',
        label: 'Start',
        title: '课程目标',
        subtitle: '学段、主题、时长',
        x: 530,
        y: 86,
        summary: '从教学目标、受众水平、授课时长和已有资料开始，让 Agent 明确要产出什么。',
        input: '课程主题、学员画像、教学目标、已有教材、企业案例和授课约束。',
        process: '把目标拆成知识点、能力点、课堂活动和测评要求。',
        effect: '后续教案、PPT、课件和试题围绕同一教学目标展开。',
      },
      {
        id: 'materials',
        label: 'Source',
        title: '资料入库',
        subtitle: '教材、案例、知识库',
        x: 530,
        y: 182,
        summary: '把教材、讲义、案例、行业资料和内部课程资料转成可检索的素材底座。',
        input: '文档、PPT、案例库、课堂记录、FAQ 和业务数据。',
        process: '提取知识点、例题、难点、案例、术语和可引用来源。',
        effect: '生成内容不再凭空编写，教师可以追溯每个资产的依据。',
      },
      {
        id: 'reference',
        label: 'Agent',
        title: '教育内容 Agent',
        subtitle: '教案 / 幻灯片 / 题库',
        x: 235,
        y: 282,
        branch: true,
        summary: '同类工具通常覆盖 lesson plan、presentation、quiz、worksheet 等资产生成能力。',
        input: '教学目标、课程标准、知识库材料和教师口径。',
        process: '生成教案结构、课堂活动、幻灯片大纲、讲稿和练习题。',
        effect: '教师准备时间被压缩，重点转向内容校准和课堂互动设计。',
      },
      {
        id: 'lesson',
        label: 'Plan',
        title: '教案编排',
        subtitle: '导入、讲授、练习',
        x: 530,
        y: 282,
        summary: '把课程目标转成可执行的课堂结构。',
        input: '知识点、学情、时间分配、教学活动和评价标准。',
        process: '生成导入、讲解、案例、练习、提问、总结和课后任务。',
        effect: '教师拿到的是可直接改稿的授课脚本，而不是零散提示词结果。',
      },
      {
        id: 'deck',
        label: 'PPT',
        title: 'PPT 与课件',
        subtitle: '页面结构、讲稿、互动',
        x: 530,
        y: 382,
        summary: '把教案转成幻灯片结构、讲稿备注、课堂互动和素材清单。',
        input: '教案、课程资料、图表需求、案例和品牌模板。',
        process: '生成页面标题、正文层级、图表建议、讲稿备注和互动问题。',
        effect: 'PPT、讲义和课件围绕同一节课同步更新。',
      },
      {
        id: 'quiz',
        label: 'Exam',
        title: '试题与测评',
        subtitle: '题库、答案、解析',
        x: 825,
        y: 382,
        branch: true,
        summary: '根据知识点和能力目标生成练习题、测验、答案和解析。',
        input: '教学目标、知识点、难度、题型、评分标准和错题反馈。',
        process: '生成选择题、简答题、案例题、答案解析和评价 rubrics。',
        effect: '课程产物能被测量，学员掌握情况可以进入复盘。',
      },
      {
        id: 'course',
        label: 'Course',
        title: '我们的课程路径',
        subtitle: 'Day 0 到毕业项目',
        x: 235,
        y: 502,
        branch: true,
        summary: '把现有课程卡片中的业务诊断、竞品洞察、选题、主内容、分发和复盘纳入资产链路。',
        input: '现有课程大纲、每节课 deliverable、练习任务和验收标准。',
        process: '为每节课生成配套 PPT、讲义、练习、检查表和测评题。',
        effect: '课程不只是展示页内容，而是能持续迭代的教学资产库。',
      },
      {
        id: 'review',
        label: 'Review',
        title: '教师确认',
        subtitle: '专业口径与风险边界',
        x: 530,
        y: 502,
        summary: '教师保留最终判断权，确认知识准确性、案例适配和表达边界。',
        input: '草稿资产、来源记录、风险提示、课程目标和课堂经验。',
        process: '人工调整重点、案例、难度、题目质量和课堂节奏。',
        effect: 'AI 承担初稿生产，教师承担质量和教学判断。',
      },
      {
        id: 'package',
        label: 'Output',
        title: '教学资产包',
        subtitle: 'PPT、课件、题库、讲义',
        x: 530,
        y: 622,
        summary: '形成可下载、可复用、可版本管理的完整授课资产。',
        input: '已确认的教案、PPT、课件、试题、讲义和课堂活动。',
        process: '按课程、课次、版本、适用对象和使用场景归档。',
        effect: '同一门课可以快速复用、改版和交付给不同教师团队。',
      },
    ],
    edges: [
      { id: 'goal-materials', from: 'goal', to: 'materials', path: 'M530 122 L530 150' },
      { id: 'materials-reference', from: 'materials', to: 'reference', path: 'M419 214 C376 214 335 230 287 258' },
      { id: 'materials-lesson', from: 'materials', to: 'lesson', path: 'M530 218 L530 250' },
      { id: 'lesson-deck', from: 'lesson', to: 'deck', path: 'M530 318 L530 350' },
      { id: 'deck-quiz', from: 'deck', to: 'quiz', path: 'M641 382 C690 356 738 356 777 382' },
      { id: 'deck-course', from: 'deck', to: 'course', path: 'M419 414 C350 430 315 462 287 478' },
      { id: 'deck-review', from: 'deck', to: 'review', path: 'M530 418 L530 470' },
      { id: 'course-review', from: 'course', to: 'review', path: 'M287 502 C356 526 440 526 478 502' },
      { id: 'quiz-review', from: 'quiz', to: 'review', path: 'M777 414 C704 470 624 494 582 502' },
      { id: 'review-package', from: 'review', to: 'package', path: 'M530 538 L530 590' },
    ],
  },
  {
    key: 'agents',
    label: '智能体',
    eyebrow: 'VERTICAL AGENTS',
    title: '从行业知识、工具权限和评估标准里做垂直智能体',
    summary: '垂直智能体不是通用聊天框，而是围绕行业数据、任务流程和工具权限搭建的可执行角色。这里展示教师智能体、自媒体智能体等行业智能体的制作链路。',
    icon: Bot,
    rail: ['需求', '知识', '工具', '评估', '发布'],
    nodes: [
      {
        id: 'need',
        label: 'Intent',
        title: '场景定义',
        subtitle: '教师 / 自媒体 / 行业岗位',
        x: 530,
        y: 86,
        summary: '先明确智能体服务的行业、角色、任务边界和交付结果。',
        input: '目标用户、典型任务、不能做什么、成功标准和人机协作方式。',
        process: '把需求拆成触发条件、输入字段、输出格式、权限和验收标准。',
        effect: '智能体从一开始就面向具体岗位，而不是泛泛回答问题。',
      },
      {
        id: 'knowledge',
        label: 'Memory',
        title: '行业知识库',
        subtitle: '标准、案例、SOP',
        x: 530,
        y: 190,
        summary: '把行业标准、课程资料、内容案例、产品文档和 SOP 变成智能体可检索记忆。',
        input: '教材、品牌资料、历史内容、客户问题、销售话术和行业规范。',
        process: '按任务类型抽取知识、约束、案例、术语和引用来源。',
        effect: '垂直智能体的回答和动作更贴近行业语境。',
      },
      {
        id: 'teacher',
        label: 'Teacher',
        title: '教师智能体',
        subtitle: '备课、答疑、测评',
        x: 235,
        y: 310,
        branch: true,
        summary: '教师智能体围绕备课、学情分析、答疑、作业反馈和测评设计工作。',
        input: '课程目标、课堂记录、题库、学生问题和教师偏好。',
        process: '生成教案、解释难点、补充例题、整理错题和形成个性化反馈。',
        effect: '教师把重复准备工作交给智能体，把精力放在教学判断上。',
      },
      {
        id: 'media',
        label: 'Media',
        title: '自媒体智能体',
        subtitle: '选题、脚本、分发',
        x: 825,
        y: 310,
        branch: true,
        summary: '自媒体智能体围绕选题、脚本、图文、评论和多平台分发工作。',
        input: '账号定位、素材库、热点、平台规则、历史表现和转化目标。',
        process: '生成选题矩阵、脚本、标题、封面方向、评论回复和分发计划。',
        effect: '内容生产从人工单点写作变成可复盘的持续工作流。',
      },
      {
        id: 'tools',
        label: 'Tools',
        title: '工具与权限',
        subtitle: '搜索、文件、发布、数据',
        x: 530,
        y: 310,
        summary: '智能体需要被授予明确工具，而不是无限制执行。',
        input: '搜索、知识库、文件生成、表格、发布接口、数据查询和审批能力。',
        process: '为不同任务配置可调用工具、权限范围、审批节点和失败兜底。',
        effect: '智能体能真正完成工作，同时保持边界和可审计性。',
      },
      {
        id: 'skills',
        label: 'Skills',
        title: '技能编排',
        subtitle: 'Prompt、流程、输出协议',
        x: 530,
        y: 426,
        summary: '把行业任务拆成稳定技能，并规定输入输出协议。',
        input: '任务模板、提示词、工具调用顺序、字段结构和验收清单。',
        process: '编排分析、生成、检查、改写、导出和回写等步骤。',
        effect: '智能体行为可复用，团队可以复制到相近行业场景。',
      },
      {
        id: 'eval',
        label: 'Eval',
        title: '评估与护栏',
        subtitle: '准确性、风控、人工确认',
        x: 530,
        y: 542,
        summary: '智能体上线前需要针对行业任务建立评估集和风险护栏。',
        input: '典型样例、错误样例、合规规则、人工确认点和用户反馈。',
        process: '评估事实准确、格式稳定、工具调用、风险表达和失败恢复。',
        effect: '智能体不是一次配置完成，而是持续被测试和改进。',
      },
      {
        id: 'publish',
        label: 'Deploy',
        title: '发布到工作台',
        subtitle: '角色、权限、日志',
        x: 530,
        y: 650,
        summary: '把确认后的智能体发布到工作台，让业务人员以角色方式使用。',
        input: '智能体配置、知识库、工具权限、使用说明和日志策略。',
        process: '按团队角色开放使用，记录输入、输出、工具调用和人工修订。',
        effect: '形成教师、自媒体、销售、客服等行业智能体的可运营体系。',
      },
    ],
    edges: [
      { id: 'need-knowledge', from: 'need', to: 'knowledge', path: 'M530 122 L530 158' },
      { id: 'knowledge-teacher', from: 'knowledge', to: 'teacher', path: 'M419 222 C360 232 315 258 287 286' },
      { id: 'knowledge-tools', from: 'knowledge', to: 'tools', path: 'M530 226 L530 278' },
      { id: 'knowledge-media', from: 'knowledge', to: 'media', path: 'M641 222 C700 232 746 258 777 286' },
      { id: 'teacher-skills', from: 'teacher', to: 'skills', path: 'M287 342 C360 398 440 418 478 426' },
      { id: 'media-skills', from: 'media', to: 'skills', path: 'M777 342 C704 398 624 418 582 426' },
      { id: 'tools-skills', from: 'tools', to: 'skills', path: 'M530 346 L530 394' },
      { id: 'skills-eval', from: 'skills', to: 'eval', path: 'M530 462 L530 510' },
      { id: 'eval-publish', from: 'eval', to: 'publish', path: 'M530 578 L530 618' },
    ],
  },
  {
    key: 'director-stage',
    label: '导演台',
    eyebrow: 'INTERACTIVE DIRECTOR STAGE',
    title: '用导演台把互动影游的空间、站位、镜头和分支调度讲清楚',
    summary: '参考 LibTV 导演台的轻量 3D 构图思路：先把空间、角色、道具、镜头和关键帧摆出来，再让 AI 生成分镜、视频和互动分支，解决角色站位和镜头连续性问题。',
    icon: Film,
    rail: ['剧本', '空间', '镜头', '分支', '生成'],
    nodes: [
      {
        id: 'script',
        label: 'Script',
        title: '互动剧本',
        subtitle: '剧情、角色、选择点',
        x: 530,
        y: 82,
        summary: '从互动影游剧本开始，明确角色、场景、冲突、选择点和结局分支。',
        input: '故事梗概、角色设定、场景、玩家选择、关键对白和情绪节奏。',
        process: '拆成场景节点、角色行动、镜头目的和可交互选择。',
        effect: '后续导演台不是单纯画面摆放，而是服务剧情和互动节奏。',
      },
      {
        id: 'assets',
        label: 'Assets',
        title: '角色与道具',
        subtitle: '素模、道具、群众阵列',
        x: 530,
        y: 186,
        summary: '建立角色、道具、空间元素和可复用资产清单。',
        input: '角色图、服装、道具、场景参考、基础几何和已有素材。',
        process: '给资产命名、分组、设定比例、可见性和复用关系。',
        effect: '多人、多道具、多场景的连续性有了可管理的资产底座。',
      },
      {
        id: 'space',
        label: '3D',
        title: '空间构图',
        subtitle: '位置、比例、遮挡',
        x: 530,
        y: 304,
        summary: '用轻量 3D 空间表达角色站位、道具关系、前后景和遮挡。',
        input: '场景平面、角色数量、相对距离、动作方向和空间限制。',
        process: '摆放人体素模、基础几何、道具和人群，校准比例和动线。',
        effect: '提示词里难描述的“谁站哪、往哪看、离多远”变成可视化约束。',
      },
      {
        id: 'camera',
        label: 'Camera',
        title: '镜头与机位',
        subtitle: '角度、景别、运镜',
        x: 825,
        y: 304,
        branch: true,
        summary: '为每个关键节点设计机位、景别、焦点和运镜方向。',
        input: '剧情意图、角色关系、情绪重点、镜头语言和互动提示。',
        process: '设定全景、中景、特写、过肩、俯仰角和镜头运动。',
        effect: '同一场戏的多镜头更容易保持空间关系和叙事连贯。',
      },
      {
        id: 'pose',
        label: 'Pose',
        title: '动作关键帧',
        subtitle: '姿势、走位、表演',
        x: 235,
        y: 304,
        branch: true,
        summary: '用关键帧定义角色姿势、走位、相互距离和动作起止点。',
        input: '角色意图、动作描述、情绪状态和玩家选择造成的变化。',
        process: '为重要瞬间摆出姿势、方向、接触关系和转场位置。',
        effect: '减少 AI 视频生成里角色突然换位、比例失真和动作不连续。',
      },
      {
        id: 'branch',
        label: 'Branch',
        title: '互动分支调度',
        subtitle: '选择、状态、后果',
        x: 530,
        y: 426,
        summary: '把玩家选择映射到空间、镜头和角色状态变化。',
        input: '选择项、状态变量、触发条件、分支后果和回收节点。',
        process: '为每个选择生成对应的镜头节点、角色站位和道具变化。',
        effect: '互动影游的分支不只是文本跳转，而是画面调度也能跟着变。',
      },
      {
        id: 'generate',
        label: 'Gen',
        title: '分镜与视频生成',
        subtitle: '提示词、分镜图、视频',
        x: 530,
        y: 542,
        summary: '把导演台的空间和镜头约束转成 AI 可执行的分镜与视频生成任务。',
        input: '场景节点、角色资产、镜头设定、动作关键帧和台词。',
        process: '生成分镜图、视频提示词、镜头素材和可回看预览。',
        effect: '从纯文字提示升级为“剧本 - 空间 - 镜头 - 生成”的工作流。',
      },
      {
        id: 'playtest',
        label: 'Test',
        title: '试玩复盘',
        subtitle: '节奏、选择、连续性',
        x: 530,
        y: 650,
        summary: '把生成结果放回互动影游进行试玩，检查叙事、节奏和画面一致性。',
        input: '视频片段、分支节点、玩家反馈、失败镜头和重生成记录。',
        process: '标记不连贯镜头、选择反馈不明确处和需要重调度的空间节点。',
        effect: '导演台成为互动影游持续迭代的中控层。',
      },
    ],
    edges: [
      { id: 'script-assets', from: 'script', to: 'assets', path: 'M530 118 L530 154' },
      { id: 'assets-space', from: 'assets', to: 'space', path: 'M530 222 L530 272' },
      { id: 'space-pose', from: 'space', to: 'pose', path: 'M419 304 C360 282 314 282 287 304' },
      { id: 'space-camera', from: 'space', to: 'camera', path: 'M641 304 C700 282 746 282 777 304' },
      { id: 'pose-branch', from: 'pose', to: 'branch', path: 'M287 336 C360 392 440 416 478 426' },
      { id: 'camera-branch', from: 'camera', to: 'branch', path: 'M777 336 C704 392 624 416 582 426' },
      { id: 'space-branch', from: 'space', to: 'branch', path: 'M530 340 L530 394' },
      { id: 'branch-generate', from: 'branch', to: 'generate', path: 'M530 462 L530 510' },
      { id: 'generate-playtest', from: 'generate', to: 'playtest', path: 'M530 578 L530 618' },
      { id: 'playtest-space', from: 'playtest', to: 'space', path: 'M478 650 C92 575 92 170 530 272' },
    ],
  },
]

const topicIconByKey: Record<string, LucideIcon> = {
  'pain-point-topics': MessageCircleWarning,
  'gap-opportunity-topics': Search,
  'crossover-topics': Puzzle,
  'counterintuitive-topics': Zap,
  'trend-topics': TrendingUp,
  'festival-topics': CalendarDays,
  'controversy-topics': Flame,
  'series-topics': Layers3,
  'seasonal-topics': Route,
}

const scriptIconByKey: Record<string, LucideIcon> = {
  'script-master-draft': ScrollText,
  'viral-template-adaptation': Flame,
  'warm-healing-script': MessageCircle,
  'professional-authority-script': Target,
  'lively-humor-script': Sparkles,
  'humanize-script': PenLine,
}

const topicPlanningItems = VISIBLE_CAPABILITY_ENTRIES
  .filter((entry) => entry.group === 'topic-planning')
  .map((entry) => ({
    label: entry.navLabel,
    path: entry.path,
    description: entry.description,
    icon: topicIconByKey[entry.key] ?? Lightbulb,
  }))

const scriptCreationItems = VISIBLE_CAPABILITY_ENTRIES
  .filter((entry) => entry.group === 'script-creation')
  .map((entry) => ({
    label: entry.navLabel,
    path: entry.path,
    description: entry.description,
    icon: scriptIconByKey[entry.key] ?? PenLine,
  }))

export const landingNavGroups: LandingNavGroup[] = [
  {
    label: CONTENT_GROWTH_TOOL.navLabel,
    path: CONTENT_GROWTH_TOOL.path,
    icon: BarChart3,
    items: [
      {
        label: '内容资产库',
        path: '/content-growth?stage=assets',
        description: '上传和沉淀对标素材、搜索入口、知识条目和内容资产。',
        icon: Database,
      },
      {
        label: '选题策略',
        path: '/content-growth?stage=strategy&strategyMode=standard',
        description: '基于内容资产生成可筛选、可下载、可复盘的选题策略表。',
        icon: Network,
      },
      {
        label: '稿件生产',
        path: '/content-growth?stage=production&writerMode=single',
        description: '选择策略种子，生产主稿、变体和后续内容包。',
        icon: FileText,
      },
      {
        label: '生成图文',
        path: '/content-growth?stage=social',
        description: '选择已完成稿件，生成小红书图文卡和图文正文。',
        icon: Layers3,
      },
    ],
  },
  {
    label: '工具',
    path: '/dashboard',
    icon: Wrench,
    items: [
      {
        label: AGENT_TOOL.navLabel,
        path: AGENT_TOOL.path,
        description: AGENT_TOOL.description,
        icon: Bot,
      },
      {
        label: INTERACTIVE_MOVIE_TOOL.navLabel,
        path: INTERACTIVE_MOVIE_TOOL.path,
        description: INTERACTIVE_MOVIE_TOOL.description,
        icon: Film,
      },
      {
        label: PERSONAL_AIWIKI_TOOL.navLabel,
        path: PERSONAL_AIWIKI_TOOL.path,
        description: PERSONAL_AIWIKI_TOOL.description,
        icon: NotebookText,
      },
      {
        label: GESTURE_CONTROL_TOOL.navLabel,
        path: GESTURE_CONTROL_TOOL.path,
        description: GESTURE_CONTROL_TOOL.description,
        icon: Hand,
      },
      {
        label: WECHAT_AUTOMATION_FLOW_TOOL.navLabel,
        path: WECHAT_AUTOMATION_FLOW_TOOL.path,
        description: WECHAT_AUTOMATION_FLOW_TOOL.description,
        icon: Route,
      },
      {
        label: WECOM_MOMENTS_PUBLISH_TOOL.navLabel,
        path: WECOM_MOMENTS_PUBLISH_TOOL.path,
        description: WECOM_MOMENTS_PUBLISH_TOOL.description,
        icon: Network,
      },
      {
        label: INFO_DISTRIBUTION_TOOL.navLabel,
        path: INFO_DISTRIBUTION_TOOL.path,
        description: INFO_DISTRIBUTION_TOOL.description,
        icon: Network,
        externalConfigKey: INFO_DISTRIBUTION_TOOL.externalConfigKey,
      },
    ],
  },
  {
    label: CAPABILITY_GROUP_META['topic-planning'].title,
    path: topicPlanningItems[0]?.path ?? '/dashboard',
    icon: Lightbulb,
    items: topicPlanningItems,
  },
  {
    label: CAPABILITY_GROUP_META['script-creation'].title,
    path: scriptCreationItems[0]?.path ?? '/dashboard',
    icon: PenTool,
    items: scriptCreationItems,
  },
]

export const audience = [
  'B2B / SaaS 企业',
  '消费品牌 / 新零售团队',
  '教育培训 / 知识服务机构',
  '本地生活 / 连锁服务企业',
  '制造业 / 供应链企业',
  '企业老板、市场、运营和销售负责人',
]

export const productionSteps = [
  {
    icon: UploadCloud,
    title: '对标内容入库',
    text: '把竞品账号、爆款内容、评论区问题和人工备注整理成可复用原始素材。',
  },
  {
    icon: Database,
    title: '知识库生成',
    text: '从素材中提取痛点、热点、解决方案、选题、搜索入口和知识库条目。',
  },
  {
    icon: Network,
    title: '选题矩阵生成',
    text: '生成 30 天选题矩阵，包含选题、痛点、方案、钩子、承接动作和发布提醒。',
  },
  {
    icon: FileText,
    title: '主内容生成',
    text: '围绕选题种子生成长文/主稿，保留来源矩阵、metadata 和内容产物路径。',
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
    text: '让内容导向咨询、留资、预约、试用、下单、私域沉淀和下一轮复盘。',
  },
  {
    icon: Archive,
    title: '内容资产沉淀',
    text: '把素材库、选题库、内容资产库和复盘表接回下一轮内容生产。',
  },
]

export const productionFlow = [
  ['从素材到选题', '对标内容、评论需求和业务目标进入知识库，生成可生产的选题种子。'],
  ['从选题到内容包', '一个种子生成主稿，再拆出标题、图文卡、短视频旁白和封面方向。'],
  ['从发布到转化', '按平台重写表达，设计评论、私信、到店、预约和购买承接动作。'],
  ['从复盘到资产库', '把表现数据、用户问题和新素材回写，下一轮继续复用。'],
]

export const deliverables = [
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
