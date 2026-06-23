import type { CSSProperties } from 'react'

export type Course = {
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

export const PROGRESSIVE_BLOCK_IDS = ['course-intro', 'production', 'deliverables', 'contact', 'footer'] as const
export const INTRO_UNLOCK_DELAY_MS = 1900

export type ProgressiveBlockId = (typeof PROGRESSIVE_BLOCK_IDS)[number]
export type RevealStyle = CSSProperties & Record<'--reveal-delay', string>

export type CourseOrbitItem = Course & {
  copyIndex: number
  courseIndex: number
  orbitIndex: number
}

export type CourseOrbitPointerState = {
  isDragging: boolean
  hasDragged: boolean
  lastX: number
  lastTime: number
  velocity: number
}

export type ViewportSize = {
  width: number
  height: number
}

export type CourseCardStyle = CSSProperties & Record<
  | '--course-accent'
  | '--orbit-x'
  | '--orbit-y'
  | '--orbit-z'
  | '--orbit-scale'
  | '--orbit-opacity'
  | '--orbit-brightness'
  | '--orbit-rotate-y'
  | '--orbit-tilt'
  | '--orbit-pointer',
  string
>

export type CourseFocusCardStyle = CSSProperties & Record<
  | '--course-accent'
  | '--focus-x'
  | '--focus-y'
  | '--focus-z'
  | '--focus-scale'
  | '--focus-opacity'
  | '--focus-brightness'
  | '--focus-rotate-y'
  | '--focus-rotate-z',
  string
>
