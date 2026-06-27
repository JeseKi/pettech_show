import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import type {
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent,
  WheelEvent as ReactWheelEvent,
} from 'react'
import { isAxiosError } from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  App,
  Button,
  Collapse,
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
  CheckCircleOutlined,
  CloudUploadOutlined,
  DeleteOutlined,
  DoubleLeftOutlined,
  DoubleRightOutlined,
  DownOutlined,
  EditOutlined,
  FileTextOutlined,
  FullscreenOutlined,
  GlobalOutlined,
  ItalicOutlined,
  LinkOutlined,
  OrderedListOutlined,
  PictureOutlined,
  PlusOutlined,
  PoweroffOutlined,
  PlayCircleOutlined,
  SaveOutlined,
  UploadOutlined,
  UnorderedListOutlined,
  UpOutlined,
  VideoCameraOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons'
import {
  closeInteractiveMoviePublication,
  createInteractiveMovieProject,
  deleteInteractiveMovieProject,
  getInteractiveMovieProject,
  getInteractiveMoviePromptTemplate,
  getInteractiveMovieSyncState,
  listInteractiveMovieReleases,
  listInteractiveMovieProjects,
  patchInteractiveMovieProject,
  publishInteractiveMovieProject,
  renameInteractiveMovieProject,
  setInteractiveMoviePublishedRelease,
  uploadInteractiveMovieImage,
  uploadInteractiveMovieVideo,
} from '../../lib/interactiveMovie'
import type {
  InteractiveMovieProjectDetail,
  InteractiveMovieProjectPatch,
  InteractiveMovieRelease,
  PromptTemplate,
} from '../../lib/interactiveMovie'
import { resolveErrorMessage } from '../../lib/errorMessage'
import BrandNavPill from '../../components/brand/BrandNavPill'
import WorkbenchHomeButton from '../../components/brand/WorkbenchHomeButton'
import './InteractiveMoviePage.css'

type SceneRole = 'start' | 'middle' | 'ending'
type AssetNodeType = 'text' | 'image' | 'video'
type ConnectableNodeType = 'scene' | AssetNodeType
type NodeHandleSide = 'top' | 'right' | 'bottom' | 'left'
type SelectedObject = { type: 'scene' | 'choice' | AssetNodeType | 'nodeLink'; id: string }

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
    videoNodeId?: string
    coverImageNodeId?: string
    status: 'empty' | 'mock' | 'ready'
  }
}

type AssetNode = {
  id: string
  type: AssetNodeType
  title: string
  position: { x: number; y: number }
  text?: string
  media: {
    url?: string
    objectKey?: string
    storageUri?: string
    contentType?: string
    size?: number
    status: 'empty' | 'ready'
  }
}

type ChoiceEdge = {
  id: string
  fromSceneId: string
  toSceneId: string
  label: string
  trigger: 'after_scene'
  offsetX?: number
  offsetY?: number
}

type NodeLinkEndpoint = {
  type: ConnectableNodeType
  id: string
  handle: NodeHandleSide
}

type NodeLink = {
  id: string
  from: NodeLinkEndpoint
  to: NodeLinkEndpoint
  offsetX?: number
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

type AssetUploadState = {
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
  isPublished?: boolean
  publishedReleaseId?: string | null
  publishedVersionNo?: number | null
  publishedAt?: string | null
  publicPath?: string | null
  scenes: SceneNode[]
  choices: ChoiceEdge[]
  assetNodes: AssetNode[]
  nodeLinks: NodeLink[]
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
    nodeType: 'scene' | AssetNodeType
    nodeId: string
    startClient: { x: number; y: number }
    startPosition: { x: number; y: number }
  }
  | {
    type: 'choice'
    pointerId: number
    choiceId: string
    startClient: { x: number; y: number }
    startOffsetX: number
    startOffsetY: number
  }
  | {
    type: 'link'
    pointerId: number
    source: NodeLinkEndpoint
  }
  | {
    type: 'nodeLink'
    pointerId: number
    linkId: string
    startClient: { x: number; y: number }
    startOffsetX: number
    startOffsetY: number
  }
  | {
    type: 'nodeLinkEndpoint'
    pointerId: number
    linkId: string
    activeEnd: 'from' | 'to'
  }

type CanvasContextMenuState = {
  screenX: number
  screenY: number
  canvasPosition: { x: number; y: number }
}

type LinkDraftState = {
  mode: 'create'
  source: NodeLinkEndpoint
  current: { x: number; y: number }
  target?: NodeLinkEndpoint
} | {
  mode: 'reconnect'
  linkId: string
  activeEnd: 'from' | 'to'
  fixedEndpoint: NodeLinkEndpoint
  current: { x: number; y: number }
  target?: NodeLinkEndpoint
}

const STORAGE_KEY = 'pettech.interactiveMovie.workspace.v1'
const CLOUD_REPLICA_PREFIX = 'pettech.interactiveMovie.cloudReplica.'
const DRAFT_REPLICA_PREFIX = 'pettech.interactiveMovie.draftReplica.'
const SCENE_PANEL_STATE_KEY = 'pettech.interactiveMovie.scenePanelState.v1'
const MISSING_PROJECT_DETAIL = '互动电影项目不存在'
const NODE_WIDTH = 292
const NODE_HEIGHT = 236
const ASSET_NODE_WIDTH = 244
const ASSET_NODE_TEXT_HEIGHT = 142
const ASSET_NODE_MEDIA_HEIGHT = 190
const MIN_ZOOM = 0.25
const MAX_ZOOM = 2
const LINK_SNAP_RADIUS = 44
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
    assetNodes: [],
    nodeLinks: [],
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

const createDraftAssetNode = (
  type: AssetNodeType,
  title: string,
  position: { x: number; y: number },
): AssetNode => ({
  id: uniqueId(type),
  type,
  title,
  position,
  text: type === 'text' ? '## 新文本\n\n输入 Markdown 内容。' : '',
  media: { status: 'empty' },
})

const normalizeProjectShape = (project: InteractiveMovieProject): InteractiveMovieProject => ({
  ...project,
  assetNodes: Array.isArray(project.assetNodes) ? project.assetNodes : [],
  nodeLinks: Array.isArray(project.nodeLinks)
    ? project.nodeLinks.map((link) => ({ ...link, offsetX: link.offsetX ?? 0, offsetY: link.offsetY ?? 0 }))
    : [],
  choices: Array.isArray(project.choices)
    ? project.choices.map((choice) => ({ ...choice, offsetX: choice.offsetX ?? 0, offsetY: choice.offsetY ?? 0 }))
    : [],
  scenes: project.scenes.map((scene) => ({
    ...scene,
    media: {
      ...scene.media,
      videoNodeId: scene.media.videoNodeId ?? '',
      coverImageNodeId: scene.media.coverImageNodeId ?? '',
    },
  })),
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
        const projects = parsed.projects.map(normalizeProjectShape)
        const activeProject = projects.find((project) => project.id === parsed.activeProjectId) ?? projects[0]
        return { activeProjectId: activeProject.id, projects }
      }
    }
  } catch {
    window.localStorage.removeItem(STORAGE_KEY)
  }
  const project = createDefaultProject()
  return { activeProjectId: project.id, projects: [project] }
}

const loadScenePanelState = (): Record<string, string[]> => {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(SCENE_PANEL_STATE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, unknown>
    return Object.fromEntries(
      Object.entries(parsed).map(([sceneId, keys]) => [
        sceneId,
        Array.isArray(keys) ? keys.filter((key): key is string => typeof key === 'string') : [],
      ]),
    )
  } catch {
    window.localStorage.removeItem(SCENE_PANEL_STATE_KEY)
    return {}
  }
}

const persistScenePanelState = (state: Record<string, string[]>) => {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(SCENE_PANEL_STATE_KEY, JSON.stringify(state))
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
    return raw ? normalizeProjectShape(JSON.parse(raw) as InteractiveMovieProject) : null
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
  detail: InteractiveMovieProjectDetail<InteractiveMovieProject>,
): InteractiveMovieProject => normalizeProjectShape({
  ...detail.document,
  version: detail.version,
  contentHash: detail.content_hash,
  cloudUpdatedAt: detail.updated_at,
  updatedAt: detail.document.updatedAt || detail.updated_at,
  isPublished: detail.is_published,
  publishedReleaseId: detail.published_release_id ?? null,
  publishedVersionNo: detail.published_version_no ?? null,
  publishedAt: detail.published_at ?? null,
  publicPath: detail.public_path ?? `/interactive-movie/play/${detail.id}`,
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
  videoNodeId: scene.media.videoNodeId ?? '',
  coverImageNodeId: scene.media.coverImageNodeId ?? '',
  mediaStatus: scene.media.status,
  sortOrder,
})

const flattenAssetNode = (asset: AssetNode, sortOrder: number): Record<string, unknown> => ({
  id: asset.id,
  type: asset.type,
  title: asset.title,
  positionX: asset.position.x,
  positionY: asset.position.y,
  text: asset.text ?? '',
  mediaUrl: asset.media.url ?? '',
  mediaObjectKey: asset.media.objectKey ?? '',
  mediaStorageUri: asset.media.storageUri ?? '',
  mediaContentType: asset.media.contentType ?? '',
  mediaSize: asset.media.size ?? 0,
  mediaStatus: asset.media.status,
  sortOrder,
})

const flattenChoice = (choice: ChoiceEdge, sortOrder: number): Record<string, unknown> => ({
  id: choice.id,
  fromSceneId: choice.fromSceneId,
  toSceneId: choice.toSceneId,
  label: choice.label,
  trigger: choice.trigger,
  offsetX: choice.offsetX ?? 0,
  offsetY: choice.offsetY ?? 0,
  sortOrder,
})

