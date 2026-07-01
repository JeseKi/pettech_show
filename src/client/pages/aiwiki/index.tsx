import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  Alert,
  App,
  Button,
  Empty,
  Flex,
  Form,
  Input,
  List,
  Modal,
  Pagination,
  Progress,
  Segmented,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  CloudUploadOutlined,
  DeleteOutlined,
  DoubleLeftOutlined,
  DoubleRightOutlined,
  EditOutlined,
  EyeOutlined,
  FileMarkdownOutlined,
  FilePdfOutlined,
  FileTextOutlined,
  PictureOutlined,
  PlusOutlined,
  ReloadOutlined,
  TableOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons'
import { useLocation, useSearchParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import * as XLSX from 'xlsx'
import {
  createAiwikiJob,
  deleteAiwikiJob,
  getAiwikiFile,
  getAiwikiJob,
  getAiwikiResult,
  listAiwikiJobs,
  updateAiwikiJob,
  type AiwikiFilePreview,
  type AiwikiJob,
  type AiwikiJobStatus,
  type AiwikiJobSummary,
  type AiwikiPdfPreview,
  type AiwikiResult,
  type AiwikiSpreadsheetPreview,
  type AiwikiTextPreview,
  type AiwikiUploadedFile,
} from '../../lib/aiwiki'
import {
  type AiwikiModeId,
  type DailyWriterModeId,
  type SeedMatrixModeId,
} from '../../lib/workflowModes'
import { listSeedMatrixJobs } from '../../lib/seedMatrix'
import { listDailyWriterJobs } from '../../lib/dailyWriter'
import { listSocialCardJobs } from '../../lib/socialCards'
import { resolveErrorMessage } from '../../lib/errorMessage'
import KeywordModal from './KeywordModal'
import ResultView from './ResultView'
import { ACTIVE_STATUSES, entryTypeLabel, formatDateTime, progressEventColor, statusMeta } from './helpers'
import SeedMatrixPage from '../seedMatrix'
import DailyWriterPage from '../dailyWriter'
import SocialCardsPage from '../socialCards'
import SocialCardVideosPage from '../socialCardVideos'
import DistributionStagePage from '../distribution'
import WorkbenchHomeButton from '../../components/brand/WorkbenchHomeButton'
import './AiwikiWorkbench.css'

type FileCategory = 'document' | 'spreadsheet'
type TaskFilter = 'all' | 'active' | 'completed' | 'failed'
type WorkbenchStage = 'assets' | 'strategy' | 'production' | 'social' | 'video' | 'distribution'
type DisplayFile = AiwikiUploadedFile & {
  id: string
  job_id?: string
  job_status?: AiwikiJob['status']
  file_index?: number
  isLocal?: boolean
  localFile?: File
  localObjectUrl?: string
  uploadState?: 'preview' | 'uploading' | 'failed'
  uploadProgress?: number
  created_at?: string
}
type DisplayTask = {
  id: string
  title: string
  description: string | null
  status: AiwikiJobStatus | 'draft'
  created_at?: string
  files: DisplayFile[]
  isDraft?: boolean
  summary?: AiwikiJobSummary
}
type WorkflowReadiness = {
  completedSeedMatrices: number
  completedDailyWriters: number
  completedSocialCards: number
}
type StagePrerequisite = {
  type: 'info' | 'warning'
  message: string
  actionText: string
  targetStage: WorkbenchStage
}

const ACCEPTED_TYPES = '.md,.markdown,.txt,.xlsx,.csv,.pdf'
const CREATE_TASK_ID = '__create_task__'
const TASK_PAGE_SIZE = 5
const ACCEPTED_TYPE_HINT = '文档: .md、.markdown、.txt；表格: .xlsx、.csv；PDF: .pdf'
const STRATEGY_MODE_IDS: SeedMatrixModeId[] = ['standard', 'batch', 'high-frequency', 'hook-driven']
const WRITER_MODE_IDS: DailyWriterModeId[] = ['single', 'batch', 'five-pack']

function isWorkbenchStage(value: string | null): value is WorkbenchStage {
  return value === 'assets'
    || value === 'strategy'
    || value === 'production'
    || value === 'social'
    || value === 'video'
    || value === 'distribution'
}

function isStrategyMode(value: string | null): value is SeedMatrixModeId {
  return STRATEGY_MODE_IDS.includes(value as SeedMatrixModeId)
}

function isWriterMode(value: string | null): value is DailyWriterModeId {
  return WRITER_MODE_IDS.includes(value as DailyWriterModeId)
}

export default function AiwikiPage({ mode = 'full' }: { mode?: AiwikiModeId }) {
  const { message, modal } = App.useApp()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const rawStage = searchParams.get('stage')
  const activeStage: WorkbenchStage = isWorkbenchStage(rawStage) ? rawStage : 'assets'
  const isContentGrowthWorkbench = location.pathname === '/content-growth'
  const strategyMode: SeedMatrixModeId = isStrategyMode(searchParams.get('strategyMode'))
    ? searchParams.get('strategyMode') as SeedMatrixModeId
    : 'standard'
  const writerMode: DailyWriterModeId = isWriterMode(searchParams.get('writerMode'))
    ? searchParams.get('writerMode') as DailyWriterModeId
    : 'single'
  const localFilesRef = useRef<DisplayFile[]>([])
  const [editForm] = Form.useForm<{ title?: string; description?: string }>()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [history, setHistory] = useState<AiwikiJobSummary[]>([])
  const [historyPage, setHistoryPage] = useState(1)
  const [historyTotal, setHistoryTotal] = useState(0)
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [isCreatingTask, setIsCreatingTask] = useState(false)
  const [job, setJob] = useState<AiwikiJob | null>(null)
  const [result, setResult] = useState<AiwikiResult | null>(null)
  const [localFiles, setLocalFiles] = useState<DisplayFile[]>([])
  const [previewFile, setPreviewFile] = useState<DisplayFile | null>(null)
  const [editingJob, setEditingJob] = useState<AiwikiJob | AiwikiJobSummary | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [savingMetadata, setSavingMetadata] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [taskFilter, setTaskFilter] = useState<TaskFilter>('all')
  const [search, setSearch] = useState('')
  const [selectedTerms, setSelectedTerms] = useState<string[]>([])
  const [entryFilter, setEntryFilter] = useState<string>('全部')
  const [activeEntrySlug, setActiveEntrySlug] = useState<string | null>(null)
  const [keywordModalOpen, setKeywordModalOpen] = useState(false)
  const [keywordSearch, setKeywordSearch] = useState('')
  const [workflowReadiness, setWorkflowReadiness] = useState<WorkflowReadiness>({
    completedSeedMatrices: 0,
    completedDailyWriters: 0,
    completedSocialCards: 0,
  })

  const meta = statusMeta(job?.status)
  const workspaceSubtitle = mode === 'full'
    ? '内容资产生成 / 任务管理 / 文件预览'
    : '内容资产生成 / 任务管理'

  const loadHistory = useCallback(async (page = historyPage) => {
    setHistoryLoading(true)
    try {
      const list = await listAiwikiJobs({ limit: TASK_PAGE_SIZE, offset: (page - 1) * TASK_PAGE_SIZE })
      setHistory(list.items)
      setHistoryTotal(list.total)
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setHistoryLoading(false)
    }
  }, [historyPage, message])

  const loadWorkflowReadiness = useCallback(async () => {
    if (!isContentGrowthWorkbench) return
    try {
      const [seedMatrices, dailyWriters, socialCards] = await Promise.all([
        listSeedMatrixJobs({ limit: TASK_PAGE_SIZE, offset: 0 }),
        listDailyWriterJobs({ limit: TASK_PAGE_SIZE, offset: 0 }),
        listSocialCardJobs({ limit: TASK_PAGE_SIZE, offset: 0 }),
      ])
      setWorkflowReadiness({
        completedSeedMatrices: seedMatrices.items.filter((item) => item.status === 'completed').length,
        completedDailyWriters: dailyWriters.items.filter((item) => item.status === 'completed' || item.status === 'partial_failed').length,
        completedSocialCards: socialCards.items.filter((item) => item.status === 'completed').length,
      })
    } catch (err) {
      message.error(resolveErrorMessage(err))
    }
  }, [isContentGrowthWorkbench, message])

  const loadJob = useCallback(async (jobId: string, silent = false) => {
    try {
      const latest = await getAiwikiJob(jobId)
      setIsCreatingTask(false)
      setActiveTaskId(jobId)
      setJob(latest)
      setResult(latest.status === 'completed' ? await getAiwikiResult(jobId) : null)
      setHistory((items) => upsertHistory(items, latest))
    } catch (err) {
      if (!silent) message.error(resolveErrorMessage(err))
    }
  }, [message])

  useEffect(() => {
    void loadHistory()
  }, [loadHistory])

  useEffect(() => {
    void loadWorkflowReadiness()
  }, [loadWorkflowReadiness])

  useEffect(() => {
    localFilesRef.current = localFiles
  }, [localFiles])

  useEffect(() => () => revokeLocalUrls(localFilesRef.current), [])

  useEffect(() => {
    if (!job?.id || !ACTIVE_STATUSES.has(job.status)) return
    const timer = window.setInterval(() => {
      void loadJob(job.id, true)
      void loadHistory()
    }, 2200)
    return () => window.clearInterval(timer)
  }, [job?.id, job?.status, loadHistory, loadJob])

  const draftTask = useMemo<DisplayTask>(() => ({
    id: CREATE_TASK_ID,
    title: localFiles.length ? `创建新任务（${localFiles.length} 个文件）` : '创建新任务',
    description: '文件尚未提交生成。',
    status: 'draft',
    files: localFiles,
    isDraft: true,
  }), [localFiles])

  const activeJob = !isCreatingTask && job?.id === activeTaskId ? job : null
  const activeFiles = useMemo<DisplayFile[]>(() => {
    if (isCreatingTask) return localFiles
    const source = activeJob ?? history.find((item) => item.id === activeTaskId)
    if (!source) return []
    return source.files.map((file, fileIndex) => toDisplayFile(file, source, fileIndex))
  }, [activeJob, activeTaskId, history, isCreatingTask, localFiles])

  const taskItems = useMemo<DisplayTask[]>(() => {
    return history.map((item) => ({
      id: item.id,
      title: item.title,
      description: item.description,
      status: item.status,
      created_at: item.created_at,
      files: item.files.map((file, fileIndex) => toDisplayFile(file, item, fileIndex)),
      summary: item,
    }))
  }, [history])

  const displayTasks = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()
    return taskItems.filter((task) => {
      const statusMatch = taskFilter === 'all'
        || (taskFilter === 'active' && (task.status === 'queued' || task.status === 'running'))
        || task.status === taskFilter
      const searchText = [
        task.title,
        task.description ?? '',
        task.id,
        ...task.files.map((file) => file.filename),
      ].join(' ').toLowerCase()
      return statusMatch && (!normalizedSearch || searchText.includes(normalizedSearch))
    })
  }, [search, taskFilter, taskItems])

  const activeTask = useMemo(() => (
    isCreatingTask ? draftTask : taskItems.find((item) => item.id === activeTaskId) ?? null
  ), [activeTaskId, draftTask, isCreatingTask, taskItems])

  const workbenchClassName = [
    'aiwiki-workbench',
    sidebarCollapsed ? 'is-sidebar-collapsed' : '',
    isContentGrowthWorkbench || activeStage !== 'assets' ? 'is-growth-workbench' : '',
  ].filter(Boolean).join(' ')
  const stageTitle = {
    assets: activeTask?.title ?? '内容资产库',
    strategy: '选题生成',
    production: '稿件生产',
    social: '生成图文',
    video: '轮播视频',
    distribution: '内容分发',
  }[activeStage]
  const stageSubtitle = {
    assets: workspaceSubtitle,
    strategy: '选择知识库生成选题策略',
    production: '选择选题策略和种子生产稿件',
    social: '选择已完成稿件生成图文卡',
    video: '选择已完成图文卡生成轮播视频',
    distribution: '集中上传稿件和图文到分发平台',
  }[activeStage]

  const updateWorkbenchParams = (updates: Partial<Record<'stage' | 'strategyMode' | 'writerMode', string>>) => {
    const next = new URLSearchParams(searchParams)
    Object.entries(updates).forEach(([key, value]) => {
      if (value) next.set(key, value)
    })
    setSearchParams(next)
  }

  useEffect(() => {
    if (isCreatingTask) return
    if (activeTaskId && taskItems.some((item) => item.id === activeTaskId)) return
    const nextTask = taskItems[0]
    if (!nextTask) {
      setActiveTaskId(null)
      setJob(null)
      setResult(null)
      return
    }
    void loadJob(nextTask.id, true)
  }, [activeTaskId, isCreatingTask, loadJob, taskItems])

  const stats = useMemo(() => {
    const serverTasks = history.length
    const activeCount = history.filter((item) => item.status === 'queued' || item.status === 'running').length
    const completedCount = history.filter((item) => item.status === 'completed').length
    const fileCount = history.reduce((total, item) => total + item.files.length, 0)
    return {
      serverTasks,
      activeCount,
      completedCount,
      fileCount,
    }
  }, [history])

  const stagePrerequisite = useMemo<StagePrerequisite | null>(() => {
    if (!isContentGrowthWorkbench) return null
    if (activeStage === 'strategy') {
      if (stats.completedCount > 0) {
        return {
          type: 'info',
          message: `已找到 ${stats.completedCount} 个已完成知识库，可以选择其中一个生成选题矩阵。`,
          actionText: '查看知识库',
          targetStage: 'assets',
        }
      }
      return {
        type: 'warning',
        message: '生成选题矩阵前，至少需要 1 个已完成知识库。',
        actionText: '去创建知识库',
        targetStage: 'assets',
      }
    }
    if (activeStage === 'production') {
      if (workflowReadiness.completedSeedMatrices > 0) {
        return {
          type: 'info',
          message: `已找到 ${workflowReadiness.completedSeedMatrices} 个已完成选题矩阵，可以选择种子生产稿件。`,
          actionText: '查看选题矩阵',
          targetStage: 'strategy',
        }
      }
      return {
        type: 'warning',
        message: '生产稿件前，至少需要 1 个已完成选题矩阵。',
        actionText: '去生成选题矩阵',
        targetStage: 'strategy',
      }
    }
    if (activeStage === 'social') {
      if (workflowReadiness.completedDailyWriters > 0) {
        return {
          type: 'info',
          message: `已找到 ${workflowReadiness.completedDailyWriters} 个已完成稿件，可以继续生成小红书图文卡。`,
          actionText: '查看稿件',
          targetStage: 'production',
        }
      }
      return {
        type: 'warning',
        message: '生成图文前，至少需要 1 个已完成稿件。',
        actionText: '去生产稿件',
        targetStage: 'production',
      }
    }
    if (activeStage === 'video') {
      if (workflowReadiness.completedSocialCards > 0) {
        return {
          type: 'info',
          message: `已找到 ${workflowReadiness.completedSocialCards} 个已完成图文任务，可以继续生成轮播视频。`,
          actionText: '查看图文',
          targetStage: 'social',
        }
      }
      return {
        type: 'warning',
        message: '生成轮播视频前，至少需要 1 个已完成图文任务。',
        actionText: '去生成图文',
        targetStage: 'social',
      }
    }
    if (activeStage === 'distribution') {
      const sourceCount = workflowReadiness.completedDailyWriters + workflowReadiness.completedSocialCards
      if (sourceCount > 0) {
        return {
          type: 'info',
          message: `已找到 ${workflowReadiness.completedDailyWriters} 个稿件、${workflowReadiness.completedSocialCards} 个图文任务，可集中上传到分发平台。`,
          actionText: workflowReadiness.completedSocialCards > 0 ? '查看图文' : '查看稿件',
          targetStage: workflowReadiness.completedSocialCards > 0 ? 'social' : 'production',
        }
      }
      return {
        type: 'warning',
        message: '分发前至少需要 1 个已完成稿件或图文任务。',
        actionText: '去生产稿件',
        targetStage: 'production',
      }
    }
    return null
  }, [
    activeStage,
    isContentGrowthWorkbench,
    stats.completedCount,
    workflowReadiness.completedDailyWriters,
    workflowReadiness.completedSeedMatrices,
    workflowReadiness.completedSocialCards,
  ])

  const entriesBySlug = useMemo(() => (
    new Map((result?.wiki_entries ?? []).map((entry) => [entry.slug, entry]))
  ), [result?.wiki_entries])

  const activeEntry = useMemo(() => (
    activeEntrySlug ? entriesBySlug.get(activeEntrySlug) ?? null : null
  ), [activeEntrySlug, entriesBySlug])

  const availableTerms = useMemo(() => result?.highlight_terms ?? [], [result])

  const filteredEntries = useMemo(() => {
    if (!result) return []
    return entryFilter === '全部'
      ? result.wiki_entries
      : result.wiki_entries.filter((entry) => entryTypeLabel(entry.type) === entryFilter)
  }, [entryFilter, result])

  useEffect(() => {
    setSelectedTerms([])
  }, [availableTerms])

  const handleFilesSelected = async (files: File[]) => {
    if (!files.length) return
    try {
      const startIndex = localFilesRef.current.length
      const previews = await Promise.all(files.map((file, index) => buildLocalFile(file, startIndex + index)))
      setLocalFiles((items) => [...items, ...previews])
      setIsCreatingTask(true)
      setActiveTaskId(null)
      setJob(null)
      setResult(null)
    } catch (err) {
      message.error(resolveErrorMessage(err))
    }
  }

  const startNewTask = () => {
    setIsCreatingTask(true)
    setActiveTaskId(null)
    setJob(null)
    setResult(null)
    setActiveEntrySlug(null)
  }

  const submitFiles = async () => {
    const files = localFiles.map((file) => file.localFile).filter(Boolean) as File[]
    if (!files.length) {
      message.warning('请先选择文档或表格文件')
      return
    }
    setSubmitting(true)
    setUploadProgress(1)
    setLocalFiles((items) => items.map((item) => ({ ...item, uploadState: 'uploading', uploadProgress: 1 })))
    try {
      const created = await createAiwikiJob(
        files,
        { generate_search_assets: true },
        (percent) => {
          setUploadProgress(percent)
          setLocalFiles((items) => items.map((item) => ({ ...item, uploadState: 'uploading', uploadProgress: percent })))
        },
      )
      revokeLocalUrls(localFiles)
      setLocalFiles([])
      setIsCreatingTask(false)
      setActiveTaskId(created.id)
      setJob(created)
      setResult(null)
      setPreviewFile(null)
      message.success('内容资产任务已创建')
      await loadHistory()
      void loadJob(created.id, true)
    } catch (err) {
      setLocalFiles((items) => items.map((item) => ({ ...item, uploadState: 'failed' })))
      message.error(resolveErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const selectTask = async (task: DisplayTask) => {
    setActiveEntrySlug(null)
    setIsCreatingTask(false)
    await loadJob(task.id)
  }

  const removeLocalFile = (file: DisplayFile) => {
    revokeLocalUrls([file])
    setLocalFiles((items) => items.filter((item) => item.id !== file.id))
    if (previewFile?.id === file.id) setPreviewFile(null)
  }

  const handleDeleteJob = async (targetJob: AiwikiJobSummary | AiwikiJob) => {
    try {
      await deleteAiwikiJob(targetJob.id)
      message.success('内容资产任务已删除')
      if (activeTaskId === targetJob.id) {
        setActiveTaskId(null)
        setJob(null)
        setResult(null)
      }
      await loadHistory()
    } catch (err) {
      message.error(resolveErrorMessage(err))
    }
  }

  const confirmDeleteJob = (targetJob: AiwikiJobSummary | AiwikiJob) => {
    modal.confirm({
      title: `删除任务「${targetJob.title}」？`,
      content: '此操作无法撤回。任务记录和生成文件会从服务端删除，审计日志会保留。',
      okText: '确认删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        await handleDeleteJob(targetJob)
      },
    })
  }

  const openEditModal = (target: AiwikiJob | AiwikiJobSummary) => {
    setEditingJob(target)
    editForm.setFieldsValue({
      title: target.title,
      description: target.description ?? '',
    })
  }

  const saveMetadata = async () => {
    if (!editingJob) return
    const values = await editForm.validateFields()
    setSavingMetadata(true)
    try {
      const updated = await updateAiwikiJob(editingJob.id, {
        title: values.title?.trim() || null,
        description: values.description?.trim() || null,
      })
      setHistory((items) => upsertHistory(items, updated))
      if (job?.id === updated.id) setJob(updated)
      message.success('任务信息已更新')
      setEditingJob(null)
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setSavingMetadata(false)
    }
  }

  return (
    <div className={workbenchClassName}>
      <aside className="aiwiki-sidebar">
        <div className="aiwiki-sidebar-chrome">
          <WorkbenchHomeButton className="aiwiki-workbench-home" />
        </div>
        <button type="button" className="aiwiki-collapse" onClick={() => setSidebarCollapsed((value) => !value)}>
          {sidebarCollapsed ? <DoubleRightOutlined /> : <DoubleLeftOutlined />}
        </button>
        {activeStage === 'assets' && !isContentGrowthWorkbench ? (
          <>
            <div className="aiwiki-brand">
              <span className="aiwiki-logo"><FileTextOutlined /></span>
              <div className="aiwiki-brand-text">
                <Typography.Text className="aiwiki-kicker">Content Assets</Typography.Text>
                <Typography.Title level={5} className="aiwiki-sidebar-title">内容资产任务</Typography.Title>
              </div>
            </div>
            <Button block type="primary" icon={<PlusOutlined />} disabled={submitting} onClick={startNewTask} className="aiwiki-upload-button">
              创建新任务
            </Button>
            <div className="aiwiki-filter-stack">
              <Input.Search value={search} allowClear placeholder="搜索任务或文件" onChange={(event) => setSearch(event.target.value)} />
              <Segmented
                block
                value={taskFilter}
                onChange={(value) => setTaskFilter(value as TaskFilter)}
                options={[
                  { label: '全部', value: 'all' },
                  { label: '进行中', value: 'active' },
                  { label: '完成', value: 'completed' },
                  { label: '失败', value: 'failed' },
                ]}
              />
            </div>
            <div className="aiwiki-task-list">
              <List
                size="small"
                loading={historyLoading}
                dataSource={displayTasks}
                locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无任务" /> }}
                renderItem={(task) => (
                  <List.Item>
                    <div
                      className={task.id === activeTaskId ? 'aiwiki-task-item is-active' : 'aiwiki-task-item'}
                      onClick={() => void selectTask(task)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          void selectTask(task)
                        }
                      }}
                      role="button"
                      tabIndex={0}
                    >
                      <span className="aiwiki-file-icon"><FileTextOutlined /></span>
                      <span className="aiwiki-file-copy">
                        <span className="aiwiki-file-name">{task.title}</span>
                        <span className="aiwiki-file-meta">
                          {task.files.length} 个文件 · {taskStatusLabel(task.status)}
                        </span>
                      </span>
                      {task.summary ? (
                        <span className="aiwiki-task-list-actions" onKeyDown={(event) => event.stopPropagation()}>
                          <Tooltip title="编辑">
                            <button
                              aria-label={`编辑任务 ${task.summary.title}`}
                              className="aiwiki-task-action-button"
                              onClick={(event) => {
                                event.stopPropagation()
                                openEditModal(task.summary!)
                              }}
                              type="button"
                            >
                              <EditOutlined />
                            </button>
                          </Tooltip>
                          <Tooltip title="删除">
                            <button
                              aria-label={`删除任务 ${task.summary.title}`}
                              className="aiwiki-task-action-button is-danger"
                              disabled={task.summary.status === 'queued' || task.summary.status === 'running'}
                              onClick={(event) => {
                                event.stopPropagation()
                                confirmDeleteJob(task.summary!)
                              }}
                              type="button"
                            >
                              <DeleteOutlined />
                            </button>
                          </Tooltip>
                        </span>
                      ) : null}
                    </div>
                  </List.Item>
                )}
              />
            </div>
          </>
        ) : (
          <div className="aiwiki-stage-rail">
            <div className="aiwiki-stage-rail-brand">
              <span className="aiwiki-logo"><FileTextOutlined /></span>
              <span className="aiwiki-stage-rail-title">内容增长</span>
            </div>
            <nav className="aiwiki-stage-nav" aria-label="内容增长阶段">
              <Tooltip title="知识库生成" placement="right">
                <button
                  type="button"
                  className={activeStage === 'assets' ? 'aiwiki-stage-nav-button is-active' : 'aiwiki-stage-nav-button'}
                  onClick={() => updateWorkbenchParams({ stage: 'assets' })}
                  aria-label="知识库生成"
                >
                  <FileTextOutlined />
                  <span>知识库</span>
                </button>
              </Tooltip>
              <Tooltip title="选题生成" placement="right">
                <button
                  type="button"
                  className={activeStage === 'strategy' ? 'aiwiki-stage-nav-button is-active' : 'aiwiki-stage-nav-button'}
                  onClick={() => updateWorkbenchParams({ stage: 'strategy' })}
                  aria-label="选题生成"
                >
                  <TableOutlined />
                  <span>选题</span>
                </button>
              </Tooltip>
              <Tooltip title="稿件生产" placement="right">
                <button
                  type="button"
                  className={activeStage === 'production' ? 'aiwiki-stage-nav-button is-active' : 'aiwiki-stage-nav-button'}
                  onClick={() => updateWorkbenchParams({ stage: 'production' })}
                  aria-label="稿件生产"
                >
                  <FileMarkdownOutlined />
                  <span>稿件</span>
                </button>
              </Tooltip>
              <Tooltip title="生成图文" placement="right">
                <button
                  type="button"
                  className={activeStage === 'social' ? 'aiwiki-stage-nav-button is-active' : 'aiwiki-stage-nav-button'}
                  onClick={() => updateWorkbenchParams({ stage: 'social' })}
                  aria-label="生成图文"
                >
                  <PictureOutlined />
                  <span>图文</span>
                </button>
              </Tooltip>
              <Tooltip title="轮播视频" placement="right">
                <button
                  type="button"
                  className={activeStage === 'video' ? 'aiwiki-stage-nav-button is-active' : 'aiwiki-stage-nav-button'}
                  onClick={() => updateWorkbenchParams({ stage: 'video' })}
                  aria-label="轮播视频"
                >
                  <VideoCameraOutlined />
                  <span>视频</span>
                </button>
              </Tooltip>
              <Tooltip title="内容分发" placement="right">
                <button
                  type="button"
                  className={activeStage === 'distribution' ? 'aiwiki-stage-nav-button is-active' : 'aiwiki-stage-nav-button'}
                  onClick={() => updateWorkbenchParams({ stage: 'distribution' })}
                  aria-label="内容分发"
                >
                  <CloudUploadOutlined />
                  <span>分发</span>
                </button>
              </Tooltip>
            </nav>
            <div className="aiwiki-stage-source">
              <Typography.Text className="aiwiki-kicker">
                {activeStage === 'distribution' ? '分发中心' : '当前知识库'}
              </Typography.Text>
              <Typography.Text className="aiwiki-stage-source-title">
                {activeStage === 'distribution' ? '稿件 / 图文' : activeTask?.title ?? '未选择'}
              </Typography.Text>
            </div>
          </div>
        )}
      </aside>

      <main className="aiwiki-main">
        <header className="aiwiki-topbar">
          <Flex vertical gap={10} className="aiwiki-heading">
            <Typography.Text className="aiwiki-kicker">{stageSubtitle}</Typography.Text>
            <Typography.Title level={3} className="aiwiki-title">{stageTitle}</Typography.Title>
          </Flex>
          {activeStage === 'assets' && (
            <Space wrap className="aiwiki-top-actions">
              <Button icon={<ReloadOutlined />} loading={historyLoading} onClick={() => void loadHistory()}>刷新</Button>
            </Space>
          )}
        </header>

        {stagePrerequisite && (
          <Alert
            className="aiwiki-stage-prerequisite"
            type={stagePrerequisite.type}
            showIcon
            message={(
              <span>
                {stagePrerequisite.message}
                <Button
                  className="aiwiki-stage-prerequisite-link"
                  type="link"
                  size="small"
                  onClick={() => updateWorkbenchParams({ stage: stagePrerequisite.targetStage })}
                >
                  {stagePrerequisite.actionText}
                </Button>
              </span>
            )}
          />
        )}

        <section className={activeStage === 'assets' ? 'aiwiki-canvas' : 'aiwiki-canvas aiwiki-canvas-stage-flow'}>
          {activeStage === 'assets' && (
            <div className="aiwiki-stat-strip">
              <Statistic title="历史任务" value={stats.serverTasks} />
              <Statistic title="进行中" value={stats.activeCount} />
              <Statistic title="已完成" value={stats.completedCount} />
              <Statistic title="总文件" value={stats.fileCount} />
            </div>
          )}
          <div className="aiwiki-stage">
            {activeStage === 'assets' && (
              isContentGrowthWorkbench ? (
                <AssetStageContent
                  activeTaskId={activeTaskId}
                  displayTasks={displayTasks}
                  historyLoading={historyLoading}
                  historyPage={historyPage}
                  historyPageSize={TASK_PAGE_SIZE}
                  historyTotal={historyTotal}
                  search={search}
                  taskFilter={taskFilter}
                  content={result ? (
                    <div className="aiwiki-result-scroll">
                      <ResultView
                        result={result}
                        selectedTerms={selectedTerms}
                        entryFilter={entryFilter}
                        filteredEntries={filteredEntries}
                        entriesBySlug={entriesBySlug}
                        activeEntry={activeEntry}
                        onOpenKeywordModal={() => setKeywordModalOpen(true)}
                        onEntryFilterChange={setEntryFilter}
                        onOpenEntry={setActiveEntrySlug}
                        onCloseEntry={() => setActiveEntrySlug(null)}
                      />
                    </div>
                  ) : (
                    <TaskOverview
                      task={activeTask}
                      files={activeFiles}
                      uploading={submitting && isCreatingTask}
                      uploadProgress={uploadProgress}
                      onPreview={setPreviewFile}
                      onRemoveLocal={removeLocalFile}
                      onFilesSelected={(files) => void handleFilesSelected(files)}
                      onStartNewTask={startNewTask}
                      onSubmit={() => void submitFiles()}
                    />
                  )}
                  submitting={submitting}
                  onDeleteJob={confirmDeleteJob}
                  onEditJob={openEditModal}
                  onRefresh={() => void loadHistory()}
                  onHistoryPageChange={(page) => {
                    setHistoryPage(page)
                    void loadHistory(page)
                  }}
                  onSearchChange={setSearch}
                  onSelectTask={(task) => void selectTask(task)}
                  onSetTaskFilter={setTaskFilter}
                  onStartNewTask={startNewTask}
                />
              ) : result ? (
                <div className="aiwiki-result-scroll">
                  <ResultView
                    result={result}
                    selectedTerms={selectedTerms}
                    entryFilter={entryFilter}
                    filteredEntries={filteredEntries}
                    entriesBySlug={entriesBySlug}
                    activeEntry={activeEntry}
                    onOpenKeywordModal={() => setKeywordModalOpen(true)}
                    onEntryFilterChange={setEntryFilter}
                    onOpenEntry={setActiveEntrySlug}
                    onCloseEntry={() => setActiveEntrySlug(null)}
                  />
                </div>
              ) : (
                <TaskOverview
                  task={activeTask}
                  files={activeFiles}
                  uploading={submitting && isCreatingTask}
                  uploadProgress={uploadProgress}
                  onPreview={setPreviewFile}
                  onRemoveLocal={removeLocalFile}
                  onFilesSelected={(files) => void handleFilesSelected(files)}
                  onStartNewTask={startNewTask}
                  onSubmit={() => void submitFiles()}
                />
              )
            )}
            {activeStage === 'strategy' && (
              <div className="aiwiki-growth-stage-body">
                <SeedMatrixPage
                  key={`strategy-${strategyMode}`}
                  embedded
                  mode={strategyMode}
                  onOpenProductionStage={() => updateWorkbenchParams({ stage: 'production' })}
                />
              </div>
            )}
            {activeStage === 'production' && (
              <div className="aiwiki-growth-stage-body">
                <DailyWriterPage
                  key={`production-${writerMode}`}
                  embedded
                  mode={writerMode}
                />
              </div>
            )}
            {activeStage === 'social' && (
              <div className="aiwiki-growth-stage-body">
                <SocialCardsPage />
              </div>
            )}
            {activeStage === 'video' && (
              <div className="aiwiki-growth-stage-body">
                <SocialCardVideosPage />
              </div>
            )}
            {activeStage === 'distribution' && (
              <div className="aiwiki-growth-stage-body">
                <DistributionStagePage />
              </div>
            )}
          </div>

          {submitting && (
            <div className="aiwiki-upload-progress">
              <Typography.Text>上传并创建新任务</Typography.Text>
              <Progress percent={uploadProgress} size="small" status="active" />
            </div>
          )}

          {activeStage === 'assets' && (
            <aside className="aiwiki-right-panel">
              <TaskPanel
                task={activeTask}
                job={activeJob}
                meta={meta}
                refreshing={historyLoading}
                onRefresh={() => activeTask && !activeTask.isDraft ? void loadJob(activeTask.id) : void loadHistory()}
              />
              <SourceFilesPanel
                files={activeFiles}
                uploading={submitting && isCreatingTask}
                onPreview={setPreviewFile}
                onRemoveLocal={removeLocalFile}
              />
            </aside>
          )}
        </section>
      </main>

      <KeywordModal
        open={keywordModalOpen}
        terms={availableTerms}
        selectedTerms={selectedTerms}
        keywordSearch={keywordSearch}
        onSearch={setKeywordSearch}
        onApply={(terms) => {
          setSelectedTerms(terms)
          setKeywordModalOpen(false)
        }}
        onClose={() => setKeywordModalOpen(false)}
      />

      <Modal
        title={previewFile?.filename ?? '文件预览'}
        open={Boolean(previewFile)}
        onCancel={() => setPreviewFile(null)}
        footer={null}
        width="min(1120px, 92vw)"
        destroyOnHidden
      >
        {previewFile && (
          <div className="aiwiki-preview-modal-body">
            <Space wrap className="aiwiki-preview-meta">
              <Tag>{categoryLabel(fileCategory(previewFile))}</Tag>
              <Tag>{(previewFile.extension ?? extensionOf(previewFile.filename)).replace('.', '').toUpperCase()}</Tag>
              <Tag>{formatBytes(previewFile.size_bytes)}</Tag>
              {previewFile.job_status && <Tag color={previewFile.job_status === 'completed' ? 'green' : previewFile.job_status === 'failed' ? 'red' : 'blue'}>{statusMeta(previewFile.job_status).label}</Tag>}
              {previewFile.isLocal && <Tag color={previewFile.uploadState === 'failed' ? 'red' : 'gold'}>{previewFile.uploadState === 'failed' ? '上传失败' : '上传前预览'}</Tag>}
            </Space>
            <PreviewContent file={previewFile} job={activeJob} />
          </div>
        )}
      </Modal>

      <Modal
        title="编辑任务信息"
        open={Boolean(editingJob)}
        onCancel={() => setEditingJob(null)}
        onOk={() => void saveMetadata()}
        okText="保存"
        cancelText="取消"
        confirmLoading={savingMetadata}
        destroyOnHidden
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="title" label="任务名称">
            <Input maxLength={120} placeholder="留空则使用文件名自动显示" />
          </Form.Item>
          <Form.Item name="description" label="备注">
            <Input.TextArea rows={4} maxLength={1000} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

function AssetStageContent({
  activeTaskId,
  content,
  displayTasks,
  historyLoading,
  historyPage,
  historyPageSize,
  historyTotal,
  search,
  submitting,
  taskFilter,
  onDeleteJob,
  onEditJob,
  onRefresh,
  onHistoryPageChange,
  onSearchChange,
  onSelectTask,
  onSetTaskFilter,
  onStartNewTask,
}: {
  activeTaskId: string | null
  content: ReactNode
  displayTasks: DisplayTask[]
  historyLoading: boolean
  historyPage: number
  historyPageSize: number
  historyTotal: number
  search: string
  submitting: boolean
  taskFilter: TaskFilter
  onDeleteJob: (job: AiwikiJobSummary | AiwikiJob) => void
  onEditJob: (job: AiwikiJobSummary | AiwikiJob) => void
  onRefresh: () => void
  onHistoryPageChange: (page: number) => void
  onSearchChange: (value: string) => void
  onSelectTask: (task: DisplayTask) => void
  onSetTaskFilter: (value: TaskFilter) => void
  onStartNewTask: () => void
}) {
  return (
    <div className="aiwiki-assets-workflow">
      <aside className="aiwiki-asset-task-rail">
        <Flex align="center" justify="space-between" gap={10}>
          <div>
            <Typography.Text className="aiwiki-kicker">Asset Tasks</Typography.Text>
            <Typography.Title level={5} className="aiwiki-panel-title">资产任务</Typography.Title>
          </div>
          <Button size="small" icon={<ReloadOutlined />} loading={historyLoading} onClick={onRefresh} />
        </Flex>
        <Button block type="primary" icon={<PlusOutlined />} disabled={submitting} onClick={onStartNewTask}>
          创建新任务
        </Button>
        <div className="aiwiki-filter-stack">
          <Input.Search value={search} allowClear placeholder="搜索任务或文件" onChange={(event) => onSearchChange(event.target.value)} />
          <Segmented
            block
            value={taskFilter}
            onChange={(value) => onSetTaskFilter(value as TaskFilter)}
            options={[
              { label: '全部', value: 'all' },
              { label: '进行中', value: 'active' },
              { label: '完成', value: 'completed' },
              { label: '失败', value: 'failed' },
            ]}
          />
        </div>
        <div className="aiwiki-task-list">
          <List
            size="small"
            loading={historyLoading}
            dataSource={displayTasks}
            locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无任务" /> }}
            renderItem={(task) => (
              <List.Item>
                <div
                  className={task.id === activeTaskId ? 'aiwiki-task-item is-active' : 'aiwiki-task-item'}
                  onClick={() => onSelectTask(task)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      onSelectTask(task)
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <span className="aiwiki-file-icon"><FileTextOutlined /></span>
                  <span className="aiwiki-file-copy">
                    <span className="aiwiki-file-name">{task.title}</span>
                    <span className="aiwiki-file-meta">
                      {task.files.length} 个文件 · {taskStatusLabel(task.status)}
                    </span>
                  </span>
                  {task.summary ? (
                    <span className="aiwiki-task-list-actions" onKeyDown={(event) => event.stopPropagation()}>
                      <Tooltip title="编辑">
                        <button
                          aria-label={`编辑任务 ${task.summary.title}`}
                          className="aiwiki-task-action-button"
                          onClick={(event) => {
                            event.stopPropagation()
                            onEditJob(task.summary!)
                          }}
                          type="button"
                        >
                          <EditOutlined />
                        </button>
                      </Tooltip>
                      <Tooltip title="删除">
                        <button
                          aria-label={`删除任务 ${task.summary.title}`}
                          className="aiwiki-task-action-button is-danger"
                          disabled={task.summary.status === 'queued' || task.summary.status === 'running'}
                          onClick={(event) => {
                            event.stopPropagation()
                            onDeleteJob(task.summary!)
                          }}
                          type="button"
                        >
                          <DeleteOutlined />
                        </button>
                      </Tooltip>
                    </span>
                  ) : null}
                </div>
              </List.Item>
            )}
          />
        </div>
        {historyTotal > historyPageSize && (
          <Pagination
            size="small"
            simple
            current={historyPage}
            pageSize={historyPageSize}
            total={historyTotal}
            onChange={onHistoryPageChange}
          />
        )}
      </aside>
      <section className="aiwiki-assets-main">
        {content}
      </section>
    </div>
  )
}

function TaskOverview({
  task,
  files,
  uploading,
  uploadProgress,
  onPreview,
  onRemoveLocal,
  onFilesSelected,
  onStartNewTask,
  onSubmit,
}: {
  task: DisplayTask | null
  files: DisplayFile[]
  uploading?: boolean
  uploadProgress: number
  onPreview: (file: DisplayFile) => void
  onRemoveLocal: (file: DisplayFile) => void
  onFilesSelected: (files: File[]) => void
  onStartNewTask: () => void
  onSubmit: () => void
}) {
  if (!task) {
    return (
      <div className="aiwiki-task-empty">
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="创建一个新任务，或选择一个历史任务" />
        <Button type="primary" icon={<PlusOutlined />} onClick={onStartNewTask}>创建新任务</Button>
      </div>
    )
  }
  return (
    <div className={task.isDraft ? 'aiwiki-task-overview is-draft' : 'aiwiki-task-overview'}>
      <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
        <div>
          <Typography.Text className="aiwiki-kicker">{task.isDraft ? '新任务' : task.id}</Typography.Text>
          <Typography.Title level={3} style={{ marginTop: 4 }}>{task.title}</Typography.Title>
          {task.description && <Typography.Paragraph type="secondary">{task.description}</Typography.Paragraph>}
        </div>
        <Space wrap>
          <Tag color={taskStatusColor(task.status)}>{taskStatusLabel(task.status)}</Tag>
          {task.created_at && <Tag>{formatDateTime(task.created_at)}</Tag>}
        </Space>
      </Flex>
      {uploading && <Progress percent={uploadProgress} status="active" />}
      {task.isDraft && (
        <TaskUploadDropzone disabled={uploading} onFilesSelected={onFilesSelected} />
      )}
      {files.length > 0 && (
        <FileList files={files} uploading={uploading} onPreview={onPreview} onRemoveLocal={onRemoveLocal} />
      )}
      {task.isDraft && files.length > 0 && (
        <Button
          type="primary"
          size="large"
          icon={<PlusOutlined />}
          loading={uploading}
          disabled={!files.length}
          onClick={onSubmit}
          className="aiwiki-create-task-submit"
        >
          开始生成
        </Button>
      )}
    </div>
  )
}

function TaskUploadDropzone({
  disabled,
  onFilesSelected,
}: {
  disabled?: boolean
  onFilesSelected: (files: File[]) => void
}) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [dragging, setDragging] = useState(false)

  const acceptFiles = (fileList: FileList | null) => {
    const files = Array.from(fileList ?? [])
    if (!files.length) return
    onFilesSelected(files)
  }

  return (
    <div
      className={dragging ? 'aiwiki-upload-dropzone is-dragging' : 'aiwiki-upload-dropzone'}
      onClick={() => {
        if (!disabled) inputRef.current?.click()
      }}
      onDragEnter={(event) => {
        event.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={(event) => {
        event.preventDefault()
        setDragging(false)
      }}
      onDragOver={(event) => {
        event.preventDefault()
      }}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        if (!disabled) acceptFiles(event.dataTransfer.files)
      }}
      onKeyDown={(event) => {
        if (disabled) return
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          inputRef.current?.click()
        }
      }}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED_TYPES}
        disabled={disabled}
        className="aiwiki-upload-input"
        onChange={(event) => {
          acceptFiles(event.target.files)
          event.currentTarget.value = ''
        }}
      />
      <div className="aiwiki-upload-dropzone-icon"><CloudUploadOutlined /></div>
      <Typography.Title level={3} className="aiwiki-upload-dropzone-title">拖拽文件到这里，或点击选择</Typography.Title>
      <Typography.Paragraph type="secondary" className="aiwiki-upload-dropzone-copy">
        一个任务可以包含多个文件。先添加文件，确认清单后再创建任务。
      </Typography.Paragraph>
      <Tooltip title={ACCEPTED_TYPE_HINT}>
        <Typography.Text type="secondary" className="aiwiki-upload-limit">
          支持文档、表格和 PDF
        </Typography.Text>
      </Tooltip>
    </div>
  )
}

