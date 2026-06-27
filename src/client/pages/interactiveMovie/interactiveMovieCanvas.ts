import type { AssetNode, AssetNodeType, ConnectableNodeType, InteractiveMovieProject, NodeHandleSide, NodeLinkEndpoint, SceneNode } from './interactiveMovieTypes'
import { ASSET_NODE_MEDIA_HEIGHT, ASSET_NODE_TEXT_HEIGHT, ASSET_NODE_WIDTH, NODE_HEIGHT, NODE_WIDTH } from './interactiveMovieConstants'

export const formatDateTime = (value: string | null | undefined) => {
  if (!value) return '-'
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return value
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(timestamp))
}

export const assetTypeLabel = (type: AssetNodeType) => {
  if (type === 'text') return 'Text'
  if (type === 'image') return 'Image'
  return 'Video'
}

export const getSceneVideoUrl = (scene: SceneNode | null | undefined, assetMap: Map<string, AssetNode>) => {
  if (!scene) return undefined
  const videoNode = scene.media.videoNodeId ? assetMap.get(scene.media.videoNodeId) : undefined
  const referencedUrl = videoNode?.type === 'video' ? videoNode.media.url?.trim() : ''
  if (referencedUrl) return referencedUrl
  if (scene.media.kind !== 'video') return undefined
  const legacyUrl = scene.media.url?.trim()
  return legacyUrl || undefined
}

export const getScenePosterUrl = (scene: SceneNode | null | undefined, assetMap: Map<string, AssetNode>) => {
  if (!scene) return undefined
  const imageNode = scene.media.coverImageNodeId ? assetMap.get(scene.media.coverImageNodeId) : undefined
  const referencedUrl = imageNode?.type === 'image' ? imageNode.media.url?.trim() : ''
  return referencedUrl || scene.media.posterUrl?.trim() || undefined
}

export const nodeDimensions = (type: ConnectableNodeType) => {
  if (type === 'scene') return { width: NODE_WIDTH, height: NODE_HEIGHT }
  if (type === 'text') return { width: ASSET_NODE_WIDTH, height: ASSET_NODE_TEXT_HEIGHT }
  return { width: ASSET_NODE_WIDTH, height: ASSET_NODE_MEDIA_HEIGHT }
}

export const nodePosition = (
  endpoint: Pick<NodeLinkEndpoint, 'type' | 'id'>,
  sceneMap: Map<string, SceneNode>,
  assetMap: Map<string, AssetNode>,
) => {
  if (endpoint.type === 'scene') return sceneMap.get(endpoint.id)?.position ?? null
  return assetMap.get(endpoint.id)?.position ?? null
}

export const nodeBounds = (
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

export const floatingHandle = (
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

export const resolveFloatingEndpoint = (
  endpoint: NodeLinkEndpoint,
  other: NodeLinkEndpoint,
  sceneMap: Map<string, SceneNode>,
  assetMap: Map<string, AssetNode>,
): NodeLinkEndpoint => ({
  ...endpoint,
  handle: floatingHandle(endpoint, other, sceneMap, assetMap),
})

export const handleAnchor = (
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

export const linkPath = (
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

export const sameNodeEndpoint = (a: Pick<NodeLinkEndpoint, 'type' | 'id'>, b: Pick<NodeLinkEndpoint, 'type' | 'id'>) => (
  a.type === b.type && a.id === b.id
)

export const nodePairKey = (a: Pick<NodeLinkEndpoint, 'type' | 'id'>, b: Pick<NodeLinkEndpoint, 'type' | 'id'>) => (
  [`${a.type}:${a.id}`, `${b.type}:${b.id}`].sort().join('|')
)

export const projectHasNodePairLink = (
  project: InteractiveMovieProject,
  from: NodeLinkEndpoint,
  to: NodeLinkEndpoint,
  exceptLinkId = '',
) => project.nodeLinks.some((link) => (
  link.id !== exceptLinkId && nodePairKey(link.from, link.to) === nodePairKey(from, to)
))
