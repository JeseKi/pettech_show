import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  App,
  Button,
  Empty,
  Flex,
  Input,
  List,
  Popconfirm,
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
  DeleteOutlined,
  DoubleLeftOutlined,
  DoubleRightOutlined,
  FileMarkdownOutlined,
  FilePdfOutlined,
  FileTextOutlined,
  HomeOutlined,
  PlayCircleOutlined,
  QuestionCircleOutlined,
  ReloadOutlined,
  RotateLeftOutlined,
  TableOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import * as XLSX from 'xlsx'
import { useAuth } from '../../hooks/useAuth'
import {
  createAiwikiJob,
  deleteAiwikiJob,
  getAiwikiFile,
  getAiwikiJob,
  getAiwikiResult,
  listAiwikiAuditLogs,
  listAiwikiJobs,
  type AiwikiAuditLog,
  type AiwikiFilePreview,
  type AiwikiJob,
  type AiwikiJobSummary,
  type AiwikiResult,
  type AiwikiSpreadsheetPreview,
  type AiwikiTextPreview,
  type AiwikiUploadedFile,
} from '../../lib/aiwiki'
import type { AiwikiModeId } from '../../lib/workflowModes'
import { resolveErrorMessage } from '../../lib/errorMessage'
import KeywordModal from './KeywordModal'
import ResultView from './ResultView'
import { ACTIVE_STATUSES, entryTypeLabel, formatDateTime, progressEventColor, statusMeta } from './helpers'
import './AiwikiWorkbench.css'

type FileCategory = 'document' | 'spreadsheet'
type FileFilter = 'all' | FileCategory
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

const ACCEPTED_TYPES = '.md,.markdown,.txt,.xlsx,.pdf'
const formatOptions = [
  ['文档', '.md / .markdown / .txt / .pdf'],
  ['表格', '.xlsx'],
] as const