function TaskPanel({
  task,
  job,
  meta,
  refreshing,
  onRefresh,
}: {
  task: DisplayTask | null
  job: AiwikiJob | null
  meta: ReturnType<typeof statusMeta>
  refreshing: boolean
  onRefresh: () => void
}) {
  const [logView, setLogView] = useState<'task' | 'opencode'>('task')
  const progressEvents = job?.progress?.events ?? []
  return (
    <section className="aiwiki-panel-section aiwiki-audit-section">
      <Flex align="center" justify="space-between" gap={10}>
        <div>
          <Typography.Text className="aiwiki-panel-kicker">任务</Typography.Text>
          <Typography.Title level={5} className="aiwiki-panel-title">{task?.title ?? '未选择任务'}</Typography.Title>
        </div>
        <Button size="small" icon={<ReloadOutlined />} loading={refreshing} onClick={onRefresh} />
      </Flex>
      {task ? (
        <>
          <div className="aiwiki-task-card">
            <Progress percent={task.isDraft ? 0 : meta.percent} status={task.isDraft ? 'normal' : meta.status} />
            <Space wrap>
              <Tag color={taskStatusColor(task.status)}>{taskStatusLabel(task.status)}</Tag>
              <Tag>{task.files.length} 个文件</Tag>
            </Space>
            {job?.message && <Typography.Text>{job.message}</Typography.Text>}
          </div>
          {!task.isDraft && (
            <>
              <Segmented
                block
                size="small"
                value={logView}
                onChange={(value) => setLogView(value as 'task' | 'opencode')}
                options={[
                  { label: '任务日志', value: 'task' },
                  { label: '处理日志', value: 'opencode' },
                ]}
              />
              {logView === 'task' && (
                <List
                  size="small"
                  dataSource={progressEvents}
                  locale={{ emptyText: job ? '暂无任务事件' : '任务详情加载后显示日志' }}
                  className="aiwiki-audit-list"
                  renderItem={(item) => (
                    <List.Item>
                      <Flex vertical gap={4}>
                        <Space wrap>
                          <Tag color={progressEventColor(item.event)}>{item.step}</Tag>
                          <Typography.Text className="aiwiki-audit-message">{item.summary}</Typography.Text>
                        </Space>
                      </Flex>
                    </List.Item>
                  )}
                />
              )}
              {logView === 'opencode' && (
                job?.log_tail?.length ? (
                  <pre className="aiwiki-opencode-log">{job.log_tail.join('\n')}</pre>
                ) : (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={job ? '暂无 OpenCode 输出' : '任务详情加载后显示处理日志'} />
                )
              )}
            </>
          )}
        </>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未选择任务" />
      )}
    </section>
  )
}

