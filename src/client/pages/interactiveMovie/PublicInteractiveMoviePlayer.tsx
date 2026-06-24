import { useEffect, useMemo, useRef, useState } from 'react'
import { Button, Empty, Spin, Typography } from 'antd'
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
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

const PRELOAD_TIMEOUT_MS = 15000

export default function PublicInteractiveMoviePlayer() {
  const { projectId } = useParams<{ projectId?: string }>()
  const [document, setDocument] = useState<PublicMovieDocument | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [sceneId, setSceneId] = useState('')
  const [lineIndex, setLineIndex] = useState(0)
  const [choicesVisible, setChoicesVisible] = useState(false)
  const [ended, setEnded] = useState(false)
  const [gameStarted, setGameStarted] = useState(false)
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
        setSceneId(startScene?.id ?? '')
        setLineIndex(0)
        setChoicesVisible(false)
        setEnded(false)
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
    setSceneId(choice.toSceneId)
    setLineIndex(0)
    setChoicesVisible(false)
    setEnded(false)
  }

  const startGame = () => {
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
        {gameStarted && !choicesVisible && !ended && videoUrl && (
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

function findStartScene(document: PublicMovieDocument) {
  return document.scenes.find((scene) => scene.role === 'start') ?? document.scenes[0] ?? null
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
