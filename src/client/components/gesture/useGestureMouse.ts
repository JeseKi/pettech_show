import { useCallback, useEffect, useRef, useState } from 'react'
import type { Category, GestureRecognizerResult, NormalizedLandmark } from '@mediapipe/tasks-vision'
import { clamp } from '../../pages/landing/LandingPage/utils'

export type GestureMouseMode = 'waiting' | 'tracking' | 'hover' | 'pinching' | 'clicking' | 'grabbing' | 'swiping'
export type GestureSwipeDirection = 'left' | 'right' | 'up' | 'down'

export type GestureMouseCursor = {
  x: number
  y: number
  visible: boolean
}

type GestureMouseSnapshot = {
  cursor: GestureMouseCursor
  message: string
  mode: GestureMouseMode
  swipeDirection: GestureSwipeDirection | null
}

type GestureMouseOptions = {
  enabled: boolean
  onInteractionEnd: () => void
  onInteractionStart: () => void
  onSwipeMove: (direction: GestureSwipeDirection, deltaX: number, deltaY: number) => void
  viewportSize: {
    width: number
    height: number
  }
}

type Point = {
  x: number
  y: number
}

type PinchStart = {
  hasClicked: boolean
  point: Point
  target: HTMLElement | null
  timestamp: number
}

type TrackedHand = {
  classifierFistScore: number
  fistScore: number
  gesture: Category | undefined
  landmarks: NormalizedLandmark[]
  landmarkFistScore: number
}

type GestureDebugWindow = Window & {
  __PETTECH_GESTURE_DEBUG__?: Record<string, unknown>
}

const CLICKABLE_SELECTOR = [
  'button',
  'a[href]',
  '[role="button"]',
  '[tabindex]:not([tabindex="-1"])',
  'input',
  'select',
  'textarea',
  'summary',
  '[contenteditable="true"]',
].join(',')

const CLOSED_FIST_GESTURE = 'Closed_Fist'
const CLOSED_FIST_SCORE_THRESHOLD = 0.55
const LANDMARK_FIST_SCORE_THRESHOLD = 0.85
const CLOSED_FIST_ENTER_FRAMES = 3
const CLOSED_FIST_EXIT_FRAMES = 2
const CURSOR_SMOOTHING = 0.28
const PINCH_ENTER_THRESHOLD = 0.42
const PINCH_EXIT_THRESHOLD = 0.62
const PINCH_EXTENDED_FINGER_THRESHOLD = 0.72
const PINCH_REQUIRED_EXTENDED_FINGERS = 3
const CLICK_MIN_MS = 90
const CLICK_MAX_MS = 900
const CLICK_MAX_MOVE_PX = 42
const SWIPE_AXIS_RATIO = 1.3
const SCROLL_MULTIPLIER = 1.6
const ORBIT_SWIPE_SENSITIVITY = 0.14
const GESTURE_MOUSE_DEBUG_LOGS = true
const GESTURE_MOUSE_DEBUG_INTERVAL_MS = 800

const INITIAL_CURSOR: GestureMouseCursor = {
  visible: false,
  x: 0,
  y: 0,
}

const logGestureMouseDebug = (message: string, payload?: unknown) => {
  if (!GESTURE_MOUSE_DEBUG_LOGS) return
  ;(window as GestureDebugWindow).__PETTECH_GESTURE_DEBUG__ = {
    ...((window as GestureDebugWindow).__PETTECH_GESTURE_DEBUG__ ?? {}),
    mouse: {
      message,
      payload,
      timestamp: new Date().toISOString(),
    },
  }
  if (payload === undefined) {
    console.log(`[GestureMouse] ${message}`)
    return
  }
  console.log(`[GestureMouse] ${message}`, payload)
}

const getDistance = (start: Point, end: Point) => {
  const deltaX = start.x - end.x
  const deltaY = start.y - end.y
  return Math.sqrt(deltaX * deltaX + deltaY * deltaY)
}

const getViewportPoint = (landmark: NormalizedLandmark, viewportSize: GestureMouseOptions['viewportSize']): Point => ({
  x: clamp((1 - landmark.x) * viewportSize.width, 0, viewportSize.width),
  y: clamp(landmark.y * viewportSize.height, 0, viewportSize.height),
})

