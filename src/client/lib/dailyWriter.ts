import api from './api'

export type DailyWriterJobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'partial_failed'

export interface DailyWriterCreatePayload {
  source_seed_matrix_job_id: string
  seed_id: string
  output_date?: string | null
  generate_variants?: boolean
  variant_count?: number
  generate_artwork?: boolean
}

export interface DailyWriterJob {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  source_seed_matrix_job_id: string
  source_aiwiki_job_id: string
  seed_id: string
  title: string | null
  status: DailyWriterJobStatus
  queue_position: number | null
  message: string | null
  row: Record<string, string>
  params: Record<string, unknown>
  summary: Record<string, unknown>
  article_path: string | null
  metadata_path: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  progress: {
    status?: string
    current_step?: string
    events?: Array<{ event: string; step: string; summary: string }>
  }
  log_tail: string[]
}

export interface DailyWriterJobSummary {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  source_seed_matrix_job_id: string
  source_aiwiki_job_id: string
  seed_id: string
  title: string | null
  status: DailyWriterJobStatus
  message: string | null
  row: Record<string, string>
  params: Record<string, unknown>
  summary: Record<string, unknown>
  article_path: string | null
  metadata_path: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface DailyWriterJobList {
  items: DailyWriterJobSummary[]
  total: number
  limit: number
  offset: number
}

export interface DailyWriterResult {
  job_id: string
  source_seed_matrix_job_id: string
  source_aiwiki_job_id: string
  seed_id: string
  article_path: string
  metadata_path: string
  markdown: string
  illustrated_markdown: string
  metadata: Record<string, unknown>
  summary: Record<string, unknown>
  variants: DailyWriterVariant[]
  artwork: DailyWriterArtwork
}

export interface DailyWriterVariant {
  angle: string
  directory: string
  markdown_path: string
  metadata_path: string
  markdown: string
  illustrated_markdown: string
  metadata: Record<string, unknown>
}

export interface DailyWriterArtworkAsset {
  key: string
  path: string
  url: string
  kind: 'cover' | 'inline'
  filename: string
  content_type: string
}

export interface DailyWriterArtwork {
  cover_images: DailyWriterArtworkAsset[]
  inline_images: DailyWriterArtworkAsset[]
  assets_path: string | null
}

export async function createDailyWriterJob(payload: DailyWriterCreatePayload): Promise<DailyWriterJob> {
  const { data } = await api.post<DailyWriterJob>('/daily-writer/jobs', payload)
  return data
}

export async function listDailyWriterJobs(params: { limit?: number; offset?: number; source_seed_matrix_job_id?: string } = {}): Promise<DailyWriterJobList> {
  const { data } = await api.get<DailyWriterJobList>('/daily-writer/jobs', { params })
  return data
}

export async function getDailyWriterJob(jobId: string): Promise<DailyWriterJob> {
  const { data } = await api.get<DailyWriterJob>(`/daily-writer/jobs/${jobId}`)
  return data
}

export async function updateDailyWriterJob(jobId: string, payload: { title?: string | null }): Promise<DailyWriterJob> {
  const { data } = await api.patch<DailyWriterJob>(`/daily-writer/jobs/${jobId}`, payload)
  return data
}

export async function getDailyWriterResult(jobId: string): Promise<DailyWriterResult> {
  const { data } = await api.get<DailyWriterResult>(`/daily-writer/jobs/${jobId}/result`)
  return data
}

export async function downloadDailyWriterResult(jobId: string): Promise<void> {
  const response = await api.get<Blob>(`/daily-writer/jobs/${jobId}/download`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = `${jobId}.zip`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export async function getDailyWriterArtworkBlob(jobId: string, assetKey: string): Promise<Blob> {
  const response = await api.get<Blob>(`/daily-writer/jobs/${jobId}/artwork/${assetKey}`, {
    responseType: 'blob',
  })
  return response.data
}

export async function deleteDailyWriterJob(jobId: string): Promise<void> {
  await api.delete(`/daily-writer/jobs/${jobId}`)
}
