import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Button, Empty, Spin, Tooltip, Typography } from 'antd'
import { BranchesOutlined, CloseOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import { Link, useParams } from 'react-router-dom'
import { getInteractiveMoviePublicProject } from '../../lib/interactiveMovie'
import './InteractiveMoviePage.css'

type ScriptLine = {
  id: string
  speaker: string
  text: string
}

type SceneNode = {
  id: string
  title: string
  role: 'start' | 'middle' | 'ending'
  script: {
    lines: ScriptLine[]
  }
  media: {
    kind: 'image' | 'video' | 'placeholder'
    url?: string
    posterUrl?: string
  }
}

type ChoiceEdge = {
  id: string
  fromSceneId: string
  toSceneId: string
  label: string
}

type PublicMovieDocument = {
  id: string
  title: string
  scenes: SceneNode[]
  choices: ChoiceEdge[]
}

type BootPreloadState = {
  status: 'idle' | 'loading' | 'ready'
  loaded: number
  total: number
  message: string
}

type UnlockProgress = {
  releaseId: string
  visitedSceneIds: string[]
  chosenChoiceIds: string[]
  updatedAt: string
}

type RouteTreeNodeStatus = 'current' | 'unlocked' | 'locked'
type RouteTreeEdgeStatus = 'chosen' | 'available' | 'locked'

type RouteTreeNode = {
  scene: SceneNode
  x: number
  y: number
  status: RouteTreeNodeStatus
}

type RouteTreeEdge = {
  id: string
  path: string
  status: RouteTreeEdgeStatus
}

type RouteTreeChoice = {
  choice: ChoiceEdge
  x: number
  y: number
  status: RouteTreeEdgeStatus
}

type RouteTree = {
  nodes: RouteTreeNode[]
  choiceNodes: RouteTreeChoice[]
  edges: RouteTreeEdge[]
  width: number
  height: number
}

const PRELOAD_TIMEOUT_MS = 15000
const UNLOCK_STORAGE_PREFIX = 'pettech.interactiveMovie.unlockProgress.'
const TREE_NODE_WIDTH = 152
const TREE_NODE_HEIGHT = 58
const TREE_CHOICE_WIDTH = 132
const TREE_CHOICE_HEIGHT = 38
const TREE_COLUMN_GAP = 320
const TREE_ROW_GAP = 86

export default function PublicInteractiveMoviePlayer() {
  const { projectId } = useParams<{ projectId?: string }>()
  const [document, setDocument] = useState<PublicMovieDocument | null>(null)
  const [releaseId, setReleaseId] = useState('')
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [sceneId, setSceneId] = useState('')
  const [lineIndex, setLineIndex] = useState(0)
  const [choicesVisible, setChoicesVisible] = useState(false)
  const [ended, setEnded] = useState(false)
  const [gameStarted, setGameStarted] = useState(false)
  const [routePanelOpen, setRoutePanelOpen] = useState(false)
  const [visitedSceneIds, setVisitedSceneIds] = useState<Set<string>>(() => new Set())
  const [chosenChoiceIds, setChosenChoiceIds] = useState<Set<string>>(() => new Set())
  const [bootPreload, setBootPreload] = useState<BootPreloadState>({
    status: 'idle',
    loaded: 0,
    total: 0,
    message: '正在准备影游',
  })
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const preloadPromiseByUrlRef = useRef(new Map<string, Promise<void>>())
  const preloadedUrlRef = useRef(new Set<string>())
  const preloadedVideoByUrlRef = useRef(new Map<string, HTMLVideoElement>())

  useEffect(() => (
    () => {
      resetPreloadedVideos(preloadedVideoByUrlRef.current)
      preloadPromiseByUrlRef.current = new Map()
      preloadedUrlRef.current = new Set()
      preloadedVideoByUrlRef.current = new Map()
    }
  ), [])

  useEffect(() => {
    let cancelled = false
    const loadProject = async () => {
      if (!projectId) {
        setNotFound(true)
        setLoading(false)
        return
      }
      setLoading(true)
      setNotFound(false)
      setGameStarted(false)
      setRoutePanelOpen(false)
      setReleaseId('')
      setVisitedSceneIds(new Set())
      setChosenChoiceIds(new Set())
      setBootPreload({ status: 'idle', loaded: 0, total: 0, message: '正在准备影游' })
      resetPreloadedVideos(preloadedVideoByUrlRef.current)
      preloadPromiseByUrlRef.current = new Map()
      preloadedUrlRef.current = new Set()
      preloadedVideoByUrlRef.current = new Map()
      try {
        const result = await getInteractiveMoviePublicProject<PublicMovieDocument>(projectId)
        if (cancelled) return
        const startScene = findStartScene(result.document)
        setDocument(result.document)
        setReleaseId(result.release_id)
        setSceneId(startScene?.id ?? '')
        setLineIndex(0)
        setChoicesVisible(false)
        setEnded(false)
        const progress = readUnlockProgress(projectId, result.release_id)
        setVisitedSceneIds(new Set(progress?.visitedSceneIds ?? []))
        setChosenChoiceIds(new Set(progress?.chosenChoiceIds ?? []))
      } catch {
        if (!cancelled) {
          setDocument(null)
          setNotFound(true)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void loadProject()
    return () => {
      cancelled = true
    }
  }, [projectId])

  const sceneMap = useMemo(() => new Map((document?.scenes ?? []).map((scene) => [scene.id, scene])), [document])
  const startScene = document ? findStartScene(document) : null
  const scene = sceneMap.get(sceneId) ?? startScene
  const outgoingChoices = (document?.choices ?? []).filter((choice) => (
    choice.fromSceneId === scene?.id && sceneMap.has(choice.toSceneId)
  ))
  const videoUrl = getSceneVideoUrl(scene)
  const hasVideo = Boolean(videoUrl)
  const currentLine = scene?.script.lines[lineIndex]
  const routeTree = useMemo(() => (
    document
      ? buildRouteTree(document, startScene?.id ?? '', scene?.id ?? '', visitedSceneIds, chosenChoiceIds)
      : null
  ), [chosenChoiceIds, document, scene?.id, startScene?.id, visitedSceneIds])
  const unlockedSceneCount = visitedSceneIds.size
  const totalSceneCount = document?.scenes.length ?? 0

  useEffect(() => {
    if (!document || !scene?.id || gameStarted) return

    let cancelled = false
    const urls = collectSceneAndNextVideoUrls(document, scene.id)

    if (urls.length === 0) {
      setBootPreload({ status: 'ready', loaded: 0, total: 0, message: '准备完成' })
      return undefined
    }

    let settledCount = 0
    setBootPreload({
      status: 'loading',
      loaded: 0,
      total: urls.length,
      message: '正在加载起始视频和第一层分支',
    })

    void Promise.all(
      urls.map((url) => preloadVideo(
        url,
        preloadPromiseByUrlRef.current,
        preloadedUrlRef.current,
        preloadedVideoByUrlRef.current,
      ).finally(() => {
        settledCount += 1
        if (!cancelled) {
          setBootPreload({
            status: 'loading',
            loaded: settledCount,
            total: urls.length,
            message: '正在加载起始视频和第一层分支',
          })
        }
      })),
    ).then(() => {
      if (!cancelled) {
        setBootPreload({
          status: 'ready',
          loaded: urls.length,
          total: urls.length,
          message: '加载完成',
        })
      }
    })

    return () => {
      cancelled = true
    }
  }, [document, gameStarted, scene?.id])

  useEffect(() => {
    if (!document || !scene?.id || !gameStarted) return
    const urls = collectSceneAndNextVideoUrls(document, scene.id)
    urls.forEach((url) => {
      void preloadVideo(
        url,
        preloadPromiseByUrlRef.current,
        preloadedUrlRef.current,
        preloadedVideoByUrlRef.current,
      )
    })
  }, [document, gameStarted, scene?.id])

  useEffect(() => {
    if (!gameStarted || !videoUrl) return
    void videoRef.current?.play().catch(() => undefined)
  }, [gameStarted, scene?.id, videoUrl])

  useEffect(() => {
    if (!projectId || !releaseId) return
    writeUnlockProgress(projectId, {
      releaseId,
      visitedSceneIds: Array.from(visitedSceneIds),
      chosenChoiceIds: Array.from(chosenChoiceIds),
      updatedAt: new Date().toISOString(),
    })
  }, [chosenChoiceIds, projectId, releaseId, visitedSceneIds])

  const unlockScene = (targetSceneId: string) => {
    if (!targetSceneId) return
    setVisitedSceneIds((current) => {
      if (current.has(targetSceneId)) return current
      const next = new Set(current)
      next.add(targetSceneId)
      return next
    })
  }

  const unlockChoice = (choiceId: string) => {
    if (!choiceId) return
    setChosenChoiceIds((current) => {
      if (current.has(choiceId)) return current
      const next = new Set(current)
      next.add(choiceId)
      return next
    })
  }

  const finishScene = () => {
    if (outgoingChoices.length > 0) {
      setChoicesVisible(true)
      return
    }
    setEnded(true)
  }

  const advanceDialogue = () => {
    if (!scene) return
    if (lineIndex < scene.script.lines.length - 1) {
      setLineIndex((index) => index + 1)
      return
    }
    finishScene()
  }

  const choose = (choice: ChoiceEdge) => {
    if (!sceneMap.has(choice.toSceneId)) return
    unlockChoice(choice.id)
    unlockScene(choice.toSceneId)
    setSceneId(choice.toSceneId)
    setLineIndex(0)
    setChoicesVisible(false)
    setEnded(false)
  }

  const startGame = () => {
    unlockScene(scene?.id ?? startScene?.id ?? '')
    setGameStarted(true)
    setLineIndex(0)
    setChoicesVisible(false)
    setEnded(false)
  }

  const restart = () => {
    const nextStartScene = document ? findStartScene(document) : null
    setSceneId(nextStartScene?.id ?? '')
    setLineIndex(0)
    setChoicesVisible(false)
    setEnded(false)
    setGameStarted(false)
  }

  useEffect(() => {
    if (!gameStarted || !document || !scene || choicesVisible || ended || hasVideo || currentLine) return
    if (outgoingChoices.length > 0) {
      setChoicesVisible(true)
      return
    }
    setEnded(true)
  }, [choicesVisible, currentLine, document, ended, gameStarted, hasVideo, outgoingChoices.length, scene])

  if (loading) {
    return (
      <main className="movie-public-page">
        <Spin size="large" />
      </main>
    )
  }

  if (notFound || !document || !scene) {
    return (
      <main className="movie-public-page">
        <div className="movie-public-empty">
          <Empty description="这个互动影游暂不可访问" />
          <Link to="/">
            <Button>返回首页</Button>
          </Link>
        </div>
      </main>
    )
  }

  return (
    <main className="movie-public-page">
      <section className={hasVideo ? 'movie-public-stage has-video' : 'movie-public-stage'}>
        {gameStarted && !ended && videoUrl && (
          <video
            key={scene.id}
            ref={videoRef}
            src={videoUrl}
            poster={scene.media.posterUrl}
            className="movie-public-video"
            controls
            autoPlay
            preload="auto"
            playsInline
            onEnded={finishScene}
          />
        )}
        <div className="movie-public-vignette" />
        <div className="movie-public-heading">
          <Typography.Text className="movie-public-kicker">{document.title}</Typography.Text>
          <Typography.Title level={2}>{scene.title}</Typography.Title>
        </div>
        <div className="movie-public-route-control">
          <Tooltip title={routePanelOpen ? '收起路线图' : '查看已解锁路线'}>
            <Button
              icon={<BranchesOutlined />}
              onClick={() => setRoutePanelOpen((value) => !value)}
            >
              路线图
            </Button>
          </Tooltip>
        </div>
        {routePanelOpen && routeTree && (
          <RouteTreePanel
            currentSceneId={scene.id}
            tree={routeTree}
            unlockedSceneCount={unlockedSceneCount}
            totalSceneCount={totalSceneCount}
            onClose={() => setRoutePanelOpen(false)}
            onSelectScene={(nextSceneId) => {
              if (!visitedSceneIds.has(nextSceneId)) return
              setSceneId(nextSceneId)
              setLineIndex(0)
              setChoicesVisible(false)
              setEnded(false)
            }}
          />
        )}
        {!gameStarted && (
          <div className="movie-public-loader">
            <div className="movie-public-loader-mark" aria-hidden="true" />
            <Typography.Title level={3}>正在加载影游</Typography.Title>
            <Typography.Text className="movie-public-loader-text">
              {bootPreload.message}
              {bootPreload.total > 0 ? ` ${bootPreload.loaded}/${bootPreload.total}` : ''}
            </Typography.Text>
            <div className="movie-public-loader-bar" aria-hidden="true">
              <span
                style={{
                  transform: `scaleX(${bootPreload.total > 0 ? bootPreload.loaded / bootPreload.total : 1})`,
                }}
              />
            </div>
            <Button
              size="large"
              type="primary"
              icon={<PlayCircleOutlined />}
              disabled={bootPreload.status !== 'ready'}
              onClick={startGame}
            >
              开始游戏
            </Button>
          </div>
        )}
        {gameStarted && choicesVisible && (
          <div className="movie-public-choices">
            {outgoingChoices.map((choice) => (
              <Button key={choice.id} size="large" onClick={() => choose(choice)}>
                {choice.label}
              </Button>
            ))}
          </div>
        )}
        {gameStarted && !choicesVisible && !ended && !hasVideo && currentLine && (
          <button type="button" className="movie-public-dialogue" onClick={advanceDialogue}>
            <span className="movie-dialogue-speaker">{currentLine.speaker || '角色'}</span>
            <span className="movie-dialogue-text">{currentLine.text}</span>
            <span className="movie-dialogue-next">点击继续</span>
          </button>
        )}
        {gameStarted && ended && (
          <div className="movie-public-ended">
            <PlayCircleOutlined />
            <Typography.Title level={3}>剧终</Typography.Title>
            <Button icon={<ReloadOutlined />} onClick={restart}>重新开始</Button>
          </div>
        )}
      </section>
    </main>
  )
}

function RouteTreePanel({
  currentSceneId,
  onClose,
  onSelectScene,
  totalSceneCount,
  tree,
  unlockedSceneCount,
}: {
  currentSceneId: string
  onClose: () => void
  onSelectScene: (sceneId: string) => void
  totalSceneCount: number
  tree: RouteTree
  unlockedSceneCount: number
}) {
  return (
    <aside className="movie-route-tree-panel" aria-label="互动影游路线图">
      <div className="movie-route-tree-header">
        <div>
          <Typography.Text className="movie-public-kicker">路线探索</Typography.Text>
          <Typography.Title level={5}>已解锁 {unlockedSceneCount}/{totalSceneCount}</Typography.Title>
        </div>
        <Button
          shape="circle"
          icon={<CloseOutlined />}
          aria-label="关闭路线图"
          onClick={onClose}
        />
      </div>
      <div className="movie-route-tree-scroll">
        <div
          className="movie-route-tree-canvas"
          style={{
            width: tree.width,
            height: tree.height,
          }}
        >
          <svg className="movie-route-tree-edges" width={tree.width} height={tree.height}>
            {tree.edges.map((edge) => (
              <g key={edge.id} className={`movie-route-tree-edge is-${edge.status}`}>
                <path d={edge.path} />
              </g>
            ))}
          </svg>
          {tree.nodes.map((node) => {
            const isUnlocked = node.status !== 'locked'
            return (
              <button
                key={node.scene.id}
                type="button"
                className={`movie-route-tree-node is-${node.status}`}
                style={{
                  '--route-node-x': `${node.x}px`,
                  '--route-node-y': `${node.y}px`,
                } as CSSProperties}
                disabled={!isUnlocked}
                aria-current={node.scene.id === currentSceneId ? 'step' : undefined}
                onClick={() => onSelectScene(node.scene.id)}
              >
                <span className="movie-route-node-role">{sceneRoleLabel(node.scene.role)}</span>
                <span className="movie-route-node-title">{isUnlocked ? node.scene.title : '未解锁节点'}</span>
              </button>
            )
          })}
          {tree.choiceNodes.map((node) => {
            const isLocked = node.status === 'locked'
            return (
              <div
                key={node.choice.id}
                className={`movie-route-tree-choice is-${node.status}`}
                style={{
                  '--route-choice-x': `${node.x}px`,
                  '--route-choice-y': `${node.y}px`,
                } as CSSProperties}
                aria-label={`选择：${node.choice.label}`}
              >
                <span className="movie-route-choice-kicker">选择</span>
                <span className="movie-route-choice-title">{isLocked ? '未解锁选择' : node.choice.label}</span>
              </div>
            )
          })}
        </div>
      </div>
    </aside>
  )
}

function findStartScene(document: PublicMovieDocument) {
  return document.scenes.find((scene) => scene.role === 'start') ?? document.scenes[0] ?? null
}

function sceneRoleLabel(role: SceneNode['role']) {
  if (role === 'start') return '开场'
  if (role === 'ending') return '结局'
  return '节点'
}

function getSceneVideoUrl(scene?: SceneNode | null) {
  if (scene?.media.kind !== 'video') return undefined
  const url = scene.media.url?.trim()
  return url || undefined
}

function collectSceneAndNextVideoUrls(document: PublicMovieDocument, sceneId: string) {
  const sceneMap = new Map(document.scenes.map((scene) => [scene.id, scene]))
  const currentScene = sceneMap.get(sceneId)
  const urls = new Set<string>()
  const currentUrl = getSceneVideoUrl(currentScene)
  if (currentUrl) urls.add(currentUrl)

  document.choices
    .filter((choice) => choice.fromSceneId === sceneId)
    .forEach((choice) => {
      const nextUrl = getSceneVideoUrl(sceneMap.get(choice.toSceneId))
      if (nextUrl) urls.add(nextUrl)
    })

  return Array.from(urls)
}

function preloadVideo(
  url: string,
  promiseByUrl: Map<string, Promise<void>>,
  preloadedUrls: Set<string>,
  videoByUrl: Map<string, HTMLVideoElement>,
) {
  if (preloadedUrls.has(url)) return Promise.resolve()

  const existingPromise = promiseByUrl.get(url)
  if (existingPromise) return existingPromise

  const promise = new Promise<void>((resolve) => {
    const video = globalThis.document.createElement('video')
    let timeoutId = 0
    let settled = false

    const settle = () => {
      if (settled) return
      settled = true
      window.clearTimeout(timeoutId)
      video.removeEventListener('loadeddata', settle)
      video.removeEventListener('canplaythrough', settle)
      video.removeEventListener('error', settle)
      preloadedUrls.add(url)
      resolve()
    }

    video.preload = 'auto'
    video.muted = true
    video.playsInline = true
    video.addEventListener('loadeddata', settle)
    video.addEventListener('canplaythrough', settle)
    video.addEventListener('error', settle)
    timeoutId = window.setTimeout(settle, PRELOAD_TIMEOUT_MS)
    video.src = url
    video.load()
    videoByUrl.set(url, video)
  })

  promiseByUrl.set(url, promise)
  return promise
}

function resetPreloadedVideos(videoByUrl: Map<string, HTMLVideoElement>) {
  videoByUrl.forEach((video) => {
    video.pause()
    video.removeAttribute('src')
    video.load()
  })
  videoByUrl.clear()
}

function unlockStorageKey(projectId: string, releaseId: string) {
  return `${UNLOCK_STORAGE_PREFIX}${projectId}.${releaseId}`
}

function readUnlockProgress(projectId: string, releaseId: string): UnlockProgress | null {
  try {
    const raw = window.localStorage.getItem(unlockStorageKey(projectId, releaseId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<UnlockProgress>
    if (parsed.releaseId !== releaseId) return null
    return {
      releaseId,
      visitedSceneIds: Array.isArray(parsed.visitedSceneIds) ? parsed.visitedSceneIds.filter(isString) : [],
      chosenChoiceIds: Array.isArray(parsed.chosenChoiceIds) ? parsed.chosenChoiceIds.filter(isString) : [],
      updatedAt: typeof parsed.updatedAt === 'string' ? parsed.updatedAt : '',
    }
  } catch {
    return null
  }
}

function writeUnlockProgress(projectId: string, progress: UnlockProgress) {
  try {
    window.localStorage.setItem(unlockStorageKey(projectId, progress.releaseId), JSON.stringify(progress))
  } catch {
    // Private browsing and embedded webviews may deny localStorage writes.
  }
}

function isString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}

function buildRouteTree(
  document: PublicMovieDocument,
  startSceneId: string,
  currentSceneId: string,
  visitedSceneIds: Set<string>,
  chosenChoiceIds: Set<string>,
): RouteTree {
  const sceneMap = new Map(document.scenes.map((scene) => [scene.id, scene]))
  const outgoingByScene = new Map<string, ChoiceEdge[]>()
  document.choices.forEach((choice) => {
    if (!sceneMap.has(choice.fromSceneId) || !sceneMap.has(choice.toSceneId)) return
    const choices = outgoingByScene.get(choice.fromSceneId) ?? []
    choices.push(choice)
    outgoingByScene.set(choice.fromSceneId, choices)
  })

  const depthByScene = new Map<string, number>()
  const queue: string[] = []
  if (startSceneId && sceneMap.has(startSceneId)) {
    depthByScene.set(startSceneId, 0)
    queue.push(startSceneId)
  }

  while (queue.length > 0) {
    const sceneId = queue.shift() ?? ''
    const depth = depthByScene.get(sceneId) ?? 0
    ;(outgoingByScene.get(sceneId) ?? []).forEach((choice) => {
      if (depthByScene.has(choice.toSceneId)) return
      depthByScene.set(choice.toSceneId, depth + 1)
      queue.push(choice.toSceneId)
    })
  }

  const connectedMaxDepth = Math.max(0, ...Array.from(depthByScene.values()))
  document.scenes.forEach((scene) => {
    if (!depthByScene.has(scene.id)) depthByScene.set(scene.id, connectedMaxDepth + 1)
  })

  const groups = new Map<number, SceneNode[]>()
  document.scenes.forEach((scene) => {
    const depth = depthByScene.get(scene.id) ?? 0
    const scenes = groups.get(depth) ?? []
    scenes.push(scene)
    groups.set(depth, scenes)
  })

  const nodes: RouteTreeNode[] = []
  groups.forEach((scenes, depth) => {
    scenes.forEach((scene, index) => {
      const status: RouteTreeNodeStatus = scene.id === currentSceneId
        ? 'current'
        : visitedSceneIds.has(scene.id)
          ? 'unlocked'
          : 'locked'
      nodes.push({
        scene,
        status,
        x: 18 + depth * TREE_COLUMN_GAP,
        y: 18 + index * TREE_ROW_GAP,
      })
    })
  })

  const nodeBySceneId = new Map(nodes.map((node) => [node.scene.id, node]))
  const choiceNodes: RouteTreeChoice[] = []
  const edgeSegments: RouteTreeEdge[] = []
  const choicePairIndex = new Map<string, number>()

  document.choices.forEach((choice) => {
    const from = nodeBySceneId.get(choice.fromSceneId)
    const to = nodeBySceneId.get(choice.toSceneId)
    if (!from || !to) return
    const pairKey = `${choice.fromSceneId}:${choice.toSceneId}`
    const pairIndex = choicePairIndex.get(pairKey) ?? 0
    choicePairIndex.set(pairKey, pairIndex + 1)

    const status: RouteTreeEdgeStatus = chosenChoiceIds.has(choice.id)
      ? 'chosen'
      : visitedSceneIds.has(choice.fromSceneId)
        ? 'available'
        : 'locked'
    const fromCenterY = from.y + TREE_NODE_HEIGHT / 2
    const toCenterY = to.y + TREE_NODE_HEIGHT / 2
    const choiceX = from.x + TREE_NODE_WIDTH + 34
    const choiceY = (fromCenterY + toCenterY) / 2 - TREE_CHOICE_HEIGHT / 2 + pairIndex * (TREE_CHOICE_HEIGHT + 8)
    const choiceCenterX = choiceX + TREE_CHOICE_WIDTH / 2
    const choiceCenterY = choiceY + TREE_CHOICE_HEIGHT / 2

    choiceNodes.push({
      choice,
      status,
      x: choiceX,
      y: choiceY,
    })

    const startX = from.x + TREE_NODE_WIDTH
    const startY = fromCenterY
    const endX = to.x
    const endY = toCenterY
    const firstControlOffset = Math.max(28, Math.abs(choiceX - startX) * 0.5)
    const secondControlOffset = Math.max(28, Math.abs(endX - (choiceX + TREE_CHOICE_WIDTH)) * 0.5)
    const direction = endX >= startX ? 1 : -1

    edgeSegments.push({
      id: `${choice.id}:from`,
      status,
      path: [
        `M ${startX} ${startY}`,
        `C ${startX + firstControlOffset * direction} ${startY}, ${choiceCenterX - firstControlOffset * direction} ${choiceCenterY}, ${choiceX} ${choiceCenterY}`,
      ].join(' '),
    })
    edgeSegments.push({
      id: `${choice.id}:to`,
      status,
      path: [
        `M ${choiceX + TREE_CHOICE_WIDTH} ${choiceCenterY}`,
        `C ${choiceCenterX + secondControlOffset * direction} ${choiceCenterY}, ${endX - secondControlOffset * direction} ${endY}, ${endX} ${endY}`,
      ].join(' '),
    })
  })

  const maxX = Math.max(
    0,
    ...nodes.map((node) => node.x + TREE_NODE_WIDTH),
    ...choiceNodes.map((node) => node.x + TREE_CHOICE_WIDTH),
  )
  const maxY = Math.max(
    0,
    ...nodes.map((node) => node.y + TREE_NODE_HEIGHT),
    ...choiceNodes.map((node) => node.y + TREE_CHOICE_HEIGHT),
  )

  return {
    nodes,
    choiceNodes,
    edges: edgeSegments,
    width: maxX + 36,
    height: maxY + 36,
  }
}
