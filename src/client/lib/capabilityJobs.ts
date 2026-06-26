import api from './api'

export type CapabilityJobStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface CapabilityJob {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  capability_key: string
  title: string | null
  status: CapabilityJobStatus
  queue_position: number | null
  message: string | null
  inputs: Record<string, unknown>
  summary: Record<string, unknown>
  result_markdown_path: string | null
  result_json_path: string | null
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

export interface CapabilityJobSummary {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  capability_key: string
  title: string | null
  status: CapabilityJobStatus
  message: string | null
  inputs: Record<string, unknown>
  summary: Record<string, unknown>
  result_markdown_path: string | null
  result_json_path: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface CapabilityJobList {
  items: CapabilityJobSummary[]
  total: number
  limit: number
  offset: number
}

export interface CapabilityResult {
  job_id: string
  capability_key: string
  markdown: string
  data: Record<string, unknown>
  summary: Record<string, unknown>
}

export async function createCapabilityJob(payload: { capability_key: string; inputs: Record<string, unknown> }): Promise<CapabilityJob> {
  const { data } = await api.post<CapabilityJob>('/capability-jobs', payload)
  return data
}

export async function listCapabilityJobs(params: { limit?: number; offset?: number; capability_key?: string } = {}): Promise<CapabilityJobList> {
  const { data } = await api.get<CapabilityJobList>('/capability-jobs', { params })
  return data
}

export async function getCapabilityJob(jobId: string): Promise<CapabilityJob> {
  const { data } = await api.get<CapabilityJob>(`/capability-jobs/${jobId}`)
  return data
}

export async function updateCapabilityJob(jobId: string, payload: { title?: string | null }): Promise<CapabilityJob> {
  const { data } = await api.patch<CapabilityJob>(`/capability-jobs/${jobId}`, payload)
  return data
}

export async function getCapabilityResult(jobId: string): Promise<CapabilityResult> {
  const { data } = await api.get<CapabilityResult>(`/capability-jobs/${jobId}/result`)
  return data
}

export async function downloadCapabilityResult(jobId: string): Promise<void> {
  const response = await api.get<Blob>(`/capability-jobs/${jobId}/download`, { responseType: 'blob' })
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = `${jobId}.zip`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export async function deleteCapabilityJob(jobId: string): Promise<void> {
  await api.delete(`/capability-jobs/${jobId}`)
}
