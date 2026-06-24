import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from 'react'
import { isAxiosError } from 'axios'
import {
  App,
  Button,
  Empty,
  Flex,
  Input,
  Modal,
  Select,
  Space,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from 'antd'
import {
  BorderOuterOutlined,
  BranchesOutlined,
  DeleteOutlined,
  DoubleLeftOutlined,
  DoubleRightOutlined,
  DownOutlined,
  EditOutlined,
  FullscreenOutlined,
  MessageOutlined,
  PlusOutlined,
  PlayCircleOutlined,
  SaveOutlined,
  UploadOutlined,
  UpOutlined,
  VideoCameraOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons'
import { Link } from 'react-router-dom'
import {
  createInteractiveMovieProject,
  deleteInteractiveMovieProject,
  getInteractiveMovieProject,
  getInteractiveMoviePromptTemplate,
  getInteractiveMovieSyncState,
  listInteractiveMovieProjects,
  patchInteractiveMovieProject,
  renameInteractiveMovieProject,
  uploadInteractiveMovieVideo,
} from '../../lib/interactiveMovie'
import type { InteractiveMovieProjectDetail, InteractiveMovieProjectPatch, PromptTemplate } from '../../lib/interactiveMovie'
import { resolveErrorMessage } from '../../lib/errorMessage'
import './InteractiveMoviePage.css'

type SceneRole = 'start' | 'middle' | 'ending'
type SelectedObject = { type: 'scene' | 'choice'; id: string }

type ScriptLine = {
  id: string
  speaker: string
  text: string
}

type SceneScript = {
  synopsis: string
  visualDescription: string
  lines: ScriptLine[]
  videoPrompt: string
  promptParts?: VideoPromptParts
}

type SceneNode = {
  id: string
  title: string
  role: SceneRole
  position: { x: number; y: number }
  script: SceneScript
  media: {
    kind: 'image' | 'video' | 'placeholder'
    url?: string
    objectKey?: string
    storageUri?: string
    posterUrl?: string
    status: 'empty' | 'mock' | 'ready'
  }
}

type ChoiceEdge = {
  id: string
  fromSceneId: string
  toSceneId: string
  label: string
  trigger: 'after_scene'
  offsetY?: number
}

type CanvasViewport = {
  x: number
  y: number
  zoom: number
}

type VideoPromptParts = {
  subject: string
  action: string
  scene: string
  camera: string
  timeline: string
  style: string
  constraints: string
}

type SceneUploadState = {
  status: 'idle' | 'uploading' | 'ready' | 'failed'
  message?: string
}

type InteractiveMovieProject = {
  id: string
  title: string
  updatedAt: string
  version?: number
  contentHash?: string
  cloudUpdatedAt?: string
  scenes: SceneNode[]
  choices: ChoiceEdge[]
  selectedObject: SelectedObject
  viewport: CanvasViewport
}

type StoredWorkspace = {
  activeProjectId: string
  projects: InteractiveMovieProject[]
}

type InteractionState =
  | {
    type: 'pan'
    pointerId: number
    startClient: { x: number; y: number }
    startViewport: CanvasViewport
  }
  | {
    type: 'node'
    pointerId: number
    sceneId: string
    startClient: { x: number; y: number }
    startPosition: { x: number; y: number }
  }
  | {
    type: 'choice'
    pointerId: number
    choiceId: string
    startClient: { x: number; y: number }
    startOffsetY: number
  }

const STORAGE_KEY = 'pettech.interactiveMovie.workspace.v1'
const CLOUD_REPLICA_PREFIX = 'pettech.interactiveMovie.cloudReplica.'
const DRAFT_REPLICA_PREFIX = 'pettech.interactiveMovie.draftReplica.'
const MISSING_PROJECT_DETAIL = '互动电影项目不存在'
const NODE_WIDTH = 292
const NODE_HEIGHT = 236
const MIN_ZOOM = 0.25
const MAX_ZOOM = 2
const CREATE_SCENE_SELECT_VALUE = '__create_scene__'

const roleLabels: Record<SceneRole, string> = {
  start: '开场',
  middle: '过场',
  ending: '结局',
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

const uniqueId = (prefix: string) => `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`

const defaultPromptParts = (sceneTitle: string): VideoPromptParts => ({
  subject: sceneTitle,
  action: '',
  scene: '',
  camera: '电影级中景缓慢推近，浅景深',
  timeline: '[0-2s] 建立场景和主体状态；[2-5s] 主体完成关键动作并留下悬念。',
  style: '电影感，写实，低饱和，高对比，细腻光影',
  constraints: '不出现文字水印，不切换主角，主体外观保持一致',
})

const buildVideoPrompt = (scene: SceneNode): string => {
  const parts = scene.script.promptParts ?? defaultPromptParts(scene.title)
  const sections = [
    ['主体', parts.subject],
    ['动作', parts.action || scene.script.synopsis],
    ['场景', parts.scene || scene.script.visualDescription],
    ['镜头', parts.camera],
    ['时序', parts.timeline],
    ['风格', parts.style],
    ['约束', parts.constraints],
  ]
  return sections
    .filter(([, value]) => value.trim())
    .map(([label, value]) => `${label}：${value.trim()}`)
    .join('\n')
}

const captureVideoPoster = (file: File): Promise<string> => new Promise((resolve, reject) => {
  const objectUrl = URL.createObjectURL(file)
  const video = document.createElement('video')
  const cleanup = () => {
    URL.revokeObjectURL(objectUrl)
    video.removeAttribute('src')
    video.load()
  }
  video.preload = 'metadata'
  video.muted = true
  video.playsInline = true
  video.src = objectUrl

  video.onloadeddata = () => {
    try {
      const canvas = document.createElement('canvas')
      canvas.width = video.videoWidth || 1280
      canvas.height = video.videoHeight || 720
      const context = canvas.getContext('2d')
      if (!context) {
        throw new Error('无法创建视频封面')
      }
      context.drawImage(video, 0, 0, canvas.width, canvas.height)
      const posterUrl = canvas.toDataURL('image/jpeg', 0.82)
      cleanup()
      resolve(posterUrl)
    } catch (error) {
      cleanup()
      reject(error)
    }
  }
  video.onerror = () => {
    cleanup()
    reject(new Error('无法读取视频第一帧'))
  }
})

const createDefaultProject = (title = '互动电影草稿'): InteractiveMovieProject => {
  const startSceneId = uniqueId('scene-start')
  const nextSceneId = uniqueId('scene-next')
  const projectId = uniqueId('movie')
  return {
    id: projectId,
    title,
    updatedAt: new Date().toISOString(),
    selectedObject: { type: 'scene', id: startSceneId },
    viewport: { x: 360, y: 160, zoom: 1 },
    scenes: [
      {
        id: startSceneId,
        title: '雨夜来信',
        role: 'start',
        position: { x: 0, y: 0 },
        media: { kind: 'placeholder', status: 'mock' },
        script: {
          synopsis: '雨夜，主角在旧公寓门口收到一封没有署名的信。',
          visualDescription: '狭窄的老式公寓走廊，窗外下着雨，暖黄色楼道灯闪烁，地上有一封湿掉的信。',
          videoPrompt: 'cinematic rainy night apartment hallway, warm flickering light, mysterious envelope on the floor, slow push-in, suspense mood',
          promptParts: {
            subject: '年轻女性林夏站在老式公寓走廊，手里拿着一封湿掉的信',
            action: '她迟疑地拆开信封，抬头看向走廊尽头',
            scene: '雨夜，狭窄老公寓走廊，暖黄色灯光闪烁，地面潮湿',
            camera: '电影级中景缓慢推近，浅景深，轻微手持感',
            timeline: '[0-2s] 她发现门口的信；[2-5s] 她蹲下捡起信并拆开，神情紧张',
            style: '悬疑短片，写实，低饱和，高对比，环境声紧张',
            constraints: '不出现文字水印，不切换主角，不夸张恐怖',
          },
          lines: [
            { id: uniqueId('line'), speaker: '林夏', text: '这封信……为什么会在我家门口？' },
          ],
        },
      },
      {
        id: nextSceneId,
        title: '门后的声音',
        role: 'middle',
        position: { x: 480, y: 90 },
        media: { kind: 'placeholder', status: 'mock' },
        script: {
          synopsis: '主角拆开信后，隔壁空置已久的房间传来轻轻的敲门声。',
          visualDescription: '镜头贴近主角手中的信纸，字迹慢慢显现；远处传来敲门声，走廊尽头的门缝透出蓝光。',
          videoPrompt: 'close-up of wet paper letter, ink appearing slowly, empty hallway door with blue light leak, subtle horror, cinematic shallow depth of field',
          promptParts: {
            subject: '林夏站在走廊中央，手中拿着展开的信纸',
            action: '她被身后的敲门声惊到，缓慢转身',
            scene: '老公寓走廊尽头的空房间门缝透出蓝光，空气潮湿',
            camera: '从信纸特写切到主角背影，随后缓慢拉远',
            timeline: '[0-2s] 信纸字迹显现；[2-5s] 远处响起敲门声，主角缓慢转身',
            style: '悬疑电影，冷暖光对比，克制恐怖，真实质感',
            constraints: '不出现额外角色，不出现字幕水印，主角服装和上一场保持一致',
          },
          lines: [
            { id: uniqueId('line'), speaker: '林夏', text: '可身后的门，已经响了。' },
          ],
        },
      },
    ],
    choices: [
      {
        id: uniqueId('choice'),
        fromSceneId: startSceneId,
        toSceneId: nextSceneId,
        label: '打开那封信',
        trigger: 'after_scene',
      },
    ],
  }
}

const createDraftScene = (title: string, position: { x: number; y: number }): SceneNode => ({
  id: uniqueId('scene'),
  title,
  role: 'middle',
  position,
  media: { kind: 'placeholder', status: 'mock' },
  script: {
    synopsis: '补充这个场景要发生的关键事件。',
    visualDescription: '描述画面、人物位置、镜头运动和情绪氛围。',
    videoPrompt: 'describe the cinematic shot, action, mood and camera movement',
    promptParts: defaultPromptParts(title),
    lines: [{ id: uniqueId('line'), speaker: '角色', text: '新的剧情片段从这里开始。' }],
  },
})

const loadWorkspace = (): StoredWorkspace => {
  if (typeof window === 'undefined') {
    const project = createDefaultProject()
    return { activeProjectId: project.id, projects: [project] }
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as StoredWorkspace
      if (Array.isArray(parsed.projects) && parsed.projects.length > 0) {
        const activeProject = parsed.projects.find((project) => project.id === parsed.activeProjectId) ?? parsed.projects[0]
        return { activeProjectId: activeProject.id, projects: parsed.projects }
      }
    }
  } catch {
    window.localStorage.removeItem(STORAGE_KEY)
  }
  const project = createDefaultProject()
  return { activeProjectId: project.id, projects: [project] }
}

const normalizeProjectChoices = (project: InteractiveMovieProject): InteractiveMovieProject => {
  const choices = project.choices
    .map((choice) => {
      if (choice.fromSceneId !== choice.toSceneId) return choice
      const fallbackTarget = project.scenes.find((scene) => scene.id !== choice.fromSceneId)
      return fallbackTarget ? { ...choice, toSceneId: fallbackTarget.id } : null
    })
    .filter((choice): choice is ChoiceEdge => choice !== null)
  return { ...project, choices }
}

const cloudReplicaKey = (projectId: string) => `${CLOUD_REPLICA_PREFIX}${projectId}`
const draftReplicaKey = (projectId: string) => `${DRAFT_REPLICA_PREFIX}${projectId}`

const hasCloudCopy = (project: InteractiveMovieProject) => Boolean(project.version && project.contentHash)

const isMissingCloudProjectError = (error: unknown) => {
  if (!isAxiosError(error) || error.response?.status !== 404) return false
  const payload = error.response.data as { detail?: unknown } | undefined
  return payload?.detail === MISSING_PROJECT_DETAIL
}

const readProjectReplica = (key: string): InteractiveMovieProject | null => {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? JSON.parse(raw) as InteractiveMovieProject : null
  } catch {
    window.localStorage.removeItem(key)
    return null
  }
}

const removeProjectReplicas = (projectId: string) => {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(cloudReplicaKey(projectId))
  window.localStorage.removeItem(draftReplicaKey(projectId))
}

const cleanupProjectReplicasOutside = (projectIdsToKeep: Set<string>) => {
  if (typeof window === 'undefined') return
  const staleProjectIds = new Set<string>()
  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index)
    if (!key) continue
    if (key.startsWith(CLOUD_REPLICA_PREFIX)) {
      const projectId = key.slice(CLOUD_REPLICA_PREFIX.length)
      if (!projectIdsToKeep.has(projectId)) staleProjectIds.add(projectId)
    }
    if (key.startsWith(DRAFT_REPLICA_PREFIX)) {
      const projectId = key.slice(DRAFT_REPLICA_PREFIX.length)
      if (!projectIdsToKeep.has(projectId)) staleProjectIds.add(projectId)
    }
  }
  staleProjectIds.forEach(removeProjectReplicas)
}

