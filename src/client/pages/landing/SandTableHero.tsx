import { Camera } from '@mediapipe/camera_utils'
import { drawConnectors, drawLandmarks } from '@mediapipe/drawing_utils'
import { HAND_CONNECTIONS, Hands, type Results } from '@mediapipe/hands'
import { useCallback, useEffect, useRef, useState } from 'react'
import * as THREE from 'three'

type GestureMode = 'loading' | 'drag' | 'aim' | 'idle-safe' | 'demo'

type NodeMetric = {
  id: string
  name: string
  input: string
  output: string
  day: string
  useCase: string
  status: string
  color: string
  position: THREE.Vector3
}

type SceneControls = {
  panByNormalized: (deltaX: number, deltaY: number) => void
  aimAtNormalized: (x: number, y: number) => void
  aimAtClientPoint: (x: number, y: number) => void
  clearAim: () => void
}

const modeText: Record<GestureMode, string> = {
  loading: '空间沙盘初始化中',
  drag: '拖动查看内容增长链路',
  aim: '指向查看课程交付物',
  'idle-safe': '内容沙盘保持稳定',
  demo: '鼠标/触控演示模式',
}

const nodeTemplates = [
  {
    name: '对标内容入库',
    input: '竞品账号 / 爆款内容',
    output: '原始素材库',
    day: 'Day 2',
    useCase: '沉淀可复用素材',
  },
  {
    name: '知识库生成',
    input: '运营素材 / 评论问题',
    output: '痛点 / 方案 / 搜索入口',
    day: 'Day 2',
    useCase: '生成结构化 Wiki',
  },
  {
    name: '选题矩阵生成',
    input: '结构化素材 / 资产库',
    output: '30 天选题矩阵',
    day: 'Day 3',
    useCase: '规划可生产选题',
  },
  {
    name: '主内容生成',
    input: '优先选题 seed',
    output: '长文 / 主稿',
    day: 'Day 4',
    useCase: '写完整内容母稿',
  },
  {
    name: '内容变体改写',
    input: '主内容 / 账号定位',
    output: '短视频旁白 / 图文结构',
    day: 'Day 4',
    useCase: '适配不同表达角度',
  },
  {
    name: '标题与封面方向',
    input: '主稿 / 平台目标',
    output: '标题池 / 封面方案',
    day: 'Day 5',
    useCase: '提升点击和收藏',
  },
  {
    name: '图文卡与短视频化',
    input: '内容包 / 图文卡',
    output: '轮播 / 短视频方案',
    day: 'Day 5-6',
    useCase: '一题多发',
  },
  {
    name: '多平台分发',
    input: '内容变体 / 发布节奏',
    output: '多平台分发计划',
    day: 'Day 6',
    useCase: '适配推荐流和搜索流',
  },
  {
    name: '转化路径设计',
    input: '业务目标 / 内容入口',
    output: '咨询 / 到店 / 私域承接',
    day: 'Day 7',
    useCase: '把内容接到成交动作',
  },
  {
    name: '内容资产沉淀',
    input: '素材 / 数据 / 复盘',
    output: '内容资产库',
    day: 'Day 7',
    useCase: '支持下一轮生产',
  },
]

