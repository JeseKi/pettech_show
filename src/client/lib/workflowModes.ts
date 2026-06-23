import type { SeedMatrixCreatePayload } from './seedMatrix'

export type AiwikiModeId = 'materials' | 'search-assets' | 'full'
export type SeedMatrixModeId = 'standard' | 'batch' | 'high-frequency' | 'hook-driven'
export type DailyWriterModeId = 'single' | 'batch' | 'five-pack'
export type CapabilityGroupId = 'competitor-insights' | 'topic-planning' | 'script-creation'

export const AIWIKI_MODES: Record<AiwikiModeId, {
  key: string
  path: string
  navLabel: string
  title: string
  description: string
  buttonText: string
  generateSearchAssets: boolean
}> = {
  materials: {
    key: 'aiwiki-materials',
    path: '/aiwiki/materials',
    navLabel: '生文材料整理',
    title: '对标文章生文材料整理',
    description: '上传对标文章，整理热点、痛点、解决方案和选题素材，不额外生成搜索入口资产。',
    buttonText: '开始整理材料',
    generateSearchAssets: false,
  },
  'search-assets': {
    key: 'aiwiki-search-assets',
    path: '/aiwiki/search-assets',
    navLabel: '搜索入口生成',
    title: '搜索入口与关键词池生成',
    description: '围绕上传文章生成搜索入口、关键词池和可复用 Wiki 资产，适合做 SEO/搜索流量规划。',
    buttonText: '生成搜索入口',
    generateSearchAssets: true,
  },
  full: {
    key: 'aiwiki-full',
    path: '/aiwiki/full',
    navLabel: 'AI Wiki 完整资产',
    title: 'AI Wiki 完整资产生成',
    description: '一次性生成生文材料、关键词池、搜索入口、选题资产和可跳转 AI Wiki。',
    buttonText: '生成完整资产',
    generateSearchAssets: true,
  },
}

export const SEED_MATRIX_MODES: Record<SeedMatrixModeId, {
  key: string
  path: string
  navLabel: string
  title: string
  description: string
  buttonText: string
  defaults: Omit<SeedMatrixCreatePayload, 'source_aiwiki_job_id'>
  showHooks: boolean
}> = {
  standard: {
    key: 'seed-matrix-standard',
    path: '/seed-matrices/standard',
    navLabel: '标准选题矩阵',
    title: '标准选题矩阵',
    description: '从 AI Wiki 资产生成日常使用的选题矩阵，适合常规内容排期。',
    buttonText: '生成标准矩阵',
    defaults: { expected_seed_count: 10, slots_per_day: 3, hooks: [] },
    showHooks: false,
  },
  batch: {
    key: 'seed-matrix-batch',
    path: '/seed-matrices/batch',
    navLabel: '批量选题矩阵',
    title: '批量选题矩阵',
    description: '一次性拉高 seed 数量，适合为一批素材快速生成更多选题储备。',
    buttonText: '生成批量矩阵',
    defaults: { expected_seed_count: 50, slots_per_day: 5, hooks: [] },
    showHooks: false,
  },
  'high-frequency': {
    key: 'seed-matrix-high-frequency',
    path: '/seed-matrices/high-frequency',
    navLabel: '高频发布矩阵',
    title: '高频发布矩阵',
    description: '按更高每日发布槽位规划内容，适合密集发布节奏。',
    buttonText: '生成高频矩阵',
    defaults: { expected_seed_count: 30, slots_per_day: 8, hooks: [] },
    showHooks: false,
  },
  'hook-driven': {
    key: 'seed-matrix-hook-driven',
    path: '/seed-matrices/hook-driven',
    navLabel: 'Hook 强化矩阵',
    title: 'Hook 强化矩阵',
    description: '在矩阵生成时注入指定 hook 方向，适合围绕强开头或强转化角度批量规划。',
    buttonText: '生成 Hook 矩阵',
    defaults: { expected_seed_count: 20, slots_per_day: 3, hooks: [''] },
    showHooks: true,
  },
}

