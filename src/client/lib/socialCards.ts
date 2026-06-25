import api from './api'

export type SocialCardJobStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface SocialCardCreatePayload {
  source_daily_writer_job_id: string
  post_count?: number
  cards_per_post?: number
  card_count?: number
}

export interface SocialCardJob {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  source_daily_writer_job_id: string
  title: string | null
  status: SocialCardJobStatus
  queue_position: number | null
  message: string | null
  params: Record<string, unknown>
  summary: Record<string, unknown>
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

export interface SocialCardJobSummary {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  source_daily_writer_job_id: string
  title: string | null
  status: SocialCardJobStatus
  message: string | null
  params: Record<string, unknown>
  summary: Record<string, unknown>
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface SocialCardJobList {
  items: SocialCardJobSummary[]
  total: number
  limit: number
  offset: number
}

export interface SocialCardAsset {
  key: string
  path: string
  url: string
  filename: string
  content_type: string
}

export interface SocialCardPost {
  key: string
  title: string
  images: SocialCardAsset[]
  markdown: string
  main_path: string | null
  manifest_path: string | null
  index_path: string | null
  plan_path: string | null
  summary: Record<string, unknown>
}

export interface SocialCardResult {
  job_id: string
  source_daily_writer_job_id: string
  images: SocialCardAsset[]
  posts: SocialCardPost[]
  markdown: string
  main_path: string | null
  manifest_path: string | null
  index_path: string | null
  plan_path: string | null
  summary: Record<string, unknown>
}

export async function createSocialCardJob(payload: SocialCardCreatePayload): Promise<SocialCardJob> {
  const { data } = await api.post<SocialCardJob>('/social-cards/jobs', payload)
  return data
}

export async function listSocialCardJobs(params: { limit?: number; offset?: number; source_daily_writer_job_id?: string } = {}): Promise<SocialCardJobList> {
  const { data } = await api.get<SocialCardJobList>('/social-cards/jobs', { params })
  return data
}

export async function getSocialCardJob(jobId: string): Promise<SocialCardJob> {
  const { data } = await api.get<SocialCardJob>(`/social-cards/jobs/${jobId}`)
  return data
}

export async function updateSocialCardJob(jobId: string, payload: { title?: string | null }): Promise<SocialCardJob> {
  const { data } = await api.patch<SocialCardJob>(`/social-cards/jobs/${jobId}`, payload)
  return data
}

export async function getSocialCardResult(jobId: string): Promise<SocialCardResult> {
  const { data } = await api.get<SocialCardResult>(`/social-cards/jobs/${jobId}/result`)
  return data
}

export async function downloadSocialCardResult(jobId: string): Promise<void> {
  const response = await api.get<Blob>(`/social-cards/jobs/${jobId}/download`, {
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

export async function getSocialCardImageBlob(jobId: string, assetKey: string): Promise<Blob> {
  const response = await api.get<Blob>(`/social-cards/jobs/${jobId}/images/${assetKey}`, {
    responseType: 'blob',
  })
  return response.data
}

export async function deleteSocialCardJob(jobId: string): Promise<void> {
  await api.delete(`/social-cards/jobs/${jobId}`)
}
