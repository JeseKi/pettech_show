import api from './api'

export type AgentVisibility = 'public' | 'admin'

export interface AgentCategory {
  id: string
  name: string
  description: string
  visibility: AgentVisibility
  sort_order: number
  enabled: boolean
}

export interface AgentTag {
  id: string
  name: string
  sort_order: number
  enabled: boolean
}

export interface AgentMarketItem {
  id: string
  slug: string
  name: string
  title: string
  category: string
  category_id: string
  category_label: string
  visibility: AgentVisibility
  summary: string
  description: string
  tags: string[]
  tag_ids: string[]
  enabled: boolean
  is_default: boolean
  protected: boolean
  added: boolean
  current_revision_id: string | null
  current_version: number | null
  system_prompt?: string | null
}

export interface UserAgent extends AgentMarketItem {
  added_at: string
}

export interface AgentPromptRevision {
  id: string
  agent_id: string
  version: number
  active: boolean
  change_note: string
  created_by_user_id: number | null
  created_at: string
  system_prompt?: string | null
}

export interface AgentPage<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface AgentListParams {
  category?: string
  page?: number
  pageSize?: number
  search?: string
}

function buildListParams(params?: AgentListParams) {
  return {
    category: params?.category || undefined,
    page: params?.page,
    page_size: params?.pageSize,
    search: params?.search || undefined,
  }
}

export async function listAgentMarket(params?: AgentListParams): Promise<AgentPage<AgentMarketItem>> {
  const { data } = await api.get<AgentPage<AgentMarketItem>>('/agent-market/market', {
    params: buildListParams(params),
  })
  return data
}

export async function listAgentMarketCategories(): Promise<AgentCategory[]> {
  const { data } = await api.get<AgentCategory[]>('/agent-market/categories')
  return data
}

export async function getDefaultAgent(): Promise<AgentMarketItem> {
  const { data } = await api.get<AgentMarketItem>('/agent-market/default')
  return data
}

export async function listMyAgents(params?: AgentListParams): Promise<AgentPage<UserAgent>> {
  const { data } = await api.get<AgentPage<UserAgent>>('/agent-market/my', {
    params: buildListParams(params),
  })
  return data
}

export async function addMyAgent(agentId: string): Promise<UserAgent> {
  const { data } = await api.post<UserAgent>(`/agent-market/my/${agentId}`)
  return data
}

export async function removeMyAgent(agentId: string): Promise<void> {
  await api.delete(`/agent-market/my/${agentId}`)
}

export interface AgentCreatePayload {
  id: string
  name: string
  description: string
  category_id: string
  tag_ids: string[]
  visibility: AgentVisibility
  system_prompt: string
  change_note?: string
}

export type AgentUpdatePayload = Partial<Omit<AgentCreatePayload, 'id'> & {
  enabled: boolean
}>

export interface AgentCategoryCreatePayload {
  id: string
  name: string
  description?: string
  visibility: AgentVisibility
}

export type AgentCategoryUpdatePayload = Partial<Omit<AgentCategoryCreatePayload, 'id'> & {
  enabled: boolean
}>

export interface AgentTagCreatePayload {
  id: string
  name: string
}

export type AgentTagUpdatePayload = Partial<AgentTagCreatePayload & {
  enabled: boolean
}>

export async function listAdminAgents(): Promise<AgentMarketItem[]> {
  const { data } = await api.get<AgentMarketItem[]>('/agent-market/admin/market')
  return data
}

export async function getAdminAgent(agentId: string): Promise<AgentMarketItem> {
  const { data } = await api.get<AgentMarketItem>(`/agent-market/admin/market/${agentId}`)
  return data
}

export async function listAdminAgentRevisions(agentId: string): Promise<AgentPromptRevision[]> {
  const { data } = await api.get<AgentPromptRevision[]>(`/agent-market/admin/market/${agentId}/revisions`)
  return data
}

export async function createAdminAgent(payload: AgentCreatePayload): Promise<AgentMarketItem> {
  const { data } = await api.post<AgentMarketItem>('/agent-market/admin/market', payload)
  return data
}

export async function updateAdminAgent(agentId: string, payload: AgentUpdatePayload): Promise<AgentMarketItem> {
  const { data } = await api.patch<AgentMarketItem>(`/agent-market/admin/market/${agentId}`, payload)
  return data
}

export async function deleteAdminAgent(agentId: string): Promise<void> {
  await api.delete(`/agent-market/admin/market/${agentId}`)
}

export async function listAdminAgentCategories(): Promise<AgentCategory[]> {
  const { data } = await api.get<AgentCategory[]>('/agent-market/admin/categories')
  return data
}

export async function createAdminAgentCategory(payload: AgentCategoryCreatePayload): Promise<AgentCategory> {
  const { data } = await api.post<AgentCategory>('/agent-market/admin/categories', payload)
  return data
}

export async function updateAdminAgentCategory(
  categoryId: string,
  payload: AgentCategoryUpdatePayload,
): Promise<AgentCategory> {
  const { data } = await api.patch<AgentCategory>(`/agent-market/admin/categories/${categoryId}`, payload)
  return data
}

export async function deleteAdminAgentCategory(categoryId: string): Promise<void> {
  await api.delete(`/agent-market/admin/categories/${categoryId}`)
}

export async function listAdminAgentTags(): Promise<AgentTag[]> {
  const { data } = await api.get<AgentTag[]>('/agent-market/admin/tags')
  return data
}

export async function createAdminAgentTag(payload: AgentTagCreatePayload): Promise<AgentTag> {
  const { data } = await api.post<AgentTag>('/agent-market/admin/tags', payload)
  return data
}

export async function updateAdminAgentTag(tagId: string, payload: AgentTagUpdatePayload): Promise<AgentTag> {
  const { data } = await api.patch<AgentTag>(`/agent-market/admin/tags/${tagId}`, payload)
  return data
}

export async function deleteAdminAgentTag(tagId: string): Promise<void> {
  await api.delete(`/agent-market/admin/tags/${tagId}`)
}
