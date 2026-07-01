import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent } from 'react'
import { Button, Input, Select, Tag, Typography } from 'antd'
import { CloseOutlined, DragOutlined, PlusOutlined, SendOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  createChatCompletion,
  getChatSessionMessages,
  listChatSessions,
  persistChatSessionTurn,
  type ChatMessagePayload,
  type ChatSessionSummary,
} from '../../../lib/chat'
import { listMyAgents, type UserAgent } from '../../../lib/agentMarket'
import { listMyAgentSkills, type UserAgentSkill } from '../../../lib/agentSkills'
import { resolveErrorMessage } from '../../../lib/errorMessage'
import type { CanvasAgentToolCall, CanvasAgentToolResult } from '../interactiveMovieTypes'
import { useInteractiveMoviePageContext } from './useInteractiveMoviePageContext'

type CanvasAgentMessage = {
  steps?: CanvasAgentToolStep[]
  id: string
  role: 'user' | 'assistant'
  content: string
}

type CanvasAgentToolStep = {
  detail?: string
  id: string
  status: 'done' | 'error' | 'running'
  title: string
}

type PanelGeometry = {
  height: number
  width: number
  x: number
  y: number
}

type PanelInteraction =
  | {
    type: 'drag'
    pointerId: number
    startClient: { x: number; y: number }
    startGeometry: PanelGeometry
  }
  | {
    type: 'resize'
    pointerId: number
    startClient: { x: number; y: number }
    startGeometry: PanelGeometry
  }

type MentionKind = 'agent' | 'knowledge' | 'skill'

type MentionOption = {
  agentId?: string
  id: string
  insertText: string
  kind: MentionKind
  label: string
  subtitle: string
  tag: string
}

const FRONTEND_CANVAS_PREFIX = 'frontend_canvas__'
const FRONTEND_CANVAS_UNAVAILABLE_MESSAGE = '请在画布中调用智能体, 而非在聊天栏调用.'
const MAX_TOOL_STEPS = 8
const PANEL_GEOMETRY_KEY = 'interactiveMovie.canvasAgent.panelGeometry'
const PANEL_SESSION_KEY = 'interactiveMovie.canvasAgent.sessionId'
const KNOWLEDGE_MENTION = '$知识库'
const CAPABILITY_MENTION_TRIGGER_PATTERN = /(^|\s)@([\u4e00-\u9fa5A-Za-z0-9_-]*)$/
const KNOWLEDGE_MENTION_TRIGGER_PATTERN = /(^|\s)\$([\u4e00-\u9fa5A-Za-z0-9_-]*)$/
const MENTION_PAGE_SIZE = 6

const defaultPanelGeometry = (): PanelGeometry => {
  const width = 420
  const height = 520
  return {
    width,
    height,
    x: Math.max(16, (window.innerWidth - width) / 2),
    y: Math.max(80, (window.innerHeight - height) / 2),
  }
}

const clampPanelGeometry = (geometry: PanelGeometry): PanelGeometry => {
  const maxWidth = Math.max(320, window.innerWidth - 24)
  const maxHeight = Math.max(280, window.innerHeight - 80)
  const width = Math.min(Math.max(320, geometry.width), maxWidth)
  const height = Math.min(Math.max(280, geometry.height), maxHeight)
  return {
    width,
    height,
    x: Math.min(Math.max(12, geometry.x), Math.max(12, window.innerWidth - width - 12)),
    y: Math.min(Math.max(56, geometry.y), Math.max(56, window.innerHeight - height - 12)),
  }
}

const loadPanelGeometry = () => {
  try {
    const raw = localStorage.getItem(PANEL_GEOMETRY_KEY)
    if (!raw) return defaultPanelGeometry()
    const parsed = JSON.parse(raw) as Partial<PanelGeometry>
    if (
      typeof parsed.width === 'number'
      && typeof parsed.height === 'number'
      && typeof parsed.x === 'number'
      && typeof parsed.y === 'number'
    ) {
      return clampPanelGeometry(parsed as PanelGeometry)
    }
  } catch {
    // ignore invalid local state
  }
  return defaultPanelGeometry()
}

