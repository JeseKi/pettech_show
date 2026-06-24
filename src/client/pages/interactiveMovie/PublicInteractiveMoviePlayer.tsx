import { useEffect, useMemo, useState } from 'react'
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

export default function PublicInteractiveMoviePlayer() {
  const { projectId } = useParams<{ projectId?: string }>()
  const [document, setDocument] = useState<PublicMovieDocument | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [sceneId, setSceneId] = useState('')
  const [lineIndex, setLineIndex] = useState(0)
  const [choicesVisible, setChoicesVisible] = useState(false)
  const [ended, setEnded] = useState(false)

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
  const videoUrl = scene?.media.kind === 'video' ? scene.media.url : undefined
  const hasVideo = Boolean(videoUrl)
  const currentLine = scene?.script.lines[lineIndex]

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

  const restart = () => {
    const nextStartScene = document ? findStartScene(document) : null
    setSceneId(nextStartScene?.id ?? '')
    setLineIndex(0)
    setChoicesVisible(false)
    setEnded(false)
  }

  useEffect(() => {
    if (!document || !scene || choicesVisible || ended || hasVideo || currentLine) return
    if (outgoingChoices.length > 0) {
      setChoicesVisible(true)
      return
    }
    setEnded(true)
  }, [choicesVisible, currentLine, document, ended, hasVideo, outgoingChoices.length, scene])

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
        {!choicesVisible && !ended && videoUrl && (
          <video
            key={scene.id}
            src={videoUrl}
            poster={scene.media.posterUrl}
            className="movie-public-video"
            controls
            autoPlay
            playsInline
            onEnded={finishScene}
          />
        )}
        <div className="movie-public-vignette" />
        <div className="movie-public-heading">
          <Typography.Text className="movie-public-kicker">{document.title}</Typography.Text>
          <Typography.Title level={2}>{scene.title}</Typography.Title>
        </div>
        {choicesVisible && (
          <div className="movie-public-choices">
            {outgoingChoices.map((choice) => (
              <Button key={choice.id} size="large" onClick={() => choose(choice)}>
                {choice.label}
              </Button>
            ))}
          </div>
        )}
        {!choicesVisible && !ended && !hasVideo && currentLine && (
          <button type="button" className="movie-public-dialogue" onClick={advanceDialogue}>
            <span className="movie-dialogue-speaker">{currentLine.speaker || '角色'}</span>
            <span className="movie-dialogue-text">{currentLine.text}</span>
            <span className="movie-dialogue-next">点击继续</span>
          </button>
        )}
        {ended && (
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
