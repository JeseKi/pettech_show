import { isAxiosError } from 'axios'
import type { InteractiveMovieProjectDetail } from '../../lib/interactiveMovie'
import type { InteractiveMovieProject, StoredWorkspace } from './interactiveMovieTypes'
import { MISSING_PROJECT_DETAIL, STORAGE_KEY, CLOUD_REPLICA_PREFIX, DRAFT_REPLICA_PREFIX, SCENE_PANEL_STATE_KEY } from './interactiveMovieConstants'
import { createDefaultProject, normalizeProjectShape } from './interactiveMovieProject'

export const loadWorkspace = (): StoredWorkspace => {
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

export const loadScenePanelState = (): Record<string, string[]> => {
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

export const persistScenePanelState = (state: Record<string, string[]>) => {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(SCENE_PANEL_STATE_KEY, JSON.stringify(state))
}

export const cloudReplicaKey = (projectId: string) => `${CLOUD_REPLICA_PREFIX}${projectId}`
export const draftReplicaKey = (projectId: string) => `${DRAFT_REPLICA_PREFIX}${projectId}`

export const hasCloudCopy = (project: InteractiveMovieProject) => Boolean(project.version && project.contentHash)

export const isMissingCloudProjectError = (error: unknown) => {
  if (!isAxiosError(error) || error.response?.status !== 404) return false
  const payload = error.response.data as { detail?: unknown } | undefined
  return payload?.detail === MISSING_PROJECT_DETAIL
}

export const readProjectReplica = (key: string): InteractiveMovieProject | null => {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? normalizeProjectShape(JSON.parse(raw) as InteractiveMovieProject) : null
  } catch {
    window.localStorage.removeItem(key)
    return null
  }
}

export const removeProjectReplicas = (projectId: string) => {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(cloudReplicaKey(projectId))
  window.localStorage.removeItem(draftReplicaKey(projectId))
}

export const cleanupProjectReplicasOutside = (projectIdsToKeep: Set<string>) => {
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

export const writeProjectReplica = (key: string, project: InteractiveMovieProject) => {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(key, JSON.stringify(project))
}

export const persistWorkspaceLocally = (workspace: StoredWorkspace) => {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(workspace))
  workspace.projects.forEach((project) => {
    writeProjectReplica(draftReplicaKey(project.id), project)
  })
}

export const withCloudMeta = (
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
