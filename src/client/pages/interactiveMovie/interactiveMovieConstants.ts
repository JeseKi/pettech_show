import type { SceneRole } from './interactiveMovieTypes'

export const STORAGE_KEY = 'pettech.interactiveMovie.workspace.v1'
export const CLOUD_REPLICA_PREFIX = 'pettech.interactiveMovie.cloudReplica.'
export const DRAFT_REPLICA_PREFIX = 'pettech.interactiveMovie.draftReplica.'
export const SCENE_PANEL_STATE_KEY = 'pettech.interactiveMovie.scenePanelState.v1'
export const MISSING_PROJECT_DETAIL = '互动电影项目不存在'
export const NODE_WIDTH = 292
export const NODE_HEIGHT = 236
export const ASSET_NODE_WIDTH = 244
export const ASSET_NODE_TEXT_HEIGHT = 142
export const ASSET_NODE_MEDIA_HEIGHT = 190
export const MIN_ZOOM = 0.25
export const MAX_ZOOM = 2
export const LINK_SNAP_RADIUS = 44
export const CREATE_SCENE_SELECT_VALUE = '__create_scene__'

export const roleLabels: Record<SceneRole, string> = {
  start: '开场',
  middle: '过场',
  ending: '结局',
}

export const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

export const uniqueId = (prefix: string) => `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
