import type { ReactNode } from 'react'
import type { AiwikiJob, AiwikiJobSummary } from '../../lib/aiwiki'
import { formatDateTime as formatBackendDateTime } from '../../lib/dateTime'

export const ACCEPTED_TYPES = '.md,.markdown,.txt,.xlsx,.pdf'
export const ACTIVE_STATUSES = new Set(['queued', 'running'])

export function textOf(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

export function titleOf(item: Record<string, unknown>): string {
  return textOf(item.title) || textOf(item['关键词']) || textOf(item['标题']) || ''
}

export function descriptionOf(item: Record<string, unknown>): string {
  return textOf(item.description) || textOf(item['搜索意图']) || textOf(item['说明']) || textOf(item['适合文章角度']) || ''
}

export function priorityColor(priority: unknown): string {
  if (priority === '高') return 'red'
  if (priority === '中') return 'gold'
  if (priority === '低') return 'default'
  return 'blue'
}

export function entryTypeLabel(type: string): string {
  return {
    hotspot: '热点',
    pain_point: '痛点',
    solution: '解决方案',
    topic: '选题',
    search_intent: '搜索入口',
    article: '文章',
    entity: '实体',
    concept: '概念',
    comparison: '对比',
    query: '问答',
    note: '笔记',
    index: '索引',
  }[type] ?? type
}

export function statusMeta(status?: string) {
  if (status === 'queued') return { label: '排队中', percent: 15, status: 'active' as const }
  if (status === 'running') return { label: '生成中', percent: 55, status: 'active' as const }
  if (status === 'completed') return { label: '已完成', percent: 100, status: 'success' as const }
  if (status === 'partial_failed') return { label: '部分成功', percent: 100, status: 'exception' as const }
  if (status === 'failed' || status === 'failure') return { label: '失败', percent: 100, status: 'exception' as const }
  return { label: '未选择', percent: 0, status: 'normal' as const }
}

export function formatDateTime(value?: string | null): string {
  return formatBackendDateTime(value)
}

export function firstFileName(job: AiwikiJobSummary | AiwikiJob): string {
  return job.files[0]?.filename ?? job.id
}

export function progressEventColor(event: string): string {
  if (event === 'completed' || event === '完成') return 'green'
  if (event === 'failed' || event === '失败') return 'red'
  if (event === 'started' || event === '开始') return 'blue'
  return 'default'
}

export function highlight(text: string, terms: string[] | string | null): ReactNode {
  const normalizedTerms = Array.isArray(terms) ? terms : terms ? [terms] : []
  const activeTerms = normalizedTerms
    .filter((term) => term && text.includes(term))
    .sort((left, right) => right.length - left.length)
  if (!activeTerms.length) return text

  const pattern = new RegExp(`(${activeTerms.map(escapeRegExp).join('|')})`, 'g')
  return text.split(pattern).map((part, index) => (
    activeTerms.includes(part)
      ? <mark key={`${part}-${index}`}>{part}</mark>
      : <span key={`${part}-${index}`}>{part}</span>
  ))
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
