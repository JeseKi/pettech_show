import type { GestureSwipeDirection } from './useGestureMouse'

export type GlobalGestureSwipeDetail = {
  deltaX: number
  deltaY: number
  direction: GestureSwipeDirection
}

export const GLOBAL_GESTURE_SWIPE_EVENT = 'pettech:gesture-swipe'
export const GESTURE_INTERACTION_START_EVENT = 'pettech:gesture-interaction-start'
export const GESTURE_INTERACTION_END_EVENT = 'pettech:gesture-interaction-end'