export default function AiwikiPage({ mode = 'full' }: { mode?: AiwikiModeId }) {
  const { message } = App.useApp()
  const { user } = useAuth()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const localFilesRef = useRef<DisplayFile[]>([])
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [history, setHistory] = useState<AiwikiJobSummary[]>([])
  const [job, setJob] = useState<AiwikiJob | null>(null)
  const [result, setResult] = useState<AiwikiResult | null>(null)
  const [auditLogs, setAuditLogs] = useState<AiwikiAuditLog[]>([])
  const [auditScope, setAuditScope] = useState<'mine' | 'all'>('mine')
  const [localFiles, setLocalFiles] = useState<DisplayFile[]>([])
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [auditLoading, setAuditLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [fileFilter, setFileFilter] = useState<FileFilter>('all')
  const [search, setSearch] = useState('')
  const [selectedTerms, setSelectedTerms] = useState<string[]>([])
  const [entryFilter, setEntryFilter] = useState<string>('全部')
  const [activeEntrySlug, setActiveEntrySlug] = useState<string | null>(null)
  const [keywordModalOpen, setKeywordModalOpen] = useState(false)
  const [keywordSearch, setKeywordSearch] = useState('')

  const isAdmin = user?.role === 'admin'
  const meta = statusMeta(job?.status)
  const workspaceSubtitle = mode === 'full'
    ? 'OpenCode + Skill 生成 / 文件预览 / 任务日志 / 管理员审计'
    : 'OpenCode + Skill 生成 / 文件预览 / 任务日志'

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const list = await listAiwikiJobs({ limit: 100, offset: 0 })
      setHistory(list.items)
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setHistoryLoading(false)
    }
  }, [message])

  const loadAuditLogs = useCallback(async () => {
    setAuditLoading(true)
    try {
      const logs = await listAiwikiAuditLogs({
        scope: isAdmin ? auditScope : 'mine',
        limit: 80,
        offset: 0,
      })
      setAuditLogs(logs.items)
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setAuditLoading(false)
    }
  }, [auditScope, isAdmin, message])

  const loadJob = useCallback(async (jobId: string, silent = false) => {
    try {
      const latest = await getAiwikiJob(jobId)
      setJob(latest)
      setResult(latest.status === 'completed' ? await getAiwikiResult(jobId) : null)
    } catch (err) {
      if (!silent) message.error(resolveErrorMessage(err))
    }
  }, [message])

  useEffect(() => {
    void Promise.all([loadHistory(), loadAuditLogs()])
  }, [loadAuditLogs, loadHistory])

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

  const serverFiles = useMemo<DisplayFile[]>(() => {
    const items: DisplayFile[] = []
    history.forEach((item) => {
      item.files.forEach((file, fileIndex) => {
        items.push({
          ...file,
          id: `${item.id}:${fileIndex}`,
          job_id: item.id,
          job_status: item.status,
          file_index: fileIndex,
          created_at: item.created_at,
        })
      })
    })
    return items
  }, [history])

  const allFiles = useMemo<DisplayFile[]>(() => [...localFiles, ...serverFiles], [localFiles, serverFiles])

  const displayFiles = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()
    return allFiles.filter((file) => {
      const category = fileCategory(file)
      const categoryMatch = fileFilter === 'all' || category === fileFilter
      const searchMatch = !normalizedSearch || file.filename.toLowerCase().includes(normalizedSearch)
      return categoryMatch && searchMatch
    })
  }, [allFiles, fileFilter, search])

  const selectedFile = useMemo(() => (
    displayFiles.find((file) => file.id === selectedFileId) ?? displayFiles[0] ?? null
  ), [displayFiles, selectedFileId])

  useEffect(() => {
    if (!selectedFile) {
      setSelectedFileId(null)
      return
    }
    if (selectedFile.id !== selectedFileId) {
      setSelectedFileId(selectedFile.id)
    }
  }, [selectedFile, selectedFileId])

  const stats = useMemo(() => {
    const documentCount = allFiles.filter((file) => fileCategory(file) === 'document').length
    const spreadsheetCount = allFiles.filter((file) => fileCategory(file) === 'spreadsheet').length
    return {
      documentCount,
      spreadsheetCount,
      displayCount: displayFiles.length,
      totalCount: allFiles.length,
    }
  }, [allFiles, displayFiles.length])

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

  const handleFilesSelected = async (fileList: FileList | null) => {
    const files = Array.from(fileList ?? [])
    if (fileInputRef.current) fileInputRef.current.value = ''
    if (!files.length) return
    try {
      const startIndex = localFilesRef.current.length
      const previews = await Promise.all(files.map((file, index) => buildLocalFile(file, startIndex + index)))
      setLocalFiles((items) => [...items, ...previews])
      if (!selectedFileId) {
        setSelectedFileId(previews[0]?.id ?? null)
      }
    } catch (err) {
      message.error(resolveErrorMessage(err))
    }
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
      setSelectedFileId(`${created.id}:0`)
      setJob(created)
      setResult(null)
      message.success('知识库生成任务已提交')
      await Promise.all([loadHistory(), loadAuditLogs()])
      void loadJob(created.id, true)
    } catch (err) {
      setLocalFiles((items) => items.map((item) => ({ ...item, uploadState: 'failed' })))
      message.error(resolveErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const selectFile = async (file: DisplayFile) => {
    setSelectedFileId(file.id)
    if (file.job_id && file.job_id !== job?.id) {
      await loadJob(file.job_id)
    }
  }

  const openAuditFile = async (auditLog: AiwikiAuditLog, filename: string) => {
    if (!auditLog.job_id) return
    try {
      const latest = await getAiwikiJob(auditLog.job_id)
      const fileIndex = latest.files.findIndex((file) => file.filename === filename)
      if (fileIndex < 0) {
        message.warning('没有找到这份上传文件')
        return
      }
      setJob(latest)
      setResult(latest.status === 'completed' ? await getAiwikiResult(latest.id) : null)
      setSelectedFileId(`${latest.id}:${fileIndex}`)
      setHistory((items) => (
        items.some((item) => item.id === latest.id)
          ? items.map((item) => (item.id === latest.id ? { ...item, files: latest.files, status: latest.status, message: latest.message, summary: item.summary } : item))
          : [{
              id: latest.id,
              owner_user_id: latest.owner_user_id,
              owner_username: latest.owner_username,
              status: latest.status,
              message: latest.message,
              created_at: latest.created_at,
              started_at: latest.started_at,
              finished_at: latest.finished_at,
              files: latest.files,
              summary: {},
            }, ...items]
      ))
    } catch (err) {
      message.error(resolveErrorMessage(err))
    }
  }

  const handleDeleteJob = async (targetJob: AiwikiJobSummary | AiwikiJob) => {
    try {
      await deleteAiwikiJob(targetJob.id)
      message.success('知识库任务已删除')
      if (job?.id === targetJob.id) {
        setJob(null)
        setResult(null)
      }
      await Promise.all([loadHistory(), loadAuditLogs()])
    } catch (err) {
      message.error(resolveErrorMessage(err))
    }
  }

  return (
    <div className={sidebarCollapsed ? 'aiwiki-workbench is-sidebar-collapsed' : 'aiwiki-workbench'}>
      <aside className="aiwiki-sidebar">
        <button type="button" className="aiwiki-collapse" onClick={() => setSidebarCollapsed((value) => !value)}>
          {sidebarCollapsed ? <DoubleRightOutlined /> : <DoubleLeftOutlined />}
        </button>
        <div className="aiwiki-brand">
          <span className="aiwiki-logo"><FileTextOutlined /></span>
          <div className="aiwiki-brand-text">
            <Typography.Text className="aiwiki-kicker">AI Wiki</Typography.Text>
            <Typography.Title level={5} className="aiwiki-sidebar-title">知识库</Typography.Title>
          </div>
        </div>
        <Button block type="primary" icon={<UploadOutlined />} disabled={submitting} onClick={() => fileInputRef.current?.click()} className="aiwiki-upload-button">
          上传内容
        </Button>
        <Button block icon={<PlayCircleOutlined />} loading={submitting} disabled={!localFiles.length} onClick={() => void submitFiles()}>
          生成知识库
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_TYPES}
          style={{ display: 'none' }}
          onChange={(event) => void handleFilesSelected(event.target.files)}
        />
        <div className="aiwiki-filter-stack">
          <Input.Search value={search} allowClear placeholder="搜索文件" onChange={(event) => setSearch(event.target.value)} />
          <Segmented
            block
            value={fileFilter}
            onChange={(value) => setFileFilter(value as FileFilter)}
            options={[
              { label: '全部', value: 'all' },
              { label: '文档', value: 'document' },
              { label: '表格', value: 'spreadsheet' },
            ]}
          />
        </div>
        <div className="aiwiki-file-list">
          <List
            size="small"
            loading={historyLoading}
            dataSource={displayFiles}
            locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无文件" /> }}
            renderItem={(file) => (
              <List.Item>
                <button
                  type="button"
                  className={file.id === selectedFile?.id ? 'aiwiki-file-item is-active' : 'aiwiki-file-item'}
                  onClick={() => void selectFile(file)}
                >
                  <span className="aiwiki-file-icon">{fileIcon(file)}</span>
                  <span className="aiwiki-file-copy">
                    <span className="aiwiki-file-name">{file.filename}</span>
                    <span className="aiwiki-file-meta">{categoryLabel(fileCategory(file))} · {formatBytes(file.size_bytes)}</span>
                  </span>
                  {file.isLocal && <span className="aiwiki-local-dot" />}
                </button>
              </List.Item>
            )}
          />
        </div>
        <Link to="/dashboard" className="aiwiki-dashboard-link">
          <HomeOutlined />
          <span>返回首页</span>
        </Link>
      </aside>

      <main className="aiwiki-main">
        <header className="aiwiki-topbar">
          <Flex vertical gap={4} className="aiwiki-heading">
            <Typography.Text className="aiwiki-kicker">{workspaceSubtitle}</Typography.Text>
            <Typography.Title level={3} className="aiwiki-title">知识库</Typography.Title>
          </Flex>
          <Space wrap className="aiwiki-top-actions">
            <Button icon={<ReloadOutlined />} loading={historyLoading || auditLoading} onClick={() => void Promise.all([loadHistory(), loadAuditLogs()])}>刷新</Button>
            <Button icon={<UploadOutlined />} disabled={submitting} onClick={() => fileInputRef.current?.click()}>上传内容</Button>
            <Button type="primary" icon={<PlayCircleOutlined />} loading={submitting} disabled={!localFiles.length} onClick={() => void submitFiles()}>生成知识库</Button>
          </Space>
        </header>

        <section className="aiwiki-canvas">
          <div className="aiwiki-stat-strip">
            <Statistic title="文档数量" value={stats.documentCount} />
            <Statistic title="表格数量" value={stats.spreadsheetCount} />
            <Statistic title="展示数量" value={stats.displayCount} />
            <Statistic title="总文件" value={stats.totalCount} />
          </div>
          <div className="aiwiki-format-strip">
            {formatOptions.map(([label, detail]) => (
              <Tag key={label} className="aiwiki-format-tag">
                {label}
                <Tooltip title={detail}><QuestionCircleOutlined /></Tooltip>
              </Tag>
            ))}
            <Tag className="aiwiki-format-tag">暂不支持音视频上传</Tag>
          </div>

          <div className="aiwiki-stage">
            {result ? (
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
              <FileGraph files={displayFiles} selectedId={selectedFile?.id ?? null} onSelect={(file) => void selectFile(file)} />
            )}
          </div>

          {submitting && (
            <div className="aiwiki-upload-progress">
              <Typography.Text>上传并创建生成任务</Typography.Text>
              <Progress percent={uploadProgress} size="small" status="active" />
            </div>
          )}

          <aside className="aiwiki-right-panel">
            <PreviewPanel file={selectedFile} job={job} uploading={submitting && Boolean(selectedFile?.isLocal)} onRemoveLocal={(file) => {
              revokeLocalUrls([file])
              setLocalFiles((items) => items.filter((item) => item.id !== file.id))
            }} />
            <TaskAndAuditPanel
              job={job}
              history={history}
              auditLogs={auditLogs}
              auditLoading={auditLoading}
              isAdmin={isAdmin}
              auditScope={auditScope}
              meta={meta}
              onScopeChange={setAuditScope}
              onDeleteJob={handleDeleteJob}
              onOpenAuditFile={(auditLog, filename) => void openAuditFile(auditLog, filename)}
            />
          </aside>
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
    </div>
  )
}