export const DAILY_WRITER_MODES: Record<DailyWriterModeId, {
  key: string
  path: string
  navLabel: string
  title: string
  description: string
  buttonText: string
  minTotal: number
  maxTotal: number
  defaultTotal: number
  fixedTotal?: number
}> = {
  single: {
    key: 'daily-writer-single',
    path: '/daily-writer/single',
    navLabel: '单篇长文生成',
    title: '单篇长文生成',
    description: '从选题矩阵中的一个 seed 生成一篇主稿长文。',
    buttonText: '生成单篇长文',
    minTotal: 1,
    maxTotal: 1,
    defaultTotal: 1,
    fixedTotal: 1,
  },
  batch: {
    key: 'daily-writer-batch',
    path: '/daily-writer/batch',
    navLabel: '批量长文生成',
    title: '批量长文生成',
    description: '选择生成文章总数，系统会输出 1 篇主稿和 N-1 篇结构不同的长文变体。',
    buttonText: '生成批量长文',
    minTotal: 2,
    maxTotal: 6,
    defaultTotal: 6,
  },
  'five-pack': {
    key: 'daily-writer-five-pack',
    path: '/daily-writer/five-pack',
    navLabel: '五篇长文套装',
    title: '五篇长文套装',
    description: '固定生成 5 篇文章：1 篇主稿和 4 篇变体，适合一次性准备多版本内容。',
    buttonText: '生成五篇套装',
    minTotal: 5,
    maxTotal: 5,
    defaultTotal: 5,
    fixedTotal: 5,
  },
}

export function dailyWriterModeLabel(params: Record<string, unknown>): string {
  if (!params.generate_variants) return DAILY_WRITER_MODES.single.navLabel
  return Number(params.variant_count ?? 0) === 4
    ? DAILY_WRITER_MODES['five-pack'].navLabel
    : DAILY_WRITER_MODES.batch.navLabel
}

export function seedMatrixModeLabel(params: Record<string, unknown>): string {
  const seedCount = Number(params.expected_seed_count ?? 0)
  const slots = Number(params.slots_per_day ?? 0)
  const hooks = Array.isArray(params.hooks) ? params.hooks : []
  if (hooks.length) return SEED_MATRIX_MODES['hook-driven'].navLabel
  if (seedCount >= 50) return SEED_MATRIX_MODES.batch.navLabel
  if (slots >= 8) return SEED_MATRIX_MODES['high-frequency'].navLabel
  return SEED_MATRIX_MODES.standard.navLabel
}

export type CapabilityInputConfig = {
  key: string
  label: string
  type: 'text' | 'textarea'
  required: boolean
  placeholder?: string
}

export type CapabilityEntryConfig = {
  key: string
  group: CapabilityGroupId
  path: string
  navLabel: string
  title: string
  description: string
  buttonText: string
  inputs: CapabilityInputConfig[]
  outputs: string[]
  steps: string[]
  example?: {
    title: string
    description: string
    values: Record<string, string>
  }
}

const profileInputs: CapabilityInputConfig[] = [
  { key: 'identity', label: '我的身份', type: 'text', required: true, placeholder: '例如：宠物医院 / 宠物店 / 宠物博主' },
  { key: 'direction', label: '想做方向', type: 'text', required: false, placeholder: '例如：科普 + 日常 / 本地引流 / 用品测评' },
  { key: 'brief', label: '一句话描述', type: 'textarea', required: false, placeholder: '补充你的账号现状、城市、资源或目标' },
]

export const CAPABILITY_GROUP_META: Record<CapabilityGroupId, { title: string; pathPrefix: string }> = {
  'competitor-insights': { title: '竞品洞察', pathPrefix: '/competitor-insights' },
  'topic-planning': { title: '选题策划', pathPrefix: '/topic-planning' },
  'script-creation': { title: '脚本创作', pathPrefix: '/script-creation' },
}

