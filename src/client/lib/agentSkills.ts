import api from './api'

export type AgentSkillVisibility = 'public' | 'admin'

export interface AgentSkillCategory {
  id: string
  name: string
  description: string
  sort_order: number
  enabled: boolean
}

export interface AgentSkillTag {
  id: string
  name: string
  sort_order: number
  enabled: boolean
}

export interface AgentSkill {
  id: string
  slug: string
  mention: string
  name: string
  title: string
  category: string
  category_id: string
  category_label: string
  visibility: AgentSkillVisibility
  summary: string
  description: string
  tags: string[]
  tag_ids: string[]
  added: boolean
  skill_markdown?: string | null
}

export interface UserAgentSkill extends AgentSkill {
  added_at: string
}

export interface AgentSkillPage<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface AgentSkillListParams {
  category?: string
  page?: number
  pageSize?: number
  search?: string
}

function buildListParams(params?: AgentSkillListParams) {
  return {
    category: params?.category || undefined,
    page: params?.page,
    page_size: params?.pageSize,
    search: params?.search || undefined,
  }
}

export async function listAgentSkillMarket(params?: AgentSkillListParams): Promise<AgentSkillPage<AgentSkill>> {
  const { data } = await api.get<AgentSkillPage<AgentSkill>>('/agent-skills/market', {
    params: buildListParams(params),
  })
  return data
}

export async function listAgentSkillMarketCategories(): Promise<AgentSkillCategory[]> {
  const { data } = await api.get<AgentSkillCategory[]>('/agent-skills/categories')
  return data
}

export async function listMyAgentSkills(params?: Omit<AgentSkillListParams, 'category'>): Promise<AgentSkillPage<UserAgentSkill>> {
  const { data } = await api.get<AgentSkillPage<UserAgentSkill>>('/agent-skills/my', {
    params: buildListParams(params),
  })
  return data
}

export async function addMyAgentSkill(skillId: string): Promise<UserAgentSkill> {
  const { data } = await api.post<UserAgentSkill>(`/agent-skills/my/${skillId}`)
  return data
}

export async function removeMyAgentSkill(skillId: string): Promise<void> {
  await api.delete(`/agent-skills/my/${skillId}`)
}

export interface AgentSkillCreatePayload {
  id: string
  name: string
  description: string
  category_id: string
  tag_ids: string[]
  visibility: AgentSkillVisibility
  skill_markdown: string
}

export type AgentSkillUpdatePayload = Partial<Omit<AgentSkillCreatePayload, 'id'>>

export async function listAdminAgentSkills(): Promise<AgentSkill[]> {
  const { data } = await api.get<AgentSkill[]>('/agent-skills/admin/market')
  return data
}

export async function getAdminAgentSkill(skillId: string): Promise<AgentSkill> {
  const { data } = await api.get<AgentSkill>(`/agent-skills/admin/market/${skillId}`)
  return data
}

export async function createAdminAgentSkill(payload: AgentSkillCreatePayload): Promise<AgentSkill> {
  const { data } = await api.post<AgentSkill>('/agent-skills/admin/market', payload)
  return data
}

export async function updateAdminAgentSkill(skillId: string, payload: AgentSkillUpdatePayload): Promise<AgentSkill> {
  const { data } = await api.patch<AgentSkill>(`/agent-skills/admin/market/${skillId}`, payload)
  return data
}

export async function deleteAdminAgentSkill(skillId: string): Promise<void> {
  await api.delete(`/agent-skills/admin/market/${skillId}`)
}

export interface AgentSkillCategoryCreatePayload {
  id: string
  name: string
  description?: string
}

export type AgentSkillCategoryUpdatePayload = Partial<Omit<AgentSkillCategoryCreatePayload, 'id'> & {
  enabled: boolean
}>

export async function listAdminAgentSkillCategories(): Promise<AgentSkillCategory[]> {
  const { data } = await api.get<AgentSkillCategory[]>('/agent-skills/admin/categories')
  return data
}

export async function createAdminAgentSkillCategory(
  payload: AgentSkillCategoryCreatePayload,
): Promise<AgentSkillCategory> {
  const { data } = await api.post<AgentSkillCategory>('/agent-skills/admin/categories', payload)
  return data
}

export async function updateAdminAgentSkillCategory(
  categoryId: string,
  payload: AgentSkillCategoryUpdatePayload,
): Promise<AgentSkillCategory> {
  const { data } = await api.patch<AgentSkillCategory>(`/agent-skills/admin/categories/${categoryId}`, payload)
  return data
}

export async function deleteAdminAgentSkillCategory(categoryId: string): Promise<void> {
  await api.delete(`/agent-skills/admin/categories/${categoryId}`)
}

export interface AgentSkillTagCreatePayload {
  id: string
  name: string
}

export type AgentSkillTagUpdatePayload = Partial<AgentSkillTagCreatePayload & {
  enabled: boolean
}>

export async function listAdminAgentSkillTags(): Promise<AgentSkillTag[]> {
  const { data } = await api.get<AgentSkillTag[]>('/agent-skills/admin/tags')
  return data
}

export async function createAdminAgentSkillTag(payload: AgentSkillTagCreatePayload): Promise<AgentSkillTag> {
  const { data } = await api.post<AgentSkillTag>('/agent-skills/admin/tags', payload)
  return data
}

export async function updateAdminAgentSkillTag(
  tagId: string,
  payload: AgentSkillTagUpdatePayload,
): Promise<AgentSkillTag> {
  const { data } = await api.patch<AgentSkillTag>(`/agent-skills/admin/tags/${tagId}`, payload)
  return data
}

export async function deleteAdminAgentSkillTag(tagId: string): Promise<void> {
  await api.delete(`/agent-skills/admin/tags/${tagId}`)
}
