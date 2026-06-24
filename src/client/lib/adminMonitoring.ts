import api from './api'

export interface MonitoringRange {
  start_at: string
  end_at: string
  today_start_at: string
  last_7_days_start_at: string
  timezone: string
}

export interface MetricCard {
  key: string
  title: string
  value: number
  total: number | null
  range_value: number | null
  today_value: number | null
  last_7_days_value: number | null
  unit: string
  description: string | null
  extra: Record<string, unknown>
}

export interface TrendPoint {
  date: string
  metric: string
  value: number
}

export interface BreakdownItem {
  key: string
  label: string
  value: number
}

export interface MonitoringModule {
  key: string
  title: string
  description: string | null
  cards: MetricCard[]
  trends: TrendPoint[]
  breakdowns: Record<string, BreakdownItem[]>
  rows: Array<Record<string, unknown>>
}

export interface MonitoringOverview {
  range: MonitoringRange
  cards: MetricCard[]
  modules: MonitoringModule[]
  trends: TrendPoint[]
}

export interface MonitoringDetail extends MonitoringModule {
  range: MonitoringRange
}

export interface MonitoringQuery {
  startAt?: string
  endAt?: string
  tz?: string
}

const endpointByModule: Record<string, string> = {
  aiwiki: '/admin/monitoring/aiwiki',
  'seed-matrix': '/admin/monitoring/seed-matrix',
  'daily-writer': '/admin/monitoring/daily-writer',
  scripts: '/admin/monitoring/scripts',
  capabilities: '/admin/monitoring/capabilities',
  'agent-skills': '/admin/monitoring/agent-skills',
  'interactive-movie': '/admin/monitoring/interactive-movie',
  users: '/admin/monitoring/users',
  chat: '/admin/monitoring/chat',
}

function buildParams(query: MonitoringQuery = {}) {
  return {
    start_at: query.startAt,
    end_at: query.endAt,
    tz: query.tz ?? 'Asia/Shanghai',
  }
}

export async function getMonitoringOverview(query: MonitoringQuery = {}): Promise<MonitoringOverview> {
  const { data } = await api.get<MonitoringOverview>('/admin/monitoring/overview', {
    params: buildParams(query),
  })
  return data
}

export async function getMonitoringDetail(moduleKey: string, query: MonitoringQuery = {}): Promise<MonitoringDetail> {
  const endpoint = endpointByModule[moduleKey]
  if (!endpoint) {
    throw new Error(`Unknown monitoring module: ${moduleKey}`)
  }
  const { data } = await api.get<MonitoringDetail>(endpoint, {
    params: buildParams(query),
  })
  return data
}
