import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Drawer,
  Empty,
  Flex,
  Input,
  List,
  Pagination,
  Popconfirm,
  Progress,
  Segmented,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { DeleteOutlined, DownloadOutlined, EditOutlined, PlusOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import { listAiwikiJobs, type AiwikiJobSummary } from '../../lib/aiwiki'
import {
  createSeedMatrixJob,
  deleteSeedMatrixJob,
  downloadSeedMatrixCsv,
  getSeedMatrixJob,
  getSeedMatrixResult,
  listSeedMatrixJobs,
  updateSeedMatrixJob,
  type SeedMatrixJob,
  type SeedMatrixJobSummary,
  type SeedMatrixResult,
} from '../../lib/seedMatrix'
import { resolveErrorMessage } from '../../lib/errorMessage'
import { formatDateTime, progressEventColor, statusMeta } from '../aiwiki/helpers'
import { SEED_MATRIX_MODES, seedMatrixModeLabel, type SeedMatrixModeId } from '../../lib/workflowModes'
import './GrowthWorkflow.css'

type MatrixRow = Record<string, string>

const ACTIVE_STATUSES = new Set(['queued', 'running'])
const TASK_PAGE_SIZE = 5

export default function SeedMatrixPage({
  mode = 'standard',
  sourceAiwikiJobId,
  onOpenProductionStage,
}: {
  mode?: SeedMatrixModeId
  sourceAiwikiJobId?: string | null
  embedded?: boolean
  onOpenProductionStage?: () => void
}) {
  const { message, modal } = App.useApp()
  const [draftMode, setDraftMode] = useState<SeedMatrixModeId>(mode)
  const draftModeConfig = SEED_MATRIX_MODES[draftMode]
  const [aiwikiJobs, setAiwikiJobs] = useState<AiwikiJobSummary[]>([])
  const [aiwikiJobsPage, setAiwikiJobsPage] = useState(1)
  const [aiwikiJobsTotal, setAiwikiJobsTotal] = useState(0)
  const [matrixJobs, setMatrixJobs] = useState<SeedMatrixJobSummary[]>([])
  const [matrixJobsPage, setMatrixJobsPage] = useState(1)
  const [matrixJobsTotal, setMatrixJobsTotal] = useState(0)
  const [selectedAiwikiJobId, setSelectedAiwikiJobId] = useState<string | null>(sourceAiwikiJobId ?? null)
  const [activeJob, setActiveJob] = useState<SeedMatrixJob | null>(null)
  const [result, setResult] = useState<SeedMatrixResult | null>(null)
  const [activeRow, setActiveRow] = useState<MatrixRow | null>(null)
  const [creating, setCreating] = useState(true)
  const [loadingInputs, setLoadingInputs] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [dayFilter, setDayFilter] = useState<string>('全部')
  const [accountFilter, setAccountFilter] = useState<string>('全部')

  const loadAiwikiJobs = useCallback(async (page = aiwikiJobsPage) => {
    setLoadingInputs(true)
    try {
      const data = await listAiwikiJobs({
        limit: TASK_PAGE_SIZE,
        offset: (page - 1) * TASK_PAGE_SIZE,
        status: 'completed',
      })
      setAiwikiJobs(data.items)
      setAiwikiJobsTotal(data.total)
      setSelectedAiwikiJobId((current) => current ?? data.items[0]?.id ?? null)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingInputs(false)
    }
  }, [aiwikiJobsPage])

  const loadMatrixJobs = useCallback(async (page = matrixJobsPage) => {
    setLoadingHistory(true)
    try {
      const data = await listSeedMatrixJobs({
        limit: TASK_PAGE_SIZE,
        offset: (page - 1) * TASK_PAGE_SIZE,
        source_aiwiki_job_id: sourceAiwikiJobId ?? undefined,
      })
      setMatrixJobs(data.items)
      setMatrixJobsTotal(data.total)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingHistory(false)
    }
  }, [matrixJobsPage, sourceAiwikiJobId])

  const refreshJob = useCallback(async (jobId: string, silent = false) => {
    if (!silent) setRefreshing(true)
    try {
      const job = await getSeedMatrixJob(jobId)
      setActiveJob(job)
      setError(null)
      if (job.status === 'completed') {
        setResult(await getSeedMatrixResult(jobId))
        void loadMatrixJobs()
      } else if (job.status === 'failed') {
        setResult(null)
        void loadMatrixJobs()
      }
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      if (!silent) message.error(text)
    } finally {
      if (!silent) setRefreshing(false)
    }
  }, [loadMatrixJobs, message])

  useEffect(() => {
    setDraftMode(mode)
  }, [mode])

  useEffect(() => {
    if (sourceAiwikiJobId) {
      setSelectedAiwikiJobId(sourceAiwikiJobId)
    }
    void loadAiwikiJobs()
    void loadMatrixJobs()
  }, [loadAiwikiJobs, loadMatrixJobs, sourceAiwikiJobId])

  useEffect(() => {
    if (!activeJob?.id || !ACTIVE_STATUSES.has(activeJob.status)) return
    const timer = window.setInterval(() => {
      void refreshJob(activeJob.id, true)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [activeJob?.id, activeJob?.status, refreshJob])

  const filteredRows = useMemo(() => {
    const rows = result?.rows ?? []
    const text = query.trim().toLowerCase()
    return rows.filter((row) => {
      if (dayFilter !== '全部' && row.day !== dayFilter) return false
      if (accountFilter !== '全部' && row.primary_account_type !== accountFilter) return false
      if (!text) return true
      return ['seed_id', 'content_pool', 'topic', 'pain_point', 'solution', 'hook', 'mother_topic_prompt']
        .some((key) => (row[key] ?? '').toLowerCase().includes(text))
    })
  }, [accountFilter, dayFilter, query, result?.rows])

  const dayOptions = useMemo(
    () => ['全部', ...Array.from(new Set((result?.rows ?? []).map((row) => row.day).filter(Boolean)))],
    [result?.rows],
  )
  const accountOptions = useMemo(
    () => ['全部', ...Array.from(new Set((result?.rows ?? []).map((row) => row.primary_account_type).filter(Boolean)))],
    [result?.rows],
  )

  const columns: ColumnsType<MatrixRow> = [
    { title: '天', dataIndex: 'day', width: 72, fixed: 'left' },
    { title: '每日文章数', dataIndex: 'slot', width: 112 },
    { title: '选题ID', dataIndex: 'seed_id', width: 96 },
    { title: '内容池', dataIndex: 'content_pool', width: 180, ellipsis: true },
    { title: '选题', dataIndex: 'topic', width: 280, ellipsis: true },
    { title: '痛点', dataIndex: 'pain_point', width: 260, ellipsis: true },
    { title: '解决方案', dataIndex: 'solution', width: 260, ellipsis: true },
    { title: '账号', dataIndex: 'primary_account_type', width: 120 },
    { title: '预计篇数', dataIndex: 'expected_article_count', width: 96 },
    {
      title: '操作',
      key: 'action',
      width: 90,
      fixed: 'right',
      render: (_, row) => <Button size="small" onClick={() => setActiveRow(row)}>详情</Button>,
    },
  ]

  const startCreate = () => {
    setCreating(true)
    setActiveJob(null)
    setResult(null)
    setActiveRow(null)
    setError(null)
  }

  const submit = async () => {
    if (!selectedAiwikiJobId) {
      setError('请先选择一个已完成的知识库作为输入')
      return
    }
    setSubmitting(true)
    setError(null)
    setResult(null)
    try {
      const created = await createSeedMatrixJob({
        ...draftModeConfig.defaults,
        hooks: draftModeConfig.defaults.hooks,
        source_aiwiki_job_id: selectedAiwikiJobId,
      })
      setCreating(false)
      setActiveJob(created)
      message.success('选题任务已提交')
      void loadMatrixJobs()
      void refreshJob(created.id, true)
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    } finally {
      setSubmitting(false)
    }
  }

  const selectMatrixJob = async (jobId: string) => {
    setCreating(false)
    setRefreshing(true)
    setResult(null)
    setActiveRow(null)
    setError(null)
    try {
      const job = await getSeedMatrixJob(jobId)
      setActiveJob(job)
      setSelectedAiwikiJobId(job.source_aiwiki_job_id)
      if (job.status === 'completed') {
        setResult(await getSeedMatrixResult(jobId))
      }
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    } finally {
      setRefreshing(false)
    }
  }

  const deleteMatrixJob = async (jobId: string) => {
    try {
      await deleteSeedMatrixJob(jobId)
      message.success('选题任务已删除')
      setMatrixJobs((items) => items.filter((item) => item.id !== jobId))
      if (activeJob?.id === jobId) {
        setActiveJob(null)
        setResult(null)
        setActiveRow(null)
        setCreating(true)
      }
      void loadMatrixJobs()
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    }
  }

  const renameMatrixJob = (job: SeedMatrixJobSummary) => {
    let nextTitle = matrixJobTitle(job)
    modal.confirm({
      title: '编辑任务名称',
      content: (
        <Input
          autoFocus
          defaultValue={nextTitle}
          maxLength={255}
          placeholder={seedMatrixModeLabel(job.params)}
          onChange={(event) => {
            nextTitle = event.target.value
          }}
        />
      ),
      okText: '保存',
      cancelText: '取消',
      onOk: async () => {
        const updated = await updateSeedMatrixJob(job.id, { title: nextTitle })
        setMatrixJobs((items) => items.map((item) => (
          item.id === updated.id ? { ...item, title: updated.title } : item
        )))
        if (activeJob?.id === updated.id) {
          setActiveJob(updated)
        }
        message.success('任务名称已更新')
      },
    })
  }

  return (
    <div className="growth-workflow">
      <TaskRail
        activeJobId={creating ? null : activeJob?.id ?? null}
        jobs={matrixJobs}
        loading={loadingHistory}
        page={matrixJobsPage}
        pageSize={TASK_PAGE_SIZE}
        total={matrixJobsTotal}
        onCreate={startCreate}
        onDelete={(jobId) => void deleteMatrixJob(jobId)}
        onPageChange={(page) => {
          setMatrixJobsPage(page)
          void loadMatrixJobs(page)
        }}
        onRefresh={() => void loadMatrixJobs()}
        onRename={renameMatrixJob}
        onSelect={(jobId) => void selectMatrixJob(jobId)}
      />

      <main className="growth-main-stage">
        {creating ? (
          <CreateMatrixTask
            aiwikiJobs={aiwikiJobs}
            aiwikiJobsPage={aiwikiJobsPage}
            aiwikiJobsPageSize={TASK_PAGE_SIZE}
            aiwikiJobsTotal={aiwikiJobsTotal}
            loadingInputs={loadingInputs}
            mode={draftMode}
            selectedAiwikiJobId={selectedAiwikiJobId}
            submitting={submitting}
            error={error}
            onRefreshInputs={() => void loadAiwikiJobs()}
            onAiwikiJobsPageChange={(page) => {
              setAiwikiJobsPage(page)
              void loadAiwikiJobs(page)
            }}
            onSelectAiwikiJob={setSelectedAiwikiJobId}
            onSubmit={() => void submit()}
          />
        ) : activeJob && ACTIVE_STATUSES.has(activeJob.status) ? (
          <GenerationStatus
            title="正在生成选题"
            job={activeJob}
            refreshing={refreshing}
            onRefresh={() => void refreshJob(activeJob.id)}
          />
        ) : activeJob ? (
          <MatrixTaskDetail
            job={activeJob}
            result={result}
            filteredRows={filteredRows}
            columns={columns}
            dayFilter={dayFilter}
            dayOptions={dayOptions}
            accountFilter={accountFilter}
            accountOptions={accountOptions}
            query={query}
            error={error}
            onAccountFilterChange={setAccountFilter}
            onDayFilterChange={setDayFilter}
            onDownload={() => void downloadSeedMatrixCsv(activeJob.id)}
            onOpenProductionStage={onOpenProductionStage}
            onQueryChange={setQuery}
            onRefresh={() => void refreshJob(activeJob.id)}
          />
        ) : (
          <div className="growth-empty-state">
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="新建一个选题任务，或从左侧选择历史任务" />
            <Button type="primary" icon={<PlusOutlined />} onClick={startCreate}>新建选题任务</Button>
          </div>
        )}
      </main>

      <Drawer
        title={activeRow?.topic ?? '选题详情'}
        open={Boolean(activeRow)}
        onClose={() => setActiveRow(null)}
        width={620}
      >
        {activeRow && <SeedDetail row={activeRow} />}
      </Drawer>
    </div>
  )
}

function TaskRail({
  activeJobId,
  jobs,
  loading,
  page,
  pageSize,
  total,
  onCreate,
  onDelete,
  onPageChange,
  onRefresh,
  onRename,
  onSelect,
}: {
  activeJobId: string | null
  jobs: SeedMatrixJobSummary[]
  loading: boolean
  page: number
  pageSize: number
  total: number
  onCreate: () => void
  onDelete: (jobId: string) => void
  onPageChange: (page: number) => void
  onRefresh: () => void
  onRename: (job: SeedMatrixJobSummary) => void
  onSelect: (jobId: string) => void
}) {
  return (
    <aside className="growth-task-rail">
      <Flex align="center" justify="space-between" gap={10} className="growth-task-rail-head">
        <div>
          <Typography.Text className="growth-eyebrow">Topic Tasks</Typography.Text>
          <Typography.Title level={5} className="growth-rail-title">选题任务</Typography.Title>
        </div>
        <Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={onRefresh} />
      </Flex>
      <Button block type="primary" icon={<PlusOutlined />} onClick={onCreate}>新建选题任务</Button>
      <List
        className="growth-task-list"
        loading={loading}
        dataSource={jobs}
        locale={{ emptyText: '暂无选题任务' }}
        renderItem={(job) => (
          <List.Item>
            <button
              type="button"
              className={job.id === activeJobId ? 'growth-task-card is-active' : 'growth-task-card'}
              onClick={() => onSelect(job.id)}
            >
              <span className="growth-task-card-title">{matrixJobTitle(job)}</span>
              <span className="growth-task-card-meta">
                输入 {shortId(job.source_aiwiki_job_id)} · {formatDateTime(job.created_at)}
              </span>
              <span className="growth-task-card-tags">
                <Tag color={statusColor(job.status)}>{statusMeta(job.status).label}</Tag>
                <Tag>选题数量 {Number(job.summary.seed_count ?? job.params.expected_seed_count ?? 0)}</Tag>
                <Tag>每日文章数 {Number(job.params.slots_per_day ?? 0)}</Tag>
              </span>
              <Popconfirm
                title="删除任务"
                description="会删除该选题任务记录和 CSV 文件。"
                okText="删除"
                cancelText="取消"
                okButtonProps={{ danger: true }}
                onConfirm={(event) => {
                  event?.stopPropagation()
                  onDelete(job.id)
                }}
                onCancel={(event) => event?.stopPropagation()}
              >
                <span
                  className="growth-task-card-delete"
                  role="button"
                  tabIndex={0}
                  aria-label="删除选题任务"
                  onClick={(event) => event.stopPropagation()}
                  onKeyDown={(event) => event.stopPropagation()}
                >
                  <DeleteOutlined />
                </span>
              </Popconfirm>
              <span
                className="growth-task-card-edit"
                role="button"
                tabIndex={0}
                aria-label="编辑选题任务名称"
                onClick={(event) => {
                  event.stopPropagation()
                  onRename(job)
                }}
                onKeyDown={(event) => event.stopPropagation()}
              >
                <EditOutlined />
              </span>
            </button>
          </List.Item>
        )}
      />
      {total > pageSize && (
        <Pagination
          size="small"
          simple
          current={page}
          pageSize={pageSize}
          total={total}
          onChange={onPageChange}
        />
      )}
    </aside>
  )
}

function CreateMatrixTask({
  aiwikiJobs,
  aiwikiJobsPage,
  aiwikiJobsPageSize,
  aiwikiJobsTotal,
  loadingInputs,
  mode,
  selectedAiwikiJobId,
  submitting,
  error,
  onAiwikiJobsPageChange,
  onRefreshInputs,
  onSelectAiwikiJob,
  onSubmit,
}: {
  aiwikiJobs: AiwikiJobSummary[]
  aiwikiJobsPage: number
  aiwikiJobsPageSize: number
  aiwikiJobsTotal: number
  loadingInputs: boolean
  mode: SeedMatrixModeId
  selectedAiwikiJobId: string | null
  submitting: boolean
  error: string | null
  onAiwikiJobsPageChange: (page: number) => void
  onRefreshInputs: () => void
  onSelectAiwikiJob: (jobId: string) => void
  onSubmit: () => void
}) {
  const modeConfig = SEED_MATRIX_MODES[mode]
  return (
    <section className="growth-create-panel">
      <div className="growth-panel-heading">
        <Typography.Text className="growth-eyebrow">新建任务</Typography.Text>
        <Typography.Title level={3}>生成选题策略</Typography.Title>
        <Typography.Paragraph>
          选择一个已完成的知识库作为输入，系统会使用默认配置生成选题策略。
        </Typography.Paragraph>
      </div>

      {error && <Alert type="error" showIcon message={error} />}
      <div className="growth-config-section">
        <Flex align="center" justify="space-between" gap={12} className="growth-step-heading">
          <div className="growth-step-title">
            <Typography.Title level={5}>选择输入知识库</Typography.Title>
          </div>
          <Button size="small" icon={<ReloadOutlined />} loading={loadingInputs} onClick={onRefreshInputs} />
        </Flex>
        <List
          className="growth-input-source-list"
          loading={loadingInputs}
          dataSource={aiwikiJobs}
          locale={{ emptyText: '暂无已完成知识库' }}
          renderItem={(job) => (
            <List.Item>
              <button
                type="button"
                className={job.id === selectedAiwikiJobId ? 'growth-input-source is-active' : 'growth-input-source'}
                onClick={() => onSelectAiwikiJob(job.id)}
              >
                <span>{job.title || job.files[0]?.filename || shortId(job.id)}</span>
              </button>
            </List.Item>
          )}
        />
        {aiwikiJobsTotal > aiwikiJobsPageSize && (
          <Pagination
            size="small"
            simple
            current={aiwikiJobsPage}
            pageSize={aiwikiJobsPageSize}
            total={aiwikiJobsTotal}
            onChange={onAiwikiJobsPageChange}
          />
        )}
        <div className="growth-step-actions">
          <Button
            type="primary"
            size="large"
            icon={<PlayCircleOutlined />}
            loading={submitting}
            disabled={!selectedAiwikiJobId}
            onClick={onSubmit}
          >
            {modeConfig.buttonText}
          </Button>
        </div>
      </div>
    </section>
  )
}

function MatrixTaskDetail({
  job,
  result,
  filteredRows,
  columns,
  dayFilter,
  dayOptions,
  accountFilter,
  accountOptions,
  query,
  error,
  onAccountFilterChange,
  onDayFilterChange,
  onDownload,
  onOpenProductionStage,
  onQueryChange,
  onRefresh,
}: {
  job: SeedMatrixJob
  result: SeedMatrixResult | null
  filteredRows: MatrixRow[]
  columns: ColumnsType<MatrixRow>
  dayFilter: string
  dayOptions: string[]
  accountFilter: string
  accountOptions: string[]
  query: string
  error: string | null
  onAccountFilterChange: (value: string) => void
  onDayFilterChange: (value: string) => void
  onDownload: () => void
  onOpenProductionStage?: () => void
  onQueryChange: (value: string) => void
  onRefresh: () => void
}) {
  const failed = job.status === 'failed'
  return (
    <section className="growth-result-panel">
      <Flex align="flex-start" justify="space-between" wrap="wrap" gap={12}>
        <div className="growth-panel-heading">
          <Typography.Text className="growth-eyebrow">选题任务详情</Typography.Text>
          <Typography.Title level={3}>{matrixJobTitle(job)}</Typography.Title>
          <Typography.Paragraph>配置已锁定。你可以查看结果表，或基于这张策略表进入稿件生产。</Typography.Paragraph>
        </div>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={onRefresh}>刷新</Button>
          {result && <Button icon={<DownloadOutlined />} onClick={onDownload}>下载 CSV</Button>}
          {result && onOpenProductionStage && <Button type="primary" onClick={onOpenProductionStage}>用选题生成稿件</Button>}
        </Space>
      </Flex>

      <div className="growth-readonly-summary">
        <ConfigItem label="输入知识库" value={shortId(job.source_aiwiki_job_id)} />
        <ConfigItem label="生成模式" value={seedMatrixModeLabel(job.params)} />
        <ConfigItem label="选题数量" value={String(Number(job.params.expected_seed_count ?? result?.summary.seed_count ?? 0))} />
        <ConfigItem label="每日文章数" value={String(Number(job.params.slots_per_day ?? 0))} />
        <ConfigItem label="状态" value={statusMeta(job.status).label} />
        <ConfigItem label="创建时间" value={formatDateTime(job.created_at)} />
      </div>

      {error && <Alert type="error" showIcon message={error} />}
      {job.message && <Alert type={failed ? 'error' : 'info'} showIcon message={job.message} />}

      {result ? (
        <div className="growth-table-section">
          <Flex align="center" justify="space-between" wrap="wrap" gap={12} className="growth-table-toolbar">
            <Typography.Title level={4}>策略表结果</Typography.Title>
            <Space wrap>
              <Input.Search
                placeholder="搜索选题、痛点、方案"
                allowClear
                value={query}
                onSearch={onQueryChange}
                onChange={(event) => onQueryChange(event.target.value)}
                style={{ width: 260 }}
              />
              <Segmented value={dayFilter} onChange={(value) => onDayFilterChange(String(value))} options={dayOptions} />
              <Segmented value={accountFilter} onChange={(value) => onAccountFilterChange(String(value))} options={accountOptions} />
            </Space>
          </Flex>
          <div className="growth-readonly-summary is-compact">
            <ConfigItem label="选题数量" value={String(Number(result.summary.seed_count ?? 0))} />
            <ConfigItem label="覆盖天数" value={String(Number(result.summary.day_count ?? 0))} />
            <ConfigItem label="预计文章" value={String(Number(result.summary.expected_article_total ?? 0))} />
            <ConfigItem label="账号类型" value={String(Number(result.summary.account_type_count ?? 0))} />
          </div>
          <Table
            size="small"
            rowKey={(row) => row.seed_id}
            columns={columns}
            dataSource={filteredRows}
            scroll={{ x: 1500 }}
            pagination={{ pageSize: 10, showSizeChanger: true }}
          />
        </div>
      ) : (
        <div className="growth-empty-state">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={failed ? '选题任务生成失败，可查看运行详情排查原因' : '任务完成后这里会展示策略表'}
          />
        </div>
      )}

      <RunDetails job={job} />
    </section>
  )
}

function GenerationStatus({
  title,
  job,
  refreshing,
  onRefresh,
}: {
  title: string
  job: SeedMatrixJob
  refreshing: boolean
  onRefresh: () => void
}) {
  const meta = statusMeta(job.status)
  const latestEvent = latestProgressSummary(job)
  return (
    <section className="growth-generation-panel">
      <div className="growth-generation-card">
        <Typography.Text className="growth-eyebrow">生成中</Typography.Text>
        <Typography.Title level={3}>{title}</Typography.Title>
        <Progress percent={meta.percent} status={meta.status} />
        <Typography.Text className="growth-generation-current">
          {latestEvent || job.message || '任务已进入队列，正在准备生成。'}
        </Typography.Text>
        <Space wrap>
          <Tag color="blue">{statusMeta(job.status).label}</Tag>
          {job.queue_position !== null && <Tag>排队 {job.queue_position}</Tag>}
          <Tag>输入 {shortId(job.source_aiwiki_job_id)}</Tag>
        </Space>
        <Button icon={<ReloadOutlined />} loading={refreshing} onClick={onRefresh}>刷新状态</Button>
      </div>
      <RunDetails job={job} />
    </section>
  )
}

function RunDetails({ job }: { job: SeedMatrixJob }) {
  const events = Array.isArray(job.progress?.events) ? job.progress.events : []
  return (
    <details className="growth-run-details">
      <summary>查看运行详情</summary>
      <Typography.Text type="secondary">进度事件</Typography.Text>
      <List
        size="small"
        dataSource={events}
        locale={{ emptyText: '暂无进度事件' }}
        renderItem={(item) => (
          <List.Item>
            <Flex vertical gap={4} style={{ width: '100%' }}>
              <Space wrap>
                <Tag color={progressEventColor(item.event)}>{item.event}</Tag>
                <Typography.Text strong={item.summary === '任务完成'}>{item.step}</Typography.Text>
              </Space>
              <Typography.Text type="secondary">{item.summary}</Typography.Text>
            </Flex>
          </List.Item>
        )}
      />
      <Typography.Text type="secondary">OpenCode 原始日志</Typography.Text>
      <pre className="growth-log-tail">
        {job.log_tail.length ? job.log_tail.join('\n') : '暂无日志'}
      </pre>
    </details>
  )
}

function ConfigItem({ label, value }: { label: string; value: string }) {
  return (
    <span className="growth-config-item">
      <small>{label}</small>
      <strong>{value || '-'}</strong>
    </span>
  )
}

function SeedDetail({ row }: { row: MatrixRow }) {
  const fields = [
    ['seed_id', '选题ID'],
    ['day', '天'],
    ['slot', '每日文章数'],
    ['content_pool', '内容池'],
    ['topic', '选题'],
    ['pain_point', '痛点'],
    ['solution', '解决方案'],
    ['hook', '行动引导'],
    ['mother_topic_prompt', '写作要求'],
    ['variant_ids_to_generate', '多版本稿件 ID'],
    ['expected_article_count', '预计篇数'],
    ['primary_account_type', '主账号类型'],
    ['backup_account_types', '备选账号类型'],
    ['hook_package', '行动引导包'],
    ['primary_hook_ids', '行动引导 ID'],
    ['cta_strategy', '转化策略'],
    ['publishing_note', '发布备注'],
  ]
  return (
    <Flex vertical gap={14}>
      {fields.map(([key, label]) => (
        <Flex key={key} vertical gap={4}>
          <Typography.Text type="secondary">{label}</Typography.Text>
          <Typography.Text>{row[key] || '-'}</Typography.Text>
        </Flex>
      ))}
    </Flex>
  )
}

function latestProgressSummary(job: SeedMatrixJob): string {
  const events = Array.isArray(job.progress?.events) ? job.progress.events : []
  return events.at(-1)?.summary || job.progress?.current_step || ''
}

function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}...` : value
}

function matrixJobTitle(job: Pick<SeedMatrixJobSummary, 'title' | 'params'>): string {
  return job.title || seedMatrixModeLabel(job.params)
}

function statusColor(status: SeedMatrixJob['status']) {
  if (status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  return 'blue'
}