const getPalmAnchor = (landmarks: NormalizedLandmark[], viewportSize: GestureMouseOptions['viewportSize']): Point => {
  const palmIndexes = [0, 5, 9, 13, 17]
  const palm = palmIndexes.reduce<Point>((total, index) => {
    const point = getViewportPoint(landmarks[index], viewportSize)
    return { x: total.x + point.x, y: total.y + point.y }
  }, { x: 0, y: 0 })

  return {
    x: palm.x / palmIndexes.length,
    y: palm.y / palmIndexes.length,
  }
}

const getPinchRatio = (landmarks: NormalizedLandmark[]) => {
  const thumbTip = landmarks[4]
  const indexTip = landmarks[8]
  const wrist = landmarks[0]
  const middleMcp = landmarks[9]
  if (!thumbTip || !indexTip || !wrist || !middleMcp) return Number.POSITIVE_INFINITY

  const pinchDistance = getDistance(thumbTip, indexTip)
  const palmScale = getDistance(wrist, middleMcp)
  if (palmScale <= 0.001) return Number.POSITIVE_INFINITY
  return pinchDistance / palmScale
}

const getFingerExtensionScore = (landmarks: NormalizedLandmark[], mcpIndex: number, pipIndex: number, tipIndex: number) => {
  const wrist = landmarks[0]
  const mcp = landmarks[mcpIndex]
  const pip = landmarks[pipIndex]
  const tip = landmarks[tipIndex]
  if (!wrist || !mcp || !pip || !tip) return 0

  const tipToWrist = getDistance(tip, wrist)
  const pipToWrist = getDistance(pip, wrist)
  const mcpToWrist = getDistance(mcp, wrist)
  let score = 0
  if (tipToWrist > pipToWrist * 1.06) score += 0.55
  if (tipToWrist > mcpToWrist * 1.48) score += 0.45
  return score
}

const getExtendedFingerCountForPinch = (landmarks: NormalizedLandmark[]) => {
  const extensionScores = [
    getFingerExtensionScore(landmarks, 9, 10, 12),
    getFingerExtensionScore(landmarks, 13, 14, 16),
    getFingerExtensionScore(landmarks, 17, 18, 20),
  ]
  return extensionScores.filter((score) => score >= PINCH_EXTENDED_FINGER_THRESHOLD).length
}

const isIntentionalPinch = (landmarks: NormalizedLandmark[], pinchRatio: number, threshold: number) => (
  pinchRatio < threshold &&
  getExtendedFingerCountForPinch(landmarks) >= PINCH_REQUIRED_EXTENDED_FINGERS
)

const getLandmarkFistScore = (landmarks: NormalizedLandmark[]) => {
  const wrist = landmarks[0]
  if (!wrist) return 0

  const fingers = [
    { mcp: 5, pip: 6, tip: 8 },
    { mcp: 9, pip: 10, tip: 12 },
    { mcp: 13, pip: 14, tip: 16 },
    { mcp: 17, pip: 18, tip: 20 },
  ]
  const foldedCount = fingers.reduce((count, finger) => {
    const mcp = landmarks[finger.mcp]
    const pip = landmarks[finger.pip]
    const tip = landmarks[finger.tip]
    if (!mcp || !pip || !tip) return count

    const tipToWrist = getDistance(tip, wrist)
    const pipToWrist = getDistance(pip, wrist)
    const mcpToWrist = getDistance(mcp, wrist)
    const isFolded = tipToWrist < pipToWrist * 1.06 || tipToWrist < mcpToWrist * 1.45
    return isFolded ? count + 1 : count
  }, 0)

  return foldedCount / fingers.length
}

const getInteractiveTarget = (x: number, y: number) => {
  const target = document.elementFromPoint(x, y)
  if (!(target instanceof Element)) return null
  const interactiveTarget = target.closest(CLICKABLE_SELECTOR)
  if (!(interactiveTarget instanceof HTMLElement)) return null
  if (interactiveTarget.hasAttribute('disabled') || interactiveTarget.getAttribute('aria-disabled') === 'true') return null
  return interactiveTarget
}

const getPrimaryGesture = (gestures: Category[] | undefined) => gestures?.[0]

const selectTrackedHand = (result: GestureRecognizerResult): TrackedHand | null => {
  if (result.landmarks.length === 0) return null

  let selectedIndex = 0
  let selectedScore = -1
  result.landmarks.forEach((_, index) => {
    const handednessScore = result.handedness[index]?.[0]?.score ?? result.handednesses[index]?.[0]?.score ?? 0
    const gestureScore = getPrimaryGesture(result.gestures[index])?.score ?? 0
    const score = Math.max(handednessScore, gestureScore)
    if (score > selectedScore) {
      selectedIndex = index
      selectedScore = score
    }
  })

  const gesture = getPrimaryGesture(result.gestures[selectedIndex])
  const classifierFistScore = gesture?.categoryName === CLOSED_FIST_GESTURE ? gesture.score : 0
  const landmarkFistScore = getLandmarkFistScore(result.landmarks[selectedIndex])
  return {
    classifierFistScore,
    fistScore: Math.max(classifierFistScore, landmarkFistScore),
    gesture,
    landmarks: result.landmarks[selectedIndex],
    landmarkFistScore,
  }
}

