import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { Alert, App, Avatar, Dropdown, Input, Modal, Typography, type MenuProps } from 'antd'
import { DeleteOutlined, EditOutlined } from '@ant-design/icons'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Bot,
  Check,
  ChevronLeft,
  ChevronRight,
  Crown,
  Film,
  Image as ImageIcon,
  LogOut,
  MessageSquareText,
  NotebookPen,
  Plus,
  Search,
  Send,
  Store,
  UserRound,
  type LucideIcon,
} from 'lucide-react'
import { Button as LobeButton, Tag, ThemeProvider as LobeThemeProvider } from '@lobehub/ui'
import { ChatInputAreaInner, ChatList, type ChatMessage, type RenderMessage } from '@lobehub/ui/chat'
import { useAuth } from '../../hooks/useAuth'
import {
  deleteChatSession,
  getChatSessionMessages,
  listChatSessions,
  renameChatSession,
  streamChatSession,
  type ChatMessageRecord,
  type ChatSessionSummary,
} from '../../lib/chat'
import {
  addMyAgentSkill,
  listAgentSkillMarket,
  listAgentSkillMarketCategories,
  listMyAgentSkills,
  removeMyAgentSkill,
  type AgentSkill,
  type AgentSkillCategory,
  type UserAgentSkill,
} from '../../lib/agentSkills'
import {
  addMyAgent,
  listAgentMarket,
  listAgentMarketCategories,
  listMyAgents,
  removeMyAgent,
  type AgentCategory,
  type AgentMarketItem,
  type UserAgent,
} from '../../lib/agentMarket'
import { resolveErrorMessage } from '../../lib/errorMessage'
import { BRAND_LOGO_SRC } from '../../lib/brand'
import BrandNavPill from '../../components/brand/BrandNavPill'
import WorkbenchHomeButton from '../../components/brand/WorkbenchHomeButton'
import './ChatHomePage.css'

type QuickPrompt = {
  icon: LucideIcon
  key: string
  label: string
  prompt: string
}

type Recommendation = {
  className: string
  description: string
  key: string
  tag: string
  title: string
  to?: string
}

type AgentMessageDisplay = {
  id?: string | null
  isDefault?: boolean
  name?: string | null
}

type NormalizedAgentDisplay = {
  id: string
  isDefault: boolean
  name: string
}

type SkillCenterMode = 'market' | 'my'
type CapabilityMarketMode = 'agents' | 'skills'
const AGENT_CATEGORY_ALL = '__all__'
const SKILL_CATEGORY_ALL = '__all__'
const DEFAULT_AGENT_ID = 'zhongying-advertising'
const DEFAULT_AGENT_NAME = '中影广告智能体'
const AGENT_PAGE_SIZE = 30
const SKILL_PAGE_SIZE = 20
const MENTION_SKILL_PAGE_SIZE = 6

const quickPrompts: QuickPrompt[] = [
  {
    icon: NotebookPen,
    key: 'storyboard',
    label: '构建剧本与分镜图',
    prompt: '帮我为一条互动影游短片构建三幕剧本、关键选择节点和分镜图清单。',
  },
  {
    icon: ImageIcon,
    key: 'camera',
    label: '探索图片运镜效果',
    prompt: '帮我设计一组图片转视频的运镜效果，适合悬疑互动影游开场。',
  },
  {
    icon: Film,
    key: 'role',
    label: '塑造写实原创角色',
    prompt: '帮我塑造一个写实原创角色，包含身份、动机、造型和互动选择触发点。',
  },
]

const recommendations: Recommendation[] = [
  {
    className: 'chat-card-workspace',
    description: '打开节点画布、场景视频、选择跳转和互动预览。',
    key: 'workspace',
    tag: 'Workspace',
    title: '互动影游工作空间',
    to: '/interactive-movie',
  },
  {
    className: 'chat-card-script',
    description: '沉淀主线、分支和关键镜头，快速形成可制作草稿。',
    key: 'script',
    tag: 'Script',
    title: '剧本与分镜启动板',
  },
  {
    className: 'chat-card-role',
    description: '整理角色设定、视觉关键词和每个选择背后的动机。',
    key: 'role-kit',
    tag: 'Role',
    title: '原创角色设定包',
  },
]

function normalizeAgentDisplay(agent?: AgentMessageDisplay | null): NormalizedAgentDisplay {
  const id = agent?.id || DEFAULT_AGENT_ID
  const name = agent?.name?.trim() || (id === DEFAULT_AGENT_ID ? DEFAULT_AGENT_NAME : id)
  return {
    id,
    isDefault: Boolean(agent?.isDefault) || id === DEFAULT_AGENT_ID || name === DEFAULT_AGENT_NAME,
    name,
  }
}

function agentInitial(name: string): string {
  return Array.from(name.trim())[0]?.toUpperCase() || 'A'
}

function agentDisplayFromSession(session?: Pick<ChatSessionSummary, 'agent_id' | 'agent_name'> | null): AgentMessageDisplay {
  return {
    id: session?.agent_id ?? DEFAULT_AGENT_ID,
    isDefault: session?.agent_id === DEFAULT_AGENT_ID,
    name: session?.agent_name ?? (session?.agent_id === DEFAULT_AGENT_ID ? DEFAULT_AGENT_NAME : session?.agent_id),
  }
}

function agentDisplayFromAgent(agent: AgentMarketItem | null, fallbackAgentId?: string | null): AgentMessageDisplay {
  return {
    id: agent?.id ?? fallbackAgentId ?? DEFAULT_AGENT_ID,
    isDefault: Boolean(agent?.is_default) || agent?.id === DEFAULT_AGENT_ID || fallbackAgentId === DEFAULT_AGENT_ID,
    name: agent?.name ?? (fallbackAgentId === DEFAULT_AGENT_ID ? DEFAULT_AGENT_NAME : fallbackAgentId),
  }
}

function assistantAvatar(agent?: AgentMessageDisplay | null): ReactNode {
  const display = normalizeAgentDisplay(agent)
  if (display.isDefault) {
    return <img alt={display.name} className="chat-assistant-avatar" src={BRAND_LOGO_SRC} />
  }
  return <span className="chat-assistant-initial">{agentInitial(display.name)}</span>
}

function createMessage(role: ChatMessage['role'], content: string, agent?: AgentMessageDisplay | null): ChatMessage {
  const now = Date.now()
  const isUser = role === 'user'
  const display = normalizeAgentDisplay(agent)
  return {
    content,
    createAt: now,
    id: `${role}-${now}-${Math.random().toString(36).slice(2)}`,
    meta: {
      avatar: isUser ? '你' : assistantAvatar(display),
      backgroundColor: isUser ? '#2dd4bf' : (display.isDefault ? '#111712' : '#2dd4bf'),
      title: isUser ? '你' : display.name,
    },
    role,
    updateAt: now,
  }
}