const writeProjectReplica = (key: string, project: InteractiveMovieProject) => {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(key, JSON.stringify(project))
}

const persistWorkspaceLocally = (workspace: StoredWorkspace) => {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(workspace))
  workspace.projects.forEach((project) => {
    writeProjectReplica(draftReplicaKey(project.id), project)
  })
}

const withCloudMeta = (
  document: InteractiveMovieProject,
  version: number,
  contentHash: string,
  cloudUpdatedAt: string,
): InteractiveMovieProject => ({
  ...document,
  version,
  contentHash,
  cloudUpdatedAt,
  updatedAt: document.updatedAt || cloudUpdatedAt,
})

const flattenScene = (scene: SceneNode, sortOrder: number): Record<string, unknown> => ({
  id: scene.id,
  title: scene.title,
  role: scene.role,
  positionX: scene.position.x,
  positionY: scene.position.y,
  synopsis: scene.script.synopsis,
  visualDescription: scene.script.visualDescription,
  videoPrompt: scene.script.videoPrompt,
  promptSubject: scene.script.promptParts?.subject ?? '',
  promptAction: scene.script.promptParts?.action ?? '',
  promptScene: scene.script.promptParts?.scene ?? '',
  promptCamera: scene.script.promptParts?.camera ?? '',
  promptTimeline: scene.script.promptParts?.timeline ?? '',
  promptStyle: scene.script.promptParts?.style ?? '',
  promptConstraints: scene.script.promptParts?.constraints ?? '',
  mediaKind: scene.media.kind,
  mediaUrl: scene.media.url ?? '',
  mediaObjectKey: scene.media.objectKey ?? '',
  mediaStorageUri: scene.media.storageUri ?? '',
  posterUrl: scene.media.posterUrl ?? '',
  mediaStatus: scene.media.status,
  sortOrder,
})

const flattenChoice = (choice: ChoiceEdge, sortOrder: number): Record<string, unknown> => ({
  id: choice.id,
  fromSceneId: choice.fromSceneId,
  toSceneId: choice.toSceneId,
  label: choice.label,
  trigger: choice.trigger,
  offsetY: choice.offsetY ?? 0,
  sortOrder,
})

const flattenLine = (sceneId: string, line: ScriptLine, sortOrder: number): Record<string, unknown> => ({
  id: line.id,
  sceneId,
  speaker: line.speaker,
  text: line.text,
  sortOrder,
})

const shallowChanged = (before: Record<string, unknown> | undefined, after: Record<string, unknown>) => (
  !before || Object.keys(after).some((key) => before[key] !== after[key])
)

const buildProjectPatch = (base: InteractiveMovieProject, draft: InteractiveMovieProject): InteractiveMovieProjectPatch => {
  const baseScenes = new Map(base.scenes.map((scene, index) => [scene.id, flattenScene(scene, index)]))
  const draftScenes = new Map(draft.scenes.map((scene, index) => [scene.id, flattenScene(scene, index)]))
  const baseChoices = new Map(base.choices.map((choice, index) => [choice.id, flattenChoice(choice, index)]))
  const draftChoices = new Map(draft.choices.map((choice, index) => [choice.id, flattenChoice(choice, index)]))
  const baseLines = new Map<string, Record<string, unknown>>()
  const draftLines = new Map<string, Record<string, unknown>>()
  base.scenes.forEach((scene) => scene.script.lines.forEach((line, index) => baseLines.set(line.id, flattenLine(scene.id, line, index))))
  draft.scenes.forEach((scene) => scene.script.lines.forEach((line, index) => draftLines.set(line.id, flattenLine(scene.id, line, index))))

  return {
    base_version: base.version ?? 0,
    base_hash: base.contentHash ?? '',
    project: base.title !== draft.title ? { title: draft.title } : {},
    scenes: {
      upsert: [...draftScenes.values()].filter((scene) => shallowChanged(baseScenes.get(String(scene.id)), scene)),
      delete: [...baseScenes.keys()].filter((id) => !draftScenes.has(id)),
    },
    choices: {
      upsert: [...draftChoices.values()].filter((choice) => shallowChanged(baseChoices.get(String(choice.id)), choice)),
      delete: [...baseChoices.keys()].filter((id) => !draftChoices.has(id)),
    },
    script_lines: {
      upsert: [...draftLines.values()].filter((line) => shallowChanged(baseLines.get(String(line.id)), line)),
      delete: [...baseLines.keys()].filter((id) => !draftLines.has(id)),
    },
    viewport: (
      base.viewport.x !== draft.viewport.x || base.viewport.y !== draft.viewport.y || base.viewport.zoom !== draft.viewport.zoom
        ? { ...draft.viewport }
        : {}
    ),
    selected_object: (
      base.selectedObject.type !== draft.selectedObject.type || base.selectedObject.id !== draft.selectedObject.id
        ? { type: draft.selectedObject.type, id: draft.selectedObject.id }
        : {}
    ),
  }
}

const patchHasChanges = (patch: InteractiveMovieProjectPatch) => (
  Object.keys(patch.project).length > 0
  || Object.keys(patch.viewport).length > 0
  || Object.keys(patch.selected_object).length > 0
  || patch.scenes.upsert.length > 0
  || patch.scenes.delete.length > 0
  || patch.choices.upsert.length > 0
  || patch.choices.delete.length > 0
  || patch.script_lines.upsert.length > 0
  || patch.script_lines.delete.length > 0
)

const localDraftIsNewer = (draft: InteractiveMovieProject, cloud: InteractiveMovieProject) => {
  const draftTime = Date.parse(draft.updatedAt)
  const cloudTime = Date.parse(cloud.cloudUpdatedAt ?? cloud.updatedAt)
  return Number.isFinite(draftTime) && Number.isFinite(cloudTime) && draftTime > cloudTime
}