function SourceFilesPanel({
  files,
  uploading,
  onPreview,
  onRemoveLocal,
}: {
  files: DisplayFile[]
  uploading?: boolean
  onPreview: (file: DisplayFile) => void
  onRemoveLocal: (file: DisplayFile) => void
}) {
  return (
    <section className="aiwiki-panel-section aiwiki-source-section">
      <Typography.Text className="aiwiki-panel-kicker">任务文件</Typography.Text>
      <Typography.Title level={5} className="aiwiki-panel-title">文件清单</Typography.Title>
      <FileList files={files} compact uploading={uploading} onPreview={onPreview} onRemoveLocal={onRemoveLocal} />
    </section>
  )
}

function FileList({
  files,
  compact,
  uploading,
  onPreview,
  onRemoveLocal,
}: {
  files: DisplayFile[]
  compact?: boolean
  uploading?: boolean
  onPreview: (file: DisplayFile) => void
  onRemoveLocal: (file: DisplayFile) => void
}) {
  return (
    <List
      size="small"
      dataSource={files}
      locale={{ emptyText: '暂无文件' }}
      className={compact ? 'aiwiki-source-file-list is-compact' : 'aiwiki-source-file-list'}
      renderItem={(file) => (
        <List.Item>
          <Flex align="center" justify="space-between" gap={10} className="aiwiki-source-file-row">
            <Space size={10} style={{ minWidth: 0 }}>
              <span className="aiwiki-file-icon">{fileIcon(file)}</span>
              <Space direction="vertical" size={0} style={{ minWidth: 0 }}>
                <Typography.Text strong ellipsis>{file.filename}</Typography.Text>
                <Typography.Text type="secondary">{categoryLabel(fileCategory(file))} · {formatBytes(file.size_bytes)}</Typography.Text>
              </Space>
            </Space>
            <Space size={4}>
              {uploading && file.isLocal && <Progress type="circle" percent={file.uploadProgress ?? 0} size={28} />}
              <Button size="small" icon={<EyeOutlined />} onClick={() => onPreview(file)}>预览</Button>
              {file.isLocal && (
                <Button danger size="small" type="text" icon={<DeleteOutlined />} disabled={uploading} onClick={() => onRemoveLocal(file)} />
              )}
            </Space>
          </Flex>
        </List.Item>
      )}
    />
  )
}

