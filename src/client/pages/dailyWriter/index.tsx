import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Empty,
  Flex,
  Image,
  Input,
  InputNumber,
  List,
  Popconfirm,
  Progress,
  Segmented,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  DeleteOutlined,
  DownloadOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown'
import type { Components, UrlTransform } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  getSeedMatrixResult,
  listSeedMatrixJobs,
  type SeedMatrixJobSummary,
  type SeedMatrixResult,
} from '../../lib/seedMatrix'
import {
  createDailyWriterJob,
  deleteDailyWriterJob,
  downloadDailyWriterResult,
  getDailyWriterArtworkBlob,
  getDailyWriterJob,
  getDailyWriterResult,
  listDailyWriterJobs,
  type DailyWriterArtworkAsset,
  type DailyWriterJob,
  type DailyWriterJobSummary,
  type DailyWriterResult,
} from '../../lib/dailyWriter'
import { resolveErrorMessage } from '../../lib/errorMessage'
import { formatDateTime, progressEventColor, statusMeta } from '../aiwiki/helpers'
import { DAILY_WRITER_MODES, dailyWriterModeLabel, seedMatrixModeLabel, type DailyWriterModeId } from '../../lib/workflowModes'
import '../seedMatrix/GrowthWorkflow.css'

type MatrixRow = Record<string, string>