function PreviewPanel({
  file,
  job,
  uploading,
  onRemoveLocal,
}: {
  file: DisplayFile | null
  job: AiwikiJob | null
  uploading: boolean
  onRemoveLocal: (file: DisplayFile) => void
}) {
  return (
    <section className="aiwiki-panel-section aiwiki-preview-section">
      <Flex align="center" justify="space-between" gap={10}>
        <div>
          <Typography.Text className="aiwiki-panel-kicker">文件预览</Typography.Text>
          <Typography.Title level={5} className="aiwiki-panel-title">{file?.filename ?? '未选择文件'}</Typography.Title>
        </div>
        {file?.isLocal && (
          <Button danger type="text" icon={<DeleteOutlined />} disabled={uploading} onClick={() => onRemoveLocal(file)} />
        )}
      </Flex>
      {file ? (
        <>
          <Space wrap className="aiwiki-preview-meta">
            <Tag>{categoryLabel(fileCategory(file))}</Tag>
            <Tag>{(file.extension ?? extensionOf(file.filename)).replace('.', '').toUpperCase()}</Tag>
            <Tag>{formatBytes(file.size_bytes)}</Tag>
            {file.job_status && <Tag color={file.job_status === 'completed' ? 'green' : file.job_status === 'failed' ? 'red' : 'blue'}>{statusMeta(file.job_status).label}</Tag>}
            {file.isLocal && <Tag color={file.uploadState === 'failed' ? 'red' : 'gold'}>{file.uploadState === 'failed' ? '上传失败' : '上传前预览'}</Tag>}
          </Space>
          <div className="aiwiki-preview-body">
            {uploading && (
              <div className="aiwiki-preview-uploading">
                <Progress type="circle" percent={file.uploadProgress ?? 0} size={74} />
              </div>
            )}
            <PreviewContent file={file} job={job} />
          </div>
        </>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选择或上传文件后可预览" />
      )}
    </section>
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
      <Table size="small" bordered pagination={false} columns={columns} dataSource={data} scroll={{ x: width * 120, y: 360 }} />
    </Flex>
  )
}

