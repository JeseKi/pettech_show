import api from './api'
import type {
  AiwikiJobStatus,
  AiwikiProgress,
  AiwikiResult,
  AiwikiUploadedFile,
} from './aiwiki'

export type PersonalAiwikiOperation = 'ingest' | 'query' | 'lint'

export interface PersonalAiwikiJob {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  operation: PersonalAiwikiOperation
  title: string
  description: string | null
  status: AiwikiJobStatus
  queue_position: number | null
  message: string | null
  workspace_dir: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  files: AiwikiUploadedFile[]
  progress: AiwikiProgress
  log_tail: string[]
}

export interface PersonalAiwikiJobSummary {
  id: string
  owner_user_id: number | null
  owner_username: string | null
  operation: PersonalAiwikiOperation
  title: string
  description: string | null
  status: AiwikiJobStatus
  message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  files: AiwikiUploadedFile[]
  summary: Record<string, unknown>
}

export interface PersonalAiwikiJobList {
  items: PersonalAiwikiJobSummary[]
  total: number
  limit: number
  offset: number
  stats: {
    ingest_count: number
    query_count: number
    lint_count: number
    active_count: number
    completed_count: number
    total_count: number
  }
}

export interface PersonalAiwikiResult extends AiwikiResult {
  operation: PersonalAiwikiOperation | null
  answer_markdown: string | null
  workspace_dir: string | null
}

export interface PersonalAiwikiEntryPage {
  slug: string
  path: string
  title: string
  type: string
  frontmatter: Record<string, unknown>
  body_markdown: string
  markdown: string
}

export interface CreatePersonalAiwikiJobPayload {
  operation: PersonalAiwikiOperation
  input_text?: string
  title?: string
  description?: string
  files?: File[]
}

export interface UpdatePersonalAiwikiJobPayload {
  title?: string | null
  description?: string | null
}

export async function createPersonalAiwikiJob(
  payload: CreatePersonalAiwikiJobPayload,
  onProgress?: (percent: number) => void,
): Promise<PersonalAiwikiJob> {
  const formData = new FormData()
  formData.append('operation', payload.operation)
  if (payload.input_text) formData.append('input_text', payload.input_text)
  if (payload.title) formData.append('title', payload.title)
  if (payload.description) formData.append('description', payload.description)
  const files = payload.files ?? []
  files.forEach((file) => formData.append('files', file))
  const { data } = await api.post<PersonalAiwikiJob>('/personal-aiwiki/jobs', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (!event.total) return
      onProgress?.(Math.round((event.loaded * 100) / event.total))
    },
  })
  return data
}

export async function listPersonalAiwikiJobs(params: {
  limit?: number
  offset?: number
  status?: AiwikiJobStatus
  operation?: PersonalAiwikiOperation
} = {}): Promise<PersonalAiwikiJobList> {
  const { data } = await api.get<PersonalAiwikiJobList>('/personal-aiwiki/jobs', { params })
  return data
}

export async function getPersonalAiwikiJob(jobId: string): Promise<PersonalAiwikiJob> {
  const { data } = await api.get<PersonalAiwikiJob>(`/personal-aiwiki/jobs/${jobId}`)
  return data
}

export async function updatePersonalAiwikiJob(
  jobId: string,
  payload: UpdatePersonalAiwikiJobPayload,
): Promise<PersonalAiwikiJob> {
  const { data } = await api.patch<PersonalAiwikiJob>(`/personal-aiwiki/jobs/${jobId}`, payload)
  return data
}

export async function getPersonalAiwikiResult(jobId: string): Promise<PersonalAiwikiResult> {
  const { data } = await api.get<PersonalAiwikiResult>(`/personal-aiwiki/jobs/${jobId}/result`)
  return data
}

export async function getPersonalAiwikiWorkspace(): Promise<PersonalAiwikiResult> {
  const { data } = await api.get<PersonalAiwikiResult>('/personal-aiwiki/workspace')
  return data
}

export async function getPersonalAiwikiEntryPage(page: string): Promise<PersonalAiwikiEntryPage> {
  const encodedPage = page.split('/').map((part) => encodeURIComponent(part)).join('/')
  const { data } = await api.get<PersonalAiwikiEntryPage>(`/personal-aiwiki/entries/${encodedPage}`)
  return data
}

export async function deletePersonalAiwikiJob(jobId: string): Promise<void> {
  await api.delete(`/personal-aiwiki/jobs/${jobId}`)
}
