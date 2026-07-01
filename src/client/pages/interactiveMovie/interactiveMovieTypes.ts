export type SceneRole = 'start' | 'middle' | 'ending'
export type AssetNodeType = 'text' | 'image' | 'video'
export type ConnectableNodeType = 'scene' | AssetNodeType
export type NodeHandleSide = 'top' | 'right' | 'bottom' | 'left'
export type SelectedObject = { type: 'scene' | 'choice' | AssetNodeType | 'nodeLink'; id: string }

export type ScriptLine = {
  id: string
  speaker: string
  text: string
}

export type SceneScript = {
  synopsis: string
  visualDescription: string
  lines: ScriptLine[]
  videoPrompt: string
  promptParts?: VideoPromptParts
}

export type SceneNode = {
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

export type AssetNode = {
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

export type ChoiceEdge = {
  id: string
  fromSceneId: string
  toSceneId: string
  label: string
  trigger: 'after_scene'
  offsetX?: number
  offsetY?: number
}

export type NodeLinkEndpoint = {
  type: ConnectableNodeType
  id: string
  handle: NodeHandleSide
}

export type NodeLink = {
  id: string
  from: NodeLinkEndpoint
  to: NodeLinkEndpoint
  offsetX?: number
  offsetY?: number
}

export type CanvasViewport = {
  x: number
  y: number
  zoom: number
}

export type VideoPromptParts = {
  subject: string
  action: string
  scene: string
  camera: string
  timeline: string
  style: string
  constraints: string
}

export type AssetUploadState = {
  status: 'idle' | 'uploading' | 'ready' | 'failed'
  message?: string
}

export type InteractiveMovieProject = {
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

export type StoredWorkspace = {
  activeProjectId: string
  projects: InteractiveMovieProject[]
}

export type InteractionState =
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
    type: 'choiceEndpoint'
    pointerId: number
    choiceId: string
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

export type CanvasContextMenuState = {
  screenX: number
  screenY: number
  canvasPosition: { x: number; y: number }
}

export type LinkDraftState = {
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

export type ChoiceEndpointDraftState = {
  choiceId: string
  current: { x: number; y: number }
  targetSceneId?: string
}