function createMessageFromRecord(record: ChatMessageRecord, agent?: AgentMessageDisplay | null): ChatMessage {
  const createdAt = Date.parse(record.created_at)
  const role = record.role === 'system' ? 'assistant' : record.role
  return {
    ...createMessage(role, record.content, agent),
    createAt: Number.isFinite(createdAt) ? createdAt : Date.now(),
    id: record.id,
    updateAt: Number.isFinite(createdAt) ? createdAt : Date.now(),
  }
}

function sessionUpdatedAt(session: ChatSessionSummary): number {
  const updatedAt = Date.parse(session.updated_at)
  return Number.isFinite(updatedAt) ? updatedAt : 0
}

const renderChatMessage: RenderMessage = ({ editableContent }) => (
  <div className="chat-message-markdown">
    {editableContent}
  </div>
)

const CHAT_HOME_PATH = '/agents'
const SKILL_MENTION_TRIGGER_PATTERN = /(^|\s)@([A-Za-z0-9_-]*)$/

function chatSessionPath(sessionId: string): string {
  return `${CHAT_HOME_PATH}/chat/${encodeURIComponent(sessionId)}`
}

export default function ChatHomePage() {
  const navigate = useNavigate()
  const { sessionId: routeSessionId } = useParams<{ sessionId?: string }>()
  const { message, modal } = App.useApp()
  const { user, logout } = useAuth()
  const [draft, setDraft] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([])
  const [agents, setAgents] = useState<AgentMarketItem[]>([])
  const [myAgents, setMyAgents] = useState<UserAgent[]>([])
  const [agentCategories, setAgentCategories] = useState<AgentCategory[]>([])
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [agentCategory, setAgentCategory] = useState(AGENT_CATEGORY_ALL)
  const [agentSearchDraft, setAgentSearchDraft] = useState('')
  const [agentSearch, setAgentSearch] = useState('')
  const [agentsLoading, setAgentsLoading] = useState(false)
  const [agentActionId, setAgentActionId] = useState<string | null>(null)
  const [marketSkills, setMarketSkills] = useState<AgentSkill[]>([])
  const [mySkills, setMySkills] = useState<UserAgentSkill[]>([])
  const [marketSkillCategories, setMarketSkillCategories] = useState<AgentSkillCategory[]>([])
  const [skillCategory, setSkillCategory] = useState(SKILL_CATEGORY_ALL)
  const [skillSearchDraft, setSkillSearchDraft] = useState('')
  const [skillSearch, setSkillSearch] = useState('')
  const [marketSkillPage, setMarketSkillPage] = useState(1)
  const [marketSkillTotal, setMarketSkillTotal] = useState(0)
  const [capabilityMarketMode, setCapabilityMarketMode] = useState<CapabilityMarketMode>('agents')
  const [capabilityMarketOpen, setCapabilityMarketOpen] = useState(false)
  const [mentionSkillCandidates, setMentionSkillCandidates] = useState<UserAgentSkill[]>([])
  const [selectedMentionIndex, setSelectedMentionIndex] = useState(0)
  const [mentionSkillsLoading, setMentionSkillsLoading] = useState(false)
  const [skillsLoading, setSkillsLoading] = useState(false)
  const [skillActionId, setSkillActionId] = useState<string | null>(null)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [sessionLoading, setSessionLoading] = useState(Boolean(routeSessionId))
  const [thinking, setThinking] = useState(false)
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const autoScrollRef = useRef(true)
  const lastScrollYRef = useRef(0)
  const streamAbortRef = useRef<AbortController | null>(null)
  const streamFrameRef = useRef<number | null>(null)

  const renderMessages = useMemo(() => ({ default: renderChatMessage }), [])
  const orderedSessions = useMemo(
    () => [...sessions].sort((a, b) => sessionUpdatedAt(b) - sessionUpdatedAt(a)),
    [sessions],
  )
  const availableAgentCategories = useMemo(() => {
    const categories = agentCategories
      .map((category) => ({ id: category.id, label: category.name }))
    return [{ id: AGENT_CATEGORY_ALL, label: '全部' }, ...categories]
  }, [agentCategories])
  const currentAgent = useMemo(
    () => myAgents.find((agent) => agent.id === selectedAgentId)
      ?? agents.find((agent) => agent.id === selectedAgentId)
      ?? null,
    [agents, myAgents, selectedAgentId],
  )
  const selectedAgentDisplay = useMemo(
    () => agentDisplayFromAgent(currentAgent, selectedAgentId),
    [currentAgent, selectedAgentId],
  )
  const visibleAgents = useMemo(() => {
    const keyword = agentSearch.toLowerCase()
    return agents.filter((agent) => {
      if (agentCategory !== AGENT_CATEGORY_ALL && agent.category_id !== agentCategory) {
        return false
      }
      if (!keyword) {
        return true
      }
      return [
        agent.id,
        agent.name,
        agent.description,
        agent.category_label,
        ...agent.tags,
      ].some((value) => value.toLowerCase().includes(keyword))
    })
  }, [agentCategory, agentSearch, agents])
  const availableSkillCategories = useMemo(() => {
    const categories = marketSkillCategories
      .map((category) => ({ id: category.id, label: category.name }))
    return [{ id: SKILL_CATEGORY_ALL, label: '全部' }, ...categories]
  }, [marketSkillCategories])
  const marketSkillPageCount = Math.max(1, Math.ceil(marketSkillTotal / SKILL_PAGE_SIZE))
  const installedAgentIds = useMemo(() => new Set(myAgents.map((agent) => agent.id)), [myAgents])
  const activeSkillMentionQuery = useMemo(() => {
    const match = draft.match(SKILL_MENTION_TRIGGER_PATTERN)
    return match ? match[2].toLowerCase() : null
  }, [draft])
  const hasSelectableMentionSkill = activeSkillMentionQuery !== null && !mentionSkillsLoading && mentionSkillCandidates.length > 0

  const loadInstalledAgents = useCallback(async () => {
    setAgentsLoading(true)
    try {
      const nextAgents = await listMyAgents({
        page: 1,
        pageSize: AGENT_PAGE_SIZE,
      })
      setMyAgents(nextAgents.items)
      setSelectedAgentId((current) => current ?? nextAgents.items[0]?.id ?? DEFAULT_AGENT_ID)
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setAgentsLoading(false)
    }
  }, [message])

  const loadAgentMarket = useCallback(async () => {
    setAgentsLoading(true)
    try {
      const [nextAgents, nextCategories] = await Promise.all([
        listAgentMarket({
          category: agentCategory === AGENT_CATEGORY_ALL ? undefined : agentCategory,
          page: 1,
          pageSize: AGENT_PAGE_SIZE,
          search: agentSearch,
        }),
        listAgentMarketCategories(),
      ])
      setAgentCategories(nextCategories)
      setAgents((current) => {
        const byId = new Map<string, AgentMarketItem>()
        for (const item of [...nextAgents.items, ...current]) {
          byId.set(item.id, item)
        }
        return Array.from(byId.values())
      })
      if (agentCategory !== AGENT_CATEGORY_ALL && !nextCategories.some((category) => category.id === agentCategory)) {
        setAgentCategory(AGENT_CATEGORY_ALL)
      }
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setAgentsLoading(false)
    }
  }, [agentCategory, agentSearch, message])

  const loadInstalledSkills = useCallback(async () => {
    setSkillsLoading(true)
    try {
      const nextMySkills = await listMyAgentSkills({
        page: 1,
        pageSize: SKILL_PAGE_SIZE,
      })
      setMySkills(nextMySkills.items)
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setSkillsLoading(false)
    }
  }, [message])

  const loadSkillMarket = useCallback(async () => {
    setSkillsLoading(true)
    try {
      const [nextMarketSkills, nextCategories] = await Promise.all([
        listAgentSkillMarket({
          category: skillCategory === SKILL_CATEGORY_ALL ? undefined : skillCategory,
          page: marketSkillPage,
          pageSize: SKILL_PAGE_SIZE,
          search: skillSearch,
        }),
        listAgentSkillMarketCategories(),
      ])
      setMarketSkills(nextMarketSkills.items)
      setMarketSkillTotal(nextMarketSkills.total)
      setMarketSkillCategories(nextCategories)
      if (skillCategory !== SKILL_CATEGORY_ALL && !nextCategories.some((category) => category.id === skillCategory)) {
        setSkillCategory(SKILL_CATEGORY_ALL)
      }
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setSkillsLoading(false)
    }
  }, [marketSkillPage, message, skillCategory, skillSearch])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const nextSearch = skillSearchDraft.trim()
      setSkillSearch((current) => {
        if (current === nextSearch) {
          return current
        }
        setMarketSkillPage(1)
        return nextSearch
      })
    }, 300)
    return () => window.clearTimeout(timer)
  }, [skillSearchDraft])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const nextSearch = agentSearchDraft.trim()
      setAgentSearch((current) => (current === nextSearch ? current : nextSearch))
    }, 300)
    return () => window.clearTimeout(timer)
  }, [agentSearchDraft])

  useEffect(() => {
    if (activeSkillMentionQuery === null || !user?.id) {
      setMentionSkillCandidates([])
      setSelectedMentionIndex(0)
      return
    }

    let cancelled = false
    setMentionSkillsLoading(true)
    void listMyAgentSkills({
      page: 1,
      pageSize: MENTION_SKILL_PAGE_SIZE,
      search: activeSkillMentionQuery,
    })
      .then((page) => {
        if (!cancelled) {
          setMentionSkillCandidates(page.items)
          setSelectedMentionIndex(0)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMentionSkillCandidates([])
        }
      })
      .finally(() => {
        if (!cancelled) {
          setMentionSkillsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [activeSkillMentionQuery, user?.id])

  useEffect(() => {
    setSelectedMentionIndex((current) => {
      if (mentionSkillCandidates.length === 0) {
        return 0
      }
      return Math.min(current, mentionSkillCandidates.length - 1)
    })
  }, [mentionSkillCandidates.length])

  useEffect(() => () => {
    streamAbortRef.current?.abort()
    if (streamFrameRef.current !== null) {
      cancelAnimationFrame(streamFrameRef.current)
    }
  }, [])

  useEffect(() => {
    if (!user?.id) return
    void loadInstalledSkills()
  }, [loadInstalledSkills, user?.id])

  useEffect(() => {
    if (!user?.id) return
    void loadInstalledAgents()
  }, [loadInstalledAgents, user?.id])

  useEffect(() => {
    if (!user?.id || !capabilityMarketOpen) return
    void loadAgentMarket()
  }, [capabilityMarketOpen, loadAgentMarket, user?.id])

  useEffect(() => {
    if (!user?.id || !capabilityMarketOpen) return
    void loadSkillMarket()
  }, [capabilityMarketOpen, loadSkillMarket, user?.id])

  useEffect(() => {
    let cancelled = false
    setSessionLoading(Boolean(routeSessionId))
    setDraft('')
    setError(null)
    if (routeSessionId) {
      setActiveSessionId(routeSessionId)
      setMessages([])
    }

    const loadSessions = async () => {
      try {
        const nextSessions = await listChatSessions()
        if (cancelled) return

        setSessions(nextSessions)

        if (!routeSessionId) {
          setSessionLoading(false)
          setActiveSessionId(null)
          setMessages([])
          return
        }

        const routeSession = nextSessions.find((session) => session.id === routeSessionId)
        if (!routeSession) {
          message.warning('会话不存在或已删除')
          setSessionLoading(false)
          setActiveSessionId(null)
          setMessages([])
          navigate(CHAT_HOME_PATH, { replace: true })
          return
        }

        setActiveSessionId(routeSession.id)
        if (routeSession.agent_id) {
          setSelectedAgentId(routeSession.agent_id)
          if (routeSession.agent_name) {
            setAgents((current) => (
              current.some((agent) => agent.id === routeSession.agent_id)
                ? current
                : [
                    ...current,
                    {
                      id: routeSession.agent_id ?? '',
                      slug: routeSession.agent_id ?? '',
                      name: routeSession.agent_name ?? routeSession.agent_id ?? '智能体',
                      title: routeSession.agent_name ?? routeSession.agent_id ?? '智能体',
                      category: '',
                      category_id: '',
                      category_label: '会话智能体',
                      visibility: 'public',
                      summary: '',
                      description: '',
                      tags: [],
                      tag_ids: [],
                      enabled: true,
                      is_default: false,
                      protected: false,
                      added: false,
                      current_revision_id: routeSession.agent_revision_id,
                      current_version: null,
                    },
                  ]
            ))
          }
        }
        const records = await getChatSessionMessages(routeSession.id)
        if (cancelled) return
        setMessages(records.map((record) => createMessageFromRecord(record, agentDisplayFromSession(routeSession))))
        setSessionLoading(false)
        window.requestAnimationFrame(() => window.scrollTo({ top: 0 }))
      } catch (err) {
        if (cancelled) return
        const text = resolveErrorMessage(err)
        setError(text)
        setSessionLoading(false)
        message.error(text)
        if (routeSessionId) {
          setActiveSessionId(null)
          setMessages([])
          navigate(CHAT_HOME_PATH, { replace: true })
        }
      }
    }

    void loadSessions()
    return () => {
      cancelled = true
    }
  }, [message, navigate, routeSessionId, user?.id, user?.username])

  useEffect(() => {
    const handleWindowScroll = () => {
      const documentElement = document.documentElement
      const currentScrollY = window.scrollY
      const nearBottom = window.innerHeight + currentScrollY >= documentElement.scrollHeight - 120
      const scrollingUp = currentScrollY < lastScrollYRef.current - 8

      if (nearBottom) {
        autoScrollRef.current = true
      } else if (scrollingUp) {
        autoScrollRef.current = false
      }

      lastScrollYRef.current = currentScrollY
    }

    lastScrollYRef.current = window.scrollY
    window.addEventListener('scroll', handleWindowScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleWindowScroll)
  }, [])

  useEffect(() => {
    if (!autoScrollRef.current) return
    window.requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({
        behavior: thinking ? 'auto' : 'smooth',
        block: 'end',
      })
    })
  }, [messages, thinking])

  const hasSessionRoute = Boolean(routeSessionId)
  const hasConversation = messages.length > 0
  const isSessionContext = hasConversation || hasSessionRoute || Boolean(activeSessionId)
  const showSessionPlaceholder = hasSessionRoute && messages.length === 0 && !error
  const canSend = draft.trim().length > 0 && !thinking && !sessionLoading

  const startNewConversation = () => {
    if (thinking) return
    const defaultAgent = myAgents.find((agent) => agent.is_default) ?? agents.find((agent) => agent.is_default)
    autoScrollRef.current = true
    setActiveSessionId(null)
    setMessages([])
    setDraft('')
    setError(null)
    if (defaultAgent) {
      setSelectedAgentId(defaultAgent.id)
    }
    navigate(CHAT_HOME_PATH)
  }

  const selectSession = async (session: ChatSessionSummary) => {
    if (thinking) return
    autoScrollRef.current = true
    if (session.id !== routeSessionId) {
      navigate(chatSessionPath(session.id))
      return
    }
    setActiveSessionId(session.id)
    if (session.agent_id) {
      setSelectedAgentId(session.agent_id)
    }
    setDraft('')
    setError(null)
    try {
      const records = await getChatSessionMessages(session.id)
      setMessages(records.map((record) => createMessageFromRecord(record, agentDisplayFromSession(session))))
      window.requestAnimationFrame(() => window.scrollTo({ top: 0 }))
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    }
  }

  const confirmDeleteSession = (session: ChatSessionSummary) => {
    if (thinking) return

    modal.confirm({
      title: `删除会话「${session.title}」？`,
      content: '此操作无法撤回。会话记录会从服务端删除。',
      okText: '确认删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        try {
          await deleteChatSession(session.id)
          const remaining = sessions.filter((item) => item.id !== session.id)
          setSessions(remaining)

          if (activeSessionId === session.id) {
            autoScrollRef.current = true
            setActiveSessionId(null)
            setMessages([])
            setDraft('')
            setError(null)
            navigate(CHAT_HOME_PATH, { replace: true })
            window.requestAnimationFrame(() => window.scrollTo({ top: 0 }))
          }

          message.success('会话已删除')
        } catch (err) {
          const text = resolveErrorMessage(err)
          message.error(text)
          throw err
        }
      },
    })
  }

  const confirmRenameSession = (session: ChatSessionSummary) => {
    if (thinking) return

    let nextTitle = session.title
    modal.confirm({
      title: `重命名会话「${session.title}」`,
      content: (
        <Input
          autoFocus
          defaultValue={session.title}
          maxLength={40}
          onChange={(event) => {
            nextTitle = event.target.value
          }}
          placeholder="输入会话名称"
        />
      ),
      okText: '保存',
      cancelText: '取消',
      async onOk() {
        try {
          const title = nextTitle.trim() || '新对话'
          const renamed = await renameChatSession(session.id, title)
          setSessions((current) => current.map((item) => (
            item.id === session.id ? renamed : item
          )))
          message.success('会话已重命名')
        } catch (err) {
          const text = resolveErrorMessage(err)
          message.error(text)
          throw err
        }
      },
    })
  }

  const addSkillToAgent = async (skill: AgentSkill) => {
    setSkillActionId(skill.id)
    try {
      await addMyAgentSkill(skill.id)
      await loadInstalledSkills()
      if (capabilityMarketOpen) {
        await loadSkillMarket()
      }
      message.success('技能已添加到智能体')
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setSkillActionId(null)
    }
  }

  const removeSkillFromAgent = async (skill: AgentSkill | UserAgentSkill) => {
    setSkillActionId(skill.id)
    try {
      await removeMyAgentSkill(skill.id)
      await loadInstalledSkills()
      if (capabilityMarketOpen) {
        await loadSkillMarket()
      }
      message.success('技能已从智能体移除')
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setSkillActionId(null)
    }
  }

  const addAgentToUser = async (agent: AgentMarketItem) => {
    setAgentActionId(agent.id)
    try {
      await addMyAgent(agent.id)
      await loadInstalledAgents()
      if (capabilityMarketOpen) {
        await loadAgentMarket()
      }
      message.success('智能体已添加')
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setAgentActionId(null)
    }
  }

  const removeAgentFromUser = async (agent: AgentMarketItem | UserAgent) => {
    setAgentActionId(agent.id)
    try {
      await removeMyAgent(agent.id)
      await loadInstalledAgents()
      if (capabilityMarketOpen) {
        await loadAgentMarket()
      }
      if (!activeSessionId && selectedAgentId === agent.id) {
        setSelectedAgentId(DEFAULT_AGENT_ID)
      }
      message.success('智能体已移除')
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setAgentActionId(null)
    }
  }

  const insertSkillMention = (skill: AgentSkill | UserAgentSkill) => {
    const mention = `${skill.mention} `
    setDraft((current) => {
      const prefix = current.trimEnd()
      return prefix ? `${prefix} ${mention}` : mention
    })
    setError(null)
  }

  const selectMentionCandidate = (skill: UserAgentSkill) => {
    setDraft((current) => {
      if (!SKILL_MENTION_TRIGGER_PATTERN.test(current)) {
        const prefix = current.trimEnd()
        return prefix ? `${prefix} ${skill.mention} ` : `${skill.mention} `
      }
      return current.replace(SKILL_MENTION_TRIGGER_PATTERN, `$1${skill.mention} `)
    })
    setError(null)
  }

  const confirmSelectedMentionCandidate = () => {
    if (!hasSelectableMentionSkill) {
      return false
    }
    const skill = mentionSkillCandidates[selectedMentionIndex] ?? mentionSkillCandidates[0]
    if (!skill) {
      return false
    }
    selectMentionCandidate(skill)
    return true
  }

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (!hasSelectableMentionSkill) {
      return
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      event.stopPropagation()
      setSelectedMentionIndex((current) => (current + 1) % mentionSkillCandidates.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      event.stopPropagation()
      setSelectedMentionIndex((current) => (
        current - 1 < 0 ? mentionSkillCandidates.length - 1 : current - 1
      ))
    }
  }

  const handleComposerPressEnter = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (activeSkillMentionQuery === null) {
      return
    }
    event.preventDefault()
    event.stopPropagation()
  }

  const handleComposerSend = () => {
    if (activeSkillMentionQuery !== null) {
      confirmSelectedMentionCandidate()
      return
    }
    void sendPrompt()
  }

  const sendPrompt = async (value = draft) => {
    const prompt = value.trim()
    if (!prompt || thinking) return

    const userMessage = createMessage('user', prompt, selectedAgentDisplay)
    const assistantMessage = createMessage('assistant', '正在整理创作简报...', selectedAgentDisplay)
    const nextMessages = [...messages, userMessage, assistantMessage]
    const controller = new AbortController()
    let streamedContent = ''
    let pendingContent = ''
    let sessionIdForRefresh = activeSessionId

    const flushStreamedContent = () => {
      streamFrameRef.current = null
      if (!pendingContent) return

      streamedContent += pendingContent
      pendingContent = ''
      const nextContent = streamedContent
      setMessages((current) => current.map((item) => (
        item.id === assistantMessage.id
          ? { ...item, content: nextContent, updateAt: Date.now() }
          : item
      )))
    }

    const scheduleStreamFlush = () => {
      if (streamFrameRef.current !== null) return
      streamFrameRef.current = requestAnimationFrame(flushStreamedContent)
    }

    streamAbortRef.current = controller
    autoScrollRef.current = true
    setDraft('')
    setError(null)
    setMessages(nextMessages)
    setThinking(true)
    setStreamingMessageId(assistantMessage.id)

    try {
      await streamChatSession(
        {
          agent_id: selectedAgentId ?? undefined,
          content: prompt,
          session_id: activeSessionId ?? undefined,
        },
        {
          onSession: (session) => {
            sessionIdForRefresh = session.id
            setActiveSessionId(session.id)
            if (session.agent_id) {
              setSelectedAgentId(session.agent_id)
            }
            setSessions((current) => [
              session,
              ...current.filter((item) => item.id !== session.id),
            ])
          },
          onDelta: (content) => {
            pendingContent += content
            scheduleStreamFlush()
          },
        },
        controller.signal,
      )

      if (streamFrameRef.current !== null) {
        cancelAnimationFrame(streamFrameRef.current)
        flushStreamedContent()
      }

      if (!streamedContent.trim()) {
        setMessages((current) => current.map((item) => (
          item.id === assistantMessage.id
            ? { ...item, content: '没有收到有效回复。', updateAt: Date.now() }
            : item
        )))
      }

      if (sessionIdForRefresh) {
        const [nextSessions, records] = await Promise.all([
          listChatSessions(),
          getChatSessionMessages(sessionIdForRefresh),
        ])
        const refreshedSession = nextSessions.find((item) => item.id === sessionIdForRefresh)
        setSessions(nextSessions)
        setActiveSessionId(sessionIdForRefresh)
        if (refreshedSession?.agent_id) {
          setSelectedAgentId(refreshedSession.agent_id)
        }
        setMessages(records.map((record) => createMessageFromRecord(record, agentDisplayFromSession(refreshedSession))))
        if (sessionIdForRefresh !== routeSessionId) {
          navigate(chatSessionPath(sessionIdForRefresh), { replace: activeSessionId === null })
        }
      }
    } catch (err) {
      if (controller.signal.aborted) return
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
      if (sessionIdForRefresh) {
        try {
          const [nextSessions, records] = await Promise.all([
            listChatSessions(),
            getChatSessionMessages(sessionIdForRefresh),
          ])
          const refreshedSession = nextSessions.find((item) => item.id === sessionIdForRefresh)
          setSessions(nextSessions)
          setActiveSessionId(sessionIdForRefresh)
          if (refreshedSession?.agent_id) {
            setSelectedAgentId(refreshedSession.agent_id)
          }
          setMessages(records.map((record) => createMessageFromRecord(record, agentDisplayFromSession(refreshedSession))))
          if (sessionIdForRefresh !== routeSessionId) {
            navigate(chatSessionPath(sessionIdForRefresh), { replace: activeSessionId === null })
          }
        } catch {
          if (!streamedContent) {
            setMessages((current) => current.filter((item) => item.id !== assistantMessage.id))
          }
        }
      } else if (!streamedContent) {
        setMessages((current) => current.filter((item) => (
          item.id !== userMessage.id && item.id !== assistantMessage.id
        )))
      }
    } finally {
      if (streamFrameRef.current !== null) {
        cancelAnimationFrame(streamFrameRef.current)
        streamFrameRef.current = null
      }
      if (streamAbortRef.current === controller) {
        streamAbortRef.current = null
      }
      setThinking(false)
      setStreamingMessageId(null)
    }
  }

  const userMenu = useMemo<MenuProps['items']>(() => [
    {
      disabled: true,
      key: 'current-user',
      label: user?.username ?? '当前用户',
    },
    { type: 'divider' },
    {
      icon: <LogOut size={15} />,
      key: 'logout',
      label: '退出登录',
    },
  ], [user?.username])

  const handleUserMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key !== 'logout') return
    void logout().then(() => navigate('/login', { replace: true }))
  }

  const changeSkillCategory = (categoryId: string) => {
    setSkillCategory(categoryId)
    setMarketSkillPage(1)
  }

  const changeAgentCategory = (categoryId: string) => {
    setAgentCategory(categoryId)
  }

  const selectAgent = (agent: AgentMarketItem) => {
    if (thinking || agent.id === selectedAgentId) return
    if (!isSessionContext) {
      setSelectedAgentId(agent.id)
      setError(null)
      return
    }
    modal.confirm({
      title: `使用「${agent.name}」开启新对话？`,
      content: '已有会话会继续使用创建时的智能体。切换智能体需要从新对话开始。',
      okText: '新建对话',
      cancelText: '取消',
      onOk() {
        autoScrollRef.current = true
        setActiveSessionId(null)
        setMessages([])
        setDraft('')
        setError(null)
        setSelectedAgentId(agent.id)
        navigate(CHAT_HOME_PATH)
      },
    })
  }

  const renderAbilityAvatar = (label: string) => (
    <span className="chat-capability-avatar" aria-hidden>
      {agentInitial(label)}
    </span>
  )

  const renderInstalledAgentItem = (agent: UserAgent) => {
    const active = agent.id === selectedAgentId
    return (
      <button
        className={active ? 'chat-installed-item is-active' : 'chat-installed-item'}
        disabled={thinking}
        key={agent.id}
        onClick={() => selectAgent(agent)}
        type="button"
      >
        {renderAbilityAvatar(agent.name)}
        <span className="chat-installed-item-main">
          <strong>{agent.name}</strong>
          <small>{agent.category_label || '智能体'}</small>
        </span>
        {agent.visibility === 'admin' ? <Crown size={13} /> : active ? <Check size={13} /> : null}
      </button>
    )
  }

  const renderInstalledSkillItem = (skill: UserAgentSkill) => (
    <div className="chat-installed-item chat-installed-skill" key={skill.id}>
      <button type="button" onClick={() => insertSkillMention(skill)}>
        {renderAbilityAvatar(skill.name)}
        <span className="chat-installed-item-main">
          <strong>{skill.name}</strong>
          <small>{skill.mention}</small>
        </span>
      </button>
      <button
        aria-label={`移除 ${skill.name}`}
        className="chat-installed-remove"
        disabled={skillActionId === skill.id}
        onClick={() => void removeSkillFromAgent(skill)}
        type="button"
      >
        移除
      </button>
    </div>
  )

  const renderMarketAgentCard = (agent: AgentMarketItem) => {
    const active = agent.id === selectedAgentId
    const installed = agent.added || agent.is_default || installedAgentIds.has(agent.id)
    const actionLoading = agentActionId === agent.id
    return (
      <article className={active ? 'chat-agent-card is-active' : 'chat-agent-card'} key={agent.id}>
        <div className="chat-agent-card-head">
          {renderAbilityAvatar(agent.name)}
          <span>
            <strong>{agent.name}</strong>
            <small>v{agent.current_version ?? 1}</small>
          </span>
          {agent.visibility === 'admin' ? <Crown size={13} /> : agent.is_default ? <Check size={13} /> : null}
        </div>
        <p className="chat-agent-card-summary">{agent.description}</p>
        <div className="chat-agent-card-tags">
          <Tag color={agent.visibility === 'admin' ? 'warning' : 'info'} size="small">
            {agent.category_label || '智能体'}
          </Tag>
          {agent.tags.slice(0, 1).map((tag) => (
            <Tag key={tag} size="small">{tag}</Tag>
          ))}
        </div>
        <div className="chat-skill-actions">
          {installed ? (
            <>
              <button type="button" disabled={thinking || active} onClick={() => selectAgent(agent)}>
                {active ? '使用中' : '选用'}
              </button>
              {!agent.is_default && (
                <button type="button" disabled={actionLoading} onClick={() => void removeAgentFromUser(agent)}>
                  移除
                </button>
              )}
            </>
          ) : (
            <button type="button" disabled={actionLoading} onClick={() => void addAgentToUser(agent)}>
              添加
            </button>
          )}
        </div>
      </article>
    )
  }

  const renderSkillPagination = () => {
    if (marketSkillTotal <= SKILL_PAGE_SIZE && marketSkillPage === 1) {
      return null
    }
    return (
      <div className="chat-skill-pagination">
        <button
          aria-label="上一页"
          disabled={skillsLoading || marketSkillPage <= 1}
          onClick={() => setMarketSkillPage((current) => Math.max(1, current - 1))}
          type="button"
        >
          <ChevronLeft size={14} />
        </button>
        <span>{marketSkillPage} / {marketSkillPageCount}</span>
        <button
          aria-label="下一页"
          disabled={skillsLoading || marketSkillPage >= marketSkillPageCount}
          onClick={() => setMarketSkillPage((current) => Math.min(marketSkillPageCount, current + 1))}
          type="button"
        >
          <ChevronRight size={14} />
        </button>
      </div>
    )
  }

  const renderComposer = (floating = false) => (
    <div className={floating ? 'chat-composer chat-composer-floating' : 'chat-composer'}>
      {activeSkillMentionQuery !== null && (
        <div className="chat-skill-mention-popover" role="listbox">
          {mentionSkillsLoading ? (
            <p className="chat-skill-mention-empty">搜索中...</p>
          ) : mentionSkillCandidates.length > 0 ? (
            mentionSkillCandidates.map((skill, index) => (
              <button
                aria-selected={index === selectedMentionIndex}
                className={index === selectedMentionIndex ? 'chat-skill-mention-option is-active' : 'chat-skill-mention-option'}
                key={skill.id}
                onMouseDown={(event) => {
                  event.preventDefault()
                  selectMentionCandidate(skill)
                }}
                onMouseEnter={() => setSelectedMentionIndex(index)}
                role="option"
                type="button"
              >
                <span>
                  <strong>{skill.name}</strong>
                  <small>{skill.mention}</small>
                </span>
                <Tag color="info" size="small">{skill.category_label}</Tag>
              </button>
            ))
          ) : (
            <p className="chat-skill-mention-empty">
              {mySkills.length > 0 ? '没有匹配的技能' : '暂无已添加技能'}
            </p>
          )}
        </div>
      )}
      <ChatInputAreaInner
        className="chat-composer-input"
        onInput={setDraft}
        onKeyDown={handleComposerKeyDown}
        onPressEnter={handleComposerPressEnter}
        onSend={handleComposerSend}
        placeholder="开始一段灵感对话..."
        value={draft}
      />
      <div className="chat-composer-actions">
        <LobeButton
          aria-label="发送"
          className="chat-send-button"
          disabled={!canSend}
          icon={Send}
          loading={thinking}
          onClick={handleComposerSend}
          type="primary"
        />
      </div>
    </div>
  )

  const renderSkillCard = (skill: AgentSkill | UserAgentSkill, source: SkillCenterMode) => {
    const actionLoading = skillActionId === skill.id
    return (
      <article className="chat-skill-card" key={`${source}-${skill.id}`}>
        <div className="chat-skill-card-head">
          {renderAbilityAvatar(skill.name)}
          <div>
            <Typography.Text className="chat-skill-title">{skill.name}</Typography.Text>
            <Typography.Text className="chat-skill-mention">{skill.mention}</Typography.Text>
          </div>
          {skill.visibility === 'admin' && <Tag color="warning" size="small">管理员</Tag>}
        </div>
        <p>{skill.description}</p>
        <div className="chat-skill-tags">
          <Tag color="info" size="small">{skill.category_label}</Tag>
          {skill.tags.slice(0, 2).map((tag) => (
            <Tag key={tag} size="small">{tag}</Tag>
          ))}
        </div>
        <div className="chat-skill-actions">
          {source === 'my' ? (
            <>
              <button type="button" onClick={() => insertSkillMention(skill)}>
                @ 使用
              </button>
              <button type="button" disabled={actionLoading} onClick={() => void removeSkillFromAgent(skill)}>
                移除
              </button>
            </>
          ) : skill.added ? (
            <>
              <button type="button" onClick={() => insertSkillMention(skill)}>
                <Check size={13} />
                已添加
              </button>
              <button type="button" disabled={actionLoading} onClick={() => void removeSkillFromAgent(skill)}>
                移除
              </button>
            </>
          ) : (
            <button type="button" disabled={actionLoading} onClick={() => void addSkillToAgent(skill)}>
              添加到智能体
            </button>
          )}
        </div>
      </article>
    )
  }

  const renderInstalledSkeletons = (count = 2) => (
    <>
      {Array.from({ length: count }).map((_, index) => (
        <div className="chat-installed-item chat-installed-skeleton" key={`installed-skeleton-${index}`}>
          <span className="chat-skeleton chat-skeleton-avatar" />
          <span className="chat-installed-item-main">
            <span className="chat-skeleton chat-skeleton-line is-short" />
            <span className="chat-skeleton chat-skeleton-line is-tiny" />
          </span>
        </div>
      ))}
    </>
  )

  const renderMarketAgentSkeletons = () => (
    <>
      {Array.from({ length: 4 }).map((_, index) => (
        <article className="chat-agent-card chat-card-skeleton" key={`agent-market-skeleton-${index}`}>
          <div className="chat-agent-card-head">
            <span className="chat-skeleton chat-skeleton-avatar" />
            <span>
              <span className="chat-skeleton chat-skeleton-line is-medium" />
              <span className="chat-skeleton chat-skeleton-line is-tiny" />
            </span>
          </div>
          <div className="chat-card-skeleton-body">
            <span className="chat-skeleton chat-skeleton-line" />
            <span className="chat-skeleton chat-skeleton-line is-wide" />
          </div>
          <div className="chat-agent-card-tags">
            <span className="chat-skeleton chat-skeleton-pill" />
            <span className="chat-skeleton chat-skeleton-pill is-small" />
          </div>
          <span className="chat-skeleton chat-skeleton-button" />
        </article>
      ))}
    </>
  )

  const renderMarketSkillSkeletons = () => (
    <>
      {Array.from({ length: 4 }).map((_, index) => (
        <article className="chat-skill-card chat-card-skeleton" key={`skill-market-skeleton-${index}`}>
          <div className="chat-skill-card-head">
            <span className="chat-skeleton chat-skeleton-avatar" />
            <div>
              <span className="chat-skeleton chat-skeleton-line is-medium" />
              <span className="chat-skeleton chat-skeleton-line is-tiny" />
            </div>
          </div>
          <div className="chat-card-skeleton-body">
            <span className="chat-skeleton chat-skeleton-line" />
            <span className="chat-skeleton chat-skeleton-line is-wide" />
          </div>
          <div className="chat-skill-tags">
            <span className="chat-skeleton chat-skeleton-pill" />
            <span className="chat-skeleton chat-skeleton-pill is-small" />
          </div>
          <div className="chat-skill-actions">
            <span className="chat-skeleton chat-skeleton-button" />
            <span className="chat-skeleton chat-skeleton-button" />
          </div>
        </article>
      ))}
    </>
  )

  const renderSessionPlaceholder = () => (
    <div className="chat-message-skeleton-list" aria-hidden="true">
      <div className="chat-message-skeleton is-agent">
        <span className="chat-skeleton chat-message-skeleton-avatar" />
        <div className="chat-message-skeleton-content">
          <span className="chat-skeleton chat-skeleton-line is-name" />
          <div className="chat-message-skeleton-bubble">
            <span className="chat-skeleton chat-skeleton-line is-wide" />
            <span className="chat-skeleton chat-skeleton-line" />
            <span className="chat-skeleton chat-skeleton-line is-short" />
          </div>
        </div>
      </div>
      <div className="chat-message-skeleton is-user">
        <div className="chat-message-skeleton-content">
          <span className="chat-skeleton chat-skeleton-line is-name" />
          <div className="chat-message-skeleton-bubble">
            <span className="chat-skeleton chat-skeleton-line is-medium" />
            <span className="chat-skeleton chat-skeleton-line is-short" />
          </div>
        </div>
        <span className="chat-skeleton chat-message-skeleton-avatar" />
      </div>
      <div className="chat-message-skeleton is-agent is-compact">
        <span className="chat-skeleton chat-message-skeleton-avatar" />
        <div className="chat-message-skeleton-content">
          <span className="chat-skeleton chat-skeleton-line is-name" />
          <div className="chat-message-skeleton-bubble">
            <span className="chat-skeleton chat-skeleton-line" />
            <span className="chat-skeleton chat-skeleton-line is-wide" />
          </div>
        </div>
      </div>
    </div>
  )

  return (
    <LobeThemeProvider
      appearance="dark"
      enableCustomFonts={false}
      enableGlobalStyle={false}
      style={{ minHeight: '100vh' }}
    >
      <main className="chat-home-page">
        <header className="chat-home-nav">
          <WorkbenchHomeButton className="chat-workbench-home" />

          <BrandNavPill activeKey="agents" className="chat-home-nav-items" />

          <div className="chat-home-user">
            <Dropdown
              menu={{ items: userMenu, onClick: handleUserMenuClick }}
              placement="bottomRight"
              trigger={['click']}
            >
              <button className="chat-home-user-button" type="button">
                <UserRound size={16} />
                <Typography.Text ellipsis style={{ color: 'inherit', maxWidth: 150 }}>
                  {user?.username ?? '用户'}
                </Typography.Text>
                <Avatar size={30} style={{ background: '#2b2d31' }}>
                  {(user?.username ?? 'U').slice(0, 1).toUpperCase()}
                </Avatar>
              </button>
            </Dropdown>
          </div>
        </header>

        <div className="chat-home-body">
          <aside className="chat-session-sidebar" aria-label="聊天会话">
            <button
              className={activeSessionId ? 'chat-new-session-button' : 'chat-new-session-button is-active'}
              disabled={thinking}
              onClick={startNewConversation}
              type="button"
            >
              <Plus size={16} />
              <span>新对话</span>
            </button>

            {orderedSessions.length > 0 ? (
              <div className="chat-session-list">
                {orderedSessions.map((session) => (
                  <div
                    aria-disabled={thinking && session.id !== activeSessionId}
                    className={session.id === activeSessionId ? 'chat-session-item is-active' : 'chat-session-item'}
                    key={session.id}
                    onClick={() => void selectSession(session)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        void selectSession(session)
                      }
                    }}
                    role="button"
                    tabIndex={thinking && session.id !== activeSessionId ? -1 : 0}
                  >
                    <button
                      aria-label={`重命名会话 ${session.title}`}
                      className="chat-session-rename"
                      disabled={thinking}
                      onClick={(event) => {
                        event.stopPropagation()
                        confirmRenameSession(session)
                      }}
                      type="button"
                    >
                      <EditOutlined />
                    </button>
                    <button
                      aria-label={`删除会话 ${session.title}`}
                      className="chat-session-delete"
                      disabled={thinking}
                      onClick={(event) => {
                        event.stopPropagation()
                        confirmDeleteSession(session)
                      }}
                      type="button"
                    >
                      <DeleteOutlined />
                    </button>
                    <MessageSquareText size={15} />
                    <span>{session.title}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="chat-session-empty">暂无会话</p>
            )}

            <section className="chat-capability-panel" aria-label="我的能力">
              <div className="chat-skill-panel-header">
                <div>
                  <Typography.Text className="chat-skill-kicker">My Stack</Typography.Text>
                  <Typography.Text className="chat-skill-panel-title">我的能力</Typography.Text>
                </div>
                <button
                  aria-label="打开能力市场"
                  type="button"
                  onClick={() => setCapabilityMarketOpen(true)}
                >
                  <Store size={14} />
                </button>
              </div>

              <div className="chat-agent-current">
                <span>当前</span>
                <strong>{currentAgent?.name ?? '中影广告智能体'}</strong>
              </div>

              <div className="chat-capability-block">
                <div className="chat-capability-block-title">
                  <Bot size={13} />
                  <span>智能体</span>
                </div>
                <div className="chat-installed-list">
                  {agentsLoading && myAgents.length === 0 ? (
                    renderInstalledSkeletons(2)
                  ) : myAgents.length > 0 ? (
                    myAgents.map(renderInstalledAgentItem)
                  ) : (
                    <p className="chat-skill-empty">暂无已添加智能体</p>
                  )}
                </div>
              </div>

              <div className="chat-capability-block">
                <div className="chat-capability-block-title">
                  <Store size={13} />
                  <span>技能</span>
                </div>
                <div className="chat-installed-list">
                  {skillsLoading && mySkills.length === 0 ? (
                    renderInstalledSkeletons(2)
                  ) : mySkills.length > 0 ? (
                    mySkills.map(renderInstalledSkillItem)
                  ) : (
                    <p className="chat-skill-empty">还没有添加技能</p>
                  )}
                </div>
              </div>
            </section>
          </aside>

          <div className={isSessionContext ? 'chat-home-main has-conversation' : 'chat-home-main'}>
          {!isSessionContext && (
            <section className="chat-home-hero">
              <h1 className="chat-home-title">
                <span className="chat-home-mark" aria-hidden />
                <span>今天要做点什么?</span>
              </h1>

              {renderComposer()}

              <div className="chat-home-prompts">
                {quickPrompts.map((item) => {
                  const Icon = item.icon
                  return (
                    <button
                      className="chat-prompt-chip"
                      key={item.key}
                      type="button"
                      onClick={() => {
                        setDraft(item.prompt)
                        setError(null)
                      }}
                    >
                      <Icon size={15} />
                      <span>{item.label}</span>
                    </button>
                  )
                })}
              </div>
            </section>
          )}

          {(error || messages.length > 0 || showSessionPlaceholder) && (
            <section className="chat-message-panel" aria-label="对话">
              {error && (
                <Alert
                  message={error}
                  showIcon
                  style={{ marginBottom: messages.length > 0 ? 18 : 0 }}
                  type="error"
                />
              )}
              {messages.length > 0 && (
                <ChatList
                  className="chat-message-list"
                  data={messages}
                  loadingId={thinking ? streamingMessageId ?? undefined : undefined}
                  renderMessages={renderMessages}
                  showTitle
                  text={{
                    copy: '复制',
                    copySuccess: '已复制',
                    delete: '删除',
                    edit: '编辑',
                    regenerate: '重新生成',
                  }}
                  variant="bubble"
                />
              )}
              {showSessionPlaceholder && renderSessionPlaceholder()}
              <div ref={messagesEndRef} />
            </section>
          )}

          {!isSessionContext && (
            <section className="chat-home-section">
              <div className="chat-home-section-header">
                <h2 className="chat-home-section-title">精选推荐</h2>
                <Link className="chat-home-section-action" to="/interactive-movie">
                  查看工作空间
                </Link>
              </div>

              <div className="chat-recommend-grid">
                {recommendations.map((item) => {
                  const content = (
                    <article className={`chat-recommend-card ${item.className}`}>
                      <div className="chat-recommend-content">
                        <Tag color="info" size="small" variant="filled">{item.tag}</Tag>
                        <h3>{item.title}</h3>
                        <p>{item.description}</p>
                      </div>
                    </article>
                  )

                  return item.to ? (
                    <Link key={item.key} to={item.to}>
                      {content}
                    </Link>
                  ) : (
                    <div key={item.key}>{content}</div>
                  )
                })}
              </div>
            </section>
          )}

          {isSessionContext && (
            <div className="chat-fixed-composer-shell">
              {renderComposer(true)}
            </div>
          )}
          </div>
        </div>
      </main>
      <Modal
        className="chat-capability-modal"
        footer={null}
        onCancel={() => setCapabilityMarketOpen(false)}
        open={capabilityMarketOpen}
        title="能力市场"
        width={880}
      >
        <div className="chat-capability-modal-tabs">
          <button
            className={capabilityMarketMode === 'agents' ? 'is-active' : ''}
            type="button"
            onClick={() => setCapabilityMarketMode('agents')}
          >
            <Bot size={14} />
            <span>智能体</span>
          </button>
          <button
            className={capabilityMarketMode === 'skills' ? 'is-active' : ''}
            type="button"
            onClick={() => setCapabilityMarketMode('skills')}
          >
            <Store size={14} />
            <span>技能</span>
          </button>
        </div>

        {capabilityMarketMode === 'agents' ? (
          <section className="chat-capability-modal-section" aria-label="智能体市场">
            <label className="chat-skill-search">
              <Search size={14} />
              <input
                onChange={(event) => setAgentSearchDraft(event.target.value)}
                placeholder="搜索智能体"
                type="search"
                value={agentSearchDraft}
              />
            </label>

            {availableAgentCategories.length > 1 && (
              <div className="chat-skill-categories">
                {availableAgentCategories.map((category) => (
                  <button
                    key={category.id}
                    className={agentCategory === category.id ? 'is-active' : ''}
                    type="button"
                    onClick={() => changeAgentCategory(category.id)}
                  >
                    {category.label}
                  </button>
                ))}
              </div>
            )}
            {agentsLoading && availableAgentCategories.length <= 1 && (
              <div className="chat-skill-categories" aria-hidden="true">
                <span className="chat-skeleton chat-skeleton-pill" />
                <span className="chat-skeleton chat-skeleton-pill is-small" />
                <span className="chat-skeleton chat-skeleton-pill is-small" />
              </div>
            )}

            <div className="chat-market-grid">
              {agentsLoading && visibleAgents.length === 0 ? (
                renderMarketAgentSkeletons()
              ) : visibleAgents.length > 0 ? (
                visibleAgents.map(renderMarketAgentCard)
              ) : (
                <p className="chat-skill-empty">暂无可用智能体</p>
              )}
            </div>
          </section>
        ) : (
          <section className="chat-capability-modal-section" aria-label="技能市场">
            <label className="chat-skill-search">
              <Search size={14} />
              <input
                onChange={(event) => setSkillSearchDraft(event.target.value)}
                placeholder="搜索技能"
                type="search"
                value={skillSearchDraft}
              />
            </label>

            {availableSkillCategories.length > 1 && (
              <div className="chat-skill-categories">
                {availableSkillCategories.map((category) => (
                  <button
                    key={category.id}
                    className={skillCategory === category.id ? 'is-active' : ''}
                    type="button"
                    onClick={() => changeSkillCategory(category.id)}
                  >
                    {category.label}
                  </button>
                ))}
              </div>
            )}
            {skillsLoading && availableSkillCategories.length <= 1 && (
              <div className="chat-skill-categories" aria-hidden="true">
                <span className="chat-skeleton chat-skeleton-pill" />
                <span className="chat-skeleton chat-skeleton-pill is-small" />
                <span className="chat-skeleton chat-skeleton-pill is-small" />
              </div>
            )}

            <div className="chat-market-grid">
              {skillsLoading && marketSkills.length === 0 ? (
                renderMarketSkillSkeletons()
              ) : marketSkills.length > 0 ? (
                marketSkills.map((skill) => renderSkillCard(skill, 'market'))
              ) : (
                <p className="chat-skill-empty">暂无可用技能</p>
              )}
            </div>
            {renderSkillPagination()}
          </section>
        )}
      </Modal>
    </LobeThemeProvider>
  )
}