const topicPlanningExample = {
  title: '宠物医院本地获客选题示例',
  description: '适合快速体验选题策划入口，会围绕宠物医院、幼猫家长和评论区痛点生成选题池。',
  values: {
    competitor_json: JSON.stringify({
      account_positioning: '本地宠物医院账号，主打新手养宠科普、真实病例复盘和到店转化。',
      audience: ['第一次养猫的年轻人', '担心猫咪生病但不懂判断的家长', '本地有就诊需求的宠物主人'],
      high_frequency_demands: [
        '猫咪呕吐到底要不要去医院',
        '疫苗和驱虫时间总是记不清',
        '害怕被过度检查，想先知道判断标准',
      ],
      competitor_weaknesses: [
        '内容偏医学术语，新手看不懂',
        '缺少本地场景和到店前准备清单',
        '评论区问题很多，但没有整理成系列栏目',
      ],
      reusable_hooks: [
        '这 3 种情况别再观察了',
        '医生最怕你在家拖着不来',
        '花冤枉钱前先看这张判断表',
      ],
    }, null, 2),
    identity: '上海宠物医院，主做猫科问诊、疫苗驱虫和新手养猫科普',
    avoid: '低俗搞笑、制造恐慌、攻击同行、过度承诺疗效',
    advantages: '有真实病例素材、医生可出镜、能拍门诊场景、可以提供本地到店检查清单',
  },
}

const scriptCreationExample = {
  title: '猫咪呕吐科普短视频脚本示例',
  description: '适合快速体验脚本创作入口，会生成一条可拍摄、可口播、有镜头提示的内容脚本。',
  values: {
    topic_json: JSON.stringify({
      topic: '猫咪呕吐后，哪些情况必须马上去医院？',
      audience: '第一次养猫、容易焦虑但缺少判断标准的年轻家长',
      pain_point: '猫吐了不知道是毛球、吃太快，还是需要急诊，既怕耽误又怕白花钱。',
      core_message: '看频率、精神状态、呕吐物颜色和是否伴随腹泻，比单纯看吐没吐更重要。',
      hook: '猫吐一次不一定要慌，但出现这 4 个信号，别再等。',
      expected_duration: '60-90 秒',
      call_to_action: '收藏这张判断清单，需要时直接对照。',
    }, null, 2),
    asset_library: [
      '爆款结构：先反常识提醒 -> 给判断标准 -> 分场景处理 -> 总结清单。',
      '镜头参考：医生正面口播、猫咪日常空镜、白板列出 4 个危险信号。',
      '语气参考：专业但不吓人，像医生在给朋友解释。',
    ].join('\n'),
    user_viewpoint: '不要把所有呕吐都说得很严重，但要明确告诉用户哪些信号不能拖。',
  },
}

