import { useContext } from 'react'
import { GestureControlContext } from '../contexts/GestureControlContext'

export function useGestureControl() {
  const context = useContext(GestureControlContext)
  if (!context) {
    throw new Error('useGestureControl 必须在 GestureControlProvider 内使用')
  }
  return context
}
