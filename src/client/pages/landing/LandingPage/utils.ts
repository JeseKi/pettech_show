import { PROGRESSIVE_BLOCK_IDS, type ProgressiveBlockId, type RevealStyle } from './types'

export const revealItemStyle = (index: number): RevealStyle => ({
  '--reveal-delay': `${index * 48}ms`,
})

export const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

export const lerp = (from: number, to: number, amount: number) => from + (to - from) * amount

export const smoothstep = (edge0: number, edge1: number, value: number) => {
  const t = clamp((value - edge0) / (edge1 - edge0), 0, 1)
  return t * t * (3 - 2 * t)
}

export const normalizeAngle = (value: number) => ((value % 360) + 360) % 360

export const getSignedAngleDistance = (angle: number, target = 0) => (
  ((angle - target + 540) % 360) - 180
)

export const isProgressiveBlockId = (id: string | null): id is ProgressiveBlockId => (
  id !== null && PROGRESSIVE_BLOCK_IDS.includes(id as ProgressiveBlockId)
)