const flattenNodeLink = (link: NodeLink, sortOrder: number): Record<string, unknown> => ({
  id: link.id,
  fromNodeType: link.from.type,
  fromNodeId: link.from.id,
  fromHandle: link.from.handle,
  toNodeType: link.to.type,
  toNodeId: link.to.id,
  toHandle: link.to.handle,
  offsetX: link.offsetX ?? 0,
  offsetY: link.offsetY ?? 0,
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
  const baseAssets = new Map(base.assetNodes.map((asset, index) => [asset.id, flattenAssetNode(asset, index)]))
  const draftAssets = new Map(draft.assetNodes.map((asset, index) => [asset.id, flattenAssetNode(asset, index)]))
  const baseNodeLinks = new Map(base.nodeLinks.map((link, index) => [link.id, flattenNodeLink(link, index)]))
  const draftNodeLinks = new Map(draft.nodeLinks.map((link, index) => [link.id, flattenNodeLink(link, index)]))
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
    asset_nodes: {
      upsert: [...draftAssets.values()].filter((asset) => shallowChanged(baseAssets.get(String(asset.id)), asset)),
      delete: [...baseAssets.keys()].filter((id) => !draftAssets.has(id)),
    },
    node_links: {
      upsert: [...draftNodeLinks.values()].filter((link) => shallowChanged(baseNodeLinks.get(String(link.id)), link)),
      delete: [...baseNodeLinks.keys()].filter((id) => !draftNodeLinks.has(id)),
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
  || patch.asset_nodes.upsert.length > 0
  || patch.asset_nodes.delete.length > 0
  || patch.node_links.upsert.length > 0
  || patch.node_links.delete.length > 0
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

const firstSelectableObject = (scenes: SceneNode[], choices: ChoiceEdge[], assetNodes: AssetNode[] = []): SelectedObject => {
  if (scenes[0]) return { type: 'scene', id: scenes[0].id }
  if (choices[0]) return { type: 'choice', id: choices[0].id }
  if (assetNodes[0]) return { type: assetNodes[0].type, id: assetNodes[0].id }
  return { type: 'scene', id: '' }
}

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return '-'
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return value
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(timestamp))
}

const assetTypeLabel = (type: AssetNodeType) => {
  if (type === 'text') return 'Text'
  if (type === 'image') return 'Image'
  return 'Video'
}

const getSceneVideoUrl = (scene: SceneNode | null | undefined, assetMap: Map<string, AssetNode>) => {
  if (!scene) return undefined
  const videoNode = scene.media.videoNodeId ? assetMap.get(scene.media.videoNodeId) : undefined
  const referencedUrl = videoNode?.type === 'video' ? videoNode.media.url?.trim() : ''
  if (referencedUrl) return referencedUrl
  if (scene.media.kind !== 'video') return undefined
  const legacyUrl = scene.media.url?.trim()
  return legacyUrl || undefined
}

const getScenePosterUrl = (scene: SceneNode | null | undefined, assetMap: Map<string, AssetNode>) => {
  if (!scene) return undefined
  const imageNode = scene.media.coverImageNodeId ? assetMap.get(scene.media.coverImageNodeId) : undefined
  const referencedUrl = imageNode?.type === 'image' ? imageNode.media.url?.trim() : ''
  return referencedUrl || scene.media.posterUrl?.trim() || undefined
}

const nodeDimensions = (type: ConnectableNodeType) => {
  if (type === 'scene') return { width: NODE_WIDTH, height: NODE_HEIGHT }
  if (type === 'text') return { width: ASSET_NODE_WIDTH, height: ASSET_NODE_TEXT_HEIGHT }
  return { width: ASSET_NODE_WIDTH, height: ASSET_NODE_MEDIA_HEIGHT }
}

const nodePosition = (
  endpoint: Pick<NodeLinkEndpoint, 'type' | 'id'>,
  sceneMap: Map<string, SceneNode>,
  assetMap: Map<string, AssetNode>,
) => {
  if (endpoint.type === 'scene') return sceneMap.get(endpoint.id)?.position ?? null
  return assetMap.get(endpoint.id)?.position ?? null
}

const nodeBounds = (
  endpoint: Pick<NodeLinkEndpoint, 'type' | 'id'>,
  sceneMap: Map<string, SceneNode>,
  assetMap: Map<string, AssetNode>,
) => {
  const position = nodePosition(endpoint, sceneMap, assetMap)
  if (!position) return null
  const dimensions = nodeDimensions(endpoint.type)
  return {
    x: position.x,
    y: position.y,
    width: dimensions.width,
    height: dimensions.height,
    centerX: position.x + dimensions.width / 2,
    centerY: position.y + dimensions.height / 2,
  }
}

const floatingHandle = (
  endpoint: Pick<NodeLinkEndpoint, 'type' | 'id'>,
  other: Pick<NodeLinkEndpoint, 'type' | 'id'>,
  sceneMap: Map<string, SceneNode>,
  assetMap: Map<string, AssetNode>,
): NodeHandleSide => {
  const bounds = nodeBounds(endpoint, sceneMap, assetMap)
  const otherBounds = nodeBounds(other, sceneMap, assetMap)
  if (!bounds || !otherBounds) return 'right'
  const dx = otherBounds.centerX - bounds.centerX
  const dy = otherBounds.centerY - bounds.centerY
  const xWeight = Math.abs(dx) / Math.max(bounds.width, 1)
  const yWeight = Math.abs(dy) / Math.max(bounds.height, 1)
  if (xWeight >= yWeight) return dx >= 0 ? 'right' : 'left'
  return dy >= 0 ? 'bottom' : 'top'
}

const resolveFloatingEndpoint = (
  endpoint: NodeLinkEndpoint,
  other: NodeLinkEndpoint,
  sceneMap: Map<string, SceneNode>,
  assetMap: Map<string, AssetNode>,
): NodeLinkEndpoint => ({
  ...endpoint,
  handle: floatingHandle(endpoint, other, sceneMap, assetMap),
})

const handleAnchor = (
  endpoint: NodeLinkEndpoint,
  sceneMap: Map<string, SceneNode>,
  assetMap: Map<string, AssetNode>,
) => {
  const position = nodePosition(endpoint, sceneMap, assetMap)
  if (!position) return null
  const dimensions = nodeDimensions(endpoint.type)
  if (endpoint.handle === 'top') return { x: position.x + dimensions.width / 2, y: position.y }
  if (endpoint.handle === 'right') return { x: position.x + dimensions.width, y: position.y + dimensions.height / 2 }
  if (endpoint.handle === 'bottom') return { x: position.x + dimensions.width / 2, y: position.y + dimensions.height }
  return { x: position.x, y: position.y + dimensions.height / 2 }
}

const linkPath = (
  start: { x: number; y: number },
  end: { x: number; y: number },
  startHandle: NodeHandleSide = 'right',
  endHandle: NodeHandleSide = 'left',
  offset: { x: number; y: number } = { x: 0, y: 0 },
) => {
  const dx = end.x - start.x
  const dy = end.y - start.y
  const control = Math.max(80, Math.min(260, Math.hypot(dx, dy) * 0.38))
  const vector = (handle: NodeHandleSide) => {
    if (handle === 'left') return { x: -1, y: 0 }
    if (handle === 'right') return { x: 1, y: 0 }
    if (handle === 'top') return { x: 0, y: -1 }
    return { x: 0, y: 1 }
  }
  const startVector = vector(startHandle)
  const endVector = vector(endHandle)
  if (Math.abs(offset.x) > 0.1 || Math.abs(offset.y) > 0.1) {
    const mid = {
      x: (start.x + end.x) / 2 + offset.x,
      y: (start.y + end.y) / 2 + offset.y,
    }
    const firstControl = Math.max(50, Math.min(180, Math.hypot(mid.x - start.x, mid.y - start.y) * 0.32))
    const secondControl = Math.max(50, Math.min(180, Math.hypot(end.x - mid.x, end.y - mid.y) * 0.32))
    return [
      `M ${start.x} ${start.y}`,
      `C ${start.x + startVector.x * firstControl} ${start.y + startVector.y * firstControl}, ${mid.x} ${mid.y}, ${mid.x} ${mid.y}`,
      `C ${mid.x} ${mid.y}, ${end.x + endVector.x * secondControl} ${end.y + endVector.y * secondControl}, ${end.x} ${end.y}`,
    ].join(' ')
  }
  return [
    `M ${start.x} ${start.y}`,
    `C ${start.x + startVector.x * control} ${start.y + startVector.y * control},`,
    `${end.x + endVector.x * control} ${end.y + endVector.y * control},`,
    `${end.x} ${end.y}`,
  ].join(' ')
}

const sameNodeEndpoint = (a: Pick<NodeLinkEndpoint, 'type' | 'id'>, b: Pick<NodeLinkEndpoint, 'type' | 'id'>) => (
  a.type === b.type && a.id === b.id
)

const nodePairKey = (a: Pick<NodeLinkEndpoint, 'type' | 'id'>, b: Pick<NodeLinkEndpoint, 'type' | 'id'>) => (
  [`${a.type}:${a.id}`, `${b.type}:${b.id}`].sort().join('|')
)

const projectHasNodePairLink = (
  project: InteractiveMovieProject,
  from: NodeLinkEndpoint,
  to: NodeLinkEndpoint,
  exceptLinkId = '',
) => project.nodeLinks.some((link) => (
  link.id !== exceptLinkId && nodePairKey(link.from, link.to) === nodePairKey(from, to)
))

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
  const [uploadByAssetId, setUploadByAssetId] = useState<Record<string, AssetUploadState>>({})
  const [cloudReady, setCloudReady] = useState(false)
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncMessage, setSyncMessage] = useState('本地草稿')
  const [publishModalOpen, setPublishModalOpen] = useState(false)
  const [releaseHistory, setReleaseHistory] = useState<InteractiveMovieRelease[]>([])
  const [releaseLoading, setReleaseLoading] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewSceneId, setPreviewSceneId] = useState('')
  const [previewLineIndex, setPreviewLineIndex] = useState(0)
  const [previewChoicesVisible, setPreviewChoicesVisible] = useState(false)
  const [canvasContextMenu, setCanvasContextMenu] = useState<CanvasContextMenuState | null>(null)
  const [linkDraft, setLinkDraft] = useState<LinkDraftState | null>(null)
  const linkDraftRef = useRef<LinkDraftState | null>(null)
  const [scenePanelState, setScenePanelState] = useState<Record<string, string[]>>(() => loadScenePanelState())

  const activeProject = workspace.projects.find((project) => project.id === workspace.activeProjectId) ?? workspace.projects[0]
  const scenes = activeProject.scenes
  const choices = activeProject.choices
  const assetNodes = activeProject.assetNodes
  const nodeLinks = activeProject.nodeLinks
  const selectedObject = activeProject.selectedObject
  const viewport = activeProject.viewport

  const selectedScene = selectedObject.type === 'scene'
    ? scenes.find((scene) => scene.id === selectedObject.id) ?? null
    : null
  const selectedChoice = selectedObject.type === 'choice'
    ? choices.find((choice) => choice.id === selectedObject.id) ?? null
    : null
  const selectedAsset = selectedObject.type !== 'scene' && selectedObject.type !== 'choice'
    && selectedObject.type !== 'nodeLink'
    ? assetNodes.find((asset) => asset.id === selectedObject.id) ?? null
    : null
  const selectedNodeLink = selectedObject.type === 'nodeLink'
    ? nodeLinks.find((link) => link.id === selectedObject.id) ?? null
    : null
  const sceneMap = useMemo(() => new Map(scenes.map((scene) => [scene.id, scene])), [scenes])
  const assetMap = useMemo(() => new Map(assetNodes.map((asset) => [asset.id, asset])), [assetNodes])
  const videoNodes = useMemo(() => assetNodes.filter((asset) => asset.type === 'video'), [assetNodes])
  const imageNodes = useMemo(() => assetNodes.filter((asset) => asset.type === 'image'), [assetNodes])
  const startScene = scenes.find((scene) => scene.role === 'start') ?? scenes[0]
  const previewScene = scenes.find((scene) => scene.id === previewSceneId) ?? startScene
  const outgoingPreviewChoices = choices.filter((choice) => (
    choice.fromSceneId === previewScene?.id && sceneMap.has(choice.toSceneId)
  ))
  const previewVideoUrl = getSceneVideoUrl(previewScene, assetMap)
  const previewPosterUrl = getScenePosterUrl(previewScene, assetMap)
  const previewHasVideo = Boolean(previewVideoUrl)
  const currentPreviewLine = previewScene?.script.lines[previewLineIndex]
  const activeProjectCloudBase = hasCloudCopy(activeProject) ? readProjectReplica(cloudReplicaKey(activeProject.id)) : null
  const activeProjectHasUnsavedChanges = !activeProjectCloudBase
    || patchHasChanges(buildProjectPatch(activeProjectCloudBase, activeProject))
  const activeProjectPublicPath = activeProject.publicPath ?? `/interactive-movie/play/${activeProject.id}`
  const activeProjectPublicUrl = typeof window === 'undefined'
    ? activeProjectPublicPath
    : `${window.location.origin}${activeProjectPublicPath}`

  const updateLinkDraftState = (draft: LinkDraftState | null) => {
    linkDraftRef.current = draft
    setLinkDraft(draft)
  }

  useEffect(() => {
    persistWorkspaceLocally(workspace)
  }, [workspace])

  useEffect(() => {
    persistScenePanelState(scenePanelState)
  }, [scenePanelState])

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
          const project = withCloudMeta(created)
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
          const cloudProject = withCloudMeta(detail)
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

  const updateAsset = (assetId: string, updater: (asset: AssetNode) => AssetNode) => {
    updateActiveProject((project) => ({
      ...project,
      assetNodes: project.assetNodes.map((asset) => (asset.id === assetId ? updater(asset) : asset)),
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

  const replaceProjectFromServer = (detail: InteractiveMovieProjectDetail<InteractiveMovieProject>) => {
    const project = withCloudMeta(detail)
    writeProjectReplica(cloudReplicaKey(project.id), project)
    writeProjectReplica(draftReplicaKey(project.id), project)
    setWorkspace((current) => ({
      ...current,
      activeProjectId: current.activeProjectId === detail.id ? project.id : current.activeProjectId,
      projects: current.projects.map((item) => (item.id === project.id ? project : item)),
    }))
    return project
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
            const nextProject = withCloudMeta(renamed)
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
    setCanvasContextMenu(null)
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'pan',
      pointerId: event.pointerId,
      startClient: { x: event.clientX, y: event.clientY },
      startViewport: viewport,
    }
  }

  const beginNodeDrag = (event: ReactPointerEvent<HTMLDivElement>, nodeType: 'scene' | AssetNodeType, nodeId: string) => {
    if (event.button !== 0) return
    event.stopPropagation()
    const node = nodeType === 'scene'
      ? scenes.find((item) => item.id === nodeId)
      : assetNodes.find((item) => item.id === nodeId)
    if (!node) return
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'node',
      pointerId: event.pointerId,
      nodeType,
      nodeId,
      startClient: { x: event.clientX, y: event.clientY },
      startPosition: node.position,
    }
    setSelectedObject({ type: nodeType, id: nodeId })
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
      startOffsetX: choice.offsetX ?? 0,
      startOffsetY: choice.offsetY ?? 0,
    }
    setSelectedObject({ type: 'choice', id: choiceId })
  }

  const canvasPointFromEvent = (event: { clientX: number; clientY: number }) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return { x: 0, y: 0 }
    return {
      x: (event.clientX - rect.left - viewport.x) / viewport.zoom,
      y: (event.clientY - rect.top - viewport.y) / viewport.zoom,
    }
  }

  const snapEndpointFromCanvasPoint = (
    point: { x: number; y: number },
    exclude?: Pick<NodeLinkEndpoint, 'type' | 'id'>,
  ): NodeLinkEndpoint | null => {
    const radius = LINK_SNAP_RADIUS / viewport.zoom
    const candidates: Array<Pick<NodeLinkEndpoint, 'type' | 'id'>> = [
      ...scenes.map((scene) => ({ type: 'scene' as const, id: scene.id })),
      ...assetNodes.map((asset) => ({ type: asset.type, id: asset.id })),
    ]
    let bestEndpoint: NodeLinkEndpoint | null = null
    let bestDistance = Number.POSITIVE_INFINITY
    for (const candidate of candidates) {
      if (exclude && sameNodeEndpoint(candidate, exclude)) continue
      const bounds = nodeBounds(candidate, sceneMap, assetMap)
      if (!bounds) continue
      const insideExpandedBounds = (
        point.x >= bounds.x - radius
        && point.x <= bounds.x + bounds.width + radius
        && point.y >= bounds.y - radius
        && point.y <= bounds.y + bounds.height + radius
      )
      const dx = point.x - bounds.centerX
      const dy = point.y - bounds.centerY
      const side: NodeHandleSide = Math.abs(dx) / bounds.width >= Math.abs(dy) / bounds.height
        ? (dx >= 0 ? 'right' : 'left')
        : (dy >= 0 ? 'bottom' : 'top')
      const endpoint = { ...candidate, handle: side }
      const anchor = handleAnchor(endpoint, sceneMap, assetMap)
      if (!anchor) continue
      const distance = Math.hypot(point.x - anchor.x, point.y - anchor.y)
      if (!insideExpandedBounds && distance > radius) continue
      if (distance < bestDistance) {
        bestEndpoint = endpoint
        bestDistance = distance
      }
    }
    return bestEndpoint
  }

  const draftPoint = (
    point: { x: number; y: number },
    exclude?: Pick<NodeLinkEndpoint, 'type' | 'id'>,
  ) => {
    const target = snapEndpointFromCanvasPoint(point, exclude)
    if (!target) return { current: point, target: undefined }
    return {
      current: handleAnchor(target, sceneMap, assetMap) ?? point,
      target,
    }
  }

  const beginLinkDrag = (
    event: ReactPointerEvent<HTMLButtonElement>,
    endpoint: NodeLinkEndpoint,
  ) => {
    if (event.button !== 0) return
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'link',
      pointerId: event.pointerId,
      source: endpoint,
    }
    const point = canvasPointFromEvent(event)
    const snap = draftPoint(point, endpoint)
    updateLinkDraftState({ mode: 'create', source: endpoint, current: snap.current, target: snap.target })
    setSelectedObject({ type: endpoint.type, id: endpoint.id })
  }

  const beginNodeLinkRouteDrag = (
    event: ReactPointerEvent<SVGPathElement>,
    link: NodeLink,
  ) => {
    if (event.button !== 0) return
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'nodeLink',
      pointerId: event.pointerId,
      linkId: link.id,
      startClient: { x: event.clientX, y: event.clientY },
      startOffsetX: link.offsetX ?? 0,
      startOffsetY: link.offsetY ?? 0,
    }
    setSelectedObject({ type: 'nodeLink', id: link.id })
  }

  const beginNodeLinkEndpointDrag = (
    event: ReactPointerEvent<SVGPathElement | SVGCircleElement | HTMLButtonElement>,
    link: NodeLink,
    activeEnd: 'from' | 'to',
  ) => {
    if (event.button !== 0) return
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.setPointerCapture(event.pointerId)
    const point = canvasPointFromEvent(event)
    interactionRef.current = {
      type: 'nodeLinkEndpoint',
      pointerId: event.pointerId,
      linkId: link.id,
      activeEnd,
    }
    setSelectedObject({ type: 'nodeLink', id: link.id })
    const fixedEndpoint = activeEnd === 'from' ? link.to : link.from
    const snap = draftPoint(point, fixedEndpoint)
    updateLinkDraftState({
      mode: 'reconnect',
      linkId: link.id,
      activeEnd,
      fixedEndpoint,
      current: snap.current,
      target: snap.target,
    })
  }

  const completeLinkDrag = (target: NodeLinkEndpoint) => {
    const draft = linkDraftRef.current
    if (!draft) return
    const rawFrom = draft.mode === 'create'
      ? draft.source
      : draft.activeEnd === 'from'
        ? target
        : draft.fixedEndpoint
    const rawTo = draft.mode === 'create'
      ? target
      : draft.activeEnd === 'to'
        ? target
        : draft.fixedEndpoint
    if (sameNodeEndpoint(rawFrom, rawTo)) {
      interactionRef.current = null
      updateLinkDraftState(null)
      return
    }
    const nextFrom = resolveFloatingEndpoint(rawFrom, rawTo, sceneMap, assetMap)
    const nextTo = resolveFloatingEndpoint(rawTo, rawFrom, sceneMap, assetMap)
    const linkId = draft.mode === 'create' ? uniqueId('link') : draft.linkId
    let rejectedDuplicate = false
    updateActiveProject((project) => {
      if (projectHasNodePairLink(project, nextFrom, nextTo, draft.mode === 'reconnect' ? draft.linkId : '')) {
        rejectedDuplicate = true
        return project
      }
      if (draft.mode === 'reconnect') {
        return {
          ...project,
          nodeLinks: project.nodeLinks.map((link) => (
            link.id === draft.linkId ? { ...link, from: nextFrom, to: nextTo } : link
          )),
          selectedObject: { type: 'nodeLink', id: draft.linkId },
        }
      }
      return {
        ...project,
        nodeLinks: [...project.nodeLinks, { id: linkId, from: nextFrom, to: nextTo }],
        selectedObject: { type: 'nodeLink', id: linkId },
      }
    })
    if (rejectedDuplicate) message.warning('这两个节点之间已经存在连接')
    interactionRef.current = null
    updateLinkDraftState(null)
  }

  const linkEndpointFromPoint = (event: ReactPointerEvent<HTMLElement>): NodeLinkEndpoint | null => {
    const element = document.elementFromPoint(event.clientX, event.clientY)
    const handle = element?.closest<HTMLButtonElement>('.movie-node-handle')
    const type = handle?.dataset.nodeType as ConnectableNodeType | undefined
    const id = handle?.dataset.nodeId
    const side = handle?.dataset.handle as NodeHandleSide | undefined
    if (type && id && side) return { type, id, handle: side }
    const interaction = interactionRef.current
    const exclude = interaction?.type === 'link'
      ? interaction.source
      : linkDraft?.mode === 'reconnect'
        ? linkDraft.fixedEndpoint
        : undefined
    return snapEndpointFromCanvasPoint(canvasPointFromEvent(event), exclude)
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
      const nextPosition = {
        x: interaction.startPosition.x + dx,
        y: interaction.startPosition.y + dy,
      }
      if (interaction.nodeType === 'scene') {
        updateScene(interaction.nodeId, (scene) => ({ ...scene, position: nextPosition }))
      } else {
        updateAsset(interaction.nodeId, (asset) => ({ ...asset, position: nextPosition }))
      }
      return
    }
    if (interaction.type === 'link') {
      const point = canvasPointFromEvent(event)
      const snap = draftPoint(point, interaction.source)
      const current = linkDraftRef.current
      updateLinkDraftState(current && current.mode === 'create'
        ? { ...current, current: snap.current, target: snap.target }
        : current)
      return
    }
    if (interaction.type === 'nodeLink') {
      const dx = (event.clientX - interaction.startClient.x) / viewport.zoom
      const dy = (event.clientY - interaction.startClient.y) / viewport.zoom
      updateActiveProject((project) => ({
        ...project,
        nodeLinks: project.nodeLinks.map((link) => (
          link.id === interaction.linkId
            ? { ...link, offsetX: interaction.startOffsetX + dx, offsetY: interaction.startOffsetY + dy }
            : link
        )),
      }))
      return
    }
    if (interaction.type === 'nodeLinkEndpoint') {
      const point = canvasPointFromEvent(event)
      const link = activeProject.nodeLinks.find((item) => item.id === interaction.linkId)
      if (!link) return
      const fixedEndpoint = interaction.activeEnd === 'from' ? link.to : link.from
      const snap = draftPoint(point, fixedEndpoint)
      updateLinkDraftState({
        mode: 'reconnect',
        linkId: link.id,
        activeEnd: interaction.activeEnd,
        fixedEndpoint,
        current: snap.current,
        target: snap.target,
      })
      return
    }
    if (interaction.type === 'choice') {
      const dx = (event.clientX - interaction.startClient.x) / viewport.zoom
      const dy = (event.clientY - interaction.startClient.y) / viewport.zoom
      updateChoice(interaction.choiceId, (choice) => ({
        ...choice,
        offsetX: interaction.startOffsetX + dx,
        offsetY: interaction.startOffsetY + dy,
      }))
    }
  }

  const endPointerInteraction = (event: ReactPointerEvent<HTMLDivElement>) => {
    const interaction = interactionRef.current
    if (interaction?.pointerId === event.pointerId) {
      if (interaction.type === 'link') {
        const target = linkEndpointFromPoint(event)
        if (target) {
          completeLinkDrag(target)
          return
        }
      }
      if (interaction.type === 'nodeLinkEndpoint') {
        const target = linkEndpointFromPoint(event)
        if (target) {
          completeLinkDrag(target)
          return
        }
      }
      interactionRef.current = null
      updateLinkDraftState(null)
    }
  }

  const handleWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    event.preventDefault()
    setCanvasContextMenu(null)
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
    const positionedNodes = [...scenes, ...assetNodes]
    if (!canvasRef.current || positionedNodes.length === 0) return
    const rect = canvasRef.current.getBoundingClientRect()
    const minX = Math.min(...positionedNodes.map((node) => node.position.x))
    const minY = Math.min(...positionedNodes.map((node) => node.position.y))
    const maxX = Math.max(...positionedNodes.map((node) => {
      const type = 'role' in node ? 'scene' : node.type
      return node.position.x + nodeDimensions(type).width
    }))
    const maxY = Math.max(...positionedNodes.map((node) => {
      const type = 'role' in node ? 'scene' : node.type
      return node.position.y + nodeDimensions(type).height
    }))
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

  const addScene = (position = defaultNewScenePosition()) => {
    const scene = createDraftScene(`新场景 ${scenes.length + 1}`, position)
    updateActiveProject((project) => ({
      ...project,
      scenes: [...project.scenes, scene],
      selectedObject: { type: 'scene', id: scene.id },
    }))
  }

  const addAssetNode = (type: AssetNodeType, position = defaultNewScenePosition()) => {
    const titlePrefix = type === 'text' ? '文本' : type === 'image' ? '图片' : '视频'
    const count = assetNodes.filter((asset) => asset.type === type).length + 1
    const asset = createDraftAssetNode(type, `${titlePrefix} ${count}`, position)
    updateActiveProject((project) => ({
      ...project,
      assetNodes: [...project.assetNodes, asset],
      selectedObject: { type, id: asset.id },
    }))
  }

  const openCanvasContextMenu = (event: ReactMouseEvent<HTMLDivElement>) => {
    event.preventDefault()
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const menuWidth = 178
    const menuHeight = 210
    setCanvasContextMenu({
      screenX: clamp(event.clientX - rect.left, 8, Math.max(8, rect.width - menuWidth - 8)),
      screenY: clamp(event.clientY - rect.top, 8, Math.max(8, rect.height - menuHeight - 8)),
      canvasPosition: {
        x: (event.clientX - rect.left - viewport.x) / viewport.zoom,
        y: (event.clientY - rect.top - viewport.y) / viewport.zoom,
      },
    })
  }

  const runContextMenuAction = (action: () => void) => {
    action()
    setCanvasContextMenu(null)
  }

  const deleteNodeLink = (linkId: string) => {
    updateActiveProject((project) => {
      const nextNodeLinks = project.nodeLinks.filter((link) => link.id !== linkId)
      const selectedObjectWasDeleted = project.selectedObject.type === 'nodeLink' && project.selectedObject.id === linkId
      return {
        ...project,
        nodeLinks: nextNodeLinks,
        selectedObject: selectedObjectWasDeleted
          ? firstSelectableObject(project.scenes, project.choices, project.assetNodes)
          : project.selectedObject,
      }
    })
  }

  const deleteAssetNode = (assetId: string) => {
    updateActiveProject((project) => {
      const deleted = project.assetNodes.find((asset) => asset.id === assetId)
      if (!deleted) return project
      const nextAssets = project.assetNodes.filter((asset) => asset.id !== assetId)
      const removedNodeLinkIds = new Set(
        project.nodeLinks
          .filter((link) => (
            (link.from.id === assetId && link.from.type === deleted.type)
            || (link.to.id === assetId && link.to.type === deleted.type)
          ))
          .map((link) => link.id),
      )
      const nextNodeLinks = project.nodeLinks.filter((link) => !removedNodeLinkIds.has(link.id))
      const selectedObjectWasDeleted = (
        (project.selectedObject.id === assetId && project.selectedObject.type === deleted.type)
        || (project.selectedObject.type === 'nodeLink' && removedNodeLinkIds.has(project.selectedObject.id))
      )
      return {
        ...project,
        assetNodes: nextAssets,
        nodeLinks: nextNodeLinks,
        scenes: project.scenes.map((scene) => ({
          ...scene,
          media: {
            ...scene.media,
            videoNodeId: scene.media.videoNodeId === assetId ? '' : scene.media.videoNodeId,
            coverImageNodeId: scene.media.coverImageNodeId === assetId ? '' : scene.media.coverImageNodeId,
          },
        })),
        selectedObject: selectedObjectWasDeleted
          ? firstSelectableObject(project.scenes, project.choices, nextAssets)
          : project.selectedObject,
      }
    })
  }

  const confirmDeleteAssetNode = (assetId: string) => {
    const asset = assetNodes.find((item) => item.id === assetId)
    if (!asset) return
    modal.confirm({
      title: `删除素材「${asset.title}」？`,
      content: '删除后会从画布中移除这个素材，并清空场景中的关联引用。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk() {
        deleteAssetNode(assetId)
        message.success('素材已删除')
      },
    })
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
          ? firstSelectableObject(project.scenes, nextChoices, project.assetNodes)
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
      const nextNodeLinks = project.nodeLinks.filter((link) => (
        !(link.from.type === 'scene' && link.from.id === sceneId)
        && !(link.to.type === 'scene' && link.to.id === sceneId)
      ))
      const removedNodeLinkIds = new Set(project.nodeLinks.filter((link) => !nextNodeLinks.includes(link)).map((link) => link.id))
      const selectedObjectWasDeleted = (
        (project.selectedObject.type === 'scene' && project.selectedObject.id === sceneId)
        || (project.selectedObject.type === 'choice' && deletedChoiceIds.has(project.selectedObject.id))
        || (project.selectedObject.type === 'nodeLink' && removedNodeLinkIds.has(project.selectedObject.id))
      )
      const nextSelectedObject = selectedObjectWasDeleted
        ? firstSelectableObject(nextScenes, nextChoices, project.assetNodes)
        : project.selectedObject
      if (lastCanvasSceneIdByProjectRef.current[project.id] === sceneId) {
        lastCanvasSceneIdByProjectRef.current[project.id] = nextSelectedObject.type === 'scene' ? nextSelectedObject.id : ''
      }
      return {
        ...project,
        scenes: nextScenes,
        choices: nextChoices,
        nodeLinks: nextNodeLinks,
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

  const finishPreviewScene = () => {
    if (outgoingPreviewChoices.length > 0) {
      setPreviewChoicesVisible(true)
      return
    }
    message.info('预览已结束')
  }

  const advancePreview = () => {
    if (!previewScene) return
    if (previewLineIndex < previewScene.script.lines.length - 1) {
      setPreviewLineIndex((index) => index + 1)
      return
    }
    finishPreviewScene()
  }

  const choosePreviewEdge = (choice: ChoiceEdge) => {
    if (!sceneMap.has(choice.toSceneId)) return
    setPreviewSceneId(choice.toSceneId)
    setPreviewLineIndex(0)
    setPreviewChoicesVisible(false)
  }

  useEffect(() => {
    if (!previewOpen || !previewScene || previewChoicesVisible || previewHasVideo || currentPreviewLine) return
    if (outgoingPreviewChoices.length > 0) {
      setPreviewChoicesVisible(true)
    }
  }, [
    currentPreviewLine,
    outgoingPreviewChoices.length,
    previewChoicesVisible,
    previewHasVideo,
    previewOpen,
    previewScene,
  ])

  const refreshReleaseHistory = async (projectId = activeProject.id) => {
    if (!hasCloudCopy(activeProject)) {
      setReleaseHistory([])
      return
    }
    setReleaseLoading(true)
    try {
      const releases = await listInteractiveMovieReleases(projectId)
      setReleaseHistory(releases)
    } catch (error) {
      message.error(resolveErrorMessage(error))
    } finally {
      setReleaseLoading(false)
    }
  }

  const openPublishModal = () => {
    setPublishModalOpen(true)
    void refreshReleaseHistory(activeProject.id)
  }

  const publishCurrentDraft = async () => {
    if (!activeProject.version || !activeProject.contentHash) {
      message.warning('请先保存到云端后再发表')
      return
    }
    if (activeProjectHasUnsavedChanges) {
      message.warning('请先保存当前草稿后再发表')
      return
    }
    setPublishing(true)
    try {
      const result = await publishInteractiveMovieProject<InteractiveMovieProject>(
        activeProject.id,
        activeProject.version,
        activeProject.contentHash,
      )
      replaceProjectFromServer(result.project)
      await refreshReleaseHistory(activeProject.id)
      setSyncMessage(`已发表正式版 v${result.release.version_no}`)
      message.success(`已发表正式版 v${result.release.version_no}`)
    } catch (error) {
      message.error(resolveErrorMessage(error))
    } finally {
      setPublishing(false)
    }
  }

  const setReleaseOnline = async (release: InteractiveMovieRelease) => {
    setPublishing(true)
    try {
      const detail = await setInteractiveMoviePublishedRelease<InteractiveMovieProject>(activeProject.id, release.id)
      replaceProjectFromServer(detail)
      await refreshReleaseHistory(activeProject.id)
      setSyncMessage(`已切换线上版 v${release.version_no}`)
      message.success(`已切换线上版 v${release.version_no}`)
    } catch (error) {
      message.error(resolveErrorMessage(error))
    } finally {
      setPublishing(false)
    }
  }

  const closePublishedProject = async () => {
    if (!activeProject.isPublished) return
    modal.confirm({
      title: '关闭发表？',
      content: '关闭后固定公开 URL 会立即变为 404，正式版历史仍会保留。',
      okText: '关闭发表',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        setPublishing(true)
        try {
          const detail = await closeInteractiveMoviePublication<InteractiveMovieProject>(activeProject.id)
          replaceProjectFromServer(detail)
          await refreshReleaseHistory(activeProject.id)
          setSyncMessage('已关闭发表')
          message.success('已关闭发表')
        } catch (error) {
          message.error(resolveErrorMessage(error))
          throw error
        } finally {
          setPublishing(false)
        }
      },
    })
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
        const project = withCloudMeta(created)
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
      const project = withCloudMeta(saved)
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
      const target = event.target as HTMLElement | null
      const isEditingText = target?.closest('input, textarea, [contenteditable="true"]')
      if (!isEditingText && selectedObject.type === 'nodeLink' && (event.key === 'Delete' || event.key === 'Backspace')) {
        event.preventDefault()
        event.stopPropagation()
        deleteNodeLink(selectedObject.id)
      }
    }
    window.addEventListener('keydown', handleKeyDown, true)
    return () => window.removeEventListener('keydown', handleKeyDown, true)
  }, [deleteNodeLink, saveDraft, selectedObject])

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
        const project = withCloudMeta(latest)
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

  const uploadAssetFile = async (asset: AssetNode, file: File) => {
    setUploadByAssetId((current) => ({
      ...current,
      [asset.id]: { status: 'uploading', message: asset.type === 'image' ? '图片上传中' : '视频上传中' },
    }))
    try {
      const uploaded = asset.type === 'image'
        ? await uploadInteractiveMovieImage(file)
        : await uploadInteractiveMovieVideo(file)
      if (!uploaded.url) {
        setUploadByAssetId((current) => ({
          ...current,
          [asset.id]: { status: 'failed', message: '上传成功，但没有返回可访问 URL' },
        }))
        message.warning('上传成功，但没有返回可访问 URL')
        return
      }
      updateAsset(asset.id, (current) => ({
        ...current,
        media: {
          url: uploaded.url ?? undefined,
          objectKey: uploaded.object_key,
          storageUri: uploaded.storage_uri,
          contentType: uploaded.content_type,
          size: uploaded.size,
          status: 'ready',
        },
      }))
      setUploadByAssetId((current) => ({
        ...current,
        [asset.id]: { status: 'ready', message: `已上传：${uploaded.filename}` },
      }))
      message.success(asset.type === 'image' ? '图片已上传' : '视频已上传')
    } catch (error) {
      const text = resolveErrorMessage(error)
      setUploadByAssetId((current) => ({
        ...current,
        [asset.id]: { status: 'failed', message: text },
      }))
      message.error(text)
    }
  }

  const uploadSceneAsset = async (scene: SceneNode, type: 'image' | 'video', file: File) => {
    try {
      const uploaded = type === 'image'
        ? await uploadInteractiveMovieImage(file)
        : await uploadInteractiveMovieVideo(file)
      if (!uploaded.url) {
        message.warning('上传成功，但没有返回可访问 URL')
        return
      }
      if (type === 'image') {
        updateScene(scene.id, (current) => ({
          ...current,
          media: {
            ...current.media,
            posterUrl: uploaded.url ?? undefined,
            coverImageNodeId: '',
            status: 'ready',
          },
        }))
        message.success('封面图片已上传')
        return
      }
      const asset = createDraftAssetNode(
        type,
        uploaded.filename,
        {
          x: scene.position.x + NODE_WIDTH + 80,
          y: scene.position.y,
        },
      )
      const uploadedAsset: AssetNode = {
        ...asset,
        media: {
          url: uploaded.url ?? undefined,
          objectKey: uploaded.object_key,
          storageUri: uploaded.storage_uri,
          contentType: uploaded.content_type,
          size: uploaded.size,
          status: 'ready',
        },
      }
      updateActiveProject((project) => ({
        ...project,
        assetNodes: [...project.assetNodes, uploadedAsset],
        scenes: project.scenes.map((item) => (
          item.id === scene.id
            ? {
              ...item,
              media: {
                ...item.media,
                kind: 'video',
                videoNodeId: uploadedAsset.id,
              },
            }
            : item
        )),
        selectedObject: { type: uploadedAsset.type, id: uploadedAsset.id },
      }))
      message.success('视频已上传并关联')
    } catch (error) {
      message.error(resolveErrorMessage(error))
    }
  }

  return (
    <div className={workspaceCollapsed ? 'interactive-movie-page workspace-collapsed' : 'interactive-movie-page'}>
      <aside className="movie-workspace-sidebar">
        <div className="movie-sidebar-chrome">
          <WorkbenchHomeButton className="movie-workbench-home" />
        </div>
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
              <span className="movie-project-meta">{project.scenes.length} 场景 · {project.choices.length} 选择 · {project.assetNodes.length} 素材</span>
            </div>
          ))}
        </div>
      </aside>

      <main className="movie-editor-shell">
        <header className="movie-topbar">
          <WorkbenchHomeButton className="movie-mobile-workbench-home" />
          <Flex align="center" gap={12} className="movie-project-heading">
            <div>
              <Typography.Text className="movie-kicker">云端项目 / 互动电影创作平台 MVP</Typography.Text>
              <Input
                variant="borderless"
                value={activeProject.title}
                onChange={(event) => renameProject(event.target.value)}
                className="movie-title-input"
                aria-label="项目名"
              />
            </div>
          </Flex>
          <BrandNavPill activeKey="interactive-movie" className="movie-top-nav" />
          <Space wrap>
            <Tag className="movie-status-tag">{syncing ? '同步检查中' : syncMessage}</Tag>
            {activeProject.isPublished && (
              <Tag color="green" icon={<GlobalOutlined />}>线上 v{activeProject.publishedVersionNo}</Tag>
            )}
            <Button icon={<SaveOutlined />} loading={saving} onClick={() => void saveDraft()}>保存</Button>
            <Button icon={<CloudUploadOutlined />} onClick={openPublishModal}>
              {activeProject.isPublished ? '管理发表' : '发表'}
            </Button>
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
          onContextMenu={openCanvasContextMenu}
        >
          <div
            className={linkDraft ? 'movie-canvas-stage is-linking' : 'movie-canvas-stage'}
            style={{
              transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`,
            }}
          >
            <svg className="movie-edge-layer">
              {nodeLinks.map((link) => {
                const fromEndpoint = resolveFloatingEndpoint(link.from, link.to, sceneMap, assetMap)
                const toEndpoint = resolveFloatingEndpoint(link.to, link.from, sceneMap, assetMap)
                const start = handleAnchor(fromEndpoint, sceneMap, assetMap)
                const end = handleAnchor(toEndpoint, sceneMap, assetMap)
                if (!start || !end) return null
                const selected = selectedObject.type === 'nodeLink' && selectedObject.id === link.id
                const routeOffset = { x: link.offsetX ?? 0, y: link.offsetY ?? 0 }
                const path = linkPath(start, end, fromEndpoint.handle, toEndpoint.handle, routeOffset)
                const midX = (start.x + end.x) / 2 + routeOffset.x
                const midY = (start.y + end.y) / 2 + routeOffset.y
                return (
                  <g key={link.id} className={selected ? 'movie-node-link is-selected' : 'movie-node-link'}>
                    <path
                      className="movie-node-link-hit"
                      d={path}
                      onPointerDown={(event) => beginNodeLinkRouteDrag(event, link)}
                    />
                    <path className="movie-node-link-line" d={path} />
                    {selected && (
                      <>
                        <circle
                          className="movie-node-link-endpoint"
                          cx={start.x}
                          cy={start.y}
                          r={8}
                          onPointerDown={(event) => beginNodeLinkEndpointDrag(event, link, 'from')}
                        />
                        <circle
                          className="movie-node-link-endpoint"
                          cx={end.x}
                          cy={end.y}
                          r={8}
                          onPointerDown={(event) => beginNodeLinkEndpointDrag(event, link, 'to')}
                        />
                        <foreignObject x={midX - 17} y={midY - 17} width="34" height="34">
                          <button
                            type="button"
                            className="movie-node-link-delete"
                            title="删除连接"
                            aria-label="删除连接"
                            onPointerDown={(event) => event.stopPropagation()}
                            onClick={(event) => {
                              event.stopPropagation()
                              deleteNodeLink(link.id)
                            }}
                          >
                            <DeleteOutlined />
                          </button>
                        </foreignObject>
                      </>
                    )}
                  </g>
                )
              })}
              {linkDraft && (() => {
                if (linkDraft.mode === 'create') {
                  const source = linkDraft.target
                    ? resolveFloatingEndpoint(linkDraft.source, linkDraft.target, sceneMap, assetMap)
                    : linkDraft.source
                  const start = handleAnchor(source, sceneMap, assetMap)
                  if (!start) return null
                  const endHandle = linkDraft.target?.handle ?? 'left'
                  return (
                    <g className="movie-node-link is-draft">
                      <path className="movie-node-link-line" d={linkPath(start, linkDraft.current, source.handle, endHandle)} />
                    </g>
                  )
                }
                const movingTarget = linkDraft.target
                const fixed = movingTarget
                  ? resolveFloatingEndpoint(linkDraft.fixedEndpoint, movingTarget, sceneMap, assetMap)
                  : linkDraft.fixedEndpoint
                const fixedAnchor = handleAnchor(fixed, sceneMap, assetMap)
                if (!fixedAnchor) return null
                const movingHandle = movingTarget?.handle ?? (linkDraft.activeEnd === 'from' ? 'right' : 'left')
                const start = linkDraft.activeEnd === 'from' ? linkDraft.current : fixedAnchor
                const end = linkDraft.activeEnd === 'from' ? fixedAnchor : linkDraft.current
                const startHandle = linkDraft.activeEnd === 'from' ? movingHandle : fixed.handle
                const endHandle = linkDraft.activeEnd === 'from' ? fixed.handle : movingHandle
                return (
                  <g className="movie-node-link is-draft">
                    <path className="movie-node-link-line" d={linkPath(start, end, startHandle, endHandle)} />
                  </g>
                )
              })()}
              {choices.map((choice) => {
                const fromScene = sceneMap.get(choice.fromSceneId)
                const toScene = sceneMap.get(choice.toSceneId)
                if (!fromScene || !toScene) return null
                const siblingChoices = choices.filter((item) => (
                  item.fromSceneId === choice.fromSceneId && item.toSceneId === choice.toSceneId
                ))
                const siblingIndex = siblingChoices.findIndex((item) => item.id === choice.id)
                const siblingOffset = (siblingIndex - (siblingChoices.length - 1) / 2) * 46
                const choiceOffsetX = choice.offsetX ?? 0
                const choiceOffsetY = siblingOffset + (choice.offsetY ?? 0)
                const start = {
                  x: fromScene.position.x + NODE_WIDTH,
                  y: fromScene.position.y + NODE_HEIGHT * 0.5 + siblingOffset * 0.28,
                }
                const end = {
                  x: toScene.position.x,
                  y: toScene.position.y + NODE_HEIGHT * 0.5 + siblingOffset * 0.28,
                }
                const midX = (start.x + end.x) / 2 + choiceOffsetX
                const midY = (start.y + end.y) / 2 + choiceOffsetY
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
              const posterUrl = getScenePosterUrl(scene, assetMap)
              return (
                <div
                  key={scene.id}
                  className={selected ? 'movie-scene-node is-selected' : 'movie-scene-node'}
                  style={{ left: scene.position.x, top: scene.position.y }}
                  onPointerDown={(event) => beginNodeDrag(event, 'scene', scene.id)}
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
                    {posterUrl ? (
                      <img src={posterUrl} alt="" className="movie-node-preview-poster" draggable={false} />
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
                  <NodeHandles
                    node={{ type: 'scene', id: scene.id }}
                    highlightedSide={linkDraft?.target?.type === 'scene' && linkDraft.target.id === scene.id ? linkDraft.target.handle : undefined}
                    onBegin={beginLinkDrag}
                  />
                </div>
              )
            })}

            {assetNodes.map((asset) => {
              const selected = selectedObject.type === asset.type && selectedObject.id === asset.id
              const icon = asset.type === 'text'
                ? <FileTextOutlined />
                : asset.type === 'image'
                  ? <PictureOutlined />
                  : <VideoCameraOutlined />
              return (
                <div
                  key={asset.id}
                  className={[
                    'movie-asset-node',
                    `is-${asset.type}`,
                    selected ? 'is-selected' : '',
                  ].filter(Boolean).join(' ')}
                  style={{ left: asset.position.x, top: asset.position.y }}
                  onPointerDown={(event) => beginNodeDrag(event, asset.type, asset.id)}
                  onClick={(event) => {
                    event.stopPropagation()
                    setSelectedObject({ type: asset.type, id: asset.id })
                  }}
                >
                  <Flex align="center" justify="space-between" className="movie-asset-header">
                    <div className="movie-asset-heading">
                      <span className="movie-asset-icon">{icon}</span>
                      <div>
                        <Typography.Text className="movie-node-eyebrow">{assetTypeLabel(asset.type)}</Typography.Text>
                        <Typography.Text className="movie-asset-title">{asset.title}</Typography.Text>
                      </div>
                    </div>
                    <div className="movie-node-actions">
                      <button
                        type="button"
                        className="movie-node-delete"
                        title="删除素材"
                        aria-label={`删除素材 ${asset.title}`}
                        onPointerDown={(event) => event.stopPropagation()}
                        onClick={(event) => {
                          event.stopPropagation()
                          confirmDeleteAssetNode(asset.id)
                        }}
                      >
                        <DeleteOutlined />
                      </button>
                    </div>
                  </Flex>
                  {asset.type === 'text' ? (
                    <div className="movie-asset-text-body">
                      {asset.text?.trim() ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {asset.text}
                        </ReactMarkdown>
                      ) : (
                        '空文本'
                      )}
                    </div>
                  ) : (
                    <div className="movie-asset-media-preview">
                      {asset.type === 'image' && asset.media.url ? (
                        <img src={asset.media.url} alt="" draggable={false} />
                      ) : asset.type === 'video' && asset.media.url ? (
                        <video src={asset.media.url} muted preload="metadata" draggable={false} />
                      ) : (
                        <div className="movie-asset-media-empty">{icon}</div>
                      )}
                    </div>
                  )}
                  <Flex align="center" justify="space-between">
                    <span className="movie-node-meta">{asset.media.status === 'ready' ? '已上传' : asset.type === 'text' ? 'Markdown' : '待上传'}</span>
                    <span className="movie-node-dot" />
                  </Flex>
                  <NodeHandles
                    node={{ type: asset.type, id: asset.id }}
                    highlightedSide={linkDraft?.target?.type === asset.type && linkDraft.target.id === asset.id ? linkDraft.target.handle : undefined}
                    onBegin={beginLinkDrag}
                  />
                </div>
              )
            })}
          </div>

          <div className="movie-canvas-hint">无限画布 · 拖拽空白移动 · 拖拽节点/Choice 调整结构 · 滚轮缩放</div>

          {canvasContextMenu && (
            <div
              className="movie-canvas-context-menu"
              style={{ left: canvasContextMenu.screenX, top: canvasContextMenu.screenY }}
              onPointerDown={(event) => event.stopPropagation()}
              onWheel={(event) => event.stopPropagation()}
            >
              <button type="button" onClick={() => runContextMenuAction(() => addScene(canvasContextMenu.canvasPosition))}>
                <BorderOuterOutlined />
                <span>创建场景</span>
              </button>
              <button type="button" onClick={() => runContextMenuAction(() => addAssetNode('text', canvasContextMenu.canvasPosition))}>
                <FileTextOutlined />
                <span>创建文本</span>
              </button>
              <button type="button" onClick={() => runContextMenuAction(() => addAssetNode('image', canvasContextMenu.canvasPosition))}>
                <PictureOutlined />
                <span>创建图片</span>
              </button>
              <button type="button" onClick={() => runContextMenuAction(() => addAssetNode('video', canvasContextMenu.canvasPosition))}>
                <VideoCameraOutlined />
                <span>创建视频</span>
              </button>
              <button type="button" onClick={() => runContextMenuAction(addChoice)}>
                <BranchesOutlined />
                <span>创建选择</span>
              </button>
            </div>
          )}

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
                    videoNodes={videoNodes}
                    imageNodes={imageNodes}
                    assetMap={assetMap}
                    promptTemplate={promptTemplate}
                    activePanelKeys={scenePanelState[selectedScene.id] ?? []}
                    onActivePanelKeysChange={(keys) => setScenePanelState((current) => ({
                      ...current,
                      [selectedScene.id]: keys,
                    }))}
                    onChange={(updater) => updateScene(selectedScene.id, updater)}
                    onAddLine={() => addLine(selectedScene.id)}
                    onDeleteLine={(lineId) => deleteLine(selectedScene.id, lineId)}
                    onSelectChoice={(choiceId) => setSelectedObject({ type: 'choice', id: choiceId })}
                    onDeleteChoice={confirmDeleteChoice}
                    onUploadSceneAsset={(type, file) => uploadSceneAsset(selectedScene, type, file)}
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
              {selectedAsset && (
                <AssetEditor
                  asset={selectedAsset}
                  uploadState={uploadByAssetId[selectedAsset.id] ?? { status: 'idle' }}
                  onChange={(updater) => updateAsset(selectedAsset.id, updater)}
                  onUpload={(file) => void uploadAssetFile(selectedAsset, file)}
                  onDelete={() => confirmDeleteAssetNode(selectedAsset.id)}
                />
              )}
              {selectedNodeLink && (
                <NodeLinkEditor
                  link={selectedNodeLink}
                  sceneMap={sceneMap}
                  assetMap={assetMap}
                  onDelete={() => deleteNodeLink(selectedNodeLink.id)}
                />
              )}
              {!selectedScene && !selectedChoice && !selectedAsset && !selectedNodeLink && (
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
                <Button shape="circle" icon={<PlusOutlined />} onClick={() => addScene()} />
              </Tooltip>
              <Tooltip title="添加选择">
                <Button shape="circle" icon={<BranchesOutlined />} onClick={addChoice} />
              </Tooltip>
              <Tooltip title="添加文本">
                <Button shape="circle" icon={<FileTextOutlined />} onClick={() => addAssetNode('text')} />
              </Tooltip>
              <Tooltip title="添加图片">
                <Button shape="circle" icon={<PictureOutlined />} onClick={() => addAssetNode('image')} />
              </Tooltip>
              <Tooltip title="添加视频">
                <Button shape="circle" icon={<VideoCameraOutlined />} onClick={() => addAssetNode('video')} />
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
            <div className={previewHasVideo ? 'movie-preview-scene has-video' : 'movie-preview-scene'}>
              {previewVideoUrl && (
                <video
                  key={previewScene.id}
                  src={previewVideoUrl}
                  poster={previewPosterUrl}
                  className="movie-preview-video"
                  controls
                  autoPlay
                  playsInline
                  draggable={false}
                  onEnded={finishPreviewScene}
                />
              )}
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
              {!previewChoicesVisible && !previewHasVideo && currentPreviewLine && (
                <button type="button" className="movie-dialogue-box" onClick={advancePreview}>
                  <span className="movie-dialogue-speaker">{currentPreviewLine.speaker || '角色'}</span>
                  <span className="movie-dialogue-text">{currentPreviewLine.text}</span>
                  <span className="movie-dialogue-next">点击继续</span>
                </button>
              )}
              {!previewChoicesVisible && !previewHasVideo && !currentPreviewLine && (
                <div className="movie-preview-choices">
                  <Button size="large" onClick={advancePreview}>继续</Button>
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      <Modal
        title="发表与正式版"
        open={publishModalOpen}
        onCancel={() => setPublishModalOpen(false)}
        footer={null}
        width={760}
        className="movie-publish-modal"
      >
        <Flex vertical gap={16}>
          <section className="movie-publish-status">
            <Flex align="center" justify="space-between" gap={12} wrap>
              <div>
                <Typography.Text className="movie-panel-kicker">公开地址</Typography.Text>
                <Typography.Title level={5} className="movie-publish-title">
                  {activeProject.isPublished ? `已发表 v${activeProject.publishedVersionNo}` : '未发表'}
                </Typography.Title>
              </div>
              <Space wrap>
                {activeProject.isPublished && (
                  <Button danger icon={<PoweroffOutlined />} loading={publishing} onClick={() => void closePublishedProject()}>
                    关闭发表
                  </Button>
                )}
                <Button
                  type="primary"
                  icon={<CloudUploadOutlined />}
                  loading={publishing}
                  disabled={saving || activeProjectHasUnsavedChanges}
                  onClick={() => void publishCurrentDraft()}
                >
                  发表当前草稿
                </Button>
              </Space>
            </Flex>
            <div className="movie-public-url">
              <LinkOutlined />
              <Typography.Text copyable={{ text: activeProjectPublicUrl }} className="movie-public-url-text">
                {activeProjectPublicUrl}
              </Typography.Text>
            </div>
            {activeProjectHasUnsavedChanges && (
              <div className="movie-publish-warning">请先保存当前草稿后再发表。</div>
            )}
          </section>

          <section className="movie-panel-section">
            <Flex align="center" justify="space-between">
              <Typography.Text className="movie-panel-label">正式版历史</Typography.Text>
              <Button size="small" loading={releaseLoading} onClick={() => void refreshReleaseHistory(activeProject.id)}>
                刷新
              </Button>
            </Flex>
            {releaseHistory.length > 0 ? (
              <div className="movie-release-list">
                {releaseHistory.map((release) => (
                  <div key={release.id} className={release.is_current ? 'movie-release-row is-current' : 'movie-release-row'}>
                    <div className="movie-release-main">
                      <span className="movie-release-version">v{release.version_no}</span>
                      <span className="movie-release-title">{release.title}</span>
                      <span className="movie-release-time">{formatDateTime(release.created_at)}</span>
                    </div>
                    {release.is_current ? (
                      <Tag color="green" icon={<CheckCircleOutlined />}>线上版</Tag>
                    ) : (
                      <Button size="small" loading={publishing} onClick={() => void setReleaseOnline(release)}>
                        设为线上版
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={releaseLoading ? '加载正式版历史中' : '暂无正式版'} />
            )}
          </section>
        </Flex>
      </Modal>
    </div>
  )
}

function SceneEditor({
  scene,
  outgoingChoices,
  videoNodes,
  imageNodes,
  assetMap,
  promptTemplate,
  activePanelKeys,
  onActivePanelKeysChange,
  onChange,
  onAddLine,
  onDeleteLine,
  onSelectChoice,
  onDeleteChoice,
  onUploadSceneAsset,
  onPreview,
  onDeleteScene,
}: {
  scene: SceneNode
  outgoingChoices: ChoiceEdge[]
  videoNodes: AssetNode[]
  imageNodes: AssetNode[]
  assetMap: Map<string, AssetNode>
  promptTemplate: PromptTemplate | null
  activePanelKeys: string[]
  onActivePanelKeysChange: (keys: string[]) => void
  onChange: (updater: (scene: SceneNode) => SceneNode) => void
  onAddLine: () => void
  onDeleteLine: (lineId: string) => void
  onSelectChoice: (choiceId: string) => void
  onDeleteChoice: (choiceId: string) => void
  onUploadSceneAsset: (type: 'image' | 'video', file: File) => Promise<void>
  onPreview: () => void
  onDeleteScene: () => void
}) {
  const promptParts = scene.script.promptParts ?? defaultPromptParts(scene.title)
  const generatedPrompt = buildVideoPrompt(scene)
  const [videoPreviewOpen, setVideoPreviewOpen] = useState(false)
  const [assetPickerType, setAssetPickerType] = useState<'image' | 'video' | null>(null)
  const [sceneUploadingType, setSceneUploadingType] = useState<'image' | 'video' | null>(null)
  const sceneVideoUrl = getSceneVideoUrl(scene, assetMap)
  const scenePosterUrl = getScenePosterUrl(scene, assetMap)
  const selectedVideoNode = scene.media.videoNodeId ? assetMap.get(scene.media.videoNodeId) : null
  const selectedImageNode = scene.media.coverImageNodeId ? assetMap.get(scene.media.coverImageNodeId) : null

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

  const configPanel = (
    <Flex vertical gap={14}>
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
        <Flex align="center" justify="space-between">
          <Typography.Text className="movie-panel-label">场景结束后的选择</Typography.Text>
          <Tag className="movie-choice-count-tag">{outgoingChoices.length}</Tag>
        </Flex>
        {outgoingChoices.length > 0 ? (
          <Flex vertical gap={8}>
            {outgoingChoices.map((choice) => (
              <div key={choice.id} className="movie-choice-row">
                <button type="button" className="movie-choice-row-main" onClick={() => onSelectChoice(choice.id)}>
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
    </Flex>
  )

  const mediaPanel = (
    <section className="movie-panel-section">
      <Typography.Text className="movie-panel-label">画面占位</Typography.Text>
      <div className="movie-panel-media" tabIndex={0}>
        {scenePosterUrl ? (
          <img src={scenePosterUrl} alt={`${scene.title} 封面`} className="movie-panel-poster" draggable={false} />
        ) : sceneVideoUrl ? (
          <video src={sceneVideoUrl} muted preload="metadata" className="movie-panel-video" draggable={false} />
        ) : (
          <div className="movie-panel-media-empty">
            <VideoCameraOutlined />
            <span>选择视频和封面素材</span>
          </div>
        )}
        <div className="movie-panel-media-overlay">
          {sceneVideoUrl && (
            <Button icon={<PlayCircleOutlined />} onClick={() => setVideoPreviewOpen(true)}>
              预览
            </Button>
          )}
        </div>
      </div>
      <Flex vertical gap={10} style={{ marginTop: 12 }}>
        <div className="movie-scene-asset-row">
          <div>
            <Typography.Text className="movie-panel-label">画面视频</Typography.Text>
            <div className="movie-scene-asset-name">{selectedVideoNode?.title ?? '未选择视频'}</div>
          </div>
          <Space>
            <Upload
              accept="video/*"
              showUploadList={false}
              beforeUpload={(file) => {
                setSceneUploadingType('video')
                void onUploadSceneAsset('video', file).finally(() => setSceneUploadingType(null))
                return Upload.LIST_IGNORE
              }}
            >
              <Button size="small" icon={<UploadOutlined />} loading={sceneUploadingType === 'video'}>上传</Button>
            </Upload>
            <Button size="small" icon={<VideoCameraOutlined />} onClick={() => setAssetPickerType('video')}>选择</Button>
          </Space>
        </div>
        <div className="movie-scene-asset-row">
          <div>
            <Typography.Text className="movie-panel-label">封面图片</Typography.Text>
            <div className="movie-scene-asset-name">{selectedImageNode?.title ?? '未选择图片'}</div>
          </div>
          <Space>
            <Upload
              accept="image/*"
              showUploadList={false}
              beforeUpload={(file) => {
                setSceneUploadingType('image')
                void onUploadSceneAsset('image', file).finally(() => setSceneUploadingType(null))
                return Upload.LIST_IGNORE
              }}
            >
              <Button size="small" icon={<UploadOutlined />} loading={sceneUploadingType === 'image'}>上传</Button>
            </Upload>
            <Button size="small" icon={<PictureOutlined />} onClick={() => setAssetPickerType('image')}>选择</Button>
          </Space>
        </div>
      </Flex>
    </section>
  )

  const promptPanel = (
    <section className="movie-panel-section">
      <Typography.Text className="movie-panel-label">视频提示词</Typography.Text>
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
      <Input value={promptParts.subject} onChange={(event) => updatePromptParts({ subject: event.target.value })} placeholder="主体：例如，年轻女性林夏站在老式公寓走廊" />
      <Input.TextArea value={promptParts.action} autoSize={{ minRows: 2, maxRows: 4 }} onChange={(event) => updatePromptParts({ action: event.target.value })} placeholder="动作：主体做什么，尽量聚焦一组主要动作" />
      <Input.TextArea value={promptParts.scene} autoSize={{ minRows: 2, maxRows: 4 }} onChange={(event) => updatePromptParts({ scene: event.target.value })} placeholder="场景：空间、时代、天气、道具、情绪氛围" />
      <Input.TextArea value={promptParts.camera} autoSize={{ minRows: 2, maxRows: 4 }} onChange={(event) => updatePromptParts({ camera: event.target.value })} placeholder="镜头：景别、机位、运镜或镜头切换" />
      <Input.TextArea value={promptParts.timeline} autoSize={{ minRows: 2, maxRows: 4 }} onChange={(event) => updatePromptParts({ timeline: event.target.value })} placeholder="时序：例如 [0-2s] 建立场景；[2-5s] 完成关键动作" />
      <Input.TextArea value={promptParts.style} autoSize={{ minRows: 2, maxRows: 4 }} onChange={(event) => updatePromptParts({ style: event.target.value })} placeholder="风格：电影感、写实、低饱和、高对比、细腻光影" />
      <Input.TextArea value={promptParts.constraints} autoSize={{ minRows: 2, maxRows: 4 }} onChange={(event) => updatePromptParts({ constraints: event.target.value })} placeholder="约束：不出现文字水印，不切换主角，主体一致" />
      <Typography.Text className="movie-panel-label">最终提示词</Typography.Text>
      <Input.TextArea
        value={scene.script.videoPrompt || generatedPrompt}
        autoSize={{ minRows: 3, maxRows: 6 }}
        onChange={(event) => updateScript({ videoPrompt: event.target.value })}
      />
    </section>
  )

  return (
    <>
      <Collapse
        className="movie-scene-collapse"
        activeKey={activePanelKeys}
        onChange={(keys) => onActivePanelKeysChange(Array.isArray(keys) ? keys.map(String) : [String(keys)])}
        items={[
          { key: 'config', label: '节点配置', children: configPanel },
          { key: 'media', label: '画面选择', children: mediaPanel },
          { key: 'prompt', label: '提示词编辑', children: promptPanel },
        ]}
      />
      <Modal
        title={scene.title}
        open={videoPreviewOpen}
        footer={null}
        centered
        width={860}
        onCancel={() => setVideoPreviewOpen(false)}
        className="movie-video-preview-modal"
      >
        {sceneVideoUrl && (
          <video src={sceneVideoUrl} controls autoPlay className="movie-video-preview-player" draggable={false} />
        )}
      </Modal>
      <Modal
        title={assetPickerType === 'video' ? '选择画面视频' : '选择封面图片'}
        open={assetPickerType !== null}
        footer={null}
        width={620}
        onCancel={() => setAssetPickerType(null)}
        className="movie-video-preview-modal"
      >
        <AssetPickerList
          assets={assetPickerType === 'video' ? videoNodes : imageNodes}
          emptyText={assetPickerType === 'video' ? '还没有视频素材' : '还没有图片素材'}
          onSelect={(assetId) => {
            onChange((current) => ({
              ...current,
              media: {
                ...current.media,
                kind: assetPickerType === 'video' ? 'video' : current.media.kind,
                videoNodeId: assetPickerType === 'video' ? assetId : current.media.videoNodeId,
                coverImageNodeId: assetPickerType === 'image' ? assetId : current.media.coverImageNodeId,
              },
            }))
            setAssetPickerType(null)
          }}
        />
      </Modal>
    </>
  )
}

function endpointLabel(
  endpoint: NodeLinkEndpoint,
  sceneMap: Map<string, SceneNode>,
  assetMap: Map<string, AssetNode>,
) {
  if (endpoint.type === 'scene') {
    const scene = sceneMap.get(endpoint.id)
    return `场景：${scene?.title ?? endpoint.id} · ${endpoint.handle}`
  }
  const asset = assetMap.get(endpoint.id)
  return `${assetTypeLabel(endpoint.type)}：${asset?.title ?? endpoint.id} · ${endpoint.handle}`
}

function NodeLinkEditor({
  link,
  sceneMap,
  assetMap,
  onDelete,
}: {
  link: NodeLink
  sceneMap: Map<string, SceneNode>
  assetMap: Map<string, AssetNode>
  onDelete: () => void
}) {
  return (
    <section className="movie-panel-section movie-node-link-editor">
      <Flex align="center" justify="space-between">
        <div>
          <Typography.Text className="movie-panel-label">节点连接</Typography.Text>
          <Typography.Title level={4}>连接关系</Typography.Title>
        </div>
        <Button danger icon={<DeleteOutlined />} onClick={onDelete}>删除</Button>
      </Flex>
      <div className="movie-link-endpoint-list">
        <div>
          <Typography.Text className="movie-panel-label">起点</Typography.Text>
          <Typography.Text>{endpointLabel(link.from, sceneMap, assetMap)}</Typography.Text>
        </div>
        <div>
          <Typography.Text className="movie-panel-label">终点</Typography.Text>
          <Typography.Text>{endpointLabel(link.to, sceneMap, assetMap)}</Typography.Text>
        </div>
      </div>
    </section>
  )
}

function NodeHandles({
  node,
  highlightedSide,
  onBegin,
}: {
  node: Pick<NodeLinkEndpoint, 'type' | 'id'>
  highlightedSide?: NodeHandleSide
  onBegin: (event: ReactPointerEvent<HTMLButtonElement>, endpoint: NodeLinkEndpoint) => void
}) {
  const sides: NodeHandleSide[] = ['top', 'right', 'bottom', 'left']
  return (
    <div className="movie-node-handles" aria-hidden="true">
      {sides.map((side) => {
        const endpoint: NodeLinkEndpoint = { ...node, handle: side }
        return (
          <button
            key={side}
            type="button"
            className={[
              'movie-node-handle',
              `is-${side}`,
              highlightedSide === side ? 'is-snap-target' : '',
            ].filter(Boolean).join(' ')}
            data-node-type={node.type}
            data-node-id={node.id}
            data-handle={side}
            onPointerDown={(event) => onBegin(event, endpoint)}
            title="拖拽连接节点"
          />
        )
      })}
    </div>
  )
}

function AssetPickerList({
  assets,
  emptyText,
  onSelect,
}: {
  assets: AssetNode[]
  emptyText: string
  onSelect: (assetId: string) => void
}) {
  if (assets.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />
  }
  return (
    <div className="movie-asset-picker-list">
      {assets.map((asset) => (
        <button key={asset.id} type="button" className="movie-asset-picker-item" onClick={() => onSelect(asset.id)}>
          <span className="movie-asset-picker-thumb">
            {asset.type === 'image' && asset.media.url ? (
              <img src={asset.media.url} alt="" draggable={false} />
            ) : asset.type === 'video' && asset.media.url ? (
              <video src={asset.media.url} muted preload="metadata" draggable={false} />
            ) : asset.type === 'image' ? (
              <PictureOutlined />
            ) : (
              <VideoCameraOutlined />
            )}
          </span>
          <span className="movie-asset-picker-main">
            <span className="movie-asset-picker-title">{asset.title}</span>
            <span className="movie-asset-picker-meta">{asset.media.status === 'ready' ? '可用素材' : '未上传'}</span>
          </span>
        </button>
      ))}
    </div>
  )
}

function AssetEditor({
  asset,
  uploadState,
  onChange,
  onUpload,
  onDelete,
}: {
  asset: AssetNode
  uploadState: AssetUploadState
  onChange: (updater: (asset: AssetNode) => AssetNode) => void
  onUpload: (file: File) => void
  onDelete: () => void
}) {
  const [markdownPreview, setMarkdownPreview] = useState(false)
  const isUploading = uploadState.status === 'uploading'
  const isText = asset.type === 'text'
  const isImage = asset.type === 'image'

  const updateText = (text: string) => {
    onChange((current) => ({ ...current, text }))
  }

  const appendMarkdown = (prefix: string, suffix = '') => {
    const currentText = asset.text ?? ''
    updateText(`${currentText}${currentText.endsWith('\n') || !currentText ? '' : '\n'}${prefix}${suffix}`)
  }

  return (
    <Flex vertical gap={16}>
      <Flex align="flex-start" justify="space-between" gap={12}>
        <div className="movie-panel-title-block">
          <Typography.Text className="movie-panel-kicker">{assetTypeLabel(asset.type)}</Typography.Text>
          <Input
            value={asset.title}
            onChange={(event) => onChange((current) => ({ ...current, title: event.target.value }))}
            className="movie-panel-title-input"
          />
        </div>
        <Button danger type="text" icon={<DeleteOutlined />} onClick={onDelete} aria-label={`删除素材 ${asset.title}`} />
      </Flex>

      {isText ? (
        <section className="movie-panel-section">
          <Flex align="center" justify="space-between">
            <Typography.Text className="movie-panel-label">文本内容</Typography.Text>
            <Space>
              <Tooltip title="加粗">
                <Button size="small" icon={<BorderOuterOutlined />} onClick={() => appendMarkdown('**加粗文本**')} />
              </Tooltip>
              <Tooltip title="斜体">
                <Button size="small" icon={<ItalicOutlined />} onClick={() => appendMarkdown('*斜体文本*')} />
              </Tooltip>
              <Tooltip title="无序列表">
                <Button size="small" icon={<UnorderedListOutlined />} onClick={() => appendMarkdown('- 列表项')} />
              </Tooltip>
              <Tooltip title="有序列表">
                <Button size="small" icon={<OrderedListOutlined />} onClick={() => appendMarkdown('1. 列表项')} />
              </Tooltip>
              <Button size="small" icon={<EditOutlined />} onClick={() => setMarkdownPreview((value) => !value)}>
                {markdownPreview ? '编辑' : '预览'}
              </Button>
            </Space>
          </Flex>
          {markdownPreview ? (
            <div className="movie-markdown-preview">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{asset.text ?? ''}</ReactMarkdown>
            </div>
          ) : (
            <Input.TextArea
              value={asset.text ?? ''}
              autoSize={{ minRows: 10, maxRows: 18 }}
              onChange={(event) => updateText(event.target.value)}
            />
          )}
        </section>
      ) : (
        <section className="movie-panel-section">
          <Typography.Text className="movie-panel-label">{isImage ? '图片文件' : '视频文件'}</Typography.Text>
          <div className="movie-panel-media" tabIndex={0}>
            {isImage && asset.media.url ? (
              <img src={asset.media.url} alt={asset.title} className="movie-panel-poster" draggable={false} />
            ) : !isImage && asset.media.url ? (
              <video src={asset.media.url} muted preload="metadata" className="movie-panel-video" draggable={false} />
            ) : (
              <div className="movie-panel-media-empty">
                {isImage ? <PictureOutlined /> : <VideoCameraOutlined />}
                <span>{isImage ? '图片待上传' : '视频待上传'}</span>
              </div>
            )}
            <div className="movie-panel-media-overlay">
              <Upload
                accept={isImage ? 'image/*' : 'video/*'}
                showUploadList={false}
                beforeUpload={(file) => {
                  onUpload(file)
                  return Upload.LIST_IGNORE
                }}
              >
                <Button icon={<UploadOutlined />} loading={isUploading}>
                  上传
                </Button>
              </Upload>
              {asset.media.url && !isImage && (
                <Button icon={<PlayCircleOutlined />} onClick={() => window.open(asset.media.url, '_blank', 'noreferrer')}>
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
        </section>
      )}
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
