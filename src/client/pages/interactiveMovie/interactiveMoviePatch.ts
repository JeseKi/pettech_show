import type { InteractiveMovieProjectPatch } from '../../lib/interactiveMovie'
import type { AssetNode, ChoiceEdge, InteractiveMovieProject, NodeLink, ScriptLine, SceneNode } from './interactiveMovieTypes'

export const flattenScene = (scene: SceneNode, sortOrder: number): Record<string, unknown> => ({
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

export const flattenAssetNode = (asset: AssetNode, sortOrder: number): Record<string, unknown> => ({
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

export const flattenChoice = (choice: ChoiceEdge, sortOrder: number): Record<string, unknown> => ({
  id: choice.id,
  fromSceneId: choice.fromSceneId,
  toSceneId: choice.toSceneId,
  label: choice.label,
  trigger: choice.trigger,
  offsetX: choice.offsetX ?? 0,
  offsetY: choice.offsetY ?? 0,
  sortOrder,
})

export const flattenNodeLink = (link: NodeLink, sortOrder: number): Record<string, unknown> => ({
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

export const flattenLine = (sceneId: string, line: ScriptLine, sortOrder: number): Record<string, unknown> => ({
  id: line.id,
  sceneId,
  speaker: line.speaker,
  text: line.text,
  sortOrder,
})

export const shallowChanged = (before: Record<string, unknown> | undefined, after: Record<string, unknown>) => (
  !before || Object.keys(after).some((key) => before[key] !== after[key])
)

export const buildProjectPatch = (base: InteractiveMovieProject, draft: InteractiveMovieProject): InteractiveMovieProjectPatch => {
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

export const patchHasChanges = (patch: InteractiveMovieProjectPatch) => (
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

export const localDraftIsNewer = (draft: InteractiveMovieProject, cloud: InteractiveMovieProject) => {
  const draftTime = Date.parse(draft.updatedAt)
  const cloudTime = Date.parse(cloud.cloudUpdatedAt ?? cloud.updatedAt)
  return Number.isFinite(draftTime) && Number.isFinite(cloudTime) && draftTime > cloudTime
}

export const mergeDraftWithCloudMeta = (
  draft: InteractiveMovieProject,
  cloud: InteractiveMovieProject,
): InteractiveMovieProject => ({
  ...draft,
  version: cloud.version,
  contentHash: cloud.contentHash,
  cloudUpdatedAt: cloud.cloudUpdatedAt,
})