function PdfPreview({ file, job }: { file: DisplayFile; job: AiwikiJob | null }) {
  const [url, setUrl] = useState(file.localObjectUrl ?? '')
  const [error, setError] = useState('')
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
  return <iframe className="aiwiki-pdf-preview" title={file.filename} src={url} />
}

function TaskAndAuditPanel({
  job,
  history,
  auditLogs,
  auditLoading,
  isAdmin,
  auditScope,
  meta,
  onScopeChange,
  onDeleteJob,
  onOpenAuditFile,
}: {
  job: AiwikiJob | null
  history: AiwikiJobSummary[]
  auditLogs: AiwikiAuditLog[]
  auditLoading: boolean
  isAdmin: boolean
  auditScope: 'mine' | 'all'
  meta: ReturnType<typeof statusMeta>
  onScopeChange: (scope: 'mine' | 'all') => void
  onDeleteJob: (job: AiwikiJobSummary | AiwikiJob) => Promise<void>
  onOpenAuditFile: (auditLog: AiwikiAuditLog, filename: string) => void
}) {
  const [logView, setLogView] = useState<'task' | 'opencode' | 'audit'>('task')
  const logOptions = [
    { label: '任务日志', value: 'task' },
    { label: '处理日志', value: 'opencode' },
    { label: '管理员审计', value: 'audit', disabled: !isAdmin },
  ]
  const progressEvents = job?.progress?.events ?? []
  return (
    <section className="aiwiki-panel-section aiwiki-audit-section">
      <Flex align="center" justify="space-between" gap={10}>
        <div>
          <Typography.Text className="aiwiki-panel-kicker">日志</Typography.Text>
          <Typography.Title level={5} className="aiwiki-panel-title">{job ? meta.label : '任务历史'}</Typography.Title>
        </div>
      </Flex>
      <Segmented
        block
        size="small"
        value={logView}
        onChange={(value) => setLogView(value as 'task' | 'opencode' | 'audit')}
        options={logOptions}
      />
      {job && (
        <div className="aiwiki-task-card">
          <Progress percent={meta.percent} status={meta.status} />
          <Typography.Text>{job.message || meta.label}</Typography.Text>
          <Popconfirm
            title="删除知识库任务"
            description="会删除该任务记录和生成文件，但保留审计日志。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            disabled={job.status === 'queued' || job.status === 'running'}
            onConfirm={() => void onDeleteJob(job)}
          >
            <Button danger size="small" disabled={job.status === 'queued' || job.status === 'running'} icon={<DeleteOutlined />}>删除任务</Button>
          </Popconfirm>
        </div>
      )}
      {logView === 'task' && (
        <List
          size="small"
          dataSource={progressEvents}
          locale={{ emptyText: job ? '暂无任务事件' : '选择任务后查看任务日志' }}
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
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={job ? '暂无 OpenCode 输出' : '选择任务后查看处理日志'} />
        )
      )}
      {logView === 'audit' && (
        <>
          {isAdmin && (
            <Segmented size="small" value={auditScope} onChange={(value) => onScopeChange(value as 'mine' | 'all')} options={[
              { label: '我的', value: 'mine' },
              { label: '全部用户', value: 'all' },
            ]} />
          )}
          <List
            size="small"
            loading={auditLoading}
            dataSource={auditLogs}
            locale={{ emptyText: '暂无审计记录' }}
            className="aiwiki-audit-list"
            renderItem={(item) => (
              <List.Item>
                <Flex vertical gap={6}>
                  <Space wrap size={[4, 4]}>
                    <Typography.Text className="aiwiki-audit-message">
                      {item.actor_username} 进行了 {auditActionLabel(item.action)}
                    </Typography.Text>
                    {extractAuditFilenames(item).map((filename) => (
                      <Tag
                        key={`${item.id}-${filename}`}
                        color="blue"
                        className={item.job_id && item.action !== 'delete' ? 'aiwiki-clickable-file-tag' : undefined}
                        onClick={item.job_id && item.action !== 'delete' ? () => onOpenAuditFile(item, filename) : undefined}
                      >
                        {filename}
                      </Tag>
                    ))}
                  </Space>
                  <Typography.Text className="aiwiki-audit-time">{formatDateTime(item.created_at)}</Typography.Text>
                </Flex>
              </List.Item>
            )}
          />
        </>
      )}
      {!auditLogs.length && history.length > 0 && logView === 'audit' && <Typography.Text type="secondary">历史任务 {history.length} 个</Typography.Text>}
    </section>
  )
}

