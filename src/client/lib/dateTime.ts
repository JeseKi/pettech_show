const BACKEND_DATETIME_WITHOUT_TZ = /^\d{4}-\d{2}-\d{2}[ T]\d{2}/
const TIMEZONE_SUFFIX = /(?:[zZ]|[+-]\d{2}:?\d{2})$/

export const APP_DISPLAY_TIME_ZONE = 'Asia/Shanghai'

export function parseBackendDateTime(value: string): Date | null {
  const trimmed = value.trim()
  if (!trimmed) return null

  const normalized = BACKEND_DATETIME_WITHOUT_TZ.test(trimmed) && !TIMEZONE_SUFFIX.test(trimmed)
    ? `${trimmed.replace(' ', 'T')}Z`
    : trimmed
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatDateTime(value?: string | null): string {
  if (!value) return '-'
  const date = parseBackendDateTime(value)
  if (!date) return value

  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: APP_DISPLAY_TIME_ZONE,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

