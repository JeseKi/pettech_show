import api from './api'

export type AiwikiJobStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface AiwikiUploadedFile {
  filename: string
  size_bytes: number
  raw_path: string
}

export interface AiwikiProgressEvent {
  event: string
  step: string
  summary: string
}

export interface AiwikiProgress {
  status?: string
  current_step?: string
  events?: AiwikiProgressEvent[]
}

export interface AiwikiJob {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  status: AiwikiJobStatus
  queue_position: number | null
  message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  files: AiwikiUploadedFile[]
  progress: AiwikiProgress
  log_tail: string[]
}

export interface AiwikiJobSummary {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  status: AiwikiJobStatus
  message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  files: AiwikiUploadedFile[]
  summary: Record<string, unknown>
}

export interface AiwikiJobList {
  items: AiwikiJobSummary[]
  total: number
  limit: number
  offset: number
}

export interface AiwikiMaterial {
  path: string
  title: string
  positioning: string | null
  pain_points: Array<Record<string, unknown>>
  hotspots: Array<Record<string, unknown>>
  solutions: Array<Record<string, unknown>>
  topics: string[]
  search_intents: Array<Record<string, unknown>>
  summary: Record<string, unknown>
}

export interface AiwikiWikiEntry {
  path: string
  slug: string
  type: string
  title: string
  frontmatter: Record<string, unknown>
  body_markdown: string
  excerpt: string
  created: string | null
  updated: string | null
  sections: Array<{ title: string; content: string }>
  references: string[]
  reference_links: AiwikiWikiReference[]
}

export interface AiwikiWikiReference {
  slug: string
  title: string
  path: string | null
  type: string | null
}

export interface AiwikiWikiHome {
  path: string
  title: string
  body_markdown: string
  references: string[]
  headings: Array<{ id: string; title: string; level?: number }>
}

export interface AiwikiResult {
  job_id: string
  summary: Record<string, unknown>
  materials: AiwikiMaterial[]
  hotspots: Array<Record<string, unknown>>
  pain_points: Array<Record<string, unknown>>
  solutions: Array<Record<string, unknown>>
  topics: Array<Record<string, unknown>>
  search_intents: Array<Record<string, unknown>>
  wiki_home: AiwikiWikiHome | null
  wiki_entries: AiwikiWikiEntry[]
  highlight_terms: string[]
  navigation: Array<{ key: string; label: string; count: number }>
}

export interface CreateAiwikiJobOptions {
  generate_search_assets?: boolean
}

export async function createAiwikiJob(files: File[], options: CreateAiwikiJobOptions = {}): Promise<AiwikiJob> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  formData.append('generate_search_assets', String(options.generate_search_assets ?? true))
  const { data } = await api.post<AiwikiJob>('/aiwiki/jobs', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getAiwikiJob(jobId: string): Promise<AiwikiJob> {
  const { data } = await api.get<AiwikiJob>(`/aiwiki/jobs/${jobId}`)
  return data
}

export async function listAiwikiJobs(params: { limit?: number; offset?: number; status?: AiwikiJobStatus } = {}): Promise<AiwikiJobList> {
  const { data } = await api.get<AiwikiJobList>('/aiwiki/jobs', { params })
  return data
}

export async function getAiwikiResult(jobId: string): Promise<AiwikiResult> {
  const { data } = await api.get<AiwikiResult>(`/aiwiki/jobs/${jobId}/result`)
  return data
}

export async function deleteAiwikiJob(jobId: string): Promise<void> {
  await api.delete(`/aiwiki/jobs/${jobId}`)
}