export const CAPABILITY_ENTRIES: CapabilityEntryConfig[] = [
  {
    key: 'competitor-link-diagnosis',
    group: 'competitor-insights',
    path: '/competitor-insights/link-diagnosis',
    navLabel: '竞品链接诊断',
    title: '竞品链接诊断',
    description: '输入 1-3 个竞品链接，拆解对方内容打法、账号定位和可借鉴模板。',
    buttonText: '开始诊断',
    inputs: [{ key: 'competitor_links', label: '竞品链接', type: 'textarea', required: true, placeholder: '每行一个链接' }, ...profileInputs],
    outputs: ['竞品内容拆解报告', '爆款结构模板', '可借鉴要素清单'],
    steps: ['读取竞品链接', '拆解内容形态与主题', '提炼可复用打法', '生成报告和结构化 JSON'],
  },
  {
    key: 'competitor-account-discovery',
    group: 'competitor-insights',
    path: '/competitor-insights/account-discovery',
    navLabel: '对标账号发现',
    title: '对标账号发现',
    description: '不知道对手是谁时，根据身份和方向推荐 3-5 个合适的对标账号。',
    buttonText: '发现对标账号',
    inputs: profileInputs,
    outputs: ['对标账号推荐清单', '推荐理由', '后续调研优先级'],
    steps: ['理解用户身份', '搜索赛道热门账号', '筛选对标账号', '生成推荐说明'],
  },
  {
    key: 'viral-content-breakdown',
    group: 'competitor-insights',
    path: '/competitor-insights/viral-breakdown',
    navLabel: '爆款内容拆解',
    title: '爆款内容拆解',
    description: '聚焦竞品爆款内容，拆开头、节奏、主题、视觉风格和互动设计。',
    buttonText: '拆解爆款',
    inputs: [{ key: 'materials', label: '竞品内容/链接', type: 'textarea', required: true, placeholder: '粘贴爆款链接、标题、文案或数据' }, ...profileInputs],
    outputs: ['爆款拆解卡', '结构模板', '内容规律总结'],
    steps: ['识别内容形态', '按形态选择拆解维度', '提炼爆款原因', '输出可复用模板'],
  },
  {
    key: 'comment-demand-insights',
    group: 'competitor-insights',
    path: '/competitor-insights/comment-demands',
    navLabel: '评论需求洞察',
    title: '评论需求洞察',
    description: '分析评论区高频问题、情绪和未满足需求，沉淀选题弹药。',
    buttonText: '分析评论需求',
    inputs: [{ key: 'comments', label: '评论区素材', type: 'textarea', required: true, placeholder: '粘贴评论、评论截图 OCR 文本或评论导出' }, ...profileInputs],
    outputs: ['粉丝真实需求 Top 5', '情绪画像', '评论区策略建议'],
    steps: ['整理评论文本', '聚类高频问题', '识别情绪与未满足需求', '生成洞察卡'],
  },
  {
    key: 'monetization-path-analysis',
    group: 'competitor-insights',
    path: '/competitor-insights/monetization',
    navLabel: '变现路径分析',
    title: '变现路径分析',
    description: '根据竞品内容痕迹推断广告、带货、知识付费或到店引流路径。',
    buttonText: '分析变现路径',
    inputs: [{ key: 'account_trace', label: '账号商业痕迹', type: 'textarea', required: true, placeholder: '粘贴商业内容、合作品牌、直播/商品信息' }, ...profileInputs],
    outputs: ['变现模式识别', '变现效率评估', '适配路径建议'],
    steps: ['识别商业内容', '估算变现频率', '判断适配度', '生成路径建议'],
  },
  {
    key: 'differentiation-map',
    group: 'competitor-insights',
    path: '/competitor-insights/differentiation-map',
    navLabel: '差异化机会地图',
    title: '差异化机会地图',
    description: '综合竞品弱点、评论需求和自身优势，找到定位方案和启动选题。',
    buttonText: '生成机会地图',
    inputs: [{ key: 'research_notes', label: '调研素材', type: 'textarea', required: true, placeholder: '粘贴竞品拆解、评论洞察或账号现状' }, ...profileInputs],
    outputs: ['差异化定位方案', '机会地图', '启动选题清单'],
    steps: ['归纳竞品空白点', '匹配自身优势', '设计定位方案', '输出行动建议'],
  },
  {
    key: 'competitor-research-report',
    group: 'competitor-insights',
    path: '/competitor-insights/research-report',
    navLabel: '竞品调研报告',
    title: '竞品调研报告',
    description: '把竞品拆解、评论洞察、变现分析和差异化机会汇总成完整报告。',
    buttonText: '生成调研报告',
    inputs: [{ key: 'research_material', label: '调研资料', type: 'textarea', required: true, placeholder: '粘贴全部调研材料或上游 JSON' }, ...profileInputs],
    outputs: ['Markdown 调研报告', '结构化 JSON', '下一步行动建议'],
    steps: ['整合调研材料', '生成一页纸摘要', '组织四维分析', '输出报告和 JSON'],
  },
]

