import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { Alert, App, Avatar, Dropdown, Input, Typography, type MenuProps } from 'antd'
import { DeleteOutlined, EditOutlined } from '@ant-design/icons'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Film,
  Image as ImageIcon,
  LayoutGrid,
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
import { resolveErrorMessage } from '../../lib/errorMessage'
import { BRAND_LOGO_SRC, BRAND_NAME } from '../../lib/brand'
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

type SkillCenterMode = 'market' | 'my'
const SKILL_CATEGORY_ALL = '__all__'
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

function createMessage(role: ChatMessage['role'], content: string): ChatMessage {
  const now = Date.now()
  const isUser = role === 'user'
  const assistantTitle = '中影广告智能体'
  return {
    content,
    createAt: now,
    id: `${role}-${now}-${Math.random().toString(36).slice(2)}`,
    meta: {
      avatar: isUser ? '你' : <img alt={assistantTitle} className="chat-assistant-avatar" src={BRAND_LOGO_SRC} />,
      backgroundColor: isUser ? '#4f46e5' : '#111827',
      title: isUser ? '你' : assistantTitle,
    },
    role,
    updateAt: now,
  }
}

function createMessageFromRecord(record: ChatMessageRecord): ChatMessage {
  const createdAt = Date.parse(record.created_at)
  const role = record.role === 'system' ? 'assistant' : record.role
  return {
    ...createMessage(role, record.content),
    createAt: Number.isFinite(createdAt) ? createdAt : Date.now(),
    id: record.id,
    updateAt: Number.isFinite(createdAt) ? createdAt : Date.now(),
  }
}

function sessionUpdatedAt(session: ChatSessionSummary): number {
  const updatedAt = Date.parse(session.updated_at)
  return Number.isFinite(updatedAt) ? updatedAt : 0
}