function FileGraph({
  files,
  selectedId,
  onSelect,
}: {
  files: DisplayFile[]
  selectedId: string | null
  onSelect: (file: DisplayFile) => void
}) {
  const graphRef = useRef<SVGSVGElement | null>(null)
  const dragRef = useRef<{
    kind: 'canvas' | 'node'
    id?: string
    lastX: number
    lastY: number
    moved: boolean
  } | null>(null)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [nodeOffsets, setNodeOffsets] = useState<Record<string, { x: number; y: number }>>({})
  const model = useMemo(() => buildGraphModel(files), [files])
  const positionedModel = useMemo(() => {
    const nodes = model.nodes.map((node) => {
      const offset = nodeOffsets[node.id]
      return offset ? { ...node, x: node.x + offset.x, y: node.y + offset.y } : node
    })
    const nodesById = new Map(nodes.map((node) => [node.id, node]))
    return { nodes, edges: model.edges, nodesById }
  }, [model, nodeOffsets])

  const pointerDelta = useCallback((clientX: number, clientY: number) => {
    const drag = dragRef.current
    const rect = graphRef.current?.getBoundingClientRect()
    if (!drag || !rect) return { dx: 0, dy: 0 }
    const dx = (clientX - drag.lastX) * (920 / rect.width)
    const dy = (clientY - drag.lastY) * (580 / rect.height)
    drag.lastX = clientX
    drag.lastY = clientY
    if (Math.abs(dx) > 0 || Math.abs(dy) > 0) drag.moved = true
    return { dx, dy }
  }, [])

  useEffect(() => {
    const handleMove = (event: PointerEvent) => {
      const drag = dragRef.current
      if (!drag) return
      const { dx, dy } = pointerDelta(event.clientX, event.clientY)
      if (drag.kind === 'canvas') {
        setPan((current) => ({ x: current.x + dx, y: current.y + dy }))
      } else if (drag.id) {
        setNodeOffsets((current) => {
          const offset = current[drag.id!] ?? { x: 0, y: 0 }
          return { ...current, [drag.id!]: { x: offset.x + dx, y: offset.y + dy } }
        })
      }
    }
    const handleUp = () => {
      dragRef.current = null
    }
    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
    return () => {
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
    }
  }, [pointerDelta])

  if (!files.length) {
    return <div className="aiwiki-graph-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="上传内容后生成知识库图谱" /></div>
  }
  return (
    <div className="aiwiki-file-graph">
      <div className="aiwiki-graph-toolbar">
        <Button size="small" icon={<RotateLeftOutlined />} onClick={() => {
          setPan({ x: 0, y: 0 })
          setNodeOffsets({})
        }}>重置视图</Button>
      </div>
      <svg
        ref={graphRef}
        viewBox="0 0 920 580"
        className="aiwiki-graph-svg"
        role="img"
        aria-label="知识库文件图谱"
        onPointerDown={(event) => {
          if (event.target !== event.currentTarget) return
          dragRef.current = { kind: 'canvas', lastX: event.clientX, lastY: event.clientY, moved: false }
        }}
      >
        <g transform={`translate(${pan.x} ${pan.y})`}>
          {positionedModel.edges.map((edge) => (
            <line
              key={`${edge.from}-${edge.to}`}
              x1={positionedModel.nodesById.get(edge.from)?.x ?? 0}
              y1={positionedModel.nodesById.get(edge.from)?.y ?? 0}
              x2={positionedModel.nodesById.get(edge.to)?.x ?? 0}
              y2={positionedModel.nodesById.get(edge.to)?.y ?? 0}
              className="aiwiki-graph-edge"
            />
          ))}
          {positionedModel.nodes.map((node) => (
            <foreignObject key={node.id} x={node.x - node.width / 2} y={node.y - node.height / 2} width={node.width} height={node.height}>
              {node.file ? (
                <button
                  type="button"
                  className={node.file.id === selectedId ? `aiwiki-graph-node ${node.kind} is-active` : `aiwiki-graph-node ${node.kind}`}
                  onPointerDown={(event) => {
                    event.stopPropagation()
                    dragRef.current = { kind: 'node', id: node.id, lastX: event.clientX, lastY: event.clientY, moved: false }
                  }}
                  onClick={() => onSelect(node.file!)}
                >
                  <span>{node.label}</span>
                </button>
              ) : (
                <div
                  className={`aiwiki-graph-node ${node.kind}`}
                  onPointerDown={(event) => {
                    event.stopPropagation()
                    dragRef.current = { kind: 'node', id: node.id, lastX: event.clientX, lastY: event.clientY, moved: false }
                  }}
                >
                  <span>{node.label}</span>
                </div>
              )}
            </foreignObject>
          ))}
        </g>
      </svg>
    </div>
  )
}

