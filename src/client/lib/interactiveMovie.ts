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
}

export type InteractiveMovieProjectDetail<TDocument> = {
  id: string
  title: string
  version: number
  content_hash: string
  updated_at: string
  document: TDocument
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
  script_lines: InteractiveMovieEntityPatch
  viewport: Record<string, unknown>
  selected_object: Record<string, unknown>
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

export async function uploadInteractiveMovieVideo(file: File): Promise<InteractiveMovieVideoUpload> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post<InteractiveMovieVideoUpload>('/interactive-movie/videos', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}