const topicEntries = [
  ['pain-point-topics', '痛点选题池', '从评论区高频问题和未满足需求生成选题。', '生成痛点选题'],
  ['gap-opportunity-topics', '空白机会选题', '从竞品没做或做得浅的方向生成差异化选题。', '生成机会选题'],
  ['crossover-topics', '跨界灵感选题', '把宠物内容与生活方式、消费、教育等领域交叉生成新角度。', '生成跨界选题'],
  ['counterintuitive-topics', '反常识选题', '围绕颠覆认知的钩子生成高停留选题。', '生成反常识选题'],
  ['trend-topics', '热点追踪选题', '结合当日热点、行业新闻和平台话题生成时效选题。', '生成热点选题'],
  ['festival-topics', '节日节点选题', '围绕节日、节点和营销日历生成可排期选题。', '生成节日选题'],
  ['controversy-topics', '争议话题选题', '围绕争议观点生成可控、可讨论的内容选题。', '生成争议选题'],
  ['series-topics', '系列栏目选题', '设计连续栏目和分集结构，适合做长期账号资产。', '生成系列选题'],
  ['seasonal-topics', '季节场景选题', '围绕换季、温度、地域和生活场景生成选题。', '生成季节选题'],
] as const

CAPABILITY_ENTRIES.push(...topicEntries.map(([key, label, description, buttonText]) => ({
  key,
  group: 'topic-planning' as const,
  path: `/topic-planning/${key}`,
  navLabel: label,
  title: label,
  description,
  buttonText,
  inputs: [
    { key: 'competitor_json', label: '参考资料 JSON/摘要', type: 'textarea' as const, required: true, placeholder: '粘贴账号定位、用户痛点、评论需求或关键发现' },
    { key: 'identity', label: '我的身份', type: 'text' as const, required: true, placeholder: '例如：成都宠物医院' },
    { key: 'avoid', label: '不想做的内容', type: 'text' as const, required: false, placeholder: '例如：搞笑整活 / 高争议内容' },
    { key: 'advantages', label: '资源/优势', type: 'textarea' as const, required: false, placeholder: '例如：真实病例素材、门店场景、专业医生出镜' },
  ],
  outputs: ['选题池', '优先级评分', '结构化 JSON'],
  steps: ['读取参考资料', '按方法生成选题', '六维评分筛选', '去重合并并输出 JSON'],
  example: topicPlanningExample,
})))

const scriptEntries = [
  ['script-master-draft', '脚本母版生成', '把选题信息和受众画像生成一条完整可拍脚本。', '生成脚本母版'],
  ['viral-template-adaptation', '爆款模板套写', '读取爆款模板骨架，套写到当前选题和账号身份。', '套写爆款模板'],
  ['warm-healing-script', '温暖治愈脚本', '用朋友聊天式表达生成温暖、治愈、亲切的脚本。', '生成治愈脚本'],
  ['professional-authority-script', '专业权威脚本', '用医生/专家科普语气生成有理有据的脚本。', '生成权威脚本'],
  ['lively-humor-script', '活泼幽默脚本', '用轻松、有梗、节奏快的风格生成脚本。', '生成幽默脚本'],
  ['humanize-script', '去 AI 味改写', '检查并改写脚本，让语言更口语、更自然、更像真人。', '开始改写'],
] as const

CAPABILITY_ENTRIES.push(...scriptEntries.map(([key, label, description, buttonText]) => ({
  key,
  group: 'script-creation' as const,
  path: `/script-creation/${key}`,
  navLabel: label,
  title: label,
  description,
  buttonText,
  inputs: [
    { key: 'topic_json', label: '选题 JSON/内容简报', type: 'textarea' as const, required: true, placeholder: '粘贴选题、受众、核心信息和制作提示' },
    { key: 'asset_library', label: '模板资产/竞品拆解', type: 'textarea' as const, required: false, placeholder: '粘贴爆款模板、原脚本或拆解注释' },
    { key: 'user_viewpoint', label: '用户观点', type: 'textarea' as const, required: false, placeholder: '一句话补充你想表达的观点' },
  ],
  outputs: ['Markdown 脚本', '结构化 JSON', '制作提示'],
  steps: ['检索模板', '设计脚本骨架', '填充内容', '风格化改写', '输出 Markdown 和 JSON'],
  example: scriptCreationExample,
})))

export const VISIBLE_CAPABILITY_ENTRIES = CAPABILITY_ENTRIES.filter((entry) => entry.group !== 'competitor-insights')

export function capabilityEntryByPath(pathname: string): CapabilityEntryConfig | undefined {
  return VISIBLE_CAPABILITY_ENTRIES.find((entry) => entry.path === pathname)
}