const ACTIVE_STATUSES = new Set(['queued', 'running'])
const ARTWORK_IMAGE_PREFIX = 'daily-writer-artwork:'
const WRITER_MODE_IDS = Object.keys(DAILY_WRITER_MODES) as DailyWriterModeId[]
export default function DailyWriterPage({
  mode = 'single',
  sourceAiwikiJobId,
}: {
  mode?: DailyWriterModeId
  sourceAiwikiJobId?: string | null
  embedded?: boolean
}) {
  const { message } = App.useApp()
  const pendingSeedIdRef = useRef<string | null>(null)
  const [draftMode, setDraftMode] = useState<DailyWriterModeId>(mode)
  const draftModeConfig = DAILY_WRITER_MODES[draftMode]
  const [matrixJobs, setMatrixJobs] = useState<SeedMatrixJobSummary[]>([])
  const [writerJobs, setWriterJobs] = useState<DailyWriterJobSummary[]>([])
  const [selectedMatrixId, setSelectedMatrixId] = useState<string | null>(null)
  const [matrixResult, setMatrixResult] = useState<SeedMatrixResult | null>(null)
  const [selectedSeedId, setSelectedSeedId] = useState<string | null>(null)
  const [activeJob, setActiveJob] = useState<DailyWriterJob | null>(null)
  const [result, setResult] = useState<DailyWriterResult | null>(null)
  const [loadingMatrices, setLoadingMatrices] = useState(false)
  const [loadingRows, setLoadingRows] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [query, setQuery] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [articleTotal, setArticleTotal] = useState(draftModeConfig.defaultTotal)
  const [generateArtwork, setGenerateArtwork] = useState(false)
  const [creating, setCreating] = useState(true)

  const loadMatrices = useCallback(async () => {
    if (sourceAiwikiJobId === null) {
      setMatrixJobs([])
      setSelectedMatrixId(null)
      return
    }
    setLoadingMatrices(true)
    try {
      const data = await listSeedMatrixJobs({
        limit: 100,
        offset: 0,
        source_aiwiki_job_id: sourceAiwikiJobId ?? undefined,
      })
      const completed = data.items.filter((item) => item.status === 'completed')
      setMatrixJobs(completed)
      setSelectedMatrixId((current) => current ?? completed[0]?.id ?? null)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingMatrices(false)
    }
  }, [sourceAiwikiJobId])

  const loadWriterJobs = useCallback(async () => {
    setLoadingHistory(true)
    try {
      const data = await listDailyWriterJobs({ limit: 50, offset: 0 })
      setWriterJobs(sourceAiwikiJobId
        ? data.items.filter((item) => item.source_aiwiki_job_id === sourceAiwikiJobId)
        : data.items)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingHistory(false)
    }
  }, [sourceAiwikiJobId])

  const loadMatrixRows = useCallback(async (matrixId: string) => {
    setLoadingRows(true)
    setMatrixResult(null)
    setSelectedSeedId(null)
    try {
      const data = await getSeedMatrixResult(matrixId)
      const pendingSeedId = pendingSeedIdRef.current
      setMatrixResult(data)
      setSelectedSeedId(
        pendingSeedId && data.rows.some((row) => row.seed_id === pendingSeedId)
          ? pendingSeedId
          : data.rows[0]?.seed_id ?? null,
      )
      pendingSeedIdRef.current = null
      setError(null)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingRows(false)
    }
  }, [])

  const refreshJob = useCallback(async (jobId: string, silent = false) => {
    if (!silent) setRefreshing(true)
    try {
      const job = await getDailyWriterJob(jobId)
      setActiveJob(job)
      setError(null)
      if (job.status === 'completed' || job.status === 'partial_failed') {
        setResult(await getDailyWriterResult(jobId))
        void loadWriterJobs()
      } else if (job.status === 'failed') {
        setResult(null)
        void loadWriterJobs()
      }
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      if (!silent) message.error(text)
    } finally {
      if (!silent) setRefreshing(false)
    }
  }, [loadWriterJobs, message])

  useEffect(() => {
    setDraftMode(mode)
  }, [mode])

  useEffect(() => {
    void loadMatrices()
    void loadWriterJobs()
  }, [loadMatrices, loadWriterJobs])

  useEffect(() => {
    setCreating(true)
    setActiveJob(null)
    setResult(null)
    setMatrixResult(null)
    setSelectedMatrixId(null)
    setSelectedSeedId(null)
  }, [sourceAiwikiJobId])

  useEffect(() => {
    setArticleTotal(draftModeConfig.defaultTotal)
  }, [draftModeConfig.defaultTotal])

  useEffect(() => {
    if (!selectedMatrixId) return
    void loadMatrixRows(selectedMatrixId)
  }, [loadMatrixRows, selectedMatrixId])

  useEffect(() => {
    if (!activeJob?.id || !ACTIVE_STATUSES.has(activeJob.status)) return
    const timer = window.setInterval(() => {
      void refreshJob(activeJob.id, true)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [activeJob?.id, activeJob?.status, refreshJob])

  const selectedRow = useMemo(
    () => matrixResult?.rows.find((row) => row.seed_id === selectedSeedId) ?? null,
    [matrixResult?.rows, selectedSeedId],
  )

  const filteredRows = useMemo(() => {
    const text = query.trim().toLowerCase()
    return (matrixResult?.rows ?? []).filter((row) => {
      if (!text) return true
      return ['seed_id', 'topic', 'pain_point', 'solution', 'hook', 'mother_topic_prompt']
        .some((key) => (row[key] ?? '').toLowerCase().includes(text))
    })
  }, [matrixResult?.rows, query])

  const selectedMatrix = useMemo(
    () => matrixJobs.find((item) => item.id === selectedMatrixId) ?? null,
    [matrixJobs, selectedMatrixId],
  )

  const productionTotal = draftModeConfig.fixedTotal ?? articleTotal
  const variantCount = Math.max(0, productionTotal - 1)

  const submit = async () => {
    if (!selectedMatrixId || !selectedSeedId) {
      setError('请先选择一个已完成的选题策略和 seed')
      return
    }
    setSubmitting(true)
    setError(null)
    setResult(null)
    try {
      const created = await createDailyWriterJob({
        source_seed_matrix_job_id: selectedMatrixId,
        seed_id: selectedSeedId,
        generate_variants: variantCount > 0,
        variant_count: variantCount,
        generate_artwork: generateArtwork,
      })
      setCreating(false)
      setActiveJob(created)
      message.success('稿件生产任务已提交')
      void loadWriterJobs()
      void refreshJob(created.id, true)
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    } finally {
      setSubmitting(false)
    }
  }

  const selectWriterJob = async (jobId: string) => {
    setCreating(false)
    setRefreshing(true)
    setResult(null)
    try {
      const job = await getDailyWriterJob(jobId)
      setActiveJob(job)
      pendingSeedIdRef.current = job.seed_id
      setSelectedMatrixId(job.source_seed_matrix_job_id)
      setSelectedSeedId(job.seed_id)
      if (job.status === 'completed' || job.status === 'partial_failed') {
        setResult(await getDailyWriterResult(jobId))
      }
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    } finally {
      setRefreshing(false)
    }
  }

  const deleteWriterJob = async (jobId: string) => {
    try {
      await deleteDailyWriterJob(jobId)
      message.success('稿件任务已删除')
      setWriterJobs((items) => items.filter((item) => item.id !== jobId))
      if (activeJob?.id === jobId) {
        setActiveJob(null)
        setResult(null)
        setCreating(true)
      }
      void loadWriterJobs()
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    }
  }

  const columns: ColumnsType<MatrixRow> = [
    { title: 'Seed', dataIndex: 'seed_id', width: 96, fixed: 'left' },
    { title: '选题', dataIndex: 'topic', width: 280, ellipsis: true },
    { title: '痛点', dataIndex: 'pain_point', width: 260, ellipsis: true },
    { title: '解决方案', dataIndex: 'solution', width: 260, ellipsis: true },
    { title: '钩子', dataIndex: 'hook', width: 260, ellipsis: true },
    { title: '账号', dataIndex: 'primary_account_type', width: 120 },
  ]

  const startCreate = () => {
    setCreating(true)
    setActiveJob(null)
    setResult(null)
    setError(null)
    setGenerateArtwork(false)
  }

  return (
    <div className="growth-workflow">
      <WriterTaskRail
        activeJobId={creating ? null : activeJob?.id ?? null}
        jobs={writerJobs}
        loading={loadingHistory}
        onCreate={startCreate}
        onDelete={(jobId) => void deleteWriterJob(jobId)}
        onRefresh={() => void loadWriterJobs()}
        onSelect={(jobId) => void selectWriterJob(jobId)}
      />

      <main className="growth-main-stage">
        {creating ? (
          <CreateWriterTask
            mode={draftMode}
            matrixJobs={matrixJobs}
            matrixResult={matrixResult}
            selectedMatrix={selectedMatrix}
            selectedMatrixId={selectedMatrixId}
            selectedRow={selectedRow}
            selectedSeedId={selectedSeedId}
            columns={columns}
            filteredRows={filteredRows}
            articleTotal={articleTotal}
            generateArtwork={generateArtwork}
            loadingMatrices={loadingMatrices}
            loadingRows={loadingRows}
            submitting={submitting}
            error={error}
            productionTotal={productionTotal}
            variantCount={variantCount}
            onArticleTotalChange={(value) => setArticleTotal(value)}
            onGenerateArtworkChange={setGenerateArtwork}
            onModeChange={setDraftMode}
            onQueryChange={setQuery}
            onRefreshMatrices={() => void loadMatrices()}
            onSelectMatrix={setSelectedMatrixId}
            onSelectSeed={setSelectedSeedId}
            onSubmit={() => void submit()}
          />
        ) : activeJob && ACTIVE_STATUSES.has(activeJob.status) ? (
          <WriterGenerationStatus
            job={activeJob}
            refreshing={refreshing}
            onRefresh={() => void refreshJob(activeJob.id)}
          />
        ) : activeJob ? (
          <WriterTaskDetail
            job={activeJob}
            result={result}
            error={error}
            onCreateFromCurrent={() => {
              pendingSeedIdRef.current = activeJob.seed_id
              setSelectedMatrixId(activeJob.source_seed_matrix_job_id)
              setSelectedSeedId(activeJob.seed_id)
              setCreating(true)
              setResult(null)
              setActiveJob(null)
            }}
            onDownload={() => void downloadDailyWriterResult(activeJob.id)}
            onRefresh={() => void refreshJob(activeJob.id)}
          />
        ) : (
          <div className="growth-empty-state">
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="新建一个稿件任务，或从左侧选择历史任务" />
            <Button type="primary" icon={<PlayCircleOutlined />} onClick={startCreate}>新建稿件任务</Button>
          </div>
        )}
      </main>
    </div>
  )
}

function WriterTaskRail({
  activeJobId,
  jobs,
  loading,
  onCreate,
  onDelete,
  onRefresh,
  onSelect,
}: {
  activeJobId: string | null
  jobs: DailyWriterJobSummary[]
  loading: boolean
  onCreate: () => void
  onDelete: (jobId: string) => void
  onRefresh: () => void
  onSelect: (jobId: string) => void
}) {
  return (
    <aside className="growth-task-rail">
      <Flex align="center" justify="space-between" gap={10} className="growth-task-rail-head">
        <div>
          <Typography.Text className="growth-eyebrow">Article Tasks</Typography.Text>
          <Typography.Title level={5} className="growth-rail-title">稿件任务</Typography.Title>
        </div>
        <Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={onRefresh} />
      </Flex>
      <Button block type="primary" icon={<PlusOutlined />} onClick={onCreate}>新建稿件任务</Button>
      <List
        className="growth-task-list"
        loading={loading}
        dataSource={jobs}
        locale={{ emptyText: '暂无稿件任务' }}
        renderItem={(job) => (
          <List.Item>
            <button
              type="button"
              className={job.id === activeJobId ? 'growth-task-card is-active' : 'growth-task-card'}
              onClick={() => onSelect(job.id)}
            >
              <span className="growth-task-card-title">{String(job.summary.title || job.row.topic || job.id)}</span>
              <span className="growth-task-card-meta">
                Seed {job.seed_id} · {formatDateTime(job.created_at)}
              </span>
              <span className="growth-task-card-tags">
                <Tag color={statusColor(job.status)}>{statusMeta(job.status).label}</Tag>
                <Tag>{dailyWriterModeLabel(job.params)}</Tag>
                <Tag>{articleCountFromParams(job.params)} 篇</Tag>
                {job.summary.artwork_status === 'completed' && <Tag color="purple">含封面插图</Tag>}
                {job.summary.artwork_status === 'failed' && <Tag color="red">插图失败</Tag>}
              </span>
              <Popconfirm
                title="删除任务"
                description="会删除该稿件任务记录和生成文件。"
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
                  aria-label="删除稿件任务"
                  onClick={(event) => event.stopPropagation()}
                  onKeyDown={(event) => event.stopPropagation()}
                >
                  <DeleteOutlined />
                </span>
              </Popconfirm>
            </button>
          </List.Item>
        )}
      />
    </aside>
  )
}

function CreateWriterTask({
  mode,
  matrixJobs,
  matrixResult,
  selectedMatrix,
  selectedMatrixId,
  selectedRow,
  selectedSeedId,
  columns,
  filteredRows,
  articleTotal,
  generateArtwork,
  loadingMatrices,
  loadingRows,
  submitting,
  error,
  productionTotal,
  variantCount,
  onArticleTotalChange,
  onGenerateArtworkChange,
  onModeChange,
  onQueryChange,
  onRefreshMatrices,
  onSelectMatrix,
  onSelectSeed,
  onSubmit,
}: {
  mode: DailyWriterModeId
  matrixJobs: SeedMatrixJobSummary[]
  matrixResult: SeedMatrixResult | null
  selectedMatrix: SeedMatrixJobSummary | null
  selectedMatrixId: string | null
  selectedRow: MatrixRow | null
  selectedSeedId: string | null
  columns: ColumnsType<MatrixRow>
  filteredRows: MatrixRow[]
  articleTotal: number
  generateArtwork: boolean
  loadingMatrices: boolean
  loadingRows: boolean
  submitting: boolean
  error: string | null
  productionTotal: number
  variantCount: number
  onArticleTotalChange: (value: number) => void
  onGenerateArtworkChange: (value: boolean) => void
  onModeChange: (mode: DailyWriterModeId) => void
  onQueryChange: (value: string) => void
  onRefreshMatrices: () => void
  onSelectMatrix: (matrixId: string) => void
  onSelectSeed: (seedId: string) => void
  onSubmit: () => void
}) {
  const modeConfig = DAILY_WRITER_MODES[mode]
  return (
    <section className="growth-create-panel">
      <div className="growth-panel-heading">
        <Typography.Text className="growth-eyebrow">新建任务</Typography.Text>
        <Typography.Title level={3}>生成稿件</Typography.Title>
        <Typography.Paragraph>
          稿件任务以选题任务中的 seed 作为输入。提交后配置会锁定，并沉淀到左侧稿件任务列表。
        </Typography.Paragraph>
      </div>

      <div className="growth-create-grid growth-create-grid-large">
        <section className="growth-config-section">
          <Flex align="center" justify="space-between" gap={12}>
            <Typography.Title level={5}>输入选题任务</Typography.Title>
            <Button size="small" icon={<ReloadOutlined />} loading={loadingMatrices} onClick={onRefreshMatrices} />
          </Flex>
          <List
            className="growth-input-source-list"
            loading={loadingMatrices}
            dataSource={matrixJobs}
            locale={{ emptyText: '暂无已完成选题任务' }}
            renderItem={(job) => (
              <List.Item>
                <button
                  type="button"
                  className={job.id === selectedMatrixId ? 'growth-input-source is-active' : 'growth-input-source'}
                  onClick={() => onSelectMatrix(job.id)}
                >
                  <span>{seedMatrixModeLabel(job.params)}</span>
                  <small>Seed {Number(job.summary.seed_count ?? job.params.expected_seed_count ?? 0)} · {formatDateTime(job.created_at)}</small>
                </button>
              </List.Item>
            )}
          />
          {selectedMatrix && (
            <div className="growth-config-summary">
              <ConfigItem label="选题任务" value={shortId(selectedMatrix.id)} />
              <ConfigItem label="策略类型" value={seedMatrixModeLabel(selectedMatrix.params)} />
              <ConfigItem label="Seed 数量" value={String(Number(selectedMatrix.summary.seed_count ?? selectedMatrix.params.expected_seed_count ?? 0))} />
            </div>
          )}
        </section>

        <section className="growth-config-section">
          <Typography.Title level={5}>选择 Seed</Typography.Title>
          <Input.Search
            placeholder="搜索 seed、选题、痛点、方案"
            allowClear
            onSearch={onQueryChange}
            onChange={(event) => onQueryChange(event.target.value)}
          />
          <Table
            size="small"
            rowKey={(row) => row.seed_id}
            columns={columns}
            dataSource={filteredRows}
            loading={loadingRows}
            scroll={{ x: 1280, y: 300 }}
            pagination={{ pageSize: 6, showSizeChanger: false }}
            rowSelection={{
              type: 'radio',
              selectedRowKeys: selectedSeedId ? [selectedSeedId] : [],
              onChange: (keys) => {
                const nextKey = keys[0]
                if (nextKey) onSelectSeed(String(nextKey))
              },
            }}
            onRow={(row) => ({
              onClick: () => onSelectSeed(row.seed_id),
            })}
          />
          {matrixResult && (
            <div className="growth-config-summary">
              <ConfigItem label="当前 Seed" value={selectedSeedId ?? '-'} />
              <ConfigItem label="选题" value={selectedRow?.topic ?? '-'} />
              <ConfigItem label="预计篇数" value={selectedRow?.expected_article_count ?? '-'} />
            </div>
          )}
        </section>
      </div>

      <section className="growth-config-section">
        <Typography.Title level={5}>生产配置</Typography.Title>
        <Segmented
          block
          value={mode}
          onChange={(value) => onModeChange(value as DailyWriterModeId)}
          options={WRITER_MODE_IDS.map((modeId) => ({
            label: DAILY_WRITER_MODES[modeId].navLabel,
            value: modeId,
          }))}
        />
        <div className="growth-writer-config-row">
          {modeConfig.fixedTotal ? (
            <ConfigItem label="稿件总数" value={`${modeConfig.fixedTotal} 篇`} />
          ) : (
            <label className="growth-number-field">
              <span>稿件总数</span>
              <InputNumber
                min={modeConfig.minTotal}
                max={modeConfig.maxTotal}
                value={articleTotal}
                onChange={(value) => onArticleTotalChange(Number(value ?? modeConfig.defaultTotal))}
              />
            </label>
          )}
          <label className="growth-switch-field">
            <span>生成封面/插图</span>
            <Switch checked={generateArtwork} onChange={onGenerateArtworkChange} />
          </label>
          <ConfigItem label="主稿" value="1 篇" />
          <ConfigItem label="变体" value={`${variantCount} 篇`} />
          <ConfigItem label="合计产出" value={`${productionTotal} 篇`} />
        </div>
      </section>

      {error && <Alert type="error" showIcon message={error} />}
      <div className="growth-primary-action">
        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          loading={submitting}
          disabled={!selectedMatrixId || !selectedSeedId}
          onClick={onSubmit}
        >
          {modeConfig.buttonText}
        </Button>
      </div>
    </section>
  )
}

function WriterGenerationStatus({
  job,
  refreshing,
  onRefresh,
}: {
  job: DailyWriterJob
  refreshing: boolean
  onRefresh: () => void
}) {
  const meta = statusMeta(job.status)
  const latestEvent = latestWriterProgressSummary(job)
  return (
    <section className="growth-generation-panel">
      <div className="growth-generation-card">
        <Typography.Text className="growth-eyebrow">生成中</Typography.Text>
        <Typography.Title level={3}>正在生成稿件</Typography.Title>
        <Progress percent={meta.percent} status={meta.status} />
        <Typography.Text className="growth-generation-current">
          {latestEvent || job.message || '任务已进入队列，正在准备生成。'}
        </Typography.Text>
        <Space wrap>
          <Tag color="blue">{statusMeta(job.status).label}</Tag>
          {job.queue_position !== null && <Tag>排队 {job.queue_position}</Tag>}
          <Tag>Seed {job.seed_id}</Tag>
          <Tag>{dailyWriterModeLabel(job.params)}</Tag>
        </Space>
        <Button icon={<ReloadOutlined />} loading={refreshing} onClick={onRefresh}>刷新状态</Button>
      </div>
      <WriterRunDetails job={job} />
    </section>
  )
}

function WriterTaskDetail({
  job,
  result,
  error,
  onCreateFromCurrent,
  onDownload,
  onRefresh,
}: {
  job: DailyWriterJob
  result: DailyWriterResult | null
  error: string | null
  onCreateFromCurrent: () => void
  onDownload: () => void
  onRefresh: () => void
}) {
  const failed = job.status === 'failed'
  const artworkStatus = job.params.generate_artwork ? String(job.summary.artwork_status ?? '生成中') : '未开启'
  return (
    <section className="growth-result-panel">
      <Flex align="flex-start" justify="space-between" wrap="wrap" gap={12}>
        <div className="growth-panel-heading">
          <Typography.Text className="growth-eyebrow">稿件任务详情</Typography.Text>
          <Typography.Title level={3}>{String(job.summary.title || job.row.topic || `Seed ${job.seed_id}`)}</Typography.Title>
          <Typography.Paragraph>配置已锁定。你可以查看生成结果，或基于同一个 seed 新建一轮稿件任务。</Typography.Paragraph>
        </div>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={onRefresh}>刷新</Button>
          {result && <Button icon={<DownloadOutlined />} onClick={onDownload}>下载 ZIP</Button>}
          <Button type="primary" onClick={onCreateFromCurrent}>基于同一 seed 新建任务</Button>
        </Space>
      </Flex>

      <div className="growth-readonly-summary">
        <ConfigItem label="输入选题任务" value={shortId(job.source_seed_matrix_job_id)} />
        <ConfigItem label="Seed" value={job.seed_id} />
        <ConfigItem label="生产模式" value={dailyWriterModeLabel(job.params)} />
        <ConfigItem label="稿件数量" value={`${articleCountFromParams(job.params)} 篇`} />
        <ConfigItem label="插图" value={artworkStatus} />
        <ConfigItem label="创建时间" value={formatDateTime(job.created_at)} />
      </div>

      {error && <Alert type="error" showIcon message={error} />}
      {job.message && (
        <Alert
          type={failed ? 'error' : job.status === 'partial_failed' ? 'warning' : 'info'}
          showIcon
          message={job.message}
        />
      )}

      {result ? (
        <div className="growth-table-section">
          <ArticlePreviewTabs
            result={result}
            tabBarExtraContent={<Button icon={<DownloadOutlined />} onClick={onDownload}>下载 ZIP</Button>}
          />
        </div>
      ) : (
        <div className="growth-empty-state">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={failed ? '稿件任务生成失败，可查看运行详情排查原因' : '任务完成后这里会展示稿件结果'}
          />
        </div>
      )}

      <WriterRunDetails job={job} />
    </section>
  )
}

function WriterRunDetails({ job }: { job: DailyWriterJob }) {
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

function latestWriterProgressSummary(job: DailyWriterJob): string {
  const events = Array.isArray(job.progress?.events) ? job.progress.events : []
  return events.at(-1)?.summary || job.progress?.current_step || ''
}

function articleCountFromParams(params: Record<string, unknown>): number {
  if (!params.generate_variants) return 1
  return Math.max(1, Number(params.variant_count ?? 0) + 1)
}

function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}...` : value
}

function statusColor(status: DailyWriterJob['status']) {
  if (status === 'completed') return 'green'
  if (status === 'partial_failed') return 'gold'
  if (status === 'failed') return 'red'
  return 'blue'
}

function ArticlePreviewTabs({
  result,
  tabBarExtraContent,
}: {
  result: DailyWriterResult
  tabBarExtraContent: React.ReactNode
}) {
  const artwork = result.artwork
  const artworkAssets = useMemo(
    () => [...artwork.cover_images, ...artwork.inline_images],
    [artwork.cover_images, artwork.inline_images],
  )
  const hasImages = hasArtwork(result)
  const articles = [
    {
      key: 'main',
      label: '主稿',
      markdown: result.markdown,
      illustratedMarkdown: result.illustrated_markdown,
      metadata: result.metadata,
    },
    ...result.variants.map((variant, index) => ({
      key: variant.directory || `variant-${index + 1}`,
      label: variant.angle || `变体 ${index + 1}`,
      markdown: variant.markdown,
      illustratedMarkdown: variant.illustrated_markdown,
      metadata: variant.metadata,
    })),
  ]

  return (
    <Tabs
      tabBarExtraContent={tabBarExtraContent}
      items={[
        ...articles.map((article) => ({
          key: article.key,
          label: article.label,
          children: (
            <Tabs
              size="small"
              items={[
                {
                  key: 'article',
                  label: '无插图',
                  children: (
                    <ArticleMarkdown
                      jobId={result.job_id}
                      markdown={article.markdown}
                      artworkAssets={artworkAssets}
                    />
                  ),
                },
                ...(hasImages
                  ? [
                      {
                        key: 'illustrated',
                        label: '带插图',
                        children: (
                          <ArticleMarkdown
                            jobId={result.job_id}
                            markdown={article.illustratedMarkdown || article.markdown}
                            artworkAssets={artworkAssets}
                          />
                        ),
                      },
                    ]
                  : []),
                {
                  key: 'metadata',
                  label: 'Metadata',
                  children: (
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', overflow: 'auto' }}>
                      {JSON.stringify(article.metadata, null, 2)}
                    </pre>
                  ),
                },
              ]}
            />
          ),
        })),
        ...(hasImages
          ? [
              {
                key: 'artwork',
                label: '封面/插图',
                children: (
                  <ArtworkPanel
                    jobId={result.job_id}
                    coverImages={artwork.cover_images}
                    inlineImages={artwork.inline_images}
                  />
                ),
              },
            ]
          : []),
      ]}
    />
  )
}

function hasArtwork(result: DailyWriterResult): boolean {
  return Boolean(result.artwork.cover_images.length || result.artwork.inline_images.length)
}

function ArticleMarkdown({
  jobId,
  markdown,
  artworkAssets,
}: {
  jobId: string
  markdown: string
  artworkAssets: DailyWriterArtworkAsset[]
}) {
  const assetByKey = useMemo(
    () => new Map(artworkAssets.map((asset) => [asset.key, asset])),
    [artworkAssets],
  )
  const components = useMemo<Components>(() => ({
    img: ({ src, alt }) => {
      const key = parseArtworkImageKey(src)
      const asset = key ? assetByKey.get(key) : null
      if (asset) {
        return (
          <figure style={{ margin: '22px 0' }}>
            <AuthenticatedArtworkImage jobId={jobId} asset={asset} maxHeight={460} />
          </figure>
        )
      }
      return (
        <img
          src={typeof src === 'string' ? src : ''}
          alt={typeof alt === 'string' ? alt : ''}
          loading="lazy"
          style={{ maxWidth: '100%', borderRadius: 8 }}
        />
      )
    },
  }), [assetByKey, jobId])

  return (
    <article style={{ maxWidth: 820 }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={components}
        urlTransform={dailyWriterMarkdownUrlTransform}
      >
        {markdown}
      </ReactMarkdown>
    </article>
  )
}

function parseArtworkImageKey(src: unknown): string | null {
  if (typeof src !== 'string') return null
  return src.startsWith(ARTWORK_IMAGE_PREFIX) ? src.slice(ARTWORK_IMAGE_PREFIX.length) : null
}

const dailyWriterMarkdownUrlTransform: UrlTransform = (url, key, node) => {
  if (key === 'src' && node.tagName === 'img' && url.startsWith(ARTWORK_IMAGE_PREFIX)) {
    return url
  }
  return defaultUrlTransform(url)
}

function ArtworkPanel({
  jobId,
  coverImages,
  inlineImages,
}: {
  jobId: string
  coverImages: DailyWriterArtworkAsset[]
  inlineImages: DailyWriterArtworkAsset[]
}) {
  return (
    <Flex vertical gap={20}>
      <ArtworkImageList title="封面" jobId={jobId} assets={coverImages} />
      <ArtworkImageList title="正文插图" jobId={jobId} assets={inlineImages} />
    </Flex>
  )
}

function ArtworkImageList({
  title,
  jobId,
  assets,
}: {
  title: string
  jobId: string
  assets: DailyWriterArtworkAsset[]
}) {
  if (!assets.length) {
    return (
      <section>
        <Typography.Title level={5} style={{ marginTop: 0 }}>{title}</Typography.Title>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`暂无${title}`} />
      </section>
    )
  }
  return (
    <section>
      <Typography.Title level={5} style={{ marginTop: 0 }}>{title}</Typography.Title>
      <div className="growth-artwork-grid">
        {assets.map((asset) => (
          <div key={asset.key} className="growth-artwork-card">
            <AuthenticatedArtworkImage jobId={jobId} asset={asset} maxHeight={520} />
          </div>
        ))}
      </div>
    </section>
  )
}

function AuthenticatedArtworkImage({
  jobId,
  asset,
  maxHeight = 320,
}: {
  jobId: string
  asset: DailyWriterArtworkAsset
  maxHeight?: number
}) {
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false
    setSrc(null)
    setFailed(false)
    getDailyWriterArtworkBlob(jobId, asset.key)
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setSrc(objectUrl)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [asset.key, jobId])

  if (failed) {
    return <Alert type="warning" showIcon message="图片加载失败" />
  }
  if (!src) {
    return <div style={{ height: Math.min(maxHeight, 180) }} />
  }
  return (
    <Image
      src={src}
      alt={asset.filename}
      style={{ width: '100%', maxHeight, objectFit: 'contain', display: 'block' }}
    />
  )
}
