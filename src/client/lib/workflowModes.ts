import type { SeedMatrixCreatePayload } from './seedMatrix'

export type AiwikiModeId = 'materials' | 'search-assets' | 'full'
export type SeedMatrixModeId = 'standard' | 'batch' | 'high-frequency' | 'hook-driven'
export type DailyWriterModeId = 'single' | 'batch' | 'five-pack'

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
