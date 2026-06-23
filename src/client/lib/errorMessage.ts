import { resolveApiErrorMessage } from './error'

export function resolveErrorMessage(error: unknown): string {
  return resolveApiErrorMessage(error, '请求失败，请稍后再试。')
}