function createSeededRandom(seed = 20260623) {
  let value = seed
  return () => {
    value = (value * 16807) % 2147483647
    return (value - 1) / 2147483646
  }
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function isInteractivePointerTarget(target: EventTarget | null) {
  return target instanceof Element && Boolean(target.closest('button, a, input, textarea, select, .sandtable__preview'))
}

function distance2D(a: { x: number; y: number }, b: { x: number; y: number }) {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

function isFingerOpen(
  hand: Results['multiHandLandmarks'][number],
  tipIndex: number,
  pipIndex: number,
  tolerance = 0.014,
) {
  return hand[tipIndex].y < hand[pipIndex].y - tolerance
}

export default function SandTableHero() {
  const mountRef = useRef<HTMLDivElement | null>(null)
  const crosshairRef = useRef<HTMLDivElement | null>(null)
  const panelRef = useRef<HTMLDivElement | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const previewCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const controlsRef = useRef<SceneControls | null>(null)
  const lastHandPanRef = useRef<{ x: number; y: number } | null>(null)
  const cameraRef = useRef<Camera | null>(null)
  const handsRef = useRef<Hands | null>(null)
  const [mode, setMode] = useState<GestureMode>('loading')
  const [activeNode, setActiveNode] = useState<NodeMetric | null>(null)
  const [cameraState, setCameraState] = useState<'ready' | 'starting' | 'active' | 'fallback'>('ready')

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x030504)
    scene.fog = new THREE.FogExp2(0x030504, 0.0014)

    const camera = new THREE.PerspectiveCamera(58, 1, 1, 2200)
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
    renderer.domElement.className = 'sandtable__webgl'
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    mount.appendChild(renderer.domElement)

    const ambient = new THREE.AmbientLight(0xbfffe9, 0.42)
    scene.add(ambient)
    const keyLight = new THREE.DirectionalLight(0xe8fff7, 1.1)
    keyLight.position.set(120, 220, 60)
    scene.add(keyLight)
    const sideLight = new THREE.PointLight(0x9de35f, 1.2, 760)
    sideLight.position.set(-260, 180, 180)
    scene.add(sideLight)

    const oceanMaterial = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uColor: { value: new THREE.Color(0x07100d) },
        uHighlight: { value: new THREE.Color(0x84f28d) },
      },
      vertexShader: `
        uniform float uTime;
        varying float vElevation;
        void main() {
          vec4 modelPosition = modelMatrix * vec4(position, 1.0);
          float elevation = sin(modelPosition.x * 0.012 + uTime) * cos(modelPosition.z * 0.014 + uTime) * 3.5;
          elevation += sin(modelPosition.x * 0.045 - uTime * 1.4) * 0.8;
          modelPosition.y += elevation;
          vElevation = elevation;
          gl_Position = projectionMatrix * viewMatrix * modelPosition;
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        uniform vec3 uHighlight;
        varying float vElevation;
        void main() {
          float mixStrength = (vElevation + 4.0) / 8.0;
          vec3 color = mix(uColor, uHighlight, mixStrength * 0.58);
          gl_FragColor = vec4(color, 0.96);
        }
      `,
      transparent: true,
    })
    const ocean = new THREE.Mesh(new THREE.PlaneGeometry(2600, 2600, 120, 120), oceanMaterial)
    ocean.rotation.x = -Math.PI / 2
    scene.add(ocean)

    const grid = new THREE.GridHelper(1900, 34, 0x284239, 0x10231f)
    grid.position.y = 0.8
    const gridMaterial = grid.material as THREE.Material
    gridMaterial.transparent = true
    gridMaterial.opacity = 0.22
    scene.add(grid)

    const random = createSeededRandom()
    const nodeCount = 420
    const nodeGeometry = new THREE.ConeGeometry(4.2, 18, 5)
    const nodeMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.52,
      metalness: 0.24,
      flatShading: true,
    })
    const nodesMesh = new THREE.InstancedMesh(nodeGeometry, nodeMaterial, nodeCount)
    nodesMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
    const metrics: NodeMetric[] = []
    const dummy = new THREE.Object3D()
    const color = new THREE.Color()
    for (let index = 0; index < nodeCount; index += 1) {
      const radius = Math.sqrt(random()) * 790
      const angle = random() * Math.PI * 2
      const scale = random() * 0.84 + 0.44
      const heightScale = random() * 1.4 + 0.72
      const x = Math.cos(angle) * radius
      const z = Math.sin(angle) * radius
      dummy.position.set(x, 8, z)
      dummy.rotation.y = random() * Math.PI
      dummy.scale.set(scale, scale * heightScale, scale)
      dummy.updateMatrix()
      nodesMesh.setMatrixAt(index, dummy.matrix)

      const health = random()
      const nodeColor = health > 0.72 ? '#8cf47e' : health > 0.32 ? '#47d7d0' : '#f2cf66'
      const template = nodeTemplates[index % nodeTemplates.length]
      color.set(nodeColor)
      color.offsetHSL((random() - 0.5) * 0.04, 0, (random() - 0.5) * 0.08)
      nodesMesh.setColorAt(index, color)

      metrics.push({
        id: `FLOW-${String(index + 1).padStart(3, '0')}`,
        name: template.name,
        input: template.input,
        output: template.output,
        day: template.day,
        useCase: template.useCase,
        status: health > 0.72 ? '可进入生产' : health > 0.32 ? '等待复核' : '需要补素材',
        color: nodeColor,
        position: dummy.position.clone(),
      })
    }
    scene.add(nodesMesh)

    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(11, 0.36, 4, 40),
      new THREE.MeshBasicMaterial({ color: 0x98ff86, transparent: true, opacity: 0.88 }),
    )
    ring.rotation.x = -Math.PI / 2
    ring.visible = false
    scene.add(ring)

    const raycaster = new THREE.Raycaster()
    const currentLook = new THREE.Vector3(0, 0, 0)
    const pointerNdc = new THREE.Vector2(0, 0)
    const size = { width: 1, height: 1 }
    let targetLookX = 0
    let targetLookZ = 0
    let targetZoomY = 470
    let targetZoomZ = 510
    let aiming = false
    let hoveredId = -1
    let pointerDragging = false
    let lastPointer: { x: number; y: number } | null = null
    let animationFrame = 0

    const setCanvasSize = () => {
      const rect = mount.getBoundingClientRect()
      size.width = Math.max(1, rect.width)
      size.height = Math.max(1, rect.height)
      camera.aspect = size.width / size.height
      camera.updateProjectionMatrix()
      renderer.setSize(size.width, size.height)
    }
    setCanvasSize()

    const resizeObserver = new ResizeObserver(setCanvasSize)
    resizeObserver.observe(mount)

    const showCrosshair = (x: number, y: number) => {
      const crosshair = crosshairRef.current
      if (!crosshair) return
      crosshair.style.opacity = '1'
      crosshair.style.transform = `translate3d(${x}px, ${y}px, 0) translate(-50%, -50%)`
    }

    const hideCrosshair = () => {
      const crosshair = crosshairRef.current
      if (crosshair) crosshair.style.opacity = '0'
    }

    const clearHover = () => {
      if (hoveredId !== -1) {
        hoveredId = -1
        setActiveNode(null)
      }
      ring.visible = false
      const panel = panelRef.current
      if (panel) panel.style.opacity = '0'
    }

    const applyAimFromNdc = (ndcX: number, ndcY: number, screenX: number, screenY: number) => {
      pointerNdc.set(ndcX, ndcY)
      aiming = true
      showCrosshair(screenX, screenY)
    }

    controlsRef.current = {
      panByNormalized: (deltaX, deltaY) => {
        targetLookX = clamp(targetLookX - deltaX * 940, -900, 900)
        targetLookZ = clamp(targetLookZ + deltaY * 940, -900, 900)
        aiming = false
        hideCrosshair()
        clearHover()
      },
      aimAtNormalized: (x, y) => {
        applyAimFromNdc((1 - x) * 2 - 1, -y * 2 + 1, (1 - x) * size.width, y * size.height)
      },
      aimAtClientPoint: (clientX, clientY) => {
        const rect = mount.getBoundingClientRect()
        const x = clamp(clientX - rect.left, 0, rect.width)
        const y = clamp(clientY - rect.top, 0, rect.height)
        applyAimFromNdc((x / rect.width) * 2 - 1, -(y / rect.height) * 2 + 1, x, y)
      },
      clearAim: () => {
        aiming = false
        hideCrosshair()
        clearHover()
      },
    }

    const onPointerDown = (event: PointerEvent) => {
      if (isInteractivePointerTarget(event.target)) return
      pointerDragging = true
      lastPointer = { x: event.clientX, y: event.clientY }
      mount.setPointerCapture(event.pointerId)
      setMode('demo')
      controlsRef.current?.clearAim()
    }

    const onPointerMove = (event: PointerEvent) => {
      if (!pointerDragging && isInteractivePointerTarget(event.target)) return
      if (pointerDragging && lastPointer) {
        const deltaX = (event.clientX - lastPointer.x) / size.width
        const deltaY = (event.clientY - lastPointer.y) / size.height
        controlsRef.current?.panByNormalized(deltaX, deltaY)
        lastPointer = { x: event.clientX, y: event.clientY }
        return
      }
      setMode('demo')
      controlsRef.current?.aimAtClientPoint(event.clientX, event.clientY)
    }

    const onPointerUp = (event: PointerEvent) => {
      pointerDragging = false
      lastPointer = null
      if (mount.hasPointerCapture(event.pointerId)) {
        mount.releasePointerCapture(event.pointerId)
      }
    }

    const onPointerLeave = () => {
      if (!pointerDragging) controlsRef.current?.clearAim()
    }

    mount.addEventListener('pointerdown', onPointerDown)
    mount.addEventListener('pointermove', onPointerMove)
    mount.addEventListener('pointerup', onPointerUp)
    mount.addEventListener('pointercancel', onPointerUp)
    mount.addEventListener('pointerleave', onPointerLeave)

    const animate = () => {
      animationFrame = requestAnimationFrame(animate)
      oceanMaterial.uniforms.uTime.value += 0.018
      currentLook.x += (targetLookX - currentLook.x) * 0.075
      currentLook.z += (targetLookZ - currentLook.z) * 0.075
      targetZoomY += (420 - targetZoomY) * 0.008
      targetZoomZ += (500 - targetZoomZ) * 0.008
      camera.position.x += (currentLook.x - camera.position.x) * 0.075
      camera.position.y += (targetZoomY - camera.position.y) * 0.075
      camera.position.z += (currentLook.z + targetZoomZ - camera.position.z) * 0.075
      camera.lookAt(currentLook)
      ring.rotation.z += 0.04

      if (aiming) {
        raycaster.setFromCamera(pointerNdc, camera)
        const intersections = raycaster.intersectObject(nodesMesh)
        if (intersections.length > 0 && intersections[0].instanceId !== undefined) {
          const instanceId = intersections[0].instanceId
          const metric = metrics[instanceId]
          if (metric && hoveredId !== instanceId) {
            hoveredId = instanceId
            setActiveNode(metric)
            ring.position.set(metric.position.x, 5, metric.position.z)
            ring.visible = true
          }
          if (metric) {
            const panelPosition = metric.position.clone()
            panelPosition.y += 34
            panelPosition.project(camera)
            const left = (panelPosition.x * 0.5 + 0.5) * size.width
            const top = (panelPosition.y * -0.5 + 0.5) * size.height
            const panel = panelRef.current
            if (panel) {
              panel.style.opacity = '1'
              panel.style.transform = `translate3d(${left}px, ${top}px, 0) translate(-50%, -118%)`
              panel.style.borderColor = metric.color
            }
          }
        } else {
          clearHover()
        }
      } else {
        clearHover()
      }

      renderer.render(scene, camera)
    }
    animate()
    window.setTimeout(() => setMode('demo'), 600)

    return () => {
      controlsRef.current = null
      cancelAnimationFrame(animationFrame)
      resizeObserver.disconnect()
      mount.removeEventListener('pointerdown', onPointerDown)
      mount.removeEventListener('pointermove', onPointerMove)
      mount.removeEventListener('pointerup', onPointerUp)
      mount.removeEventListener('pointercancel', onPointerUp)
      mount.removeEventListener('pointerleave', onPointerLeave)
      mount.removeChild(renderer.domElement)
      oceanMaterial.dispose()
      nodeGeometry.dispose()
      nodeMaterial.dispose()
      ring.geometry.dispose()
      ;(ring.material as THREE.Material).dispose()
      renderer.dispose()
    }
  }, [])

  const enterIdleSafe = useCallback(() => {
    lastHandPanRef.current = null
    controlsRef.current?.clearAim()
    setMode('idle-safe')
  }, [])

  const handleHandResults = useCallback((results: Results) => {
    const previewCanvas = previewCanvasRef.current
    const previewContext = previewCanvas?.getContext('2d')
    if (previewCanvas && previewContext) {
      previewContext.save()
      previewContext.clearRect(0, 0, previewCanvas.width, previewCanvas.height)
      previewContext.drawImage(results.image, 0, 0, previewCanvas.width, previewCanvas.height)
      for (const landmarks of results.multiHandLandmarks ?? []) {
        drawConnectors(previewContext, landmarks, HAND_CONNECTIONS, { color: '#9afc7c', lineWidth: 3 })
        drawLandmarks(previewContext, landmarks, { color: '#ffffff', lineWidth: 1, radius: 2 })
      }
      previewContext.restore()
    }

    const hands = results.multiHandLandmarks
    if (!hands?.length) {
      enterIdleSafe()
      return
    }

    if (hands.length !== 1) {
      enterIdleSafe()
      return
    }

    const hand = hands[0]
    const wrist = hand[0]
    const indexTip = hand[8]
    const thumbTip = hand[4]
    const thumbJoint = hand[3]
    const pinkyBase = hand[17]
    const palmSize = distance2D(wrist, hand[9])
    const pinchThreshold = clamp(palmSize * 0.72, 0.055, 0.12)
    const thumbDistTip = distance2D(thumbTip, pinkyBase)
    const thumbDistJoint = distance2D(thumbJoint, pinkyBase)
    const thumbIndexDist = distance2D(thumbTip, indexTip)
    const isThumbOpen = thumbDistTip > thumbDistJoint * 1.06
    const isThumbPinchingIndex = thumbIndexDist < pinchThreshold
    const isThumbEngaged = isThumbOpen || isThumbPinchingIndex
    const isIndexOpen = isFingerOpen(hand, 8, 6)
    const openNonIndexCount = [
      isFingerOpen(hand, 12, 10),
      isFingerOpen(hand, 16, 14),
      isFingerOpen(hand, 20, 18),
    ].filter(Boolean).length
    const otherFingersMostlyClosed = openNonIndexCount <= 1

    if (isIndexOpen && isThumbEngaged && otherFingersMostlyClosed) {
      const last = lastHandPanRef.current
      if (last) {
        controlsRef.current?.panByNormalized(wrist.x - last.x, wrist.y - last.y)
      }
      lastHandPanRef.current = { x: wrist.x, y: wrist.y }
      setMode('drag')
      return
    }

    if (isIndexOpen && !isThumbEngaged && otherFingersMostlyClosed) {
      lastHandPanRef.current = null
      controlsRef.current?.aimAtNormalized(indexTip.x, indexTip.y)
      setMode('aim')
      return
    }

    enterIdleSafe()
  }, [enterIdleSafe])

  const startHandTracking = useCallback(async () => {
    if (cameraState === 'starting' || cameraState === 'active') return
    const video = videoRef.current
    if (!video) return

    setCameraState('starting')
    try {
      const hands = new Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
      })
      hands.setOptions({
        maxNumHands: 1,
        modelComplexity: 1,
        minDetectionConfidence: 0.62,
        minTrackingConfidence: 0.62,
      })
      hands.onResults(handleHandResults)

      const camera = new Camera(video, {
        onFrame: async () => {
          await hands.send({ image: video })
        },
        width: 320,
        height: 240,
      })
      await camera.start()
      handsRef.current = hands
      cameraRef.current = camera
      setCameraState('active')
      setMode('idle-safe')
    } catch {
      setCameraState('fallback')
      setMode('demo')
      controlsRef.current?.clearAim()
    }
  }, [cameraState, handleHandResults])

  useEffect(() => {
    return () => {
      cameraRef.current?.stop()
      void handsRef.current?.close()
    }
  }, [])

  const cameraButtonText = cameraState === 'active'
    ? '手势已启用'
    : cameraState === 'starting'
      ? '正在连接摄像头'
      : cameraState === 'fallback'
        ? '使用鼠标演示'
        : '启用摄像头手势'

  return (
    <div className="sandtable" ref={mountRef}>
      <div className="sandtable__crosshair" ref={crosshairRef} aria-hidden="true">
        <span />
      </div>
      <div className="sandtable__panel" ref={panelRef}>
        <p>{activeNode?.id ?? 'FLOW-000'}</p>
        <strong>{activeNode?.name ?? '内容生产节点'}</strong>
        <dl>
          <div>
            <dt>输入</dt>
            <dd>{activeNode?.input ?? '--'}</dd>
          </div>
          <div>
            <dt>输出</dt>
            <dd>{activeNode?.output ?? '--'}</dd>
          </div>
          <div>
            <dt>课程</dt>
            <dd>{activeNode?.day ?? '--'}</dd>
          </div>
        </dl>
        <span>{activeNode ? `${activeNode.status} · ${activeNode.useCase}` : '等待指向'}</span>
      </div>
      <div className="sandtable__status">
        <span className="sandtable__pulse" />
        {modeText[mode]}
      </div>
      <button
        className="sandtable__camera"
        type="button"
        onClick={() => void startHandTracking()}
        disabled={cameraState === 'starting' || cameraState === 'active'}
      >
        {cameraButtonText}
      </button>
      <div className={`sandtable__preview ${cameraState === 'active' ? 'is-visible' : ''}`} aria-hidden={cameraState !== 'active'}>
        <video ref={videoRef} className="sandtable__video" playsInline muted />
        <canvas ref={previewCanvasRef} width={320} height={240} />
      </div>
    </div>
  )
}