const mergeDraftWithCloudMeta = (
  draft: InteractiveMovieProject,
  cloud: InteractiveMovieProject,
): InteractiveMovieProject => ({
  ...draft,
  version: cloud.version,
  contentHash: cloud.contentHash,
  cloudUpdatedAt: cloud.cloudUpdatedAt,
})

const firstSelectableObject = (scenes: SceneNode[], choices: ChoiceEdge[]): SelectedObject => {
  if (scenes[0]) return { type: 'scene', id: scenes[0].id }
  if (choices[0]) return { type: 'choice', id: choices[0].id }
  return { type: 'scene', id: '' }
}

export default function InteractiveMoviePage() {
  const { message, modal } = App.useApp()
  const canvasRef = useRef<HTMLDivElement>(null)
  const interactionRef = useRef<InteractionState | null>(null)
  const lastCanvasSceneIdByProjectRef = useRef<Record<string, string>>({})

  const [workspace, setWorkspace] = useState<StoredWorkspace>(() => loadWorkspace())
  const [workspaceCollapsed, setWorkspaceCollapsed] = useState(false)
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false)
  const [bottomToolbarCollapsed, setBottomToolbarCollapsed] = useState(false)
  const [promptTemplate, setPromptTemplate] = useState<PromptTemplate | null>(null)
  const [uploadBySceneId, setUploadBySceneId] = useState<Record<string, SceneUploadState>>({})
  const [cloudReady, setCloudReady] = useState(false)
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncMessage, setSyncMessage] = useState('本地草稿')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewSceneId, setPreviewSceneId] = useState('')
  const [previewLineIndex, setPreviewLineIndex] = useState(0)
  const [previewChoicesVisible, setPreviewChoicesVisible] = useState(false)

  const activeProject = workspace.projects.find((project) => project.id === workspace.activeProjectId) ?? workspace.projects[0]
  const scenes = activeProject.scenes
  const choices = activeProject.choices
  const selectedObject = activeProject.selectedObject
  const viewport = activeProject.viewport

  const selectedScene = selectedObject.type === 'scene'
    ? scenes.find((scene) => scene.id === selectedObject.id) ?? null
    : null
  const selectedChoice = selectedObject.type === 'choice'
    ? choices.find((choice) => choice.id === selectedObject.id) ?? null
    : null
  const sceneMap = useMemo(() => new Map(scenes.map((scene) => [scene.id, scene])), [scenes])
  const startScene = scenes.find((scene) => scene.role === 'start') ?? scenes[0]
  const previewScene = scenes.find((scene) => scene.id === previewSceneId) ?? startScene
  const outgoingPreviewChoices = choices.filter((choice) => (
    choice.fromSceneId === previewScene?.id && sceneMap.has(choice.toSceneId)
  ))
  const currentPreviewLine = previewScene?.script.lines[previewLineIndex]

  useEffect(() => {
    persistWorkspaceLocally(workspace)
  }, [workspace])

  useEffect(() => {
    let cancelled = false
    const loadCloudWorkspace = async () => {
      try {
        const summaries = await listInteractiveMovieProjects()
        if (cancelled) return
        if (summaries.length === 0) {
          const localProject = workspace.projects.find((project) => !hasCloudCopy(project))
          if (!localProject) {
            const project = createDefaultProject('互动电影草稿')
            cleanupProjectReplicasOutside(new Set([project.id]))
            writeProjectReplica(draftReplicaKey(project.id), project)
            setWorkspace({ activeProjectId: project.id, projects: [project] })
            setSyncMessage('云端暂无项目')
            return
          }
          cleanupProjectReplicasOutside(new Set([localProject.id]))
          const created = await createInteractiveMovieProject(localProject.title, localProject)
          if (cancelled) return
          const project = withCloudMeta(created.document, created.version, created.content_hash, created.updated_at)
          cleanupProjectReplicasOutside(new Set([project.id]))
          writeProjectReplica(cloudReplicaKey(project.id), project)
          writeProjectReplica(draftReplicaKey(project.id), project)
          setWorkspace({ activeProjectId: project.id, projects: [project] })
          setSyncMessage('已连接云端')
          return
        }
        const detailResults = await Promise.all(summaries.map(async (summary) => {
          try {
            return await getInteractiveMovieProject<InteractiveMovieProject>(summary.id)
          } catch (error) {
            if (isMissingCloudProjectError(error)) {
              removeProjectReplicas(summary.id)
              return null
            }
            throw error
          }
        }))
        if (cancelled) return
        const details = detailResults.filter((detail): detail is InteractiveMovieProjectDetail<InteractiveMovieProject> => detail !== null)
        if (details.length === 0) {
          const project = createDefaultProject('互动电影草稿')
          cleanupProjectReplicasOutside(new Set([project.id]))
          writeProjectReplica(draftReplicaKey(project.id), project)
          setWorkspace({ activeProjectId: project.id, projects: [project] })
          setSyncMessage('云端暂无项目')
          return
        }
        const projects = details.map((detail) => {
          const cloudProject = withCloudMeta(detail.document, detail.version, detail.content_hash, detail.updated_at)
          writeProjectReplica(cloudReplicaKey(cloudProject.id), cloudProject)
          const draftProject = readProjectReplica(draftReplicaKey(cloudProject.id))
          if (draftProject) {
            const hasLocalChanges = patchHasChanges(buildProjectPatch(cloudProject, draftProject))
            if (hasLocalChanges && localDraftIsNewer(draftProject, cloudProject)) {
              return mergeDraftWithCloudMeta(draftProject, cloudProject)
            }
          }
          writeProjectReplica(draftReplicaKey(cloudProject.id), cloudProject)
          return cloudProject
        })
        cleanupProjectReplicasOutside(new Set(projects.map((project) => project.id)))
        const activeId = projects.some((project) => project.id === workspace.activeProjectId)
          ? workspace.activeProjectId
          : projects[0].id
        setWorkspace({ activeProjectId: activeId, projects })
        setSyncMessage('已连接云端')
      } catch (error) {
        setSyncMessage(resolveErrorMessage(error))
      } finally {
        if (!cancelled) setCloudReady(true)
      }
    }
    void loadCloudWorkspace()
    return () => {
      cancelled = true
    }
    // only bootstrap once from the best local snapshot available at mount time
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    setWorkspace((current) => {
      const normalizedProjects = current.projects.map(normalizeProjectChoices)
      const changed = normalizedProjects.some((project, index) => project.choices.length !== current.projects[index].choices.length
        || project.choices.some((choice, choiceIndex) => choice.toSceneId !== current.projects[index].choices[choiceIndex]?.toSceneId))
      return changed ? { ...current, projects: normalizedProjects } : current
    })
  }, [])

  useEffect(() => {
    void getInteractiveMoviePromptTemplate()
      .then(setPromptTemplate)
      .catch(() => {
        setPromptTemplate(null)
      })
  }, [])

  const updateActiveProject = (updater: (project: InteractiveMovieProject) => InteractiveMovieProject) => {
    setWorkspace((current) => ({
      ...current,
      projects: current.projects.map((project) => (
        project.id === current.activeProjectId
          ? { ...updater(project), updatedAt: new Date().toISOString() }
          : project
      )),
    }))
  }

  const updateScene = (sceneId: string, updater: (scene: SceneNode) => SceneNode) => {
    updateActiveProject((project) => ({
      ...project,
      scenes: project.scenes.map((scene) => (scene.id === sceneId ? updater(scene) : scene)),
    }))
  }

  const updateChoice = (choiceId: string, updater: (choice: ChoiceEdge) => ChoiceEdge) => {
    updateActiveProject((project) => ({
      ...project,
      choices: project.choices.map((choice) => (choice.id === choiceId ? updater(choice) : choice)),
    }))
  }

  const setSelectedObject = (nextSelectedObject: SelectedObject) => {
    updateActiveProject((project) => ({ ...project, selectedObject: nextSelectedObject }))
  }

  const selectCanvasScene = (sceneId: string) => {
    lastCanvasSceneIdByProjectRef.current[activeProject.id] = sceneId
    setSelectedObject({ type: 'scene', id: sceneId })
  }

  const setViewport = (nextViewport: CanvasViewport | ((current: CanvasViewport) => CanvasViewport)) => {
    updateActiveProject((project) => ({
      ...project,
      viewport: typeof nextViewport === 'function' ? nextViewport(project.viewport) : nextViewport,
    }))
  }

  const createProject = () => {
    const project = createDefaultProject(`互动电影 ${workspace.projects.length + 1}`)
    writeProjectReplica(draftReplicaKey(project.id), project)
    setWorkspace((current) => ({
      activeProjectId: project.id,
      projects: [project, ...current.projects],
    }))
    setSyncMessage('新项目未保存')
    message.success('已创建新项目')
  }

  const switchProject = (projectId: string) => {
    setWorkspace((current) => ({ ...current, activeProjectId: projectId }))
  }

  const cleanupMissingCloudProject = useCallback((projectId: string) => {
    removeProjectReplicas(projectId)
    setWorkspace((current) => {
      const remaining = current.projects.filter((item) => item.id !== projectId)
      if (remaining.length > 0) {
        const nextActiveId = current.activeProjectId === projectId ? remaining[0].id : current.activeProjectId
        return { activeProjectId: nextActiveId, projects: remaining }
      }
      const nextProject = createDefaultProject('互动电影草稿')
      writeProjectReplica(draftReplicaKey(nextProject.id), nextProject)
      return { activeProjectId: nextProject.id, projects: [nextProject] }
    })
    setSyncMessage('云端项目不存在，已清理本地副本')
  }, [])

  const confirmDeleteProject = (project: InteractiveMovieProject) => {
    modal.confirm({
      title: `删除项目「${project.title}」？`,
      content: '此操作无法撤回。项目会从云端和本地草稿中删除。',
      okText: '确认删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        try {
          if (hasCloudCopy(project)) {
            await deleteInteractiveMovieProject(project.id)
          }
          removeProjectReplicas(project.id)
          setWorkspace((current) => {
            const remaining = current.projects.filter((item) => item.id !== project.id)
            if (remaining.length > 0) {
              const nextActiveId = current.activeProjectId === project.id ? remaining[0].id : current.activeProjectId
              return { activeProjectId: nextActiveId, projects: remaining }
            }
            const nextProject = createDefaultProject('互动电影草稿')
            writeProjectReplica(draftReplicaKey(nextProject.id), nextProject)
            return { activeProjectId: nextProject.id, projects: [nextProject] }
          })
          setSyncMessage('项目已删除')
          message.success('项目已删除')
        } catch (error) {
          if (isMissingCloudProjectError(error)) {
            cleanupMissingCloudProject(project.id)
            message.warning('云端项目不存在，已清理本地副本')
            return
          }
          message.error(resolveErrorMessage(error))
          throw error
        }
      },
    })
  }

  const confirmRenameProject = (project: InteractiveMovieProject) => {
    let nextTitle = project.title
    modal.confirm({
      title: `重命名项目「${project.title}」`,
      content: (
        <Input
          autoFocus
          defaultValue={project.title}
          maxLength={80}
          onChange={(event) => {
            nextTitle = event.target.value
          }}
          placeholder="输入项目名称"
        />
      ),
      okText: '保存',
      cancelText: '取消',
      async onOk() {
        const title = nextTitle.trim()
        if (!title) {
          message.warning('项目名称不能为空')
          throw new Error('项目名称不能为空')
        }

        try {
          const hasCloudCopy = Boolean(project.version && project.contentHash)
          if (hasCloudCopy) {
            const renamed = await renameInteractiveMovieProject<InteractiveMovieProject>(project.id, title)
            const nextProject = withCloudMeta(
              renamed.document,
              renamed.version,
              renamed.content_hash,
              renamed.updated_at,
            )
            writeProjectReplica(cloudReplicaKey(nextProject.id), nextProject)
            writeProjectReplica(draftReplicaKey(nextProject.id), nextProject)
            setWorkspace((current) => ({
              ...current,
              projects: current.projects.map((item) => (item.id === nextProject.id ? nextProject : item)),
            }))
            setSyncMessage('项目已重命名')
            message.success('项目已重命名')
            return
          }

          const nextProject = { ...project, title, updatedAt: new Date().toISOString() }
          writeProjectReplica(draftReplicaKey(nextProject.id), nextProject)
          setWorkspace((current) => ({
            ...current,
            projects: current.projects.map((item) => (item.id === nextProject.id ? nextProject : item)),
          }))
          setSyncMessage('本地草稿已重命名')
          message.success('项目已重命名')
        } catch (error) {
          message.error(resolveErrorMessage(error))
          throw error
        }
      },
    })
  }

  const renameProject = (title: string) => {
    updateActiveProject((project) => ({ ...project, title }))
  }

  const beginPan = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'pan',
      pointerId: event.pointerId,
      startClient: { x: event.clientX, y: event.clientY },
      startViewport: viewport,
    }
  }

  const beginNodeDrag = (event: ReactPointerEvent<HTMLDivElement>, sceneId: string) => {
    if (event.button !== 0) return
    event.stopPropagation()
    const scene = scenes.find((item) => item.id === sceneId)
    if (!scene) return
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'node',
      pointerId: event.pointerId,
      sceneId,
      startClient: { x: event.clientX, y: event.clientY },
      startPosition: scene.position,
    }
    setSelectedObject({ type: 'scene', id: sceneId })
  }

  const beginChoiceDrag = (event: ReactPointerEvent<HTMLButtonElement>, choiceId: string) => {
    if (event.button !== 0) return
    event.stopPropagation()
    const choice = choices.find((item) => item.id === choiceId)
    if (!choice) return
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'choice',
      pointerId: event.pointerId,
      choiceId,
      startClient: { x: event.clientX, y: event.clientY },
      startOffsetY: choice.offsetY ?? 0,
    }
    setSelectedObject({ type: 'choice', id: choiceId })
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const interaction = interactionRef.current
    if (!interaction || interaction.pointerId !== event.pointerId) return
    if (interaction.type === 'pan') {
      setViewport({
        ...interaction.startViewport,
        x: interaction.startViewport.x + event.clientX - interaction.startClient.x,
        y: interaction.startViewport.y + event.clientY - interaction.startClient.y,
      })
      return
    }
    if (interaction.type === 'node') {
      const dx = (event.clientX - interaction.startClient.x) / viewport.zoom
      const dy = (event.clientY - interaction.startClient.y) / viewport.zoom
      updateScene(interaction.sceneId, (scene) => ({
        ...scene,
        position: {
          x: interaction.startPosition.x + dx,
          y: interaction.startPosition.y + dy,
        },
      }))
      return
    }
    if (interaction.type === 'choice') {
      const dy = (event.clientY - interaction.startClient.y) / viewport.zoom
      updateChoice(interaction.choiceId, (choice) => ({
        ...choice,
        offsetY: interaction.startOffsetY + dy,
      }))
    }
  }

  const endPointerInteraction = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (interactionRef.current?.pointerId === event.pointerId) {
      interactionRef.current = null
    }
  }

  const handleWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    event.preventDefault()
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const nextZoom = clamp(viewport.zoom - event.deltaY * 0.0012, MIN_ZOOM, MAX_ZOOM)
    const canvasX = (event.clientX - rect.left - viewport.x) / viewport.zoom
    const canvasY = (event.clientY - rect.top - viewport.y) / viewport.zoom
    setViewport({
      x: event.clientX - rect.left - canvasX * nextZoom,
      y: event.clientY - rect.top - canvasY * nextZoom,
      zoom: nextZoom,
    })
  }

  const zoomBy = (delta: number) => {
    setViewport((current) => ({ ...current, zoom: clamp(current.zoom + delta, MIN_ZOOM, MAX_ZOOM) }))
  }

  const fitView = () => {
    if (!canvasRef.current || scenes.length === 0) return
    const rect = canvasRef.current.getBoundingClientRect()
    const minX = Math.min(...scenes.map((scene) => scene.position.x))
    const minY = Math.min(...scenes.map((scene) => scene.position.y))
    const maxX = Math.max(...scenes.map((scene) => scene.position.x + NODE_WIDTH))
    const maxY = Math.max(...scenes.map((scene) => scene.position.y + NODE_HEIGHT))
    const contentWidth = maxX - minX
    const contentHeight = maxY - minY
    const zoom = clamp(Math.min((rect.width - 160) / contentWidth, (rect.height - 160) / contentHeight), MIN_ZOOM, 1.2)
    setViewport({
      x: rect.width / 2 - (minX + contentWidth / 2) * zoom,
      y: rect.height / 2 - (minY + contentHeight / 2) * zoom,
      zoom,
    })
  }

  const defaultNewScenePosition = () => ({
    x: (-viewport.x + 260) / viewport.zoom,
    y: (-viewport.y + 180) / viewport.zoom,
  })

  const addScene = () => {
    const scene = createDraftScene(`新场景 ${scenes.length + 1}`, defaultNewScenePosition())
    updateActiveProject((project) => ({
      ...project,
      scenes: [...project.scenes, scene],
      selectedObject: { type: 'scene', id: scene.id },
    }))
  }

  const createSceneForChoice = (choiceId: string, endpoint: 'from' | 'to') => {
    updateActiveProject((project) => {
      const choice = project.choices.find((item) => item.id === choiceId)
      if (!choice) return project
      const fromScene = project.scenes.find((scene) => scene.id === choice.fromSceneId)
      const toScene = project.scenes.find((scene) => scene.id === choice.toSceneId)
      const anchorScene = endpoint === 'to' ? fromScene ?? toScene : toScene ?? fromScene
      const direction = endpoint === 'to' ? 1 : -1
      const position = anchorScene
        ? {
          x: anchorScene.position.x + direction * (NODE_WIDTH + 180),
          y: anchorScene.position.y + 40,
        }
        : defaultNewScenePosition()
      const scene = createDraftScene(`新场景 ${project.scenes.length + 1}`, position)
      return {
        ...project,
        scenes: [...project.scenes, scene],
        choices: project.choices.map((item) => (
          item.id === choiceId
            ? {
              ...item,
              fromSceneId: endpoint === 'from' ? scene.id : item.fromSceneId,
              toSceneId: endpoint === 'to' ? scene.id : item.toSceneId,
            }
            : item
        )),
        selectedObject: { type: 'choice', id: choiceId },
      }
    })
  }

  const addChoice = () => {
    const lastCanvasSceneId = lastCanvasSceneIdByProjectRef.current[activeProject.id]
    const fromScene = scenes.find((scene) => scene.id === lastCanvasSceneId) ?? selectedScene ?? scenes[0]
    if (!fromScene) {
      message.warning('请先添加或选择一个场景')
      return
    }
    const choiceId = uniqueId('choice')
    const siblingCount = choices.filter((choice) => (
      choice.fromSceneId === fromScene.id && !choice.toSceneId
    )).length
    updateActiveProject((project) => ({
      ...project,
      choices: [
        ...project.choices,
        {
          id: choiceId,
          fromSceneId: fromScene.id,
          toSceneId: '',
          label: siblingCount > 0 ? `新的选择 ${siblingCount + 1}` : '新的选择',
          trigger: 'after_scene',
        },
      ],
      selectedObject: { type: 'choice', id: choiceId },
    }))
  }

  const deleteChoice = (choiceId: string) => {
    updateActiveProject((project) => {
      const nextChoices = project.choices.filter((choice) => choice.id !== choiceId)
      const selectedObjectWasDeleted = project.selectedObject.type === 'choice' && project.selectedObject.id === choiceId
      return {
        ...project,
        choices: nextChoices,
        selectedObject: selectedObjectWasDeleted
          ? firstSelectableObject(project.scenes, nextChoices)
          : project.selectedObject,
      }
    })
  }

  const confirmDeleteChoice = (choiceId: string) => {
    const choice = choices.find((item) => item.id === choiceId)
    if (!choice) return
    modal.confirm({
      title: `删除选择「${choice.label}」？`,
      content: '删除后会移除这条选择连线。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk() {
        deleteChoice(choiceId)
        message.success('选择已删除')
      },
    })
  }

  const deleteScene = (sceneId: string) => {
    updateActiveProject((project) => {
      const deletedChoiceIds = new Set(
        project.choices
          .filter((choice) => choice.fromSceneId === sceneId || choice.toSceneId === sceneId)
          .map((choice) => choice.id),
      )
      const nextScenes = project.scenes.filter((scene) => scene.id !== sceneId)
      const nextChoices = project.choices.filter((choice) => !deletedChoiceIds.has(choice.id))
      const selectedObjectWasDeleted = (
        (project.selectedObject.type === 'scene' && project.selectedObject.id === sceneId)
        || (project.selectedObject.type === 'choice' && deletedChoiceIds.has(project.selectedObject.id))
      )
      const nextSelectedObject = selectedObjectWasDeleted
        ? firstSelectableObject(nextScenes, nextChoices)
        : project.selectedObject
      if (lastCanvasSceneIdByProjectRef.current[project.id] === sceneId) {
        lastCanvasSceneIdByProjectRef.current[project.id] = nextSelectedObject.type === 'scene' ? nextSelectedObject.id : ''
      }
      return {
        ...project,
        scenes: nextScenes,
        choices: nextChoices,
        selectedObject: nextSelectedObject,
      }
    })
  }

  const confirmDeleteScene = (sceneId: string) => {
    const scene = scenes.find((item) => item.id === sceneId)
    if (!scene) return
    const connectedChoiceCount = choices.filter((choice) => (
      choice.fromSceneId === sceneId || choice.toSceneId === sceneId
    )).length
    modal.confirm({
      title: `删除场景「${scene.title}」？`,
      content: connectedChoiceCount > 0
        ? `会同时删除 ${connectedChoiceCount} 个关联选择。`
        : '删除后会从画布中移除这个场景节点。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk() {
        deleteScene(sceneId)
        message.success('场景已删除')
      },
    })
  }

  const addLine = (sceneId: string) => {
    updateScene(sceneId, (scene) => ({
      ...scene,
      script: {
        ...scene.script,
        lines: [
          ...scene.script.lines,
          {
            id: uniqueId('line'),
            speaker: '角色',
            text: '输入一句新的台词。',
          },
        ],
      },
    }))
  }

  const deleteLine = (sceneId: string, lineId: string) => {
    updateScene(sceneId, (scene) => ({
      ...scene,
      script: {
        ...scene.script,
        lines: scene.script.lines.filter((line) => line.id !== lineId),
      },
    }))
  }

  const startPreview = (sceneId = startScene?.id) => {
    if (!sceneId) return
    setPreviewSceneId(sceneId)
    setPreviewLineIndex(0)
    setPreviewChoicesVisible(false)
    setPreviewOpen(true)
  }

  const advancePreview = () => {
    if (!previewScene) return
    if (previewLineIndex < previewScene.script.lines.length - 1) {
      setPreviewLineIndex((index) => index + 1)
      return
    }
    if (outgoingPreviewChoices.length > 0) {
      setPreviewChoicesVisible(true)
      return
    }
    message.info('预览已结束')
  }

  const choosePreviewEdge = (choice: ChoiceEdge) => {
    if (!sceneMap.has(choice.toSceneId)) return
    setPreviewSceneId(choice.toSceneId)
    setPreviewLineIndex(0)
    setPreviewChoicesVisible(false)
  }

  const saveDraft = useCallback(async () => {
    const draft = activeProject
    if (!draft || saving) return
    writeProjectReplica(draftReplicaKey(draft.id), draft)
    persistWorkspaceLocally(workspace)
    setSaving(true)
    try {
      const cloudBase = readProjectReplica(cloudReplicaKey(draft.id))
      if (!cloudBase?.version || !cloudBase.contentHash) {
        const created = await createInteractiveMovieProject(draft.title, draft)
        const project = withCloudMeta(created.document, created.version, created.content_hash, created.updated_at)
        writeProjectReplica(cloudReplicaKey(project.id), project)
        writeProjectReplica(draftReplicaKey(project.id), project)
        setWorkspace((current) => ({
          activeProjectId: project.id,
          projects: current.projects.map((item) => (item.id === draft.id ? project : item)),
        }))
        setSyncMessage('已保存到云端')
        message.success('已保存到云端')
        return
      }
      const patch = buildProjectPatch(cloudBase, draft)
      if (!patchHasChanges(patch)) {
        setSyncMessage('云端已是最新')
        message.success('云端已是最新')
        return
      }
      const saved = await patchInteractiveMovieProject<InteractiveMovieProject>(draft.id, patch)
      const project = withCloudMeta(saved.document, saved.version, saved.content_hash, saved.updated_at)
      writeProjectReplica(cloudReplicaKey(project.id), project)
      writeProjectReplica(draftReplicaKey(project.id), project)
      setWorkspace((current) => ({
        ...current,
        projects: current.projects.map((item) => (item.id === project.id ? project : item)),
      }))
      setSyncMessage('已保存到云端')
      message.success('已保存到云端')
    } catch (error) {
      if (isMissingCloudProjectError(error)) {
        cleanupMissingCloudProject(draft.id)
        message.warning('云端项目不存在，已清理本地副本')
        return
      }
      const text = resolveErrorMessage(error)
      setSyncMessage(text)
      message.error(text)
    } finally {
      setSaving(false)
    }
  }, [activeProject, cleanupMissingCloudProject, message, saving, workspace])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault()
        event.stopPropagation()
        if (event.repeat) return
        void saveDraft()
      }
    }
    window.addEventListener('keydown', handleKeyDown, true)
    return () => window.removeEventListener('keydown', handleKeyDown, true)
  }, [saveDraft])

  useEffect(() => {
    if (!cloudReady || !activeProject?.contentHash) return undefined
    const syncOnce = async () => {
      if (syncing || saving) return
      setSyncing(true)
      try {
        const remote = await getInteractiveMovieSyncState(activeProject.id)
        const cloudBase = readProjectReplica(cloudReplicaKey(activeProject.id))
        if (!cloudBase || remote.content_hash === cloudBase.contentHash) {
          setSyncMessage('云端已同步')
          return
        }
        const draft = readProjectReplica(draftReplicaKey(activeProject.id)) ?? activeProject
        const localPatch = buildProjectPatch(cloudBase, draft)
        if (patchHasChanges(localPatch)) {
          setSyncMessage('云端有新版本，本地有未保存修改')
          return
        }
        const latest = await getInteractiveMovieProject<InteractiveMovieProject>(activeProject.id)
        const project = withCloudMeta(latest.document, latest.version, latest.content_hash, latest.updated_at)
        writeProjectReplica(cloudReplicaKey(project.id), project)
        writeProjectReplica(draftReplicaKey(project.id), project)
        setWorkspace((current) => ({
          ...current,
          projects: current.projects.map((item) => (item.id === project.id ? project : item)),
        }))
        setSyncMessage('已自动同步云端')
      } catch (error) {
        if (isMissingCloudProjectError(error)) {
          cleanupMissingCloudProject(activeProject.id)
          return
        }
        setSyncMessage('云端同步检查失败')
      } finally {
        setSyncing(false)
      }
    }
    const timer = window.setInterval(() => {
      void syncOnce()
    }, 60_000)
    return () => window.clearInterval(timer)
  }, [activeProject, cleanupMissingCloudProject, cloudReady, saving, syncing])

  const uploadSceneVideo = async (scene: SceneNode, file: File) => {
    setUploadBySceneId((current) => ({
      ...current,
      [scene.id]: { status: 'uploading', message: '正在截取第一帧' },
    }))
    try {
      let posterUrl: string | undefined
      try {
        posterUrl = await captureVideoPoster(file)
      } catch {
        setUploadBySceneId((current) => ({
          ...current,
          [scene.id]: { status: 'uploading', message: '封面截取失败，继续上传视频' },
        }))
      }
      setUploadBySceneId((current) => ({
        ...current,
        [scene.id]: { status: 'uploading', message: '视频上传中' },
      }))
      const uploaded = await uploadInteractiveMovieVideo(file)
      if (!uploaded.url) {
        setUploadBySceneId((current) => ({
          ...current,
          [scene.id]: { status: 'failed', message: '上传成功，但没有返回可播放的视频 URL' },
        }))
        message.warning('上传成功，但没有返回可播放的视频 URL')
        return
      }
      updateScene(scene.id, (current) => ({
        ...current,
        media: {
          ...current.media,
          kind: 'video',
          status: 'ready',
          url: uploaded.url ?? undefined,
          objectKey: uploaded.object_key,
          storageUri: uploaded.storage_uri,
          posterUrl,
        },
      }))
      setUploadBySceneId((current) => ({
        ...current,
        [scene.id]: { status: 'ready', message: `已上传：${uploaded.filename}` },
      }))
      message.success('视频已上传')
    } catch (error) {
      const text = resolveErrorMessage(error)
      setUploadBySceneId((current) => ({
        ...current,
        [scene.id]: { status: 'failed', message: text },
      }))
      message.error(text)
    }
  }

  return (
    <div className={workspaceCollapsed ? 'interactive-movie-page workspace-collapsed' : 'interactive-movie-page'}>
      <aside className="movie-workspace-sidebar">
        <button
          type="button"
          className="movie-sidebar-collapse"
          onClick={() => setWorkspaceCollapsed((value) => !value)}
          aria-label={workspaceCollapsed ? '展开工作区' : '折叠工作区'}
        >
          {workspaceCollapsed ? <DoubleRightOutlined /> : <DoubleLeftOutlined />}
        </button>
        <div className="movie-sidebar-brand">
          <span className="movie-logo-mark"><VideoCameraOutlined /></span>
          <div className="movie-sidebar-brand-text">
            <Typography.Text className="movie-kicker">互动电影生成</Typography.Text>
            <Typography.Title level={5} className="movie-sidebar-title">工作区</Typography.Title>
          </div>
        </div>
        <Button block type="primary" icon={<PlusOutlined />} onClick={createProject} className="movie-new-project-button">
          新建项目
        </Button>
        <div className="movie-project-list">
          {workspace.projects.map((project) => (
            <div
              key={project.id}
              role="button"
              tabIndex={0}
              className={project.id === activeProject.id ? 'movie-project-item is-active' : 'movie-project-item'}
              onClick={() => switchProject(project.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  switchProject(project.id)
                }
              }}
            >
              <button
                type="button"
                className="movie-project-rename"
                aria-label={`重命名项目 ${project.title}`}
                onClick={(event) => {
                  event.stopPropagation()
                  confirmRenameProject(project)
                }}
              >
                <EditOutlined />
              </button>
              <button
                type="button"
                className="movie-project-delete"
                aria-label={`删除项目 ${project.title}`}
                onClick={(event) => {
                  event.stopPropagation()
                  confirmDeleteProject(project)
                }}
              >
                <DeleteOutlined />
              </button>
              <span className="movie-project-name">{project.title}</span>
              <span className="movie-project-meta">{project.scenes.length} 场景 · {project.choices.length} 选择</span>
            </div>
          ))}
        </div>
      </aside>

      <main className="movie-editor-shell">
        <header className="movie-topbar">
          <Flex align="center" gap={12} className="movie-project-heading">
            <div>
              <Typography.Text className="movie-kicker">云端项目 / GalGame 式编辑器 MVP</Typography.Text>
              <Input
                variant="borderless"
                value={activeProject.title}
                onChange={(event) => renameProject(event.target.value)}
                className="movie-title-input"
                aria-label="项目名"
              />
            </div>
          </Flex>
          <nav className="movie-top-nav" aria-label="主导航">
            <Link className="movie-top-nav-item" to="/agents">
              <MessageOutlined />
              <span>智能体</span>
            </Link>
            <Link className="movie-top-nav-item is-active" to="/interactive-movie">
              <VideoCameraOutlined />
              <span>工作空间</span>
            </Link>
          </nav>
          <Space wrap>
            <Tag className="movie-status-tag">{syncing ? '同步检查中' : syncMessage}</Tag>
            <Button icon={<SaveOutlined />} loading={saving} onClick={() => void saveDraft()}>保存</Button>
            <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => startPreview()}>预览</Button>
          </Space>
        </header>

        <section
          ref={canvasRef}
          className="movie-canvas"
          style={{
            '--movie-grid-x': `${viewport.x}px`,
            '--movie-grid-y': `${viewport.y}px`,
            '--movie-grid-size': `${24 * viewport.zoom}px`,
            '--movie-grid-major-size': `${120 * viewport.zoom}px`,
          } as CSSProperties}
          onPointerDown={beginPan}
          onPointerMove={handlePointerMove}
          onPointerUp={endPointerInteraction}
          onPointerCancel={endPointerInteraction}
          onWheel={handleWheel}
        >
          <div
            className="movie-canvas-stage"
            style={{
              transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`,
            }}
          >
            <svg className="movie-edge-layer">
              {choices.map((choice) => {
                const fromScene = sceneMap.get(choice.fromSceneId)
                const toScene = sceneMap.get(choice.toSceneId)
                if (!fromScene || !toScene) return null
                const siblingChoices = choices.filter((item) => (
                  item.fromSceneId === choice.fromSceneId && item.toSceneId === choice.toSceneId
                ))
                const siblingIndex = siblingChoices.findIndex((item) => item.id === choice.id)
                const siblingOffset = (siblingIndex - (siblingChoices.length - 1) / 2) * 46
                const choiceOffset = siblingOffset + (choice.offsetY ?? 0)
                const start = {
                  x: fromScene.position.x + NODE_WIDTH,
                  y: fromScene.position.y + NODE_HEIGHT * 0.5 + siblingOffset * 0.28,
                }
                const end = {
                  x: toScene.position.x,
                  y: toScene.position.y + NODE_HEIGHT * 0.5 + siblingOffset * 0.28,
                }
                const midX = (start.x + end.x) / 2
                const midY = (start.y + end.y) / 2 + choiceOffset
                const controlOffset = Math.max(150, Math.abs(end.x - start.x) * 0.34)
                const direction = end.x >= start.x ? 1 : -1
                const selected = selectedObject.type === 'choice' && selectedObject.id === choice.id
                return (
                  <g key={choice.id} className={selected ? 'movie-edge is-selected' : 'movie-edge'}>
                    <path
                      d={[
                        `M ${start.x} ${start.y}`,
                        `C ${start.x + controlOffset * direction} ${start.y}, ${midX - controlOffset * 0.28 * direction} ${midY}, ${midX} ${midY}`,
                        `C ${midX + controlOffset * 0.28 * direction} ${midY}, ${end.x - controlOffset * direction} ${end.y}, ${end.x} ${end.y}`,
                      ].join(' ')}
                      onClick={(event) => {
                        event.stopPropagation()
                        setSelectedObject({ type: 'choice', id: choice.id })
                      }}
                    />
                    <foreignObject x={midX - 88} y={midY - 22} width="176" height="44">
                      <div className="movie-choice-pill">
                        <button
                          type="button"
                          className="movie-choice-label"
                          onPointerDown={(event) => beginChoiceDrag(event, choice.id)}
                          onClick={() => setSelectedObject({ type: 'choice', id: choice.id })}
                        >
                          {choice.label}
                        </button>
                        <button
                          type="button"
                          className="movie-choice-delete"
                          title="删除选择"
                          aria-label={`删除选择 ${choice.label}`}
                          onPointerDown={(event) => event.stopPropagation()}
                          onClick={(event) => {
                            event.stopPropagation()
                            confirmDeleteChoice(choice.id)
                          }}
                        >
                          <DeleteOutlined />
                        </button>
                      </div>
                    </foreignObject>
                  </g>
                )
              })}
            </svg>

            {scenes.map((scene) => {
              const selected = selectedObject.type === 'scene' && selectedObject.id === scene.id
              return (
                <div
                  key={scene.id}
                  className={selected ? 'movie-scene-node is-selected' : 'movie-scene-node'}
                  style={{ left: scene.position.x, top: scene.position.y }}
                  onPointerDown={(event) => beginNodeDrag(event, scene.id)}
                  onClick={(event) => {
                    event.stopPropagation()
                    selectCanvasScene(scene.id)
                  }}
                >
                  <Flex align="center" justify="space-between" className="movie-node-header">
                    <div>
                      <Typography.Text className="movie-node-eyebrow">Scene · {roleLabels[scene.role]}</Typography.Text>
                      <Typography.Text className="movie-node-title">{scene.title}</Typography.Text>
                    </div>
                    <div className="movie-node-actions">
                      <BorderOuterOutlined />
                      <button
                        type="button"
                        className="movie-node-delete"
                        title="删除场景"
                        aria-label={`删除场景 ${scene.title}`}
                        onPointerDown={(event) => event.stopPropagation()}
                        onClick={(event) => {
                          event.stopPropagation()
                          confirmDeleteScene(scene.id)
                        }}
                      >
                        <DeleteOutlined />
                      </button>
                    </div>
                  </Flex>
                  <div className="movie-node-preview">
                    {scene.media.posterUrl ? (
                      <img src={scene.media.posterUrl} alt="" className="movie-node-preview-poster" />
                    ) : (
                      <>
                        <div className="movie-node-preview-grid" />
                        <VideoCameraOutlined />
                      </>
                    )}
                  </div>
                  <Typography.Paragraph ellipsis={{ rows: 2 }} className="movie-node-synopsis">
                    {scene.script.synopsis}
                  </Typography.Paragraph>
                  <Flex align="center" justify="space-between">
                    <span className="movie-node-meta">{scene.script.lines.length} 句对白 · {scene.media.url ? '视频已上传' : '视频待上传'}</span>
                    <span className="movie-node-dot" />
                  </Flex>
                </div>
              )
            })}
          </div>

          <div className="movie-canvas-hint">无限画布 · 拖拽空白移动 · 拖拽 Scene/Choice 调整结构 · 滚轮缩放</div>

          <div className={rightPanelCollapsed ? 'movie-floating-panel is-collapsed' : 'movie-floating-panel'}>
            <button
              type="button"
              className="movie-panel-collapse"
              onPointerDown={(event) => event.stopPropagation()}
              onClick={() => setRightPanelCollapsed((value) => !value)}
              aria-label={rightPanelCollapsed ? '展开右侧栏' : '折叠右侧栏'}
            >
              {rightPanelCollapsed ? <DoubleLeftOutlined /> : <DoubleRightOutlined />}
            </button>
            <aside
              className="movie-right-panel"
              onPointerDown={(event) => event.stopPropagation()}
              onWheel={(event) => event.stopPropagation()}
            >
              {selectedScene && (
                  <SceneEditor
                    scene={selectedScene}
                    outgoingChoices={choices.filter((choice) => choice.fromSceneId === selectedScene.id)}
                    promptTemplate={promptTemplate}
                    uploadState={uploadBySceneId[selectedScene.id] ?? { status: 'idle' }}
                    onChange={(updater) => updateScene(selectedScene.id, updater)}
                    onAddLine={() => addLine(selectedScene.id)}
                    onDeleteLine={(lineId) => deleteLine(selectedScene.id, lineId)}
                    onSelectChoice={(choiceId) => setSelectedObject({ type: 'choice', id: choiceId })}
                    onDeleteChoice={confirmDeleteChoice}
                    onUploadVideo={(file) => void uploadSceneVideo(selectedScene, file)}
                    onPreview={() => startPreview(selectedScene.id)}
                    onDeleteScene={() => confirmDeleteScene(selectedScene.id)}
                  />
              )}
              {selectedChoice && (
                <ChoiceEditor
                  choice={selectedChoice}
                  scenes={scenes}
                  onChange={(updater) => updateChoice(selectedChoice.id, updater)}
                  onCreateScene={(endpoint) => createSceneForChoice(selectedChoice.id, endpoint)}
                  onDeleteChoice={() => confirmDeleteChoice(selectedChoice.id)}
                />
              )}
              {!selectedScene && !selectedChoice && (
                <Empty description="选择一个场景或选择连线开始编辑" />
              )}
            </aside>
          </div>

          <div
            className={bottomToolbarCollapsed ? 'movie-bottom-dock is-collapsed' : 'movie-bottom-dock'}
            onPointerDown={(event) => event.stopPropagation()}
            onWheel={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="movie-bottom-collapse"
              onClick={() => setBottomToolbarCollapsed((value) => !value)}
              aria-label={bottomToolbarCollapsed ? '展开底栏' : '折叠底栏'}
            >
              {bottomToolbarCollapsed ? <UpOutlined /> : <DownOutlined />}
            </button>
            <div className="movie-bottom-controls">
              <Tooltip title="选择 / 拖拽">
                <Button shape="circle" icon={<EditOutlined />} />
              </Tooltip>
              <Tooltip title="添加场景">
                <Button shape="circle" icon={<PlusOutlined />} onClick={addScene} />
              </Tooltip>
              <Tooltip title="添加选择">
                <Button shape="circle" icon={<BranchesOutlined />} onClick={addChoice} />
              </Tooltip>
              <span className="movie-bottom-divider" />
              <Tooltip title="缩小">
                <Button shape="circle" icon={<ZoomOutOutlined />} onClick={() => zoomBy(-0.1)} />
              </Tooltip>
              <Typography.Text className="movie-zoom-label">{Math.round(viewport.zoom * 100)}%</Typography.Text>
              <Tooltip title="放大">
                <Button shape="circle" icon={<ZoomInOutlined />} onClick={() => zoomBy(0.1)} />
              </Tooltip>
              <Tooltip title="适配视图">
                <Button icon={<FullscreenOutlined />} onClick={fitView}>适配</Button>
              </Tooltip>
            </div>
          </div>
        </section>
      </main>

      <Modal
        title="互动预览"
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        footer={null}
        width={920}
        className="movie-preview-modal"
        destroyOnClose
      >
        {previewScene && (
          <div className="movie-preview-player">
            <div className="movie-preview-scene">
              <div className="movie-preview-vignette" />
              <div className="movie-preview-title">{previewScene.title}</div>
              {previewChoicesVisible && (
                <div className="movie-preview-choices">
                  {outgoingPreviewChoices.map((choice) => (
                    <Button key={choice.id} size="large" onClick={() => choosePreviewEdge(choice)}>
                      {choice.label}
                    </Button>
                  ))}
                </div>
              )}
              {!previewChoicesVisible && currentPreviewLine && (
                <button type="button" className="movie-dialogue-box" onClick={advancePreview}>
                  <span className="movie-dialogue-speaker">{currentPreviewLine.speaker || '角色'}</span>
                  <span className="movie-dialogue-text">{currentPreviewLine.text}</span>
                  <span className="movie-dialogue-next">点击继续</span>
                </button>
              )}
              {!previewChoicesVisible && !currentPreviewLine && (
                <div className="movie-preview-choices">
                  <Button size="large" onClick={advancePreview}>继续</Button>
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

function SceneEditor({
  scene,
  outgoingChoices,
  promptTemplate,
  uploadState,
  onChange,
  onAddLine,
  onDeleteLine,
  onSelectChoice,
  onDeleteChoice,
  onUploadVideo,
  onPreview,
  onDeleteScene,
}: {
  scene: SceneNode
  outgoingChoices: ChoiceEdge[]
  promptTemplate: PromptTemplate | null
  uploadState: SceneUploadState
  onChange: (updater: (scene: SceneNode) => SceneNode) => void
  onAddLine: () => void
  onDeleteLine: (lineId: string) => void
  onSelectChoice: (choiceId: string) => void
  onDeleteChoice: (choiceId: string) => void
  onUploadVideo: (file: File) => void
  onPreview: () => void
  onDeleteScene: () => void
}) {
  const promptParts = scene.script.promptParts ?? defaultPromptParts(scene.title)
  const generatedPrompt = buildVideoPrompt(scene)
  const isUploading = uploadState.status === 'uploading'
  const [videoPreviewOpen, setVideoPreviewOpen] = useState(false)

  const updateScript = (script: Partial<SceneScript>) => {
    onChange((current) => ({
      ...current,
      script: { ...current.script, ...script },
    }))
  }

  const updatePromptParts = (patch: Partial<VideoPromptParts>) => {
    onChange((current) => ({
      ...current,
      script: {
        ...current.script,
        promptParts: {
          ...(current.script.promptParts ?? defaultPromptParts(current.title)),
          ...patch,
        },
      },
    }))
  }

  const updateLine = (lineId: string, patch: Partial<ScriptLine>) => {
    onChange((current) => ({
      ...current,
      script: {
        ...current.script,
        lines: current.script.lines.map((line) => (line.id === lineId ? { ...line, ...patch } : line)),
      },
    }))
  }

  return (
    <Flex vertical gap={16}>
      <Flex align="flex-start" justify="space-between" gap={12}>
        <div className="movie-panel-title-block">
          <Typography.Text className="movie-panel-kicker">当前场景</Typography.Text>
          <Input
            value={scene.title}
            onChange={(event) => onChange((current) => ({ ...current, title: event.target.value }))}
            className="movie-panel-title-input"
          />
        </div>
        <Button danger type="text" icon={<DeleteOutlined />} onClick={onDeleteScene} aria-label={`删除场景 ${scene.title}`} />
      </Flex>

      <Flex gap={8}>
        <Select
          value={scene.role}
          onChange={(role) => onChange((current) => ({ ...current, role }))}
          options={[
            { value: 'start', label: '开场' },
            { value: 'middle', label: '过场' },
            { value: 'ending', label: '结局' },
          ]}
          className="movie-panel-select"
        />
        <Button icon={<PlayCircleOutlined />} onClick={onPreview}>从这里预览</Button>
      </Flex>

      <section className="movie-panel-section">
        <Typography.Text className="movie-panel-label">画面占位</Typography.Text>
        <div className="movie-panel-media" tabIndex={0}>
          {scene.media.posterUrl ? (
            <img src={scene.media.posterUrl} alt={`${scene.title} 视频封面`} className="movie-panel-poster" />
          ) : scene.media.url ? (
            <video src={scene.media.url} muted preload="metadata" className="movie-panel-video" />
          ) : (
            <div className="movie-panel-media-empty">
              <VideoCameraOutlined />
              <span>视频 / 图片待生成</span>
            </div>
          )}
          <div className="movie-panel-media-overlay">
            <Upload
              accept="video/*"
              showUploadList={false}
              beforeUpload={(file) => {
                onUploadVideo(file)
                return Upload.LIST_IGNORE
              }}
            >
              <Button icon={<UploadOutlined />} loading={isUploading}>
                上传
              </Button>
            </Upload>
            {scene.media.url && (
              <Button icon={<PlayCircleOutlined />} onClick={() => setVideoPreviewOpen(true)}>
                预览
              </Button>
            )}
          </div>
        </div>
        {uploadState.message && (
          <div className={uploadState.status === 'failed' ? 'movie-generation-message is-error' : 'movie-generation-message'}>
            {uploadState.message}
          </div>
        )}
        <Modal
          title={scene.title}
          open={videoPreviewOpen}
          footer={null}
          centered
          width={860}
          onCancel={() => setVideoPreviewOpen(false)}
          className="movie-video-preview-modal"
        >
          {scene.media.url && (
            <video src={scene.media.url} controls autoPlay className="movie-video-preview-player" />
          )}
        </Modal>
      </section>

      <section className="movie-panel-section">
        <Flex align="center" justify="space-between">
          <Typography.Text className="movie-panel-label">场景结束后的选择</Typography.Text>
          <Tag className="movie-choice-count-tag">{outgoingChoices.length}</Tag>
        </Flex>
        {outgoingChoices.length > 0 ? (
          <Flex vertical gap={8}>
            {outgoingChoices.map((choice) => (
              <div key={choice.id} className="movie-choice-row">
                <button
                  type="button"
                  className="movie-choice-row-main"
                  onClick={() => onSelectChoice(choice.id)}
                >
                  <BranchesOutlined />
                  <span>{choice.label}</span>
                </button>
                <button
                  type="button"
                  className="movie-choice-row-delete"
                  title="删除选择"
                  aria-label={`删除选择 ${choice.label}`}
                  onClick={() => onDeleteChoice(choice.id)}
                >
                  <DeleteOutlined />
                </button>
              </div>
            ))}
          </Flex>
        ) : (
          <div className="movie-choice-note">这个场景还没有后续选择，可以用底部工具栏添加。</div>
        )}
      </section>

      <section className="movie-panel-section">
        <Typography.Text className="movie-panel-label">剧情摘要</Typography.Text>
        <Input.TextArea
          value={scene.script.synopsis}
          autoSize={{ minRows: 3, maxRows: 5 }}
          onChange={(event) => updateScript({ synopsis: event.target.value })}
        />
      </section>

      <section className="movie-panel-section">
        <Flex align="center" justify="space-between">
          <Typography.Text className="movie-panel-label">角色对白 / 屏幕字幕</Typography.Text>
          <Button size="small" icon={<PlusOutlined />} onClick={onAddLine}>添加</Button>
        </Flex>
        <div className="movie-choice-note">旁白默认内置在生成视频里，这里只编辑需要单独显示的角色对白或字幕。</div>
        <Flex vertical gap={10} className="movie-line-list">
          {scene.script.lines.map((line, index) => (
            <div key={line.id} className="movie-line-editor">
              <Flex align="center" gap={8}>
                <span className="movie-line-index">{index + 1}</span>
                <Input
                  value={line.speaker}
                  onChange={(event) => updateLine(line.id, { speaker: event.target.value })}
                  className="movie-line-speaker"
                  placeholder="说话人"
                />
                <Button
                  type="text"
                  icon={<DeleteOutlined />}
                  onClick={() => onDeleteLine(line.id)}
                  disabled={scene.script.lines.length <= 1}
                />
              </Flex>
              <Input.TextArea
                value={line.text}
                autoSize={{ minRows: 2, maxRows: 4 }}
                onChange={(event) => updateLine(line.id, { text: event.target.value })}
              />
            </div>
          ))}
        </Flex>
      </section>

      <section className="movie-panel-section">
        <Typography.Text className="movie-panel-label">画面描述</Typography.Text>
        <Input.TextArea
          value={scene.script.visualDescription}
          autoSize={{ minRows: 3, maxRows: 5 }}
          onChange={(event) => updateScript({ visualDescription: event.target.value })}
        />
      </section>

      <section className="movie-panel-section">
        <Typography.Text className="movie-panel-label">视频 Prompt</Typography.Text>
        <div className="movie-prompt-template">
          <Typography.Text className="movie-panel-label">结构化视频提示词</Typography.Text>
          <div className="movie-prompt-tips">
            {(promptTemplate?.sections ?? [
              '主体：谁或什么是画面核心。',
              '动作：主体正在做什么。',
              '场景：空间、天气、道具、情绪氛围。',
              '镜头：景别、机位、运镜。',
              '时序：按秒描述关键动作变化。',
              '风格：色彩、光线、材质和影片类型。',
              '约束：不希望出现的内容。',
            ]).map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </div>
        <Input
          value={promptParts.subject}
          onChange={(event) => updatePromptParts({ subject: event.target.value })}
          placeholder="主体：例如，年轻女性林夏站在老式公寓走廊"
        />
        <Input.TextArea
          value={promptParts.action}
          autoSize={{ minRows: 2, maxRows: 4 }}
          onChange={(event) => updatePromptParts({ action: event.target.value })}
          placeholder="动作：主体做什么，尽量聚焦一组主要动作"
        />
        <Input.TextArea
          value={promptParts.scene}
          autoSize={{ minRows: 2, maxRows: 4 }}
          onChange={(event) => updatePromptParts({ scene: event.target.value })}
          placeholder="场景：空间、时代、天气、道具、情绪氛围"
        />
        <Input.TextArea
          value={promptParts.camera}
          autoSize={{ minRows: 2, maxRows: 4 }}
          onChange={(event) => updatePromptParts({ camera: event.target.value })}
          placeholder="镜头：景别、机位、运镜或镜头切换"
        />
        <Input.TextArea
          value={promptParts.timeline}
          autoSize={{ minRows: 2, maxRows: 4 }}
          onChange={(event) => updatePromptParts({ timeline: event.target.value })}
          placeholder="时序：例如 [0-2s] 建立场景；[2-5s] 完成关键动作"
        />
        <Input.TextArea
          value={promptParts.style}
          autoSize={{ minRows: 2, maxRows: 4 }}
          onChange={(event) => updatePromptParts({ style: event.target.value })}
          placeholder="风格：电影感、写实、低饱和、高对比、细腻光影"
        />
        <Input.TextArea
          value={promptParts.constraints}
          autoSize={{ minRows: 2, maxRows: 4 }}
          onChange={(event) => updatePromptParts({ constraints: event.target.value })}
          placeholder="约束：不出现文字水印，不切换主角，主体一致"
        />
        <Typography.Text className="movie-panel-label">最终 Prompt</Typography.Text>
        <Input.TextArea
          value={scene.script.videoPrompt || generatedPrompt}
          autoSize={{ minRows: 3, maxRows: 6 }}
          onChange={(event) => updateScript({ videoPrompt: event.target.value })}
        />
      </section>
    </Flex>
  )
}

function ChoiceEditor({
  choice,
  scenes,
  onChange,
  onCreateScene,
  onDeleteChoice,
}: {
  choice: ChoiceEdge
  scenes: SceneNode[]
  onChange: (updater: (choice: ChoiceEdge) => ChoiceEdge) => void
  onCreateScene: (endpoint: 'from' | 'to') => void
  onDeleteChoice: () => void
}) {
  const createSceneOption = { value: CREATE_SCENE_SELECT_VALUE, label: '创建新场景' }
  const fromSceneOptions = [
    createSceneOption,
    ...scenes
      .filter((scene) => scene.id !== choice.toSceneId)
      .map((scene) => ({ value: scene.id, label: scene.title })),
  ]
  const toSceneOptions = [
    createSceneOption,
    ...scenes
      .filter((scene) => scene.id !== choice.fromSceneId)
      .map((scene) => ({ value: scene.id, label: scene.title })),
  ]

  const changeFromScene = (fromSceneId: string) => {
    if (fromSceneId === CREATE_SCENE_SELECT_VALUE) {
      onCreateScene('from')
      return
    }
    onChange((current) => {
      const fallbackTarget = scenes.find((scene) => scene.id !== fromSceneId)?.id
      return {
        ...current,
        fromSceneId,
        toSceneId: current.toSceneId === fromSceneId && fallbackTarget ? fallbackTarget : current.toSceneId,
      }
    })
  }

  const changeToScene = (toSceneId?: string) => {
    if (toSceneId === CREATE_SCENE_SELECT_VALUE) {
      onCreateScene('to')
      return
    }
    onChange((current) => {
      const nextToSceneId = toSceneId ?? ''
      const fallbackSource = scenes.find((scene) => scene.id !== nextToSceneId)?.id
      return {
        ...current,
        fromSceneId: nextToSceneId && current.fromSceneId === nextToSceneId && fallbackSource
          ? fallbackSource
          : current.fromSceneId,
        toSceneId: nextToSceneId,
      }
    })
  }

  return (
    <Flex vertical gap={16}>
      <Flex align="flex-start" justify="space-between" gap={12}>
        <div className="movie-panel-title-block">
          <Typography.Text className="movie-panel-kicker">当前选择</Typography.Text>
          <Input
            value={choice.label}
            onChange={(event) => onChange((current) => ({ ...current, label: event.target.value }))}
            className="movie-panel-title-input"
          />
        </div>
        <Button danger type="text" icon={<DeleteOutlined />} onClick={onDeleteChoice} aria-label={`删除选择 ${choice.label}`} />
      </Flex>

      <section className="movie-panel-section">
        <Typography.Text className="movie-panel-label">来源场景</Typography.Text>
        <Select
          value={choice.fromSceneId}
          onChange={changeFromScene}
          options={fromSceneOptions}
          className="movie-panel-wide-control"
        />
      </section>

      <section className="movie-panel-section">
        <Typography.Text className="movie-panel-label">目标场景</Typography.Text>
        <Select
          value={choice.toSceneId || undefined}
          onChange={changeToScene}
          options={toSceneOptions}
          allowClear
          placeholder="未选择目标场景"
          className="movie-panel-wide-control"
        />
      </section>

      <section className="movie-panel-section">
        <Typography.Text className="movie-panel-label">触发时机</Typography.Text>
        <Input value="场景播放结束后" disabled />
      </section>

      <div className="movie-choice-note">
        来源场景和目标场景必须不同。MVP 先把 Choice 固定为场景结束后出现。
      </div>
    </Flex>
  )
}