function NavItem({
  active,
  children,
  icon,
  to,
}: {
  active?: boolean
  children: ReactNode
  icon: ReactNode
  to: string
}) {
  return (
    <Link className={active ? 'chat-home-nav-item is-active' : 'chat-home-nav-item'} to={to}>
      {icon}
      <span>{children}</span>
    </Link>
  )
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
  const [marketSkills, setMarketSkills] = useState<AgentSkill[]>([])
  const [mySkills, setMySkills] = useState<UserAgentSkill[]>([])
  const [marketSkillCategories, setMarketSkillCategories] = useState<AgentSkillCategory[]>([])
  const [skillCenterMode, setSkillCenterMode] = useState<SkillCenterMode>('market')
  const [skillCategory, setSkillCategory] = useState(SKILL_CATEGORY_ALL)
  const [skillSearchDraft, setSkillSearchDraft] = useState('')
  const [skillSearch, setSkillSearch] = useState('')
  const [marketSkillPage, setMarketSkillPage] = useState(1)
  const [marketSkillTotal, setMarketSkillTotal] = useState(0)
  const [mySkillPage, setMySkillPage] = useState(1)
  const [mySkillTotal, setMySkillTotal] = useState(0)
  const [mentionSkillCandidates, setMentionSkillCandidates] = useState<UserAgentSkill[]>([])
  const [selectedMentionIndex, setSelectedMentionIndex] = useState(0)
  const [mentionSkillsLoading, setMentionSkillsLoading] = useState(false)
  const [skillsLoading, setSkillsLoading] = useState(false)
  const [skillActionId, setSkillActionId] = useState<string | null>(null)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
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
  const availableSkillCategories = useMemo(() => {
    const categories = marketSkillCategories
      .map((category) => ({ id: category.id, label: category.name }))
    return [{ id: SKILL_CATEGORY_ALL, label: '全部' }, ...categories]
  }, [marketSkillCategories])
  const marketSkillPageCount = Math.max(1, Math.ceil(marketSkillTotal / SKILL_PAGE_SIZE))
  const mySkillPageCount = Math.max(1, Math.ceil(mySkillTotal / SKILL_PAGE_SIZE))
  const activeSkillMentionQuery = useMemo(() => {
    const match = draft.match(SKILL_MENTION_TRIGGER_PATTERN)
    return match ? match[2].toLowerCase() : null
  }, [draft])
  const hasSelectableMentionSkill = activeSkillMentionQuery !== null && !mentionSkillsLoading && mentionSkillCandidates.length > 0

  const loadSkills = useCallback(async () => {
    setSkillsLoading(true)
    try {
      const [nextMarketSkills, nextMySkills, nextCategories] = await Promise.all([
        listAgentSkillMarket({
          category: skillCategory === SKILL_CATEGORY_ALL ? undefined : skillCategory,
          page: marketSkillPage,
          pageSize: SKILL_PAGE_SIZE,
          search: skillSearch,
        }),
        listMyAgentSkills({
          page: mySkillPage,
          pageSize: SKILL_PAGE_SIZE,
          search: skillSearch,
        }),
        listAgentSkillMarketCategories(),
      ])
      setMarketSkills(nextMarketSkills.items)
      setMarketSkillTotal(nextMarketSkills.total)
      setMySkills(nextMySkills.items)
      setMySkillTotal(nextMySkills.total)
      setMarketSkillCategories(nextCategories)
      if (skillCategory !== SKILL_CATEGORY_ALL && !nextCategories.some((category) => category.id === skillCategory)) {
        setSkillCategory(SKILL_CATEGORY_ALL)
      }
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setSkillsLoading(false)
    }
  }, [marketSkillPage, message, mySkillPage, skillCategory, skillSearch])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const nextSearch = skillSearchDraft.trim()
      setSkillSearch((current) => {
        if (current === nextSearch) {
          return current
        }
        setMarketSkillPage(1)
        setMySkillPage(1)
        return nextSearch
      })
    }, 300)
    return () => window.clearTimeout(timer)
  }, [skillSearchDraft])

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
    void loadSkills()
  }, [loadSkills, user?.id])

  useEffect(() => {
    let cancelled = false

    const loadSessions = async () => {
      try {
        const nextSessions = await listChatSessions()
        if (cancelled) return

        setSessions(nextSessions)
        setDraft('')
        setError(null)

        if (!routeSessionId) {
          setActiveSessionId(null)
          setMessages([])
          return
        }

        const routeSession = nextSessions.find((session) => session.id === routeSessionId)
        if (!routeSession) {
          setActiveSessionId(null)
          setMessages([])
          navigate(CHAT_HOME_PATH, { replace: true })
          return
        }

        setActiveSessionId(routeSession.id)
        const records = await getChatSessionMessages(routeSession.id)
        if (cancelled) return
        setMessages(records.map(createMessageFromRecord))
        window.requestAnimationFrame(() => window.scrollTo({ top: 0 }))
      } catch (err) {
        if (cancelled) return
        const text = resolveErrorMessage(err)
        setError(text)
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

  const canSend = draft.trim().length > 0 && !thinking
  const hasConversation = messages.length > 0

  const startNewConversation = () => {
    if (thinking) return
    autoScrollRef.current = true
    setActiveSessionId(null)
    setMessages([])
    setDraft('')
    setError(null)
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
    setDraft('')
    setError(null)
    try {
      const records = await getChatSessionMessages(session.id)
      setMessages(records.map(createMessageFromRecord))
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
      await loadSkills()
      message.success('Skill 已添加到智能体')
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
      await loadSkills()
      message.success('Skill 已从智能体移除')
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setSkillActionId(null)
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

    const userMessage = createMessage('user', prompt)
    const assistantMessage = createMessage('assistant', '正在整理创作简报...')
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
          content: prompt,
          session_id: activeSessionId ?? undefined,
        },
        {
          onSession: (session) => {
            sessionIdForRefresh = session.id
            setActiveSessionId(session.id)
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
        setSessions(nextSessions)
        setActiveSessionId(sessionIdForRefresh)
        setMessages(records.map(createMessageFromRecord))
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
          setSessions(nextSessions)
          setActiveSessionId(sessionIdForRefresh)
          setMessages(records.map(createMessageFromRecord))
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

  const renderSkillPagination = (mode: SkillCenterMode) => {
    const isMarket = mode === 'market'
    const page = isMarket ? marketSkillPage : mySkillPage
    const pageCount = isMarket ? marketSkillPageCount : mySkillPageCount
    const total = isMarket ? marketSkillTotal : mySkillTotal
    const setPage = isMarket ? setMarketSkillPage : setMySkillPage
    if (total <= SKILL_PAGE_SIZE && page === 1) {
      return null
    }
    return (
      <div className="chat-skill-pagination">
        <button
          aria-label="上一页"
          disabled={skillsLoading || page <= 1}
          onClick={() => setPage((current) => Math.max(1, current - 1))}
          type="button"
        >
          <ChevronLeft size={14} />
        </button>
        <span>{page} / {pageCount}</span>
        <button
          aria-label="下一页"
          disabled={skillsLoading || page >= pageCount}
          onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
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
              {mySkills.length > 0 ? '没有匹配的 Skill' : '暂无已添加 Skill'}
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

  return (
    <LobeThemeProvider
      appearance="dark"
      enableCustomFonts={false}
      enableGlobalStyle={false}
      style={{ minHeight: '100vh' }}
    >
      <main className="chat-home-page">
        <header className="chat-home-nav">
          <Link className="chat-home-brand" to="/" aria-label={`${BRAND_NAME} 首页`}>
            <img src={BRAND_LOGO_SRC} alt={`${BRAND_NAME} Logo`} />
            <span>{BRAND_NAME}</span>
          </Link>

          <nav className="chat-home-nav-items" aria-label="主导航">
            <NavItem active icon={<MessageSquareText size={17} />} to="/agents">
              智能体
            </NavItem>
            <NavItem icon={<LayoutGrid size={17} />} to="/interactive-movie">
              工作空间
            </NavItem>
          </nav>

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

            <section className="chat-skill-panel" aria-label="技能中心">
              <div className="chat-skill-panel-header">
                <div>
                  <Typography.Text className="chat-skill-kicker">Skill Center</Typography.Text>
                  <Typography.Text className="chat-skill-panel-title">技能中心</Typography.Text>
                </div>
                <button type="button" onClick={() => void loadSkills()} disabled={skillsLoading}>
                  <Store size={14} />
                </button>
              </div>

              <div className="chat-skill-tabs">
                <button
                  className={skillCenterMode === 'market' ? 'is-active' : ''}
                  type="button"
                  onClick={() => setSkillCenterMode('market')}
                >
                  全部
                </button>
                <button
                  className={skillCenterMode === 'my' ? 'is-active' : ''}
                  type="button"
                  onClick={() => setSkillCenterMode('my')}
                >
                  我的
                </button>
              </div>

              <label className="chat-skill-search">
                <Search size={14} />
                <input
                  onChange={(event) => setSkillSearchDraft(event.target.value)}
                  placeholder="搜索 Skill"
                  type="search"
                  value={skillSearchDraft}
                />
              </label>

              {skillCenterMode === 'market' && availableSkillCategories.length > 1 && (
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

              <div className="chat-skill-list">
                {skillsLoading ? (
                  <p className="chat-skill-empty">加载中...</p>
                ) : skillCenterMode === 'market' ? (
                  marketSkills.length > 0
                    ? marketSkills.map((skill) => renderSkillCard(skill, 'market'))
                    : <p className="chat-skill-empty">暂无可用 Skill</p>
                ) : mySkills.length > 0 ? (
                  mySkills.map((skill) => renderSkillCard(skill, 'my'))
                ) : (
                  <p className="chat-skill-empty">还没有添加 Skill</p>
                )}
              </div>
              {skillCenterMode === 'market' ? renderSkillPagination('market') : renderSkillPagination('my')}
            </section>
          </aside>

          <div className={hasConversation ? 'chat-home-main has-conversation' : 'chat-home-main'}>
          {!hasConversation && (
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

          {(error || messages.length > 0) && (
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
              <div ref={messagesEndRef} />
            </section>
          )}

          {!hasConversation && (
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

          {hasConversation && (
            <div className="chat-fixed-composer-shell">
              {renderComposer(true)}
            </div>
          )}
          </div>
        </div>
      </main>
    </LobeThemeProvider>
  )
}
