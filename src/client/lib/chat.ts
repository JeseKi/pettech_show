import api, { refreshAccessToken } from './api'
import { getAccessToken } from './tokenStorage'

export type ChatRole = 'system' | 'user' | 'assistant' | 'tool'

export interface ChatMessagePayload {
  role: ChatRole
  content: string
  name?: string
  tool_call_id?: string
  tool_calls?: Array<Record<string, unknown>>
}

export interface ChatCompletionPayload {
  messages: ChatMessagePayload[]
  agent_id?: string
  model?: string
  temperature?: number
  max_tokens?: number
  tools?: Array<Record<string, unknown>>
}

export interface ChatUsage {
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
}

export interface ChatCompletion {
  id: string | null
  model: string
  role: 'assistant'
  content: string
  usage: ChatUsage | null
  raw?: Record<string, unknown> | null
}

export interface ChatStreamHandlers {
  onSession?: (session: ChatSessionSummary) => void
  onDelta: (content: string) => void
  onDone?: () => void
  onTool?: (event: ChatToolEvent) => void
}

export interface ChatToolEvent {
  content?: string
  kind: 'model_output' | 'tool_call' | 'tool_result'
  name?: string
  status?: 'done' | 'error' | 'running'
  title: string
}

export interface ChatSessionSummary {
  id: string
  title: string
  agent_id: string | null
  agent_revision_id: string | null
  agent_name: string | null
  created_at: string
  updated_at: string
  message_count: number
}

export interface ChatMessageRecord {
  id: string
  role: ChatRole
  content: string
  created_at: string
  tool_steps?: ChatToolEvent[]
}

export interface ChatSessionStreamPayload {
  session_id?: string
  agent_id?: string
  content: string
  model?: string
  temperature?: number
  max_tokens?: number
  tools?: Array<Record<string, unknown>>
}

export interface ChatSessionPersistTurnPayload {
  session_id?: string
  agent_id?: string
  user_content: string
  assistant_content: string
  model?: string
  rollout_items?: Array<Record<string, unknown>>
}

export async function createChatCompletion(payload: ChatCompletionPayload): Promise<ChatCompletion> {
  const { data } = await api.post<ChatCompletion>('/chat/completions', payload)
  return data
}

export async function listChatSessions(): Promise<ChatSessionSummary[]> {
  const { data } = await api.get<ChatSessionSummary[]>('/chat/sessions')
  return data
}

export async function getChatSessionMessages(sessionId: string): Promise<ChatMessageRecord[]> {
  const { data } = await api.get<ChatMessageRecord[]>(`/chat/sessions/${sessionId}/messages`)
  return data
}

export async function renameChatSession(sessionId: string, title: string): Promise<ChatSessionSummary> {
  const { data } = await api.patch<ChatSessionSummary>(`/chat/sessions/${sessionId}`, { title })
  return data
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await api.delete(`/chat/sessions/${sessionId}`)
}

export async function persistChatSessionTurn(payload: ChatSessionPersistTurnPayload): Promise<ChatSessionSummary> {
  const { data } = await api.post<ChatSessionSummary>('/chat/sessions/persist-turn', payload)
  return data
}

export async function streamChatCompletion(
  payload: ChatCompletionPayload,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getAccessToken()
  let response = await fetchChatStream(payload, token, signal)

  if (response.status === 401 && token) {
    const refreshedToken = await refreshAccessToken().catch(() => null)
    if (refreshedToken) {
      response = await fetchChatStream(payload, refreshedToken, signal)
    }
  }

  if (!response.ok) {
    throw new Error(await resolveFetchErrorMessage(response))
  }

  await readSseStream(response, handlers)
}

export async function streamChatSession(
  payload: ChatSessionStreamPayload,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getAccessToken()
  let response = await fetchChatSessionStream(payload, token, signal)

  if (response.status === 401 && token) {
    const refreshedToken = await refreshAccessToken().catch(() => null)
    if (refreshedToken) {
      response = await fetchChatSessionStream(payload, refreshedToken, signal)
    }
  }

  if (!response.ok) {
    throw new Error(await resolveFetchErrorMessage(response))
  }

  await readSseStream(response, handlers)
}

function fetchChatStream(
  payload: ChatCompletionPayload,
  token: string | null,
  signal?: AbortSignal,
): Promise<Response> {
  return fetch(buildApiUrl('/chat/completions/stream'), {
    body: JSON.stringify(payload),
    credentials: 'include',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    method: 'POST',
    signal,
  })
}

