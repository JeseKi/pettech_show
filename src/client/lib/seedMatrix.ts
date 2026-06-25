import api from './api'

export type SeedMatrixJobStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface SeedMatrixCreatePayload {
  source_aiwiki_job_id: string
  expected_seed_count: number
  slots_per_day: number
  hooks: string[]
}

export interface SeedMatrixJob {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  source_aiwiki_job_id: string
  title: string | null
  status: SeedMatrixJobStatus
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

export interface SeedMatrixJobSummary {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  source_aiwiki_job_id: string
  title: string | null
  status: SeedMatrixJobStatus
  message: string | null
  params: Record<string, unknown>
  summary: Record<string, unknown>
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface SeedMatrixJobList {
  items: SeedMatrixJobSummary[]
  total: number
  limit: number
  offset: number
}

export interface SeedMatrixResult {
  job_id: string
  source_aiwiki_job_id: string
  csv_path: string
  summary: Record<string, unknown>
  columns: string[]
  rows: Array<Record<string, string>>
}

export async function createSeedMatrixJob(payload: SeedMatrixCreatePayload): Promise<SeedMatrixJob> {
  const { data } = await api.post<SeedMatrixJob>('/seed-matrices', payload)
  return data
}

export async function listSeedMatrixJobs(params: { limit?: number; offset?: number; source_aiwiki_job_id?: string } = {}): Promise<SeedMatrixJobList> {
  const { data } = await api.get<SeedMatrixJobList>('/seed-matrices', { params })
  return data
}

export async function getSeedMatrixJob(jobId: string): Promise<SeedMatrixJob> {
  const { data } = await api.get<SeedMatrixJob>(`/seed-matrices/${jobId}`)
  return data
}

export async function updateSeedMatrixJob(jobId: string, payload: { title?: string | null }): Promise<SeedMatrixJob> {
  const { data } = await api.patch<SeedMatrixJob>(`/seed-matrices/${jobId}`, payload)
  return data
}

export async function getSeedMatrixResult(jobId: string): Promise<SeedMatrixResult> {
  const { data } = await api.get<SeedMatrixResult>(`/seed-matrices/${jobId}/result`)
  return data
}

export async function downloadSeedMatrixCsv(jobId: string): Promise<void> {
  const response = await api.get<Blob>(`/seed-matrices/${jobId}/download`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = `${jobId}.csv`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export async function deleteSeedMatrixJob(jobId: string): Promise<void> {
  await api.delete(`/seed-matrices/${jobId}`)
}