const canvasToolDefinitions: Array<Record<string, unknown>> = [
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}get_overview`,
      description: '获取当前互动电影画布概括，只包含节点关系、节点 title 和节点类型。',
      parameters: { type: 'object', properties: {}, additionalProperties: false },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}get_node_detail`,
      description: '按 type 和 id 获取一个画布对象的完整详情。type 可为 scene、text、image、video、asset、choice、nodeLink。',
      parameters: {
        type: 'object',
        properties: { type: { type: 'string' }, id: { type: 'string' } },
        required: ['type', 'id'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}create_node`,
      description: '创建场景或素材节点。type 可为 scene、text、image、video。',
      parameters: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['scene', 'text', 'image', 'video'] },
          title: { type: 'string' },
          position: {
            type: 'object',
            properties: { x: { type: 'number' }, y: { type: 'number' } },
            required: ['x', 'y'],
            additionalProperties: false,
          },
          role: { type: 'string', enum: ['start', 'middle', 'ending'] },
          script: { type: 'object' },
          text: { type: 'string' },
          media: { type: 'object' },
        },
        required: ['type'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}update_node`,
      description: '更新场景或素材节点。type 可为 scene、text、image、video，patch 放需要修改的字段。',
      parameters: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['scene', 'text', 'image', 'video'] },
          id: { type: 'string' },
          patch: { type: 'object' },
        },
        required: ['type', 'id', 'patch'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}delete_node`,
      description: '删除场景或素材节点。删除时会清理相关选择线、节点连接和场景媒体引用。',
      parameters: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['scene', 'text', 'image', 'video'] },
          id: { type: 'string' },
        },
        required: ['type', 'id'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}create_relation`,
      description: '创建画布关系。type=choice 创建场景选择线；type=nodeLink 创建普通节点连接线。',
      parameters: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['choice', 'nodeLink'] },
          fromSceneId: { type: 'string' },
          toSceneId: { type: 'string' },
          label: { type: 'string' },
          from: { type: 'object' },
          to: { type: 'object' },
        },
        required: ['type'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}update_relation`,
      description: '更新选择线或普通节点连接线。type 可为 choice 或 nodeLink。',
      parameters: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['choice', 'nodeLink'] },
          id: { type: 'string' },
          patch: { type: 'object' },
        },
        required: ['type', 'id', 'patch'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}delete_relation`,
      description: '删除选择线或普通节点连接线。type 可为 choice 或 nodeLink。',
      parameters: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['choice', 'nodeLink'] },
          id: { type: 'string' },
        },
        required: ['type', 'id'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: `${FRONTEND_CANVAS_PREFIX}apply_operations`,
      description: '批量执行多个画布操作，适合一次性创建知识库图、批量创建节点和连线，减少多轮工具调用。每个 operation.action 可为 create_node、update_node、delete_node、create_relation、update_relation、delete_relation。',
      parameters: {
        type: 'object',
        properties: {
          operations: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                action: {
                  type: 'string',
                  enum: ['create_node', 'update_node', 'delete_node', 'create_relation', 'update_relation', 'delete_relation'],
                },
                type: { type: 'string' },
                id: { type: 'string' },
                title: { type: 'string' },
                position: { type: 'object' },
                patch: { type: 'object' },
                role: { type: 'string' },
                script: { type: 'object' },
                text: { type: 'string' },
                media: { type: 'object' },
                fromSceneId: { type: 'string' },
                toSceneId: { type: 'string' },
                label: { type: 'string' },
                from: { type: 'object' },
                to: { type: 'object' },
              },
              required: ['action'],
              additionalProperties: true,
            },
          },
        },
        required: ['operations'],
        additionalProperties: false,
      },
    },
  },
]

const messageId = (role: CanvasAgentMessage['role']) => `${role}-${Date.now()}-${Math.random().toString(36).slice(2)}`

