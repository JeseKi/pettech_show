import {
  type CSSProperties,
  type PointerEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { FilesetResolver, GestureRecognizer } from '@mediapipe/tasks-vision'
import { EyeOff, Hand, Move, VideoOff } from 'lucide-react'
import { GestureControlContext, type GestureControlState } from '../../contexts/GestureControlContext'
import { type GestureSwipeDirection, useGestureMouse } from './useGestureMouse'
import {
  GESTURE_INTERACTION_END_EVENT,
  GESTURE_INTERACTION_START_EVENT,
  GLOBAL_GESTURE_SWIPE_EVENT,
  type GlobalGestureSwipeDetail,
} from './events'
import './gesture-control.css'

type GestureCursorStyle = CSSProperties & Record<'--gesture-cursor-x' | '--gesture-cursor-y', string>
type GestureDebugWindow = Window & {
  __PETTECH_GESTURE_DEBUG__?: Record<string, unknown>
}

const GESTURE_MODEL_PATH = 'https://storage.googleapis.com/mediapipe-tasks/gesture_recognizer/gesture_recognizer.task'
const GESTURE_WASM_PATH = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm'
const GESTURE_FRAME_INTERVAL_MS = 1000 / 24
const GESTURE_DEBUG_LOGS = true
const GESTURE_DEBUG_LOG_INTERVAL_MS = 800
const GESTURE_MIN_CONFIDENCE = 0.35

const logGestureDebug = (message: string, payload?: unknown) => {
  if (!GESTURE_DEBUG_LOGS) return
  ;(window as GestureDebugWindow).__PETTECH_GESTURE_DEBUG__ = {
    ...((window as GestureDebugWindow).__PETTECH_GESTURE_DEBUG__ ?? {}),
    control: {
      message,
      payload,
      timestamp: new Date().toISOString(),
    },
  }
  if (payload === undefined) {
    console.log(`[GestureControl] ${message}`)
    return
  }
  console.log(`[GestureControl] ${message}`, payload)
}

const getGestureErrorMessage = (error: unknown) => {
  if (!(error instanceof DOMException)) return '无法启用摄像头'
  if (error.name === 'NotAllowedError') return '摄像头权限被拒绝'
  if (error.name === 'NotFoundError') return '未找到摄像头'
  if (error.name === 'NotReadableError') return '摄像头被占用'
  return '无法启用摄像头'
}

export function GestureControlProvider({ children }: { children: ReactNode }) {
  const [viewportSize, setViewportSize] = useState({ width: 1280, height: 720 })
  const [gestureState, setGestureState] = useState<GestureControlState>('off')
  const [gestureMessage, setGestureMessage] = useState('手势未开启')
  const [gestureDebugMessage, setGestureDebugMessage] = useState('debug: idle')
  const [panelAvailable, setPanelAvailable] = useState(false)
  const [panelVisible, setPanelVisible] = useState(true)
  const [panelPosition, setPanelPosition] = useState({ x: 14, y: 92 })
  const gestureStateRef = useRef<GestureControlState>('off')
  const gestureMessageRef = useRef('手势未开启')
  const gestureDebugMessageRef = useRef('debug: idle')
  const gestureEnabledRef = useRef(false)
  const gestureFrameRef = useRef(0)
  const gestureIsProcessingRef = useRef(false)
  const gestureLastFrameTimeRef = useRef(0)
  const gestureLastDebugLogRef = useRef(0)
  const gestureRecognizerRef = useRef<GestureRecognizer | null>(null)
  const panelEverOpenedRef = useRef(false)
  const panelDragRef = useRef({ active: false, offsetX: 0, offsetY: 0 })
  const panelRef = useRef<HTMLElement | null>(null)
  const previewVideoRef = useRef<HTMLVideoElement | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)

  const gestureEnabled = gestureState === 'loading' || gestureState === 'ready' || gestureState === 'tracking'
  const shouldUseMouseMessage = gestureState === 'ready' || gestureState === 'tracking'
  const gestureButtonLabel = gestureState === 'loading' ? '启动中' : gestureEnabled ? '关闭手势' : '开启手势'

  const setGestureFeedback = useCallback((nextState: GestureControlState, nextMessage: string) => {
    if (gestureStateRef.current !== nextState) {
      gestureStateRef.current = nextState
      setGestureState(nextState)
    }
    if (gestureMessageRef.current !== nextMessage) {
      gestureMessageRef.current = nextMessage
      setGestureMessage(nextMessage)
    }
  }, [])

  const setGestureDebugLine = useCallback((nextMessage: string) => {
    if (gestureDebugMessageRef.current === nextMessage) return
    gestureDebugMessageRef.current = nextMessage
    setGestureDebugMessage(nextMessage)
  }, [])

  const clampPanelPosition = useCallback((nextPosition: { x: number; y: number }) => {
    const panelRect = panelRef.current?.getBoundingClientRect()
    const panelWidth = panelRect?.width ?? 236
    const panelHeight = panelRect?.height ?? 176
    const padding = 8
    const maxX = Math.max(padding, window.innerWidth - panelWidth - padding)
    const maxY = Math.max(padding, window.innerHeight - panelHeight - padding)

    return {
      x: Math.min(Math.max(nextPosition.x, padding), maxX),
      y: Math.min(Math.max(nextPosition.y, padding), maxY),
    }
  }, [])

  const syncPreviewVideoStream = useCallback(() => {
    const previewElement = previewVideoRef.current
    if (!previewElement) return
    const stream = videoRef.current?.srcObject
    if (stream instanceof MediaStream) {
      previewElement.srcObject = stream
      void previewElement.play().catch(() => undefined)
      return
    }
    previewElement.srcObject = null
  }, [])

  const handlePanelPointerDown = useCallback((event: PointerEvent<HTMLElement>) => {
    const rect = panelRef.current?.getBoundingClientRect()
    if (!rect) return
    panelDragRef.current = {
      active: true,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
  }, [])

  const handlePanelPointerMove = useCallback((event: PointerEvent<HTMLElement>) => {
    if (!panelDragRef.current.active) return
    setPanelPosition(clampPanelPosition({
      x: event.clientX - panelDragRef.current.offsetX,
      y: event.clientY - panelDragRef.current.offsetY,
    }))
  }, [clampPanelPosition])

  const handlePanelPointerUp = useCallback((event: PointerEvent<HTMLElement>) => {
    panelDragRef.current.active = false
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }, [])

  const handleGestureInteractionStart = useCallback(() => {
    window.dispatchEvent(new CustomEvent(GESTURE_INTERACTION_START_EVENT))
  }, [])

  const handleGestureInteractionEnd = useCallback(() => {
    window.dispatchEvent(new CustomEvent(GESTURE_INTERACTION_END_EVENT))
  }, [])

  const handleGestureSwipeMove = useCallback((direction: GestureSwipeDirection, deltaX: number, deltaY: number) => {
    if (direction === 'left' || direction === 'right') {
      window.dispatchEvent(new CustomEvent<GlobalGestureSwipeDetail>(GLOBAL_GESTURE_SWIPE_EVENT, {
        detail: { deltaX, deltaY, direction },
      }))
      return
    }

    window.scrollBy({ top: deltaY, left: 0, behavior: 'auto' })
  }, [])

  const {
    cursor: gestureCursor,
    message: gestureMouseMessage,
    mode: gestureMouseMode,
    processGestureResult,
    resetGestureMouse,
  } = useGestureMouse({
    enabled: gestureEnabled,
    onInteractionEnd: handleGestureInteractionEnd,
    onInteractionStart: handleGestureInteractionStart,
    onSwipeMove: handleGestureSwipeMove,
    viewportSize,
  })

  const stopGestureCameraStream = useCallback(() => {
    const stream = videoRef.current?.srcObject
    if (stream instanceof MediaStream) {
      stream.getTracks().forEach((track) => track.stop())
    }
    if (videoRef.current) videoRef.current.srcObject = null
    if (previewVideoRef.current) previewVideoRef.current.srcObject = null
  }, [])

  const stopGestureControl = useCallback((resumeState = true) => {
    logGestureDebug('stop', { resumeState })
    gestureEnabledRef.current = false
    gestureIsProcessingRef.current = false
    gestureLastFrameTimeRef.current = 0
    if (gestureFrameRef.current) {
      window.cancelAnimationFrame(gestureFrameRef.current)
      gestureFrameRef.current = 0
    }
    gestureRecognizerRef.current?.close()
    gestureRecognizerRef.current = null
    stopGestureCameraStream()
    resetGestureMouse(true)
    if (resumeState) {
      setGestureFeedback('off', '手势未开启')
      setGestureDebugLine('debug: idle')
    }
  }, [resetGestureMouse, setGestureDebugLine, setGestureFeedback, stopGestureCameraStream])

  const runGestureFrame = useCallback((timestamp: number) => {
    if (!gestureEnabledRef.current) return

    gestureFrameRef.current = window.requestAnimationFrame(runGestureFrame)
    if (timestamp - gestureLastFrameTimeRef.current < GESTURE_FRAME_INTERVAL_MS) return
    if (gestureIsProcessingRef.current) return

    const videoElement = videoRef.current
    const gestureRecognizer = gestureRecognizerRef.current
    if (!videoElement || !gestureRecognizer || videoElement.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return

    gestureIsProcessingRef.current = true
    gestureLastFrameTimeRef.current = timestamp
    try {
      const results = gestureRecognizer.recognizeForVideo(videoElement, timestamp)
      if (timestamp - gestureLastDebugLogRef.current >= GESTURE_DEBUG_LOG_INTERVAL_MS) {
        gestureLastDebugLogRef.current = timestamp
        const rawGestures = results.gestures.map((gestureGroup) => gestureGroup[0]
          ? `${gestureGroup[0].categoryName}:${gestureGroup[0].score.toFixed(2)}`
          : 'None')
        const handednessGroups = results.handedness ?? results.handednesses ?? []
        const rawHandedness = handednessGroups.map((handednessGroup) => handednessGroup[0]
          ? `${handednessGroup[0].categoryName}:${handednessGroup[0].score.toFixed(2)}`
          : 'Unknown')
        setGestureDebugLine(
          `debug: hands=${results.landmarks.length} gestures=${rawGestures.join(',') || 'None'} video=${videoElement.videoWidth}x${videoElement.videoHeight}`,
        )
        logGestureDebug('raw recognition', {
          gestures: rawGestures,
          handCount: results.landmarks.length,
          handedness: rawHandedness,
          video: {
            height: videoElement.videoHeight,
            readyState: videoElement.readyState,
            width: videoElement.videoWidth,
          },
        })
      }
      processGestureResult(results, timestamp)
      if (gestureStateRef.current === 'ready') setGestureFeedback('tracking', '手势识别中')
    } catch (error) {
      console.error('[GestureControl] recognition failed', error)
      stopGestureControl(false)
      setGestureFeedback('error', '手势识别异常')
      setGestureDebugLine('debug: recognition failed')
    } finally {
      gestureIsProcessingRef.current = false
    }
  }, [
    processGestureResult,
    setGestureDebugLine,
    setGestureFeedback,
    stopGestureControl,
  ])

  const startGestureControl = useCallback(async () => {
    if (gestureStateRef.current === 'loading' || gestureEnabledRef.current) return
    if (!navigator.mediaDevices?.getUserMedia) {
      setGestureFeedback('error', '当前浏览器不支持摄像头')
      return
    }

    setPanelAvailable(true)
    if (!panelEverOpenedRef.current) {
      panelEverOpenedRef.current = true
      setPanelVisible(true)
    }
    setGestureFeedback('loading', '摄像头启动中')
    setGestureDebugLine('debug: loading model')
    logGestureDebug('start requested', {
      modelPath: GESTURE_MODEL_PATH,
      wasmPath: GESTURE_WASM_PATH,
    })

    try {
      const videoElement = videoRef.current
      if (!videoElement) throw new Error('Gesture video element is unavailable')

      const vision = await FilesetResolver.forVisionTasks(GESTURE_WASM_PATH)
      logGestureDebug('wasm runtime loaded')
      setGestureDebugLine('debug: wasm loaded')
      const gestureRecognizer = await GestureRecognizer.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath: GESTURE_MODEL_PATH,
        },
        cannedGesturesClassifierOptions: {
          scoreThreshold: GESTURE_MIN_CONFIDENCE,
        },
        minHandDetectionConfidence: GESTURE_MIN_CONFIDENCE,
        minHandPresenceConfidence: GESTURE_MIN_CONFIDENCE,
        minTrackingConfidence: GESTURE_MIN_CONFIDENCE,
        numHands: 2,
        runningMode: 'VIDEO',
      })
      logGestureDebug('gesture recognizer loaded')
      setGestureDebugLine('debug: recognizer loaded')

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: 'user',
          frameRate: { ideal: 24, max: 24 },
          height: { ideal: 480 },
          width: { ideal: 640 },
        },
      })
      logGestureDebug('camera stream granted', stream.getVideoTracks().map((track) => ({
        label: track.label,
        settings: track.getSettings(),
      })))
      setGestureDebugLine('debug: camera granted')

      videoElement.srcObject = stream
      if (previewVideoRef.current) {
        previewVideoRef.current.srcObject = stream
        void previewVideoRef.current.play().catch(() => undefined)
      }
      await videoElement.play()
      logGestureDebug('video playing', {
        height: videoElement.videoHeight,
        readyState: videoElement.readyState,
        width: videoElement.videoWidth,
      })
      gestureRecognizerRef.current = gestureRecognizer
      gestureEnabledRef.current = true
      gestureLastFrameTimeRef.current = 0
      gestureLastDebugLogRef.current = 0
      gestureFrameRef.current = window.requestAnimationFrame(runGestureFrame)
      setGestureFeedback('ready', '等待手势')
      setGestureDebugLine(`debug: video=${videoElement.videoWidth}x${videoElement.videoHeight}`)
    } catch (error) {
      console.error('[GestureControl] start failed', error)
      stopGestureCameraStream()
      resetGestureMouse(true)
      gestureEnabledRef.current = false
      gestureRecognizerRef.current?.close()
      gestureRecognizerRef.current = null
      setGestureFeedback('error', getGestureErrorMessage(error))
      setGestureDebugLine('debug: start failed')
    }
  }, [
    resetGestureMouse,
    runGestureFrame,
    setGestureDebugLine,
    setGestureFeedback,
    stopGestureCameraStream,
  ])

  const stopGestureControlFromUi = useCallback(() => {
    stopGestureControl()
  }, [stopGestureControl])

  const showGesturePanel = useCallback(() => {
    setPanelAvailable(true)
    setPanelVisible(true)
    setPanelPosition((current) => clampPanelPosition(current))
  }, [clampPanelPosition])

  const hideGesturePanel = useCallback(() => {
    setPanelVisible(false)
  }, [])

  const toggleGestureControl = useCallback(async () => {
    if (gestureStateRef.current === 'loading') return
    if (gestureEnabledRef.current || gestureStateRef.current === 'ready' || gestureStateRef.current === 'tracking') {
      stopGestureControl()
      return
    }
    await startGestureControl()
  }, [startGestureControl, stopGestureControl])

  useEffect(() => {
    const updateViewportSize = () => {
      setViewportSize({ width: window.innerWidth, height: window.innerHeight })
    }

    updateViewportSize()
    window.addEventListener('resize', updateViewportSize)
    return () => window.removeEventListener('resize', updateViewportSize)
  }, [])

  useEffect(() => () => stopGestureControl(false), [stopGestureControl])

  useEffect(() => {
    const stopWhenHidden = () => {
      if (document.hidden && gestureEnabledRef.current) stopGestureControl()
    }

    document.addEventListener('visibilitychange', stopWhenHidden)
    return () => document.removeEventListener('visibilitychange', stopWhenHidden)
  }, [stopGestureControl])

  useEffect(() => {
    if (!panelAvailable || !panelVisible) return
    syncPreviewVideoStream()
  }, [gestureState, panelAvailable, panelVisible, syncPreviewVideoStream])

  const gestureStatusMessage = shouldUseMouseMessage ? gestureMouseMessage : gestureMessage
  const gestureCursorStyle: GestureCursorStyle = {
    '--gesture-cursor-x': `${gestureCursor.x}px`,
    '--gesture-cursor-y': `${gestureCursor.y}px`,
  }
  const gestureCursorClassName = [
    'gesture-control-cursor',
    gestureCursor.visible ? 'is-visible' : '',
    `is-${gestureMouseMode}`,
  ].filter(Boolean).join(' ')
  const shouldShowGesturePanel = panelAvailable && panelVisible

  const contextValue = useMemo(() => ({
    cursor: gestureCursor,
    debugMessage: gestureDebugMessage,
    enabled: gestureEnabled,
    hidePanel: hideGesturePanel,
    loading: gestureState === 'loading',
    message: gestureMessage,
    mode: gestureMouseMode,
    mouseMessage: gestureMouseMessage,
    panelAvailable,
    panelVisible,
    showPanel: showGesturePanel,
    start: startGestureControl,
    state: gestureState,
    statusMessage: gestureStatusMessage,
    stop: stopGestureControlFromUi,
    toggle: toggleGestureControl,
  }), [
    gestureCursor,
    gestureDebugMessage,
    gestureEnabled,
    gestureMessage,
    gestureMouseMessage,
    gestureMouseMode,
    gestureState,
    gestureStatusMessage,
    hideGesturePanel,
    panelAvailable,
    panelVisible,
    showGesturePanel,
    startGestureControl,
    stopGestureControlFromUi,
    toggleGestureControl,
  ])

  return (
    <GestureControlContext.Provider value={contextValue}>
      {children}
      {shouldShowGesturePanel && (
        <aside
          aria-label="全局手势控制侧栏"
          className={[
            'gesture-control-panel',
            gestureCursor.visible ? 'is-tracking' : '',
            panelDragRef.current.active ? 'is-dragging' : '',
          ].filter(Boolean).join(' ')}
          ref={panelRef}
          style={{ transform: `translate3d(${panelPosition.x}px, ${panelPosition.y}px, 0)` }}
        >
          <div
            className="gesture-control-panel__handle"
            onPointerCancel={handlePanelPointerUp}
            onPointerDown={handlePanelPointerDown}
            onPointerMove={handlePanelPointerMove}
            onPointerUp={handlePanelPointerUp}
          >
            <span>
              <Move size={14} />
              全局手势
            </span>
            <button
              aria-label="隐藏全局手势侧栏"
              className="gesture-control-panel__icon-button"
              onClick={hideGesturePanel}
              onPointerDown={(event) => event.stopPropagation()}
              title="隐藏面板"
              type="button"
            >
              <EyeOff size={15} />
            </button>
          </div>
          <div className="gesture-control-panel__body">
            <button
              aria-pressed={gestureEnabled}
              className="gesture-control-panel__toggle"
              disabled={gestureState === 'loading'}
              onClick={() => void toggleGestureControl()}
              type="button"
            >
              {gestureEnabled ? <VideoOff size={17} /> : <Hand size={17} />}
              <span>{gestureButtonLabel}</span>
            </button>
            <div className="gesture-control-panel__status">
              <strong aria-live="polite">{gestureStatusMessage}</strong>
              <small>{gestureDebugMessage}</small>
            </div>
            <video
              aria-label="手势识别摄像头画面"
              className="gesture-control-panel__video"
              muted
              playsInline
              ref={previewVideoRef}
            />
          </div>
        </aside>
      )}
      <video
        aria-hidden="true"
        className="gesture-control__video-source"
        muted
        playsInline
        ref={videoRef}
      />
      <div
        aria-hidden="true"
        className={gestureCursorClassName}
        style={gestureCursorStyle}
      />
    </GestureControlContext.Provider>
  )
}