const getSwipeThreshold = (viewportWidth: number) => Math.max(56, Math.min(viewportWidth * 0.08, 120))

const getLockedSwipeDirection = (start: Point, current: Point, viewportWidth: number): GestureSwipeDirection | null => {
  const deltaX = current.x - start.x
  const deltaY = current.y - start.y
  const absX = Math.abs(deltaX)
  const absY = Math.abs(deltaY)
  const threshold = getSwipeThreshold(viewportWidth)

  if (absX >= threshold && absX >= absY * SWIPE_AXIS_RATIO) return deltaX < 0 ? 'left' : 'right'
  if (absY >= threshold && absY >= absX * SWIPE_AXIS_RATIO) return deltaY < 0 ? 'up' : 'down'
  return null
}

const getModeMessage = (mode: GestureMouseMode, swipeDirection: GestureSwipeDirection | null) => {
  if (mode === 'swiping' && swipeDirection) {
    const labels: Record<GestureSwipeDirection, string> = {
      down: '下滑',
      left: '左滑',
      right: '右滑',
      up: '上滑',
    }
    return labels[swipeDirection]
  }

  const labels: Record<GestureMouseMode, string> = {
    clicking: '点击',
    grabbing: '抓握',
    hover: '指向',
    pinching: '捏合',
    swiping: '滑动',
    tracking: '指向',
    waiting: '等待手势',
  }
  return labels[mode]
}