const toolStepId = (prefix: string) => `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
)

const readableValue = (value: unknown) => (typeof value === 'string' && value.trim() ? value.trim() : null)

const parseToolArguments = (raw: unknown): Record<string, unknown> => {
  if (typeof raw !== 'string') return {}
  try {
    const parsed = JSON.parse(raw) as unknown
    return isRecord(parsed) ? parsed : {}
  } catch {
    return {}
  }
}

const toolFunctionPayload = (toolCall: Record<string, unknown>) => (
  isRecord(toolCall.function) ? toolCall.function : null
)

const toolFunctionName = (toolCall: Record<string, unknown>) => {
  const functionPayload = toolFunctionPayload(toolCall)
  return typeof functionPayload?.name === 'string' ? functionPayload.name : ''
}

const toolFunctionArguments = (toolCall: Record<string, unknown>) => {
  const functionPayload = toolFunctionPayload(toolCall)
  return parseToolArguments(functionPayload?.arguments)
}

const endpointLabel = (value: unknown) => {
  if (!isRecord(value)) return ''
  const type = readableValue(value.type)
  const id = readableValue(value.id)
  return [type, id].filter(Boolean).join(':')
}

const canvasToolStepTitle = (toolCall: Record<string, unknown>) => {
  const name = toolFunctionName(toolCall).replace(FRONTEND_CANVAS_PREFIX, '')
  const args = toolFunctionArguments(toolCall)
  const type = readableValue(args.type)
  const id = readableValue(args.id)
  const title = readableValue(args.title)
  const label = readableValue(args.label)
  if (name === 'get_overview') return { title: '读取画布概括' }
  if (name === 'get_node_detail') return { title: `读取节点详情：${[type, id].filter(Boolean).join(':') || '未指定节点'}` }
  if (name === 'create_node') return { title: `创建${type === 'scene' ? '场景' : '节点'}：${title || type || '未命名'}` }
  if (name === 'update_node') return { title: `更新节点：${[type, id].filter(Boolean).join(':') || '未指定节点'}` }
  if (name === 'delete_node') return { title: `删除节点：${[type, id].filter(Boolean).join(':') || '未指定节点'}` }
  if (name === 'create_relation') {
    if (type === 'choice') return { title: `创建选择线：${label || '未命名选择'}`, detail: `${readableValue(args.fromSceneId) || '?'} -> ${readableValue(args.toSceneId) || '?'}` }
    return { title: '创建节点连接', detail: `${endpointLabel(args.from) || '?'} -> ${endpointLabel(args.to) || '?'}` }
  }
  if (name === 'update_relation') return { title: `更新关系：${[type, id].filter(Boolean).join(':') || '未指定关系'}` }
  if (name === 'delete_relation') return { title: `删除关系：${[type, id].filter(Boolean).join(':') || '未指定关系'}` }
  if (name === 'apply_operations') {
    const operations = Array.isArray(args.operations) ? args.operations : []
    return { title: `批量执行画布操作：${operations.length} 个` }
  }
  return { title: `调用画布工具：${name || 'unknown'}` }
}

const extractKnowledgeToolTrace = (raw: Record<string, unknown> | null | undefined) => {
  const trace = raw?.tool_trace
  if (!Array.isArray(trace)) return []
  return trace
    .filter((item): item is Record<string, unknown> => isRecord(item))
    .map((item) => ({
      page: readableValue(item.page) || readableValue(item.title) || '',
      source: readableValue(item.source) || 'tool_call',
    }))
    .filter((item) => item.page)
}

const extractToolCalls = (raw: Record<string, unknown> | null | undefined): Array<Record<string, unknown>> => {
  const choices = raw?.choices
  if (!Array.isArray(choices)) return []
  const firstChoice = choices[0]
  if (typeof firstChoice !== 'object' || firstChoice === null) return []
  const message = (firstChoice as { message?: unknown }).message
  if (typeof message !== 'object' || message === null) return []
  const toolCalls = (message as { tool_calls?: unknown }).tool_calls
  return Array.isArray(toolCalls) ? toolCalls.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null) : []
}

const toolCallToCanvasCall = (toolCall: Record<string, unknown>): CanvasAgentToolCall => {
  return { name: toolFunctionName(toolCall), arguments: toolFunctionArguments(toolCall) }
}

const toolCallId = (toolCall: Record<string, unknown>, index: number) => (
  typeof toolCall.id === 'string' && toolCall.id ? toolCall.id : `frontend_canvas_call_${index + 1}`
)

const sessionLabel = (session: ChatSessionSummary) => `${session.title || '新对话'} · ${session.message_count}`

const agentMentionText = (agent: UserAgent) => `@${agent.slug || agent.id}`

const mentionMatches = (values: string[], query: string) => {
  if (!query) return true
  const normalizedQuery = query.toLowerCase()
  return values.some((value) => value.toLowerCase().includes(normalizedQuery))
}

export function CanvasAgentChat({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const { activeProject, buildCanvasAgentOverview, closeCanvasContextMenu, executeCanvasAgentTool } = useInteractiveMoviePageContext()
  const [geometry, setGeometry] = useState<PanelGeometry>(() => loadPanelGeometry())
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<CanvasAgentMessage[]>([])
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(() => localStorage.getItem(PANEL_SESSION_KEY))
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [mentionAgents, setMentionAgents] = useState<UserAgent[]>([])
  const [mentionSkills, setMentionSkills] = useState<UserAgentSkill[]>([])
  const [mentionLoading, setMentionLoading] = useState(false)
  const [selectedMentionIndex, setSelectedMentionIndex] = useState(0)
  const [loading, setLoading] = useState(false)
  const interactionRef = useRef<PanelInteraction | null>(null)
  const messageListRef = useRef<HTMLDivElement>(null)

  const latestMessages = useMemo(() => messages.slice(-10), [messages])
  const activeCapabilityMentionQuery = useMemo(() => {
    const match = input.match(CAPABILITY_MENTION_TRIGGER_PATTERN)
    return match ? match[2].toLowerCase() : null
  }, [input])
  const activeKnowledgeMentionQuery = useMemo(() => {
    if (activeCapabilityMentionQuery !== null) return null
    const match = input.match(KNOWLEDGE_MENTION_TRIGGER_PATTERN)
    return match ? match[2] : null
  }, [activeCapabilityMentionQuery, input])
  const mentionOptions = useMemo<MentionOption[]>(() => {
    if (activeCapabilityMentionQuery !== null) {
      const agentOptions = mentionAgents
        .filter((agent) => mentionMatches([
          agent.id,
          agent.slug,
          agent.name,
          agent.title,
          agent.category_label,
          ...agent.tags,
        ], activeCapabilityMentionQuery))
        .map((agent): MentionOption => ({
          agentId: agent.id,
          id: `agent-${agent.id}`,
          insertText: agentMentionText(agent),
          kind: 'agent',
          label: agent.name,
          subtitle: agent.category_label || agentMentionText(agent),
          tag: '智能体',
        }))
      const skillOptions = mentionSkills
        .filter((skill) => mentionMatches([
          skill.id,
          skill.slug,
          skill.mention,
          skill.name,
          skill.title,
          skill.category_label,
          ...skill.tags,
        ], activeCapabilityMentionQuery))
        .map((skill): MentionOption => ({
          id: `skill-${skill.id}`,
          insertText: skill.mention,
          kind: 'skill',
          label: skill.name,
          subtitle: skill.mention,
          tag: '技能',
        }))
      return [...agentOptions, ...skillOptions].slice(0, MENTION_PAGE_SIZE * 2)
    }
    if (activeKnowledgeMentionQuery !== null && '知识库'.startsWith(activeKnowledgeMentionQuery)) {
      return [{
        id: 'knowledge-personal-aiwiki',
        insertText: KNOWLEDGE_MENTION,
        kind: 'knowledge',
        label: '个人 AI Wiki',
        subtitle: KNOWLEDGE_MENTION,
        tag: '知识库',
      }]
    }
    return []
  }, [activeCapabilityMentionQuery, activeKnowledgeMentionQuery, mentionAgents, mentionSkills])
  const activeMentionKind: MentionKind | null = activeCapabilityMentionQuery !== null
    ? 'agent'
    : activeKnowledgeMentionQuery !== null
      ? 'knowledge'
      : null
  const hasSelectableMention = !mentionLoading && mentionOptions.length > 0

  useEffect(() => {
    localStorage.setItem(PANEL_GEOMETRY_KEY, JSON.stringify(geometry))
  }, [geometry])

  useEffect(() => {
    if (activeSessionId) localStorage.setItem(PANEL_SESSION_KEY, activeSessionId)
    else localStorage.removeItem(PANEL_SESSION_KEY)
  }, [activeSessionId])

  useEffect(() => {
    if (!open) return
    void refreshSessions(activeSessionId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (!open) return
    messageListRef.current?.scrollTo({ top: messageListRef.current.scrollHeight })
  }, [messages, open])

  useEffect(() => {
    if (activeCapabilityMentionQuery === null || !open) {
      setMentionAgents([])
      setMentionSkills([])
      setSelectedMentionIndex(0)
      setMentionLoading(false)
      return
    }

    let cancelled = false
    setMentionLoading(true)
    void Promise.all([
      listMyAgents({ page: 1, pageSize: MENTION_PAGE_SIZE, search: activeCapabilityMentionQuery }),
      listMyAgentSkills({ page: 1, pageSize: MENTION_PAGE_SIZE, search: activeCapabilityMentionQuery }),
    ])
      .then(([agentPage, skillPage]) => {
        if (cancelled) return
        setMentionAgents(agentPage.items)
        setMentionSkills(skillPage.items)
        setSelectedMentionIndex(0)
      })
      .catch(() => {
        if (cancelled) return
        setMentionAgents([])
        setMentionSkills([])
      })
      .finally(() => {
        if (!cancelled) setMentionLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [activeCapabilityMentionQuery, open])

  useEffect(() => {
    setSelectedMentionIndex((current) => {
      if (mentionOptions.length === 0) return 0
      return Math.min(current, mentionOptions.length - 1)
    })
  }, [mentionOptions.length])

  const refreshSessions = async (sessionId = activeSessionId) => {
    const nextSessions = await listChatSessions()
    setSessions(nextSessions)
    const nextActiveSession = sessionId ? nextSessions.find((item) => item.id === sessionId) : null
    const nextActiveId = nextActiveSession
      ? sessionId
      : null
    setActiveSessionId(nextActiveId)
    setSelectedAgentId(nextActiveSession?.agent_id ?? null)
    if (!nextActiveId) {
      setMessages([])
      return
    }
    const records = await getChatSessionMessages(nextActiveId)
    setMessages(records.map((record) => ({
      id: record.id,
      role: record.role === 'user' ? 'user' : 'assistant',
      content: record.content,
    })))
  }

  const buildBaseMessages = (userContent: string): ChatMessagePayload[] => [
    {
      role: 'system',
      content: [
        '你是互动电影画布智能体。你可以通过 frontend_canvas__ 前缀工具读取和修改当前画布。',
        `这些工具只能在画布页执行；如果不在画布页，应返回：${FRONTEND_CANVAS_UNAVAILABLE_MESSAGE}`,
        '当前 system context 只包含画布概括。需要完整字段时先调用 get_node_detail，不要凭旧上下文猜测。',
        '当需要创建或修改多个节点/关系时，优先调用 frontend_canvas__apply_operations 批量提交，避免一轮只处理一个对象。',
        '完成工具调用后，用简洁中文说明你做了什么。回复支持 Markdown。',
        `当前项目：${activeProject.title}`,
        selectedAgentId ? `本轮指定智能体 id：${selectedAgentId}` : '',
        `当前画布概括：${JSON.stringify(buildCanvasAgentOverview())}`,
      ].join('\n'),
    },
    ...latestMessages.map((message): ChatMessagePayload => ({ role: message.role, content: message.content })),
    { role: 'user', content: userContent },
  ]

  const updateAssistantMessage = (
    assistantMessageId: string,
    updater: (message: CanvasAgentMessage) => CanvasAgentMessage,
  ) => {
    setMessages((current) => current.map((message) => (
      message.id === assistantMessageId ? updater(message) : message
    )))
  }

  const appendToolStep = (assistantMessageId: string, toolStep: CanvasAgentToolStep) => {
    updateAssistantMessage(assistantMessageId, (message) => ({
      ...message,
      steps: [...(message.steps ?? []), toolStep],
    }))
  }

  const updateToolStep = (
    assistantMessageId: string,
    stepId: string,
    patch: Partial<Omit<CanvasAgentToolStep, 'id'>>,
  ) => {
    updateAssistantMessage(assistantMessageId, (message) => ({
      ...message,
      steps: (message.steps ?? []).map((step) => (
        step.id === stepId ? { ...step, ...patch } : step
      )),
    }))
  }

  const appendKnowledgeTraceSteps = (
    assistantMessageId: string,
    raw: Record<string, unknown> | null | undefined,
    seenTraceKeys: Set<string>,
  ) => {
    for (const item of extractKnowledgeToolTrace(raw)) {
      const key = `${item.source}:${item.page}`
      if (seenTraceKeys.has(key)) continue
      seenTraceKeys.add(key)
      appendToolStep(assistantMessageId, {
        id: toolStepId('knowledge-entry'),
        status: 'done',
        title: `读取知识库词条：${item.page}`,
        detail: item.source === 'auto_fallback' ? '模型未主动调用工具时由后端按索引自动读取' : undefined,
      })
    }
  }

  const requestWithTools = async (
    baseMessages: ChatMessagePayload[],
    assistantMessageId: string,
    seenKnowledgeTraceKeys: Set<string>,
    step = 1,
  ): Promise<string> => {
    if (step > MAX_TOOL_STEPS) {
      appendToolStep(assistantMessageId, {
        id: toolStepId('tool-limit'),
        status: 'error',
        title: '工具调用已暂停',
        detail: '已完成的画布操作会保留，可以继续追问让智能体补齐剩余部分。',
      })
      return `工具调用已暂停。已完成的画布操作会保留，你可以继续要求我补齐剩余内容。`
    }
    const responseStepId = toolStepId('model-response')
    appendToolStep(assistantMessageId, {
      id: responseStepId,
      status: 'running',
      title: '等待模型响应',
    })
    const response = await createChatCompletion({
      messages: baseMessages,
      agent_id: selectedAgentId ?? undefined,
      tools: canvasToolDefinitions,
      temperature: 0.2,
      max_tokens: 2200,
    })
    appendKnowledgeTraceSteps(assistantMessageId, response.raw ?? null, seenKnowledgeTraceKeys)
    const toolCalls = extractToolCalls(response.raw ?? null).filter((toolCall) => {
      const name = toolFunctionName(toolCall)
      return typeof name === 'string' && name.startsWith(FRONTEND_CANVAS_PREFIX)
    })
    if (toolCalls.length === 0) {
      updateToolStep(assistantMessageId, responseStepId, {
        status: 'done',
        title: '模型生成回复',
      })
      return response.content || '已处理。'
    }
    updateToolStep(assistantMessageId, responseStepId, {
      status: 'done',
      title: `模型请求 ${toolCalls.length} 个工具调用`,
    })
    if (response.content.trim()) {
      appendToolStep(assistantMessageId, {
        id: toolStepId('model-output'),
        status: 'done',
        title: '模型输出',
        detail: response.content.trim(),
      })
    }

    const toolResults: CanvasAgentToolResult[] = []
    for (const toolCall of toolCalls) {
      const description = canvasToolStepTitle(toolCall)
      const executionStepId = toolStepId('canvas-tool')
      appendToolStep(assistantMessageId, {
        id: executionStepId,
        status: 'running',
        ...description,
      })
      const result = executeCanvasAgentTool(toolCallToCanvasCall(toolCall))
      toolResults.push(result)
      updateToolStep(assistantMessageId, executionStepId, {
        status: result.ok ? 'done' : 'error',
        detail: result.message,
      })
    }
    const nextMessages: ChatMessagePayload[] = [
      ...baseMessages,
      { role: 'assistant', content: response.content ?? '', tool_calls: toolCalls },
      ...toolResults.map((result, index): ChatMessagePayload => ({
        role: 'tool',
        tool_call_id: toolCallId(toolCalls[index], index),
        name: String(((toolCalls[index].function as { name?: unknown } | undefined)?.name) || `${FRONTEND_CANVAS_PREFIX}unknown`),
        content: JSON.stringify(result),
      })),
    ]
    return requestWithTools(nextMessages, assistantMessageId, seenKnowledgeTraceKeys, step + 1)
  }

  const sendMessage = async () => {
    const content = input.trim()
    if (!content || loading) return
    setInput('')
    setLoading(true)
    const assistantMessageId = messageId('assistant')
    const initialSteps: CanvasAgentToolStep[] = content.includes(KNOWLEDGE_MENTION)
      ? [{
        id: toolStepId('knowledge-index'),
        status: 'running',
        title: '读取个人 AI Wiki 索引',
        detail: '根据 $知识库 指令注入索引，并允许后端读取相关词条全文。',
      }]
      : []
    setMessages((current) => [
      ...current,
      { id: messageId('user'), role: 'user', content },
      { id: assistantMessageId, role: 'assistant', content: '正在处理...', steps: initialSteps },
    ])
    try {
      const seenKnowledgeTraceKeys = new Set<string>()
      const assistantContent = await requestWithTools(buildBaseMessages(content), assistantMessageId, seenKnowledgeTraceKeys)
      if (content.includes(KNOWLEDGE_MENTION)) {
        updateToolStep(assistantMessageId, initialSteps[0]?.id ?? '', {
          status: 'done',
          title: '已注入个人 AI Wiki 索引',
        })
      }
      updateAssistantMessage(assistantMessageId, (message) => ({
        ...message,
        content: assistantContent,
      }))
      const session = await persistChatSessionTurn({
        session_id: activeSessionId ?? undefined,
        agent_id: selectedAgentId ?? undefined,
        user_content: content,
        assistant_content: assistantContent,
      })
      setActiveSessionId(session.id)
      setSelectedAgentId(session.agent_id ?? selectedAgentId)
      setSessions(await listChatSessions())
    } catch (error) {
      updateAssistantMessage(assistantMessageId, (message) => ({
        ...message,
        content: resolveErrorMessage(error),
        steps: [
          ...(message.steps ?? []),
          {
            id: toolStepId('error'),
            status: 'error',
            title: '处理失败',
            detail: resolveErrorMessage(error),
          },
        ],
      }))
    } finally {
      setLoading(false)
    }
  }

  const selectMentionOption = (option: MentionOption) => {
    setInput((current) => {
      const pattern = option.kind === 'knowledge' ? KNOWLEDGE_MENTION_TRIGGER_PATTERN : CAPABILITY_MENTION_TRIGGER_PATTERN
      if (!pattern.test(current)) {
        const prefix = current.trimEnd()
        return prefix ? `${prefix} ${option.insertText} ` : `${option.insertText} `
      }
      return current.replace(pattern, `$1${option.insertText} `)
    })
    if (option.kind === 'agent' && option.agentId) {
      const activeSession = sessions.find((session) => session.id === activeSessionId)
      if (activeSessionId && activeSession?.agent_id !== option.agentId) {
        setActiveSessionId(null)
        setMessages([])
      }
      setSelectedAgentId(option.agentId)
    }
  }

  const confirmSelectedMentionCandidate = () => {
    if (!hasSelectableMention) return false
    const option = mentionOptions[selectedMentionIndex] ?? mentionOptions[0]
    if (!option) return false
    selectMentionOption(option)
    return true
  }

  const handleInputKeyDown = (event: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (!hasSelectableMention) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      event.stopPropagation()
      setSelectedMentionIndex((current) => (current + 1) % mentionOptions.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      event.stopPropagation()
      setSelectedMentionIndex((current) => (current - 1 < 0 ? mentionOptions.length - 1 : current - 1))
    } else if (event.key === 'Tab' || event.key === 'Enter') {
      event.preventDefault()
      event.stopPropagation()
      confirmSelectedMentionCandidate()
    }
  }

  const beginDrag = (event: ReactPointerEvent<HTMLButtonElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'drag',
      pointerId: event.pointerId,
      startClient: { x: event.clientX, y: event.clientY },
      startGeometry: geometry,
    }
  }

  const beginResize = (event: ReactPointerEvent<HTMLButtonElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'resize',
      pointerId: event.pointerId,
      startClient: { x: event.clientX, y: event.clientY },
      startGeometry: geometry,
    }
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const interaction = interactionRef.current
    if (!interaction || interaction.pointerId !== event.pointerId) return
    const dx = event.clientX - interaction.startClient.x
    const dy = event.clientY - interaction.startClient.y
    if (interaction.type === 'drag') {
      setGeometry(clampPanelGeometry({
        ...interaction.startGeometry,
        x: interaction.startGeometry.x + dx,
        y: interaction.startGeometry.y + dy,
      }))
      return
    }
    setGeometry(clampPanelGeometry({
      ...interaction.startGeometry,
      width: interaction.startGeometry.width + dx,
      height: interaction.startGeometry.height + dy,
    }))
  }

  const endPointerInteraction = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (interactionRef.current?.pointerId === event.pointerId) interactionRef.current = null
  }

  if (!open) return null

  return (
    <div
      className="movie-canvas-agent-panel"
      style={{ left: geometry.x, top: geometry.y, width: geometry.width, height: geometry.height }}
      onPointerMove={handlePointerMove}
      onPointerUp={endPointerInteraction}
      onPointerCancel={endPointerInteraction}
      onPointerDown={(event) => {
        closeCanvasContextMenu()
        event.stopPropagation()
      }}
      onContextMenu={(event) => {
        closeCanvasContextMenu()
        event.preventDefault()
        event.stopPropagation()
      }}
      onWheel={(event) => event.stopPropagation()}
    >
      <div className="movie-agent-panel-header">
        <button type="button" className="movie-agent-drag" onPointerDown={beginDrag} aria-label="移动智能体栏">
          <DragOutlined />
        </button>
        <div className="movie-agent-heading">
          <Typography.Text className="movie-panel-kicker">画布智能体</Typography.Text>
          <Select
            value={activeSessionId ?? undefined}
            allowClear
            placeholder="新对话"
            disabled={loading}
            options={sessions.map((session) => ({ value: session.id, label: sessionLabel(session) }))}
            onChange={(sessionId) => {
              void refreshSessions(sessionId ?? null)
            }}
            className="movie-agent-session-select"
            popupMatchSelectWidth={false}
          />
        </div>
        <Button icon={<PlusOutlined />} disabled={loading} onClick={() => {
          setActiveSessionId(null)
          setSelectedAgentId(null)
          setMessages([])
        }} aria-label="新建对话" />
        <Button icon={<CloseOutlined />} onClick={onClose} aria-label="关闭智能体栏" />
      </div>

      <div ref={messageListRef} className="movie-agent-message-list">
        {messages.length === 0 ? (
          <div className="movie-agent-empty">让智能体读取、创建、更新或删除当前画布节点和连线。</div>
        ) : messages.map((message) => (
          <div key={message.id} className={`movie-agent-message is-${message.role}`}>
            {message.steps && message.steps.length > 0 && (
              <div className="movie-agent-tool-steps">
                {message.steps.map((step) => (
                  <div className={`movie-agent-tool-step is-${step.status}`} key={step.id}>
                    <span className="movie-agent-tool-step-dot" aria-hidden />
                    <span className="movie-agent-tool-step-main">
                      <strong>{step.title}</strong>
                      {step.detail && <small>{step.detail}</small>}
                    </span>
                  </div>
                ))}
              </div>
            )}
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        ))}
      </div>

      <div className="movie-agent-form">
        <div className="movie-agent-input-shell">
          {activeMentionKind !== null && (
            <div className="movie-agent-mention-popover" role="listbox">
              {mentionLoading ? (
                <p className="movie-agent-mention-empty">搜索中...</p>
              ) : mentionOptions.length > 0 ? (
                mentionOptions.map((option, index) => (
                  <button
                    aria-selected={index === selectedMentionIndex}
                    className={index === selectedMentionIndex ? 'movie-agent-mention-option is-active' : 'movie-agent-mention-option'}
                    key={option.id}
                    onMouseDown={(event) => {
                      event.preventDefault()
                      selectMentionOption(option)
                    }}
                    onMouseEnter={() => setSelectedMentionIndex(index)}
                    role="option"
                    type="button"
                  >
                    <span>
                      <strong>{option.label}</strong>
                      <small>{option.subtitle}</small>
                    </span>
                    <Tag color={option.kind === 'knowledge' ? 'success' : option.kind === 'agent' ? 'processing' : 'info'}>{option.tag}</Tag>
                  </button>
                ))
              ) : (
                <p className="movie-agent-mention-empty">
                  {activeKnowledgeMentionQuery !== null ? '没有匹配的知识库' : '没有匹配的智能体或技能'}
                </p>
              )}
            </div>
          )}
          <Input.TextArea
            value={input}
            autoSize={{ minRows: 2, maxRows: 5 }}
            disabled={loading}
            placeholder="输入 @ 调用智能体/技能，输入 $ 选择知识库"
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleInputKeyDown}
            onPressEnter={(event) => {
              if (activeMentionKind !== null) {
                event.preventDefault()
                return
              }
              if (!event.shiftKey) {
                event.preventDefault()
                void sendMessage()
              }
            }}
          />
        </div>
        <Button
          type="primary"
          icon={<SendOutlined />}
          loading={loading}
          onClick={() => {
            if (activeMentionKind !== null && hasSelectableMention) {
              confirmSelectedMentionCandidate()
              return
            }
            void sendMessage()
          }}
          aria-label="发送"
        />
      </div>
      <button type="button" className="movie-agent-resize" onPointerDown={beginResize} aria-label="调整智能体栏大小" />
    </div>
  )
}