function PreviewContent({ file, job }: { file: DisplayFile; job: AiwikiJob | null }) {
  const preview = file.preview ?? {}
  if (isTextPreview(preview)) {
    return preview.format === 'markdown' ? (
      <div className="aiwiki-markdown-preview">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{preview.text}</ReactMarkdown>
        {preview.truncated && <Tag color="gold">已截断</Tag>}
      </div>
    ) : (
      <pre className="aiwiki-text-preview">{preview.text}{preview.truncated ? '\n\n[已截断]' : ''}</pre>
    )
  }
  if (isSpreadsheetPreview(preview)) {
    return <SpreadsheetPreview preview={preview} />
  }
  if (preview.kind === 'pdf') {
    return <PdfPreview file={file} job={job} />
  }
  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无预览" />
}

function SpreadsheetPreview({ preview }: { preview: AiwikiSpreadsheetPreview }) {
  const [sheetName, setSheetName] = useState(preview.sheets[0]?.name ?? '')
  useEffect(() => {
    setSheetName(preview.sheets[0]?.name ?? '')
  }, [preview])
  const sheet = preview.sheets.find((item) => item.name === sheetName) ?? preview.sheets[0]
  if (!sheet) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="空表格" />
  const width = Math.max(...sheet.rows.map((row) => row.length), 1)
  const columns: ColumnsType<Record<string, string>> = Array.from({ length: width }).map((_, index) => ({
    key: `col-${index}`,
    dataIndex: `col-${index}`,
    title: columnName(index),
    width: 120,
    ellipsis: true,
  }))
  const data = sheet.rows.map((row, rowIndex) => {
    const item: Record<string, string> = { key: String(rowIndex) }
    for (let index = 0; index < width; index += 1) item[`col-${index}`] = row[index] ?? ''
    return item
  })
  return (
    <Flex vertical gap={10} className="aiwiki-sheet-preview">
      <Segmented
        value={sheet.name}
        onChange={(value) => setSheetName(String(value))}
        options={preview.sheets.map((item) => ({ label: item.name, value: item.name }))}
      />
      <Space wrap>
        <Tag>{sheet.row_count} 行</Tag>
        <Tag>{sheet.column_count} 列</Tag>
        {sheet.truncated && <Tag color="gold">已截断</Tag>}
      </Space>
      <Table size="small" bordered pagination={false} columns={columns} dataSource={data} scroll={{ x: width * 120, y: 420 }} />
    </Flex>
  )
}

