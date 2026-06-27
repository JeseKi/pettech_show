import type { AssetNode, PublicMovieDocument, SceneNode, UnlockProgress } from './publicInteractiveMovieTypes'
import { PRELOAD_TIMEOUT_MS, UNLOCK_STORAGE_PREFIX } from './publicInteractiveMovieConstants'

export function findStartScene(document: PublicMovieDocument) {
  return document.scenes.find((scene) => scene.role === 'start') ?? document.scenes[0] ?? null
}

export function sceneRoleLabel(role: SceneNode['role']) {
  if (role === 'start') return '开场'
  if (role === 'ending') return '结局'
  return '节点'
}

export function getSceneVideoUrl(scene: SceneNode | null | undefined, assetMap: Map<string, AssetNode>) {
  if (!scene) return undefined
  const videoNode = scene.media.videoNodeId ? assetMap.get(scene.media.videoNodeId) : undefined
  const referencedUrl = videoNode?.type === 'video' ? videoNode.media.url?.trim() : ''
  if (referencedUrl) return referencedUrl
  if (scene.media.kind !== 'video') return undefined
  const url = scene.media.url?.trim()
  return url || undefined
}

export function getScenePosterUrl(scene: SceneNode | null | undefined, assetMap: Map<string, AssetNode>) {
  if (!scene) return undefined
  const imageNode = scene.media.coverImageNodeId ? assetMap.get(scene.media.coverImageNodeId) : undefined
  const referencedUrl = imageNode?.type === 'image' ? imageNode.media.url?.trim() : ''
  return referencedUrl || scene.media.posterUrl?.trim() || undefined
}

export function collectSceneAndNextVideoUrls(document: PublicMovieDocument, sceneId: string) {
  const sceneMap = new Map(document.scenes.map((scene) => [scene.id, scene]))
  const assetMap = new Map((document.assetNodes ?? []).map((asset) => [asset.id, asset]))
  const currentScene = sceneMap.get(sceneId)
  const urls = new Set<string>()
  const currentUrl = getSceneVideoUrl(currentScene, assetMap)
  if (currentUrl) urls.add(currentUrl)

  document.choices
    .filter((choice) => choice.fromSceneId === sceneId)
    .forEach((choice) => {
      const nextUrl = getSceneVideoUrl(sceneMap.get(choice.toSceneId), assetMap)
      if (nextUrl) urls.add(nextUrl)
    })

  return Array.from(urls)
}

export function preloadVideo(
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

export function resetPreloadedVideos(videoByUrl: Map<string, HTMLVideoElement>) {
  videoByUrl.forEach((video) => {
    video.pause()
    video.removeAttribute('src')
    video.load()
  })
  videoByUrl.clear()
}

export function unlockStorageKey(projectId: string, releaseId: string) {
  return `${UNLOCK_STORAGE_PREFIX}${projectId}.${releaseId}`
}

export function readUnlockProgress(projectId: string, releaseId: string): UnlockProgress | null {
  try {
    const raw = window.localStorage.getItem(unlockStorageKey(projectId, releaseId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<UnlockProgress>
    if (parsed.releaseId !== releaseId) return null
    return {
      releaseId,
      visitedSceneIds: Array.isArray(parsed.visitedSceneIds) ? parsed.visitedSceneIds.filter(isString) : [],
      chosenChoiceIds: Array.isArray(parsed.chosenChoiceIds) ? parsed.chosenChoiceIds.filter(isString) : [],
      updatedAt: typeof parsed.updatedAt === 'string' ? parsed.updatedAt : '',
    }
  } catch {
    return null
  }
}

export function writeUnlockProgress(projectId: string, progress: UnlockProgress) {
  try {
    window.localStorage.setItem(unlockStorageKey(projectId, progress.releaseId), JSON.stringify(progress))
  } catch {
    // Private browsing and embedded webviews may deny localStorage writes.
  }
}

export function isString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}
