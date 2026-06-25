import api from './api'

export type SocialCardVideoJobStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface SocialCardVideoCreatePayload {
  source_social_card_job_id: string
  title: string
  voice_text: string
  bgm_start?: number
  bgm_file?: File | null
}

export interface SocialCardVideoJob {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  source_social_card_job_id: string
  title: string | null
  status: SocialCardVideoJobStatus
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

export interface SocialCardVideoJobSummary {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  source_social_card_job_id: string
  title: string | null
  status: SocialCardVideoJobStatus
  message: string | null
  params: Record<string, unknown>
  summary: Record<string, unknown>
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface SocialCardVideoJobList {
  items: SocialCardVideoJobSummary[]
  total: number
  limit: number
  offset: number
}

export interface SocialCardVideoAsset {
  key: string
  path: string
  url: string
  filename: string
  content_type: string
  markdown_path: string | null
  summary: Record<string, unknown>
}

export interface SocialCardVideoResult {
  job_id: string
  source_social_card_job_id: string
  videos: SocialCardVideoAsset[]
  markdown: string
  summary: Record<string, unknown>
}

export async function createSocialCardVideoJob(payload: SocialCardVideoCreatePayload): Promise<SocialCardVideoJob> {
  const form = new FormData()
  form.append('source_social_card_job_id', payload.source_social_card_job_id)
  form.append('title', payload.title)
  form.append('voice_text', payload.voice_text)
  form.append('bgm_start', String(payload.bgm_start ?? 0))
  if (payload.bgm_file) {
    form.append('bgm_file', payload.bgm_file)
  }
  const { data } = await api.post<SocialCardVideoJob>('/social-card-videos/jobs', form)
  return data
}

export async function listSocialCardVideoJobs(params: { limit?: number; offset?: number; source_social_card_job_id?: string } = {}): Promise<SocialCardVideoJobList> {
  const { data } = await api.get<SocialCardVideoJobList>('/social-card-videos/jobs', { params })
  return data
}

export async function getSocialCardVideoJob(jobId: string): Promise<SocialCardVideoJob> {
  const { data } = await api.get<SocialCardVideoJob>(`/social-card-videos/jobs/${jobId}`)
  return data
}

export async function updateSocialCardVideoJob(jobId: string, payload: { title?: string | null }): Promise<SocialCardVideoJob> {
  const { data } = await api.patch<SocialCardVideoJob>(`/social-card-videos/jobs/${jobId}`, payload)
  return data
}

export async function getSocialCardVideoResult(jobId: string): Promise<SocialCardVideoResult> {
  const { data } = await api.get<SocialCardVideoResult>(`/social-card-videos/jobs/${jobId}/result`)
  return data
}

export async function getSocialCardVideoBlob(jobId: string, assetKey: string): Promise<Blob> {
  const response = await api.get<Blob>(`/social-card-videos/jobs/${jobId}/videos/${assetKey}`, {
    responseType: 'blob',
  })
  return response.data
}

export async function downloadSocialCardVideoResult(jobId: string): Promise<void> {
  const response = await api.get<Blob>(`/social-card-videos/jobs/${jobId}/download`, {
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

export async function deleteSocialCardVideoJob(jobId: string): Promise<void> {
  await api.delete(`/social-card-videos/jobs/${jobId}`)
}