function PdfPreview({ file, job }: { file: DisplayFile; job: AiwikiJob | null }) {
  const [url, setUrl] = useState(file.localObjectUrl ?? '')
  const [error, setError] = useState('')
  const pdfPreview = isPdfPreview(file.preview) ? file.preview : null
  useEffect(() => {
    let objectUrl = ''
    setError('')
    if (file.localObjectUrl) {
      setUrl(file.localObjectUrl)
      return undefined
    }
    if (!file.job_id || file.file_index === undefined) {
      setError('无法定位 PDF 原文件')
      return undefined
    }
    let cancelled = false
    void getAiwikiFile(file.job_id, file.file_index)
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch((err) => {
        if (!cancelled) setError(resolveErrorMessage(err))
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [file.file_index, file.job_id, file.localObjectUrl, job?.id])
  if (error) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={error} />
  if (!url) return <div className="aiwiki-pdf-loading">PDF 加载中</div>
  return (
    <Flex vertical gap={12}>
      <Space wrap>
        {pdfPreview?.page_count !== undefined && <Tag>{pdfPreview.page_count} 页</Tag>}
        {pdfPreview?.character_count !== undefined && <Tag>{pdfPreview.character_count} 字符</Tag>}
        {pdfPreview?.truncated && <Tag color="gold">文本预览已截断</Tag>}
      </Space>
      <iframe className="aiwiki-pdf-preview" title={file.filename} src={url} />
      {pdfPreview?.text && (
        <div className="aiwiki-markdown-preview">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{pdfPreview.text}</ReactMarkdown>
        </div>
      )}
    </Flex>
  )
}

async function buildLocalFile(file: File, index: number): Promise<DisplayFile> {
  const extension = extensionOf(file.name)
  if (!['.md', '.markdown', '.txt', '.xlsx', '.csv', '.pdf'].includes(extension)) {
    throw new Error(`不支持的文件类型：${extension || file.name}`)
  }
  const preview = await buildLocalPreview(file, extension)
  return {
    id: `local-${file.lastModified}-${index}-${file.name}`,
    filename: file.name,
    size_bytes: file.size,
    raw_path: '',
    upload_path: '',
    extension,
    mime_type: file.type || mimeTypeForExtension(extension),
    category: extension === '.md' || extension === '.markdown' || extension === '.txt' ? 'graphic_text' : 'document',
    preview_status: 'ready',
    preview,
    isLocal: true,
    localFile: file,
    localObjectUrl: extension === '.pdf' ? URL.createObjectURL(file) : undefined,
    uploadState: 'preview',
    uploadProgress: 0,
  }
}

async function buildLocalPreview(file: File, extension: string): Promise<AiwikiFilePreview> {
  if (extension === '.md' || extension === '.markdown' || extension === '.txt') {
    const text = await file.text()
    return {
      kind: 'text',
      format: extension === '.txt' ? 'plain' : 'markdown',
      text: text.slice(0, 200_000),
      truncated: text.length > 200_000,
      character_count: text.length,
    }
  }
  if (extension === '.xlsx' || extension === '.csv') {
    const workbook = extension === '.csv'
      ? XLSX.read(await file.text(), { type: 'string' })
      : XLSX.read(await file.arrayBuffer(), { type: 'array' })
    const sheets = workbook.SheetNames.slice(0, 20).map((name: string) => {
      const sheet = workbook.Sheets[name]
      const range = sheet['!ref'] ? XLSX.utils.decode_range(sheet['!ref']) : null
      const rowCount = range ? range.e.r - range.s.r + 1 : 0
      const columnCount = range ? range.e.c - range.s.c + 1 : 0
      const rows = XLSX.utils.sheet_to_json<string[]>(sheet, { header: 1, raw: false, defval: '' }).slice(0, 200) as string[][]
      const width = Math.min(Math.max(columnCount, ...rows.map((row) => row.length), 1), 50)
      return {
        name,
        row_count: rowCount,
        column_count: columnCount,
        truncated: rowCount > 200 || columnCount > 50,
        rows: rows.map((row) => Array.from({ length: width }, (_, rowIndex) => String(row[rowIndex] ?? ''))),
      }
    })
    return { kind: 'spreadsheet', filename: file.name, sheets, sheet_count: sheets.length, max_rows: 200, max_columns: 50 }
  }
  return { kind: 'pdf', filename: file.name, size_bytes: file.size }
}

function upsertHistory(items: AiwikiJobSummary[], latest: AiwikiJob): AiwikiJobSummary[] {
  const summary = jobSummaryFromJob(latest)
  return items.some((item) => item.id === latest.id)
    ? items.map((item) => (item.id === latest.id ? { ...item, ...summary, summary: item.summary } : item))
    : [summary, ...items]
}

function jobSummaryFromJob(job: AiwikiJob): AiwikiJobSummary {
  return {
    id: job.id,
    owner_user_id: job.owner_user_id,
    owner_username: job.owner_username,
    title: job.title,
    description: job.description,
    status: job.status,
    message: job.message,
    created_at: job.created_at,
    started_at: job.started_at,
    finished_at: job.finished_at,
    files: job.files,
    summary: {},
  }
}

function toDisplayFile(
  file: AiwikiUploadedFile,
  job: AiwikiJob | AiwikiJobSummary,
  fileIndex: number,
): DisplayFile {
  return {
    ...file,
    id: `${job.id}:${fileIndex}`,
    job_id: job.id,
    job_status: job.status,
    file_index: fileIndex,
    created_at: job.created_at,
  }
}

function isTextPreview(preview: AiwikiFilePreview): preview is AiwikiTextPreview {
  return preview.kind === 'text'
}

function isSpreadsheetPreview(preview: AiwikiFilePreview): preview is AiwikiSpreadsheetPreview {
  return preview.kind === 'spreadsheet'
}

function isPdfPreview(preview: AiwikiFilePreview | undefined): preview is AiwikiPdfPreview {
  return Boolean(preview && preview.kind === 'pdf')
}

function fileCategory(file: DisplayFile): FileCategory {
  const extension = file.extension ?? extensionOf(file.filename)
  return extension === '.xlsx' || extension === '.csv' ? 'spreadsheet' : 'document'
}

function categoryLabel(category: FileCategory): string {
  return category === 'spreadsheet' ? '表格' : '文档'
}

function fileIcon(file: DisplayFile) {
  const extension = file.extension ?? extensionOf(file.filename)
  if (extension === '.pdf') return <FilePdfOutlined />
  if (extension === '.xlsx' || extension === '.csv') return <TableOutlined />
  if (extension === '.md' || extension === '.markdown') return <FileMarkdownOutlined />
  return <FileTextOutlined />
}

function taskStatusLabel(status: DisplayTask['status']): string {
  if (status === 'draft') return '草稿'
  return statusMeta(status).label
}

function taskStatusColor(status: DisplayTask['status']): string {
  if (status === 'draft') return 'gold'
  if (status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  return 'blue'
}

function extensionOf(filename: string): string {
  const dotIndex = filename.lastIndexOf('.')
  return dotIndex >= 0 ? filename.slice(dotIndex).toLowerCase() : ''
}

function mimeTypeForExtension(extension: string): string {
  return {
    '.md': 'text/markdown',
    '.markdown': 'text/markdown',
    '.txt': 'text/plain',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.csv': 'text/csv',
    '.pdf': 'application/pdf',
  }[extension] ?? 'application/octet-stream'
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function columnName(index: number): string {
  let value = index + 1
  let name = ''
  while (value > 0) {
    const mod = (value - 1) % 26
    name = String.fromCharCode(65 + mod) + name
    value = Math.floor((value - mod) / 26)
  }
  return name
}

function revokeLocalUrls(files: DisplayFile[]) {
  files.forEach((file) => {
    if (file.localObjectUrl) URL.revokeObjectURL(file.localObjectUrl)
  })
}
