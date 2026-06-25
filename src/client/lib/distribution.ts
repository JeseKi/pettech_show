import api from './api'

export type DistributionSourceType = 'daily_writer' | 'social_cards'
export type DistributionUploadType = 'article' | 'image_text'

export interface DistributionProject {
  id: number
  name: string
  code?: string
  theme_ids?: number[]
  themes?: Array<{ id: number; name: string }>
}

export interface DistributionTheme {
  id: number
  name: string
  project_ids?: number[]
}

export interface DistributionAccount {
  id: number
  project_ids: number[]
  projects?: DistributionProject[]
  theme_id: number
  platform: string
  account_name: string
  publication_type: DistributionUploadType
  is_active: boolean
}

export interface DistributionUserAccounts {
  id: number
  name: string
  accounts: DistributionAccount[]
}

export interface DistributionDirectory {
  accounts: DistributionUserAccounts[]
  project_themes: {
    projects: DistributionProject[]
    themes: DistributionTheme[]
  }
}

export interface DistributionUploadPayload {
  source_type: DistributionSourceType
  source_job_id: string
  project_id: number
  theme_id: number
  scheduled_date: string
  per_account_count: number
  ignore_history?: boolean
  account_platforms?: string[]
  account_query?: string | null
  user_query?: string | null
  account_ids?: number[]
}

export interface DistributionPlanItem {
  source_key: string
  source_label: string
  source_path: string | null
  title: string
  keyword: string
  content_sha256: string
  markdown_content: string
  metadata: Record<string, unknown>
}

export interface DistributionPlanBatch {
  account: Record<string, unknown>
  payload: Record<string, unknown>
  items: DistributionPlanItem[]
  article_count: number
}

export interface DistributionUploadPlan {
  source_type: DistributionSourceType
  source_job_id: string
  upload_type: DistributionUploadType
  scheduled_date: string
  project: Record<string, unknown>
  theme: Record<string, unknown>
  account_count: number
  batch_count: number
  item_count: number
  skipped: Array<Record<string, unknown>>
  warnings: string[]
  batches: DistributionPlanBatch[]
}

export interface DistributionUploadJob {
  id: string
  source_type: string
  source_job_id: string
  upload_type: string
  project_id: number
  theme_id: number
  scheduled_date: string
  status: 'running' | 'completed' | 'failed'
  message: string | null
  remote_base_url: string
  plan: Record<string, unknown>
  result: Record<string, unknown>
  created_at: string
  finished_at: string | null
}

export interface DistributionUploadResult {
  job: DistributionUploadJob
  plan: DistributionUploadPlan
  results: Array<{
    account: Record<string, unknown>
    created_count: number
    response: unknown
  }>
}

export interface DistributionUploadJobList {
  items: DistributionUploadJob[]
  total: number
  limit: number
  offset: number
}

export async function getDistributionDirectory(): Promise<DistributionDirectory> {
  const { data } = await api.get<DistributionDirectory>('/distribution/remote-directory')
  return data
}

export async function previewDistributionUploadPlan(
  payload: DistributionUploadPayload,
): Promise<DistributionUploadPlan> {
  const { data } = await api.post<DistributionUploadPlan>('/distribution/uploads/plan', payload)
  return data
}

export async function createDistributionUpload(
  payload: DistributionUploadPayload,
): Promise<DistributionUploadResult> {
  const { data } = await api.post<DistributionUploadResult>('/distribution/uploads', payload)
  return data
}

export async function listDistributionUploads(params: { limit?: number; offset?: number } = {}): Promise<DistributionUploadJobList> {
  const { data } = await api.get<DistributionUploadJobList>('/distribution/uploads', { params })
  return data
}