type GraphNode = {
  id: string
  label: string
  kind: string
  x: number
  y: number
  width: number
  height: number
  file?: DisplayFile
}

function buildGraphModel(files: DisplayFile[]) {
  const nodes: GraphNode[] = [
    { id: 'root', label: '知识库', kind: 'root', x: 460, y: 72, width: 132, height: 54 },
    { id: 'document', label: '文档', kind: 'group document', x: 270, y: 178, width: 132, height: 50 },
    { id: 'spreadsheet', label: '表格', kind: 'group spreadsheet', x: 650, y: 178, width: 132, height: 50 },
  ]
  const edges = [{ from: 'root', to: 'document' }, { from: 'root', to: 'spreadsheet' }]
  const groups = new Map<string, DisplayFile[]>()
  files.slice(0, 28).forEach((file) => {
    const key = `${fileCategory(file)}:${file.extension ?? extensionOf(file.filename)}`
    groups.set(key, [...(groups.get(key) ?? []), file])
  })
  placeExtensionNodes(nodes, edges, Array.from(groups.entries()).filter(([key]) => key.startsWith('document:')), 'document', 270)
  placeExtensionNodes(nodes, edges, Array.from(groups.entries()).filter(([key]) => key.startsWith('spreadsheet:')), 'spreadsheet', 650)
  const nodesById = new Map(nodes.map((node) => [node.id, node]))
  return { nodes, edges, nodesById }
}

