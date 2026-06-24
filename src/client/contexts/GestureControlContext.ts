import { createContext } from 'react'
import type { GestureMouseCursor, GestureMouseMode } from '../components/gesture/useGestureMouse'

export type GestureControlState = 'off' | 'loading' | 'ready' | 'tracking' | 'error'

export interface GestureControlContextValue {
  cursor: GestureMouseCursor
  debugMessage: string
  enabled: boolean
  hidePanel: () => void
  loading: boolean
  message: string
  mode: GestureMouseMode
  mouseMessage: string
  panelAvailable: boolean
  panelVisible: boolean
  showPanel: () => void
  start: () => Promise<void>
  state: GestureControlState
  statusMessage: string
  stop: () => void
  toggle: () => Promise<void>
}

const GestureControlContext = createContext<GestureControlContextValue | undefined>(undefined)

export { GestureControlContext }
