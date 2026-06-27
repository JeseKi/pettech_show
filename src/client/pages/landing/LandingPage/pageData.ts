import {
  Archive,
  BarChart3,
  Bot,
  CalendarDays,
  Database,
  FileText,
  Film,
  Flame,
  Hand,
  Layers3,
  Lightbulb,
  MessageCircle,
  MessageCircleWarning,
  Network,
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
  INTERACTIVE_MOVIE_TOOL,
  WECHAT_AUTOMATION_FLOW_TOOL,
  WECOM_MOMENTS_PUBLISH_TOOL,
  VISIBLE_CAPABILITY_ENTRIES,
} from '../../../lib/workflowModes'

type LandingNavMenuItem = {
  label: string
  path: string
  description: string
  icon: LucideIcon
}

export type LandingNavGroup = {
  label: string
  path: string
  icon: LucideIcon
  items: LandingNavMenuItem[]
}

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
        label: INTERACTIVE_MOVIE_TOOL.navLabel,
        path: INTERACTIVE_MOVIE_TOOL.path,
        description: INTERACTIVE_MOVIE_TOOL.description,
        icon: Film,
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
  '宠物医院 / 诊所',
  '宠物门店 / 美容洗护 / 寄养',
  '宠物训练师',
  '宠物食品 / 用品品牌',
  '宠物博主 / 达人',
  '宠物供应链企业的老板、运营、市场负责人',
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
    text: '让内容导向咨询、到店、预约、下单、私域沉淀和下一轮复盘。',
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