export function useGestureMouse({
  enabled,
  onInteractionEnd,
  onInteractionStart,
  onSwipeMove,
  viewportSize,
}: GestureMouseOptions) {
  const [snapshot, setSnapshot] = useState<GestureMouseSnapshot>({
    cursor: INITIAL_CURSOR,
    message: '等待手势',
    mode: 'waiting',
    swipeDirection: null,
  })
  const cursorRef = useRef<GestureMouseCursor>(INITIAL_CURSOR)
  const enabledRef = useRef(enabled)
  const hoverTargetRef = useRef<HTMLElement | null>(null)
  const hasHandRef = useRef(false)
  const fistFramesRef = useRef(0)
  const fistMissFramesRef = useRef(0)
  const isGrabbingRef = useRef(false)
  const isPinchingRef = useRef(false)
  const pinchStartRef = useRef<PinchStart | null>(null)
  const grabStartRef = useRef<Point | null>(null)
  const lastSwipePointRef = useRef<Point | null>(null)
  const lockedSwipeDirectionRef = useRef<GestureSwipeDirection | null>(null)
  const lastDebugLogRef = useRef(0)

  const clearHoverTarget = useCallback(() => {
    hoverTargetRef.current?.classList.remove('is-gesture-hovered')
    hoverTargetRef.current = null
  }, [])

  const setHoverTarget = useCallback((target: HTMLElement | null) => {
    if (target === hoverTargetRef.current) return
    clearHoverTarget()
    hoverTargetRef.current = target
    hoverTargetRef.current?.classList.add('is-gesture-hovered')
  }, [clearHoverTarget])

  const resetInteraction = useCallback((hideCursor = false) => {
    fistFramesRef.current = 0
    fistMissFramesRef.current = 0
    isGrabbingRef.current = false
    isPinchingRef.current = false
    pinchStartRef.current = null
    grabStartRef.current = null
    lastSwipePointRef.current = null
    lockedSwipeDirectionRef.current = null
    hasHandRef.current = false
    clearHoverTarget()
    if (hideCursor) cursorRef.current = { ...cursorRef.current, visible: false }
    setSnapshot({
      cursor: hideCursor ? cursorRef.current : { ...cursorRef.current, visible: false },
      message: '等待手势',
      mode: 'waiting',
      swipeDirection: null,
    })
  }, [clearHoverTarget])

  const clickGestureTarget = useCallback((target: HTMLElement | null) => {
    if (!target) return
    target.focus({ preventScroll: true })
    target.click()
  }, [])

  const processGestureResult = useCallback((result: GestureRecognizerResult, timestamp: number) => {
    if (!enabledRef.current) return

    const trackedHand = selectTrackedHand(result)
    if (!trackedHand) {
      if (timestamp - lastDebugLogRef.current >= GESTURE_MOUSE_DEBUG_INTERVAL_MS) {
        lastDebugLogRef.current = timestamp
        logGestureMouseDebug('no hand', {
          handCount: result.landmarks.length,
          mode: 'waiting',
        })
      }
      if (hasHandRef.current) onInteractionEnd()
      resetInteraction(false)
      return
    }

    if (!hasHandRef.current) onInteractionStart()
    hasHandRef.current = true

    const isClosedFist = (
      trackedHand.classifierFistScore >= CLOSED_FIST_SCORE_THRESHOLD ||
      trackedHand.landmarkFistScore >= LANDMARK_FIST_SCORE_THRESHOLD
    )
    fistFramesRef.current = isClosedFist ? fistFramesRef.current + 1 : 0
    fistMissFramesRef.current = isClosedFist ? 0 : fistMissFramesRef.current + 1

    const shouldStartGrab = !isGrabbingRef.current && fistFramesRef.current >= CLOSED_FIST_ENTER_FRAMES
    const shouldStopGrab = isGrabbingRef.current && fistMissFramesRef.current >= CLOSED_FIST_EXIT_FRAMES
    const anchorPoint = isGrabbingRef.current || shouldStartGrab
      ? getPalmAnchor(trackedHand.landmarks, viewportSize)
      : getViewportPoint(trackedHand.landmarks[8], viewportSize)

    const previousCursor = cursorRef.current.visible ? cursorRef.current : { ...anchorPoint, visible: true }
    const cursor = {
      visible: true,
      x: previousCursor.x + (anchorPoint.x - previousCursor.x) * CURSOR_SMOOTHING,
      y: previousCursor.y + (anchorPoint.y - previousCursor.y) * CURSOR_SMOOTHING,
    }
    cursorRef.current = cursor

    let mode: GestureMouseMode = 'tracking'
    let swipeDirection = lockedSwipeDirectionRef.current

    if (shouldStartGrab) {
      isGrabbingRef.current = true
      isPinchingRef.current = false
      pinchStartRef.current = null
      grabStartRef.current = cursor
      lastSwipePointRef.current = cursor
      lockedSwipeDirectionRef.current = null
      swipeDirection = null
    } else if (shouldStopGrab) {
      isGrabbingRef.current = false
      grabStartRef.current = null
      lastSwipePointRef.current = null
      lockedSwipeDirectionRef.current = null
      swipeDirection = null
      onInteractionEnd()
    }

    if (isGrabbingRef.current) {
      const grabStart = grabStartRef.current ?? cursor
      const lastSwipePoint = lastSwipePointRef.current ?? cursor
      swipeDirection = lockedSwipeDirectionRef.current ?? getLockedSwipeDirection(grabStart, cursor, viewportSize.width)
      lockedSwipeDirectionRef.current = swipeDirection

      if (swipeDirection) {
        const deltaX = (cursor.x - lastSwipePoint.x) * ORBIT_SWIPE_SENSITIVITY
        const deltaY = (cursor.y - lastSwipePoint.y) * SCROLL_MULTIPLIER
        onSwipeMove(swipeDirection, deltaX, deltaY)
        mode = 'swiping'
      } else {
        mode = 'grabbing'
      }
      lastSwipePointRef.current = cursor
      clearHoverTarget()
      if (timestamp - lastDebugLogRef.current >= GESTURE_MOUSE_DEBUG_INTERVAL_MS) {
        lastDebugLogRef.current = timestamp
        logGestureMouseDebug('state', {
          cursor: {
            x: Math.round(cursor.x),
            y: Math.round(cursor.y),
          },
          fistFrames: fistFramesRef.current,
          classifierFistScore: Number(trackedHand.classifierFistScore.toFixed(3)),
          fistScore: Number(trackedHand.fistScore.toFixed(3)),
          gesture: trackedHand.gesture
            ? `${trackedHand.gesture.categoryName}:${trackedHand.gesture.score.toFixed(2)}`
            : 'None',
          handCount: result.landmarks.length,
          landmarkFistScore: Number(trackedHand.landmarkFistScore.toFixed(3)),
          mode,
          swipeDirection,
        })
      }
    } else {
      const pinchRatio = getPinchRatio(trackedHand.landmarks)
      const extendedFingerCount = getExtendedFingerCountForPinch(trackedHand.landmarks)
      const pinchDetected = isPinchingRef.current
        ? isIntentionalPinch(trackedHand.landmarks, pinchRatio, PINCH_EXIT_THRESHOLD)
        : isIntentionalPinch(trackedHand.landmarks, pinchRatio, PINCH_ENTER_THRESHOLD)
      const currentTarget = getInteractiveTarget(cursor.x, cursor.y)

      if (pinchDetected && !isPinchingRef.current) {
        isPinchingRef.current = true
        pinchStartRef.current = {
          hasClicked: false,
          point: cursor,
          target: currentTarget,
          timestamp,
        }
      }

      if (pinchDetected && isPinchingRef.current) {
        const pinchStart = pinchStartRef.current
        const clickDuration = pinchStart ? timestamp - pinchStart.timestamp : 0
        const clickMove = pinchStart ? getDistance(pinchStart.point, cursor) : Number.POSITIVE_INFINITY
        if (
          pinchStart &&
          !pinchStart.hasClicked &&
          pinchStart.target &&
          clickDuration >= CLICK_MIN_MS &&
          clickDuration <= CLICK_MAX_MS &&
          clickMove <= CLICK_MAX_MOVE_PX
        ) {
          clickGestureTarget(pinchStart.target)
          pinchStart.hasClicked = true
          mode = 'clicking'
          logGestureMouseDebug('click', {
            duration: Math.round(clickDuration),
            move: Math.round(clickMove),
            target: pinchStart.target
              ? `${pinchStart.target.tagName.toLowerCase()}${pinchStart.target.id ? `#${pinchStart.target.id}` : ''}${pinchStart.target.className ? `.${String(pinchStart.target.className).trim().replace(/\s+/g, '.')}` : ''}`
              : 'None',
          })
        }
      } else if (!pinchDetected && isPinchingRef.current) {
        const pinchStart = pinchStartRef.current
        const clickDuration = pinchStart ? timestamp - pinchStart.timestamp : 0
        const clickMove = pinchStart ? getDistance(pinchStart.point, cursor) : Number.POSITIVE_INFINITY
        isPinchingRef.current = false
        pinchStartRef.current = null

        if (
          pinchStart &&
          !pinchStart.hasClicked &&
          clickDuration >= CLICK_MIN_MS &&
          clickDuration <= CLICK_MAX_MS &&
          clickMove <= CLICK_MAX_MOVE_PX
        ) {
          clickGestureTarget(pinchStart.target ?? currentTarget)
          mode = 'clicking'
        }
      }

      if (mode !== 'clicking') {
        mode = isPinchingRef.current ? 'pinching' : currentTarget ? 'hover' : 'tracking'
      }
      setHoverTarget(mode === 'hover' || mode === 'pinching' ? (pinchStartRef.current?.target ?? currentTarget) : null)

      if (timestamp - lastDebugLogRef.current >= GESTURE_MOUSE_DEBUG_INTERVAL_MS) {
        lastDebugLogRef.current = timestamp
        logGestureMouseDebug('state', {
          cursor: {
            x: Math.round(cursor.x),
            y: Math.round(cursor.y),
          },
          fistFrames: fistFramesRef.current,
          classifierFistScore: Number(trackedHand.classifierFistScore.toFixed(3)),
          fistScore: Number(trackedHand.fistScore.toFixed(3)),
          gesture: trackedHand.gesture
            ? `${trackedHand.gesture.categoryName}:${trackedHand.gesture.score.toFixed(2)}`
            : 'None',
          handCount: result.landmarks.length,
          landmarkFistScore: Number(trackedHand.landmarkFistScore.toFixed(3)),
          mode,
          pinchExtendedFingers: extendedFingerCount,
          pinchRatio: Number(pinchRatio.toFixed(3)),
          swipeDirection,
        })
      }
    }

    setSnapshot({
      cursor,
      message: getModeMessage(mode, swipeDirection),
      mode,
      swipeDirection,
    })
  }, [
    clearHoverTarget,
    clickGestureTarget,
    onInteractionEnd,
    onInteractionStart,
    onSwipeMove,
    resetInteraction,
    setHoverTarget,
    viewportSize,
  ])

  useEffect(() => {
    enabledRef.current = enabled
  }, [enabled])

  useEffect(() => {
    if (enabled) return
    resetInteraction(true)
  }, [enabled, resetInteraction])

  useEffect(() => () => clearHoverTarget(), [clearHoverTarget])

  return {
    ...snapshot,
    processGestureResult,
    resetGestureMouse: resetInteraction,
  }
}
