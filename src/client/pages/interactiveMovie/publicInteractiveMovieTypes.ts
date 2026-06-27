export type ScriptLine = {
  id: string
  speaker: string
  text: string
}

export type SceneNode = {
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
    videoNodeId?: string
    coverImageNodeId?: string
  }
}

export type AssetNode = {
  id: string
  type: 'text' | 'image' | 'video'
  title: string
  media: {
    url?: string
  }
}

export type ChoiceEdge = {
  id: string
  fromSceneId: string
  toSceneId: string
  label: string
}

export type PublicMovieDocument = {
  id: string
  title: string
  scenes: SceneNode[]
  choices: ChoiceEdge[]
  assetNodes?: AssetNode[]
}

export type BootPreloadState = {
  status: 'idle' | 'loading' | 'ready'
  loaded: number
  total: number
  message: string
}

export type UnlockProgress = {
  releaseId: string
  visitedSceneIds: string[]
  chosenChoiceIds: string[]
  updatedAt: string
}

export type RouteTreeNodeStatus = 'current' | 'unlocked' | 'locked'
export type RouteTreeEdgeStatus = 'chosen' | 'available' | 'locked'

export type RouteTreeNode = {
  scene: SceneNode
  x: number
  y: number
  status: RouteTreeNodeStatus
}

export type RouteTreeEdge = {
  id: string
  path: string
  status: RouteTreeEdgeStatus
}

export type RouteTreeChoice = {
  choice: ChoiceEdge
  x: number
  y: number
  status: RouteTreeEdgeStatus
}

export type RouteTree = {
  nodes: RouteTreeNode[]
  choiceNodes: RouteTreeChoice[]
  edges: RouteTreeEdge[]
  width: number
  height: number
}
