import api from './api'

export type PromptTemplate = {
  sections: string[]
  example: string
}

export type InteractiveMovieVideoUpload = {
  url?: string | null
  storage_uri: string
  object_key: string
  filename: string
  content_type: string
  size: number
}

export type InteractiveMovieProjectSummary = {
  id: string
  title: string
  version: number
  content_hash: string
  updated_at: string
  scene_count: number
  choice_count: number
  is_published: boolean
  published_release_id?: string | null
  published_version_no?: number | null
  published_at?: string | null
  public_path?: string | null
}

export type InteractiveMovieProjectDetail<TDocument> = {
  id: string
  title: string
  version: number
  content_hash: string
  updated_at: string
  document: TDocument
  is_published: boolean
  published_release_id?: string | null
  published_version_no?: number | null
  published_at?: string | null
  public_path?: string | null
}

export type InteractiveMovieSyncState = {
  project_id: string
  version: number
  content_hash: string
  updated_at: string
}

export type InteractiveMovieEntityPatch = {
  upsert: Array<Record<string, unknown>>
  delete: string[]
}

export type InteractiveMovieProjectPatch = {
  base_version: number
  base_hash: string
  project: Record<string, unknown>
  scenes: InteractiveMovieEntityPatch
  choices: InteractiveMovieEntityPatch
  asset_nodes: InteractiveMovieEntityPatch
  node_links: InteractiveMovieEntityPatch
  script_lines: InteractiveMovieEntityPatch
  viewport: Record<string, unknown>
  selected_object: Record<string, unknown>
}

export type InteractiveMovieRelease = {
  id: string
  project_id: string
  version_no: number
  title: string
  content_hash: string
  created_at: string
  is_current: boolean
}

export type InteractiveMoviePublishResult<TDocument> = {
  project: InteractiveMovieProjectDetail<TDocument>
  release: InteractiveMovieRelease
}

export type InteractiveMoviePublicProject<TDocument> = {
  id: string
  title: string
  release_id: string
  version_no: number
  content_hash: string
  published_at: string
  document: TDocument
}

export async function getInteractiveMoviePromptTemplate(): Promise<PromptTemplate> {
  const response = await api.get<PromptTemplate>('/interactive-movie/prompt-template')
  return response.data
}

export async function listInteractiveMovieProjects(): Promise<InteractiveMovieProjectSummary[]> {
  const response = await api.get<InteractiveMovieProjectSummary[]>('/interactive-movie/projects')
  return response.data
}

export async function createInteractiveMovieProject<TDocument>(
  title: string,
  document: TDocument,
): Promise<InteractiveMovieProjectDetail<TDocument>> {
  const response = await api.post<InteractiveMovieProjectDetail<TDocument>>('/interactive-movie/projects', {
    title,
    document,
  })
  return response.data
}

export async function getInteractiveMovieProject<TDocument>(
  projectId: string,
): Promise<InteractiveMovieProjectDetail<TDocument>> {
  const response = await api.get<InteractiveMovieProjectDetail<TDocument>>(`/interactive-movie/projects/${projectId}`)
  return response.data
}

export async function getInteractiveMovieSyncState(projectId: string): Promise<InteractiveMovieSyncState> {
  const response = await api.get<InteractiveMovieSyncState>(`/interactive-movie/projects/${projectId}/sync-state`)
  return response.data
}

export async function listInteractiveMovieReleases(projectId: string): Promise<InteractiveMovieRelease[]> {
  const response = await api.get<InteractiveMovieRelease[]>(`/interactive-movie/projects/${projectId}/releases`)
  return response.data
}

export async function publishInteractiveMovieProject<TDocument>(
  projectId: string,
  baseVersion: number,
  baseHash: string,
): Promise<InteractiveMoviePublishResult<TDocument>> {
  const response = await api.post<InteractiveMoviePublishResult<TDocument>>(`/interactive-movie/projects/${projectId}/releases`, {
    base_version: baseVersion,
    base_hash: baseHash,
  })
  return response.data
}

export async function setInteractiveMoviePublishedRelease<TDocument>(
  projectId: string,
  releaseId: string,
): Promise<InteractiveMovieProjectDetail<TDocument>> {
  const response = await api.put<InteractiveMovieProjectDetail<TDocument>>(`/interactive-movie/projects/${projectId}/published-release`, {
    release_id: releaseId,
  })
  return response.data
}

export async function closeInteractiveMoviePublication<TDocument>(
  projectId: string,
): Promise<InteractiveMovieProjectDetail<TDocument>> {
  const response = await api.delete<InteractiveMovieProjectDetail<TDocument>>(`/interactive-movie/projects/${projectId}/published-release`)
  return response.data
}

export async function patchInteractiveMovieProject<TDocument>(
  projectId: string,
  patch: InteractiveMovieProjectPatch,
): Promise<InteractiveMovieProjectDetail<TDocument>> {
  const response = await api.patch<InteractiveMovieProjectDetail<TDocument>>(`/interactive-movie/projects/${projectId}`, patch)
  return response.data
}

export async function renameInteractiveMovieProject<TDocument>(
  projectId: string,
  title: string,
): Promise<InteractiveMovieProjectDetail<TDocument>> {
  const response = await api.patch<InteractiveMovieProjectDetail<TDocument>>(`/interactive-movie/projects/${projectId}/title`, {
    title,
  })
  return response.data
}

export async function deleteInteractiveMovieProject(projectId: string): Promise<void> {
  await api.delete(`/interactive-movie/projects/${projectId}`)
}

export async function getInteractiveMoviePublicProject<TDocument>(
  projectId: string,
): Promise<InteractiveMoviePublicProject<TDocument>> {
  const response = await api.get<InteractiveMoviePublicProject<TDocument>>(`/interactive-movie/public/${projectId}`)
  return response.data
}

export async function uploadInteractiveMovieVideo(file: File): Promise<InteractiveMovieVideoUpload> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post<InteractiveMovieVideoUpload>('/interactive-movie/assets/videos', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function uploadInteractiveMovieImage(file: File): Promise<InteractiveMovieVideoUpload> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post<InteractiveMovieVideoUpload>('/interactive-movie/assets/images', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}