function placeExtensionNodes(
  nodes: GraphNode[],
  edges: Array<{ from: string; to: string }>,
  entries: Array<[string, DisplayFile[]]>,
  parentId: string,
  centerX: number,
) {
  entries.forEach(([key, items], extensionIndex) => {
    const extension = key.split(':')[1]
    const x = centerX + (extensionIndex - (entries.length - 1) / 2) * 132
    const extensionId = `${parentId}-${extension}`
    nodes.push({ id: extensionId, label: extension.toUpperCase().replace('.', ''), kind: 'extension', x, y: 300, width: 92, height: 42 })
    edges.push({ from: parentId, to: extensionId })
    items.slice(0, 5).forEach((file, fileIndex) => {
      const row = Math.floor(fileIndex / 2)
      const column = fileIndex % 2
      nodes.push({
        id: `file-${file.id}`,
        label: file.filename,
        kind: file.isLocal ? 'file pending' : 'file',
        x: x + (column === 0 ? -54 : 54),
        y: 414 + row * 68,
        width: 142,
        height: 48,
        file,
      })
      edges.push({ from: extensionId, to: `file-${file.id}` })
    })
  })
}

async function buildLocalFile(file: File, index: number): Promise<DisplayFile> {
  const extension = extensionOf(file.name)
  if (!['.md', '.markdown', '.txt', '.xlsx', '.pdf'].includes(extension)) {
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
  if (extension === '.xlsx') {
    const workbook = XLSX.read(await file.arrayBuffer(), { type: 'array' })
    const sheets = workbook.SheetNames.slice(0, 20).map((name) => {
      const sheet = workbook.Sheets[name]
      const range = sheet['!ref'] ? XLSX.utils.decode_range(sheet['!ref']) : null
      const rowCount = range ? range.e.r - range.s.r + 1 : 0
      const columnCount = range ? range.e.c - range.s.c + 1 : 0
      const rows = XLSX.utils.sheet_to_json<string[]>(sheet, { header: 1, raw: false, defval: '' }).slice(0, 200)
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

function isTextPreview(preview: AiwikiFilePreview): preview is AiwikiTextPreview {
  return preview.kind === 'text'
}

function isSpreadsheetPreview(preview: AiwikiFilePreview): preview is AiwikiSpreadsheetPreview {
  return preview.kind === 'spreadsheet'
}

function auditActionLabel(action: string): string {
  return {
    upload: '上传',
    execute: '执行任务',
    delete: '删除',
  }[action] ?? action
}

function extractAuditFilenames(item: AiwikiAuditLog): string[] {
  const filenames = item.metadata?.filenames
  if (Array.isArray(filenames)) {
    return filenames.filter((filename): filename is string => typeof filename === 'string' && Boolean(filename.trim()))
  }
  return item.target_filename
    .split(',')
    .map((filename) => filename.trim())
    .filter(Boolean)
}

function fileCategory(file: DisplayFile): FileCategory {
  const extension = file.extension ?? extensionOf(file.filename)
  return extension === '.xlsx' ? 'spreadsheet' : 'document'
}

function categoryLabel(category: FileCategory): string {
  return category === 'spreadsheet' ? '表格' : '文档'
}

function fileIcon(file: DisplayFile) {
  const extension = file.extension ?? extensionOf(file.filename)
  if (extension === '.pdf') return <FilePdfOutlined />
  if (extension === '.xlsx') return <TableOutlined />
  if (extension === '.md' || extension === '.markdown') return <FileMarkdownOutlined />
  return <FileTextOutlined />
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
