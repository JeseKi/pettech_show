import type { ChoiceEdge, PublicMovieDocument, RouteTree, RouteTreeChoice, RouteTreeEdge, RouteTreeEdgeStatus, RouteTreeNode, RouteTreeNodeStatus, SceneNode } from './publicInteractiveMovieTypes'
import { TREE_CHOICE_HEIGHT, TREE_CHOICE_WIDTH, TREE_COLUMN_GAP, TREE_NODE_HEIGHT, TREE_NODE_WIDTH, TREE_ROW_GAP } from './publicInteractiveMovieConstants'

export function buildRouteTree(
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