function fetchChatSessionStream(
  payload: ChatSessionStreamPayload,
  token: string | null,
  signal?: AbortSignal,
): Promise<Response> {
  return fetch(buildApiUrl('/chat/sessions/stream'), {
    body: JSON.stringify(payload),
    credentials: 'include',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    method: 'POST',
    signal,
  })
}

function buildApiUrl(path: string): string {
  const baseUrl = cleanupBaseUrl(import.meta.env.VITE_API_BASE_URL ?? '/api')
  return `${baseUrl}${path}`
}

function cleanupBaseUrl(url: string): string {
  return url.endsWith('/') ? url.slice(0, -1) : url
}

async function resolveFetchErrorMessage(response: Response): Promise<string> {
  const fallback = `请求失败 (${response.status})`

  try {
    const payload = await response.json() as { detail?: unknown; message?: unknown }
    if (typeof payload.message === 'string' && payload.message.length > 0) {
      return payload.message
    }
    if (typeof payload.detail === 'string' && payload.detail.length > 0) {
      return payload.detail
    }
  } catch {
    const text = await response.text().catch(() => '')
    return text || fallback
  }

  return fallback
}

async function readSseStream(
  response: Response,
  handlers: ChatStreamHandlers,
): Promise<void> {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('当前浏览器不支持流式响应')
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let closedByEvent = false

  const consumeBlock = (block: string) => {
    const event = parseSseBlock(block)
    if (!event) return

    if (event.type === 'delta') {
      const data = parseSseData(event.data)
      const content = typeof data.content === 'string' ? data.content : ''
      if (content) {
        handlers.onDelta(content)
      }
      return
    }

    if (event.type === 'session') {
      const data = parseSseData(event.data)
      if (
        typeof data.id === 'string'
        && typeof data.title === 'string'
        && typeof data.created_at === 'string'
        && typeof data.updated_at === 'string'
      ) {
        handlers.onSession?.({
          id: data.id,
          title: data.title,
          agent_id: typeof data.agent_id === 'string' ? data.agent_id : null,
          agent_revision_id: typeof data.agent_revision_id === 'string' ? data.agent_revision_id : null,
          agent_name: typeof data.agent_name === 'string' ? data.agent_name : null,
          created_at: data.created_at,
          updated_at: data.updated_at,
          message_count: typeof data.message_count === 'number' ? data.message_count : 0,
        })
      }
      return
    }

    if (event.type === 'tool') {
      const data = parseSseData(event.data)
      if (typeof data.title === 'string' && typeof data.kind === 'string') {
        handlers.onTool?.({
          content: typeof data.content === 'string' ? data.content : undefined,
          kind: data.kind === 'tool_call' || data.kind === 'tool_result' || data.kind === 'model_output'
            ? data.kind
            : 'tool_result',
          name: typeof data.name === 'string' ? data.name : undefined,
          status: data.status === 'running' || data.status === 'error' || data.status === 'done' ? data.status : undefined,
          title: data.title,
        })
      }
      return
    }

    if (event.type === 'error') {
      const data = parseSseData(event.data)
      const text = typeof data.message === 'string' && data.message.length > 0
        ? data.message
        : 'Chat API 流式请求失败'
      throw new Error(text)
    }

    if (event.type === 'done') {
      closedByEvent = true
      handlers.onDone?.()
    }
  }

  const consumeBuffer = (flush = false) => {
    const normalized = buffer.replace(/\r\n/g, '\n')
    const blocks = normalized.split('\n\n')
    const completeBlocks = flush ? blocks : blocks.slice(0, -1)

    for (const block of completeBlocks) {
      if (!block.trim()) continue
      consumeBlock(block)
      if (closedByEvent) break
    }

    buffer = flush ? '' : blocks.at(-1) ?? ''
  }

  while (!closedByEvent) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    consumeBuffer()
  }

  if (!closedByEvent) {
    buffer += decoder.decode()
    consumeBuffer(true)
    handlers.onDone?.()
  }
}

function parseSseBlock(block: string): { data: string; type: string } | null {
  const lines = block.split('\n')
  const dataLines: string[] = []
  let type = 'message'

  for (const line of lines) {
    if (line.startsWith('event:')) {
      type = line.slice('event:'.length).trim()
      continue
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart())
    }
  }

  if (dataLines.length === 0) {
    return null
  }

  return {
    data: dataLines.join('\n'),
    type,
  }
}

function parseSseData(data: string): Record<string, unknown> {
  try {
    const payload = JSON.parse(data) as unknown
    return payload && typeof payload === 'object' ? payload as Record<string, unknown> : {}
  } catch {
    return {}
  }
}
