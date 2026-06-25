import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Empty,
  Flex,
  Image,
  InputNumber,
  List,
  Popconfirm,
  Progress,
  Space,
  Tabs,
  Tag,
  Typography,
} from 'antd'
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
  listDailyWriterJobs,
  type DailyWriterJobSummary,
} from '../../lib/dailyWriter'
import {
  createSocialCardJob,
  deleteSocialCardJob,
  downloadSocialCardResult,
  getSocialCardImageBlob,
  getSocialCardJob,
  getSocialCardResult,
  listSocialCardJobs,
  type SocialCardAsset,
  type SocialCardJob,
  type SocialCardJobSummary,
  type SocialCardPost,
  type SocialCardResult,
} from '../../lib/socialCards'
import { resolveErrorMessage } from '../../lib/errorMessage'
import { dailyWriterModeLabel } from '../../lib/workflowModes'
import { formatDateTime, progressEventColor, statusMeta } from '../aiwiki/helpers'
import '../seedMatrix/GrowthWorkflow.css'

const ACTIVE_STATUSES = new Set(['queued', 'running'])
const SOCIAL_CARD_IMAGE_PREFIX = 'social-card-image:'

type WorkflowRunJob = Pick<SocialCardJob, 'status' | 'queue_position' | 'message' | 'progress' | 'log_tail'>

export default function SocialCardsPage() {
  const { message } = App.useApp()
  const [writerJobs, setWriterJobs] = useState<DailyWriterJobSummary[]>([])
  const [cardJobs, setCardJobs] = useState<SocialCardJobSummary[]>([])
  const [selectedWriterJobId, setSelectedWriterJobId] = useState<string | null>(null)
  const [activeJob, setActiveJob] = useState<SocialCardJob | null>(null)
  const [result, setResult] = useState<SocialCardResult | null>(null)
  const [creating, setCreating] = useState(true)
  const [postCount, setPostCount] = useState(1)
  const [cardsPerPost, setCardsPerPost] = useState(6)
  const [loadingWriters, setLoadingWriters] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadWriterJobs = useCallback(async () => {
    setLoadingWriters(true)
    try {
      const data = await listDailyWriterJobs({ limit: 100, offset: 0 })
      const completed = data.items.filter((item) => item.status === 'completed' || item.status === 'partial_failed')
      setWriterJobs(completed)
      setSelectedWriterJobId((current) => current ?? completed[0]?.id ?? null)
      setError(null)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingWriters(false)
    }
  }, [])

  const loadCardJobs = useCallback(async () => {
    setLoadingHistory(true)
    try {
      const data = await listSocialCardJobs({ limit: 50, offset: 0 })
      setCardJobs(data.items)
      setError(null)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingHistory(false)
    }
  }, [])

  const refreshJob = useCallback(async (jobId: string, silent = false) => {
    if (!silent) setRefreshing(true)
    try {
      const job = await getSocialCardJob(jobId)
      setActiveJob(job)
      setError(null)
      if (job.status === 'completed') {
        setResult(await getSocialCardResult(jobId))
        void loadCardJobs()
      } else if (job.status === 'failed') {
        setResult(null)
        void loadCardJobs()
      }
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      if (!silent) message.error(text)
    } finally {
      if (!silent) setRefreshing(false)
    }
  }, [loadCardJobs, message])

  useEffect(() => {
    void loadWriterJobs()
    void loadCardJobs()
  }, [loadCardJobs, loadWriterJobs])

  useEffect(() => {
    if (!activeJob?.id || !ACTIVE_STATUSES.has(activeJob.status)) return
    const timer = window.setInterval(() => {
      void refreshJob(activeJob.id, true)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [activeJob?.id, activeJob?.status, refreshJob])

  const selectedWriterJob = useMemo(
    () => writerJobs.find((item) => item.id === selectedWriterJobId) ?? null,
    [selectedWriterJobId, writerJobs],
  )

  const startCreate = () => {
    setCreating(true)
    setActiveJob(null)
    setResult(null)
    setError(null)
  }

  const submit = async () => {
    if (!selectedWriterJobId) {
      setError('请先选择一个已完成的稿件任务')
      return
    }
    setSubmitting(true)
    setError(null)
    setResult(null)
    try {
      const created = await createSocialCardJob({
        source_daily_writer_job_id: selectedWriterJobId,
        post_count: postCount,
        cards_per_post: cardsPerPost,
      })
      setCreating(false)
      setActiveJob(created)
      message.success('图文生成任务已提交')
      void loadCardJobs()
      void refreshJob(created.id, true)
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    } finally {
      setSubmitting(false)
    }
  }

  const selectCardJob = async (jobId: string) => {
    setCreating(false)
    setRefreshing(true)
    setResult(null)
    try {
      const job = await getSocialCardJob(jobId)
      setActiveJob(job)
      setSelectedWriterJobId(job.source_daily_writer_job_id)
      if (job.status === 'completed') {
        setResult(await getSocialCardResult(jobId))
      }
      setError(null)
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    } finally {
      setRefreshing(false)
    }
  }

  const deleteJob = async (jobId: string) => {
    try {
      await deleteSocialCardJob(jobId)
      message.success('图文任务已删除')
      setCardJobs((items) => items.filter((item) => item.id !== jobId))
      if (activeJob?.id === jobId) {
        setActiveJob(null)
        setResult(null)
        setCreating(true)
      }
      void loadCardJobs()
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    }
  }

  return (
    <div className="growth-workflow">
      <SocialCardTaskRail
        activeJobId={creating ? null : activeJob?.id ?? null}
        jobs={cardJobs}
        loading={loadingHistory}
        onCreate={startCreate}
        onDelete={(jobId) => void deleteJob(jobId)}
        onRefresh={() => void loadCardJobs()}
        onSelect={(jobId) => void selectCardJob(jobId)}
      />
      <main className="growth-main-stage">
        {creating ? (
          <CreateSocialCardTask
            writerJobs={writerJobs}
            selectedWriterJob={selectedWriterJob}
            selectedWriterJobId={selectedWriterJobId}
            postCount={postCount}
            cardsPerPost={cardsPerPost}
            loadingWriters={loadingWriters}
            submitting={submitting}
            error={error}
            onCardsPerPostChange={setCardsPerPost}
            onPostCountChange={setPostCount}
            onRefreshWriters={() => void loadWriterJobs()}
            onSelectWriterJob={setSelectedWriterJobId}
            onSubmit={() => void submit()}
          />
        ) : activeJob && ACTIVE_STATUSES.has(activeJob.status) ? (
          <SocialCardGenerationStatus
            job={activeJob}
            refreshing={refreshing}
            onRefresh={() => void refreshJob(activeJob.id)}
          />
        ) : activeJob ? (
          <SocialCardTaskDetail
            job={activeJob}
            result={result}
            sourceJob={selectedWriterJob}
            error={error}
            onCreateFromCurrent={() => {
              setSelectedWriterJobId(activeJob.source_daily_writer_job_id)
              setCreating(true)
              setResult(null)
              setActiveJob(null)
            }}
            onDownload={() => void downloadSocialCardResult(activeJob.id)}
            onRefresh={() => void refreshJob(activeJob.id)}
          />
        ) : (
          <div className="growth-empty-state">
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="新建一个图文任务，或从左侧选择历史任务" />
            <Button type="primary" icon={<PlayCircleOutlined />} onClick={startCreate}>新建图文任务</Button>
          </div>
        )}
      </main>
    </div>
  )
}

function SocialCardTaskRail({
  activeJobId,
  jobs,
  loading,
  onCreate,
  onDelete,
  onRefresh,
  onSelect,
}: {
  activeJobId: string | null
  jobs: SocialCardJobSummary[]
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
          <Typography.Text className="growth-eyebrow">Image Posts</Typography.Text>
          <Typography.Title level={5} className="growth-rail-title">图文任务</Typography.Title>
        </div>
        <Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={onRefresh} />
      </Flex>
      <Button block type="primary" icon={<PlusOutlined />} onClick={onCreate}>新建图文任务</Button>
      <List
        className="growth-task-list"
        loading={loading}
        dataSource={jobs}
        locale={{ emptyText: '暂无图文任务' }}
        renderItem={(job) => (
          <List.Item>
            <button
              type="button"
              className={job.id === activeJobId ? 'growth-task-card is-active' : 'growth-task-card'}
              onClick={() => onSelect(job.id)}
            >
              <span className="growth-task-card-title">{String(job.summary.title || job.id)}</span>
              <span className="growth-task-card-meta">
                {formatDateTime(job.created_at)} · {socialCardJobCountLabel(job)}
              </span>
              <span className="growth-task-card-tags">
                <Tag color={statusColor(job.status)}>{statusMeta(job.status).label}</Tag>
                {Number(job.summary.post_count ?? job.params.post_count ?? 0) ? <Tag>图文 {Number(job.summary.post_count ?? job.params.post_count)}</Tag> : null}
                {job.summary.image_count ? <Tag color="green">图片 {Number(job.summary.image_count)}</Tag> : null}
              </span>
              <Popconfirm
                title="删除任务"
                description="会删除该图文任务记录和生成文件。"
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
                  aria-label="删除图文任务"
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

function CreateSocialCardTask({
  writerJobs,
  selectedWriterJob,
  selectedWriterJobId,
  postCount,
  cardsPerPost,
  loadingWriters,
  submitting,
  error,
  onCardsPerPostChange,
  onPostCountChange,
  onRefreshWriters,
  onSelectWriterJob,
  onSubmit,
}: {
  writerJobs: DailyWriterJobSummary[]
  selectedWriterJob: DailyWriterJobSummary | null
  selectedWriterJobId: string | null
  postCount: number
  cardsPerPost: number
  loadingWriters: boolean
  submitting: boolean
  error: string | null
  onCardsPerPostChange: (value: number) => void
  onPostCountChange: (value: number) => void
  onRefreshWriters: () => void
  onSelectWriterJob: (jobId: string) => void
  onSubmit: () => void
}) {
  return (
    <section className="growth-create-panel">
      <div className="growth-panel-heading">
        <Typography.Text className="growth-eyebrow">新建任务</Typography.Text>
        <Typography.Title level={3}>生成图文</Typography.Title>
        <Typography.Paragraph>
          选择一篇已完成稿件作为输入，再生成小红书 3:4 图文卡。
        </Typography.Paragraph>
      </div>

      <div className="growth-create-grid">
        <section className="growth-config-section">
          <Flex align="center" justify="space-between" gap={12}>
            <Typography.Title level={5}>输入稿件</Typography.Title>
            <Button size="small" icon={<ReloadOutlined />} loading={loadingWriters} onClick={onRefreshWriters} />
          </Flex>
          <List
            className="growth-input-source-list"
            loading={loadingWriters}
            dataSource={writerJobs}
            locale={{ emptyText: '暂无已完成稿件' }}
            renderItem={(job) => (
              <List.Item>
                <button
                  type="button"
                  className={job.id === selectedWriterJobId ? 'growth-input-source is-active' : 'growth-input-source'}
                  onClick={() => onSelectWriterJob(job.id)}
                >
                  <span>{String(job.summary.title || job.row.topic || job.id)}</span>
                  <small>{dailyWriterModeLabel(job.params)} · {formatDateTime(job.created_at)}</small>
                </button>
              </List.Item>
            )}
          />
          {selectedWriterJob && (
            <div className="growth-config-summary">
              <ConfigItem label="稿件任务" value={shortId(selectedWriterJob.id)} />
              <ConfigItem label="生产模式" value={dailyWriterModeLabel(selectedWriterJob.params)} />
              <ConfigItem label="稿件数量" value={`${articleCountFromParams(selectedWriterJob.params)} 篇`} />
            </div>
          )}
        </section>

        <section className="growth-config-section">
          <Typography.Title level={5}>生成配置</Typography.Title>
          <div className="growth-social-config-row">
            <label className="growth-number-field">
              <span>图文篇数</span>
              <InputNumber
                min={1}
                max={5}
                value={postCount}
                addonAfter="篇"
                onChange={(value) => onPostCountChange(Number(value ?? 1))}
              />
            </label>
            <label className="growth-number-field">
              <span>每篇卡片数</span>
              <InputNumber
                min={1}
                max={9}
                value={cardsPerPost}
                addonAfter="张"
                onChange={(value) => onCardsPerPostChange(Number(value ?? 6))}
              />
            </label>
          </div>
          <div className="growth-config-summary">
            <ConfigItem label="平台" value="小红书" />
            <ConfigItem label="比例" value="3:4" />
            <ConfigItem label="预计产出" value={`${postCount} 篇 · ${postCount * cardsPerPost} 张`} />
          </div>
        </section>
      </div>

      {error && <Alert type="error" showIcon message={error} />}
      <div className="growth-primary-action">
        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          loading={submitting}
          disabled={!selectedWriterJobId}
          onClick={onSubmit}
        >
          生成图文
        </Button>
      </div>
    </section>
  )
}

function SocialCardGenerationStatus({
  job,
  refreshing,
  onRefresh,
}: {
  job: SocialCardJob
  refreshing: boolean
  onRefresh: () => void
}) {
  const meta = statusMeta(job.status)
  const latestEvent = latestProgressSummary(job)
  return (
    <section className="growth-generation-panel">
      <div className="growth-generation-card">
        <Typography.Text className="growth-eyebrow">生成中</Typography.Text>
        <Typography.Title level={3}>正在生成图文</Typography.Title>
        <Progress percent={meta.percent} status={meta.status} />
        <Typography.Text className="growth-generation-current">
          {latestEvent || job.message || '任务已进入队列，正在准备生成。'}
        </Typography.Text>
        <Space wrap>
          <Tag color="blue">{statusMeta(job.status).label}</Tag>
          {job.queue_position !== null && <Tag>排队 {job.queue_position}</Tag>}
          <Tag>{socialCardJobCountLabel(job)}</Tag>
        </Space>
        <Button icon={<ReloadOutlined />} loading={refreshing} onClick={onRefresh}>刷新状态</Button>
      </div>
      <RunDetails job={job} />
    </section>
  )
}

function SocialCardTaskDetail({
  job,
  result,
  sourceJob,
  error,
  onCreateFromCurrent,
  onDownload,
  onRefresh,
}: {
  job: SocialCardJob
  result: SocialCardResult | null
  sourceJob: DailyWriterJobSummary | null
  error: string | null
  onCreateFromCurrent: () => void
  onDownload: () => void
  onRefresh: () => void
}) {
  const failed = job.status === 'failed'
  return (
    <section className="growth-result-panel">
      <Flex align="flex-start" justify="space-between" wrap="wrap" gap={12}>
        <div className="growth-panel-heading">
          <Typography.Text className="growth-eyebrow">图文任务详情</Typography.Text>
          <Typography.Title level={3}>{String(sourceJob?.summary.title || job.id)}</Typography.Title>
          <Typography.Paragraph>配置已锁定。你可以查看图文结果，或基于同一篇稿件重新生成。</Typography.Paragraph>
        </div>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={onRefresh}>刷新</Button>
          {result && <Button icon={<DownloadOutlined />} onClick={onDownload}>下载 ZIP</Button>}
          <Button type="primary" onClick={onCreateFromCurrent}>基于同一稿件新建任务</Button>
        </Space>
      </Flex>

      <div className="growth-readonly-summary is-compact">
        <ConfigItem label="输入稿件" value={shortId(job.source_daily_writer_job_id)} />
        <ConfigItem label="图文篇数" value={`${Number(job.summary.post_count ?? job.params.post_count ?? 1)} 篇`} />
        <ConfigItem label="每篇卡片" value={`${Number(job.summary.cards_per_post ?? job.params.cards_per_post ?? job.params.card_count ?? 0)} 张`} />
        <ConfigItem label="图片产出" value={`${Number(job.summary.image_count ?? 0)} 张`} />
        <ConfigItem label="创建时间" value={formatDateTime(job.created_at)} />
      </div>

      {error && <Alert type="error" showIcon message={error} />}
      {job.message && (
        <Alert type={failed ? 'error' : 'info'} showIcon message={job.message} />
      )}

      {result ? (
        <SocialCardResultPanel jobId={result.job_id} result={result} />
      ) : (
        <div className="growth-empty-state">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={failed ? '图文任务生成失败，可查看运行详情排查原因' : '任务完成后这里会展示图文结果'}
          />
        </div>
      )}

      <RunDetails job={job} />
    </section>
  )
}

function SocialCardResultPanel({
  jobId,
  result,
}: {
  jobId: string
  result: SocialCardResult
}) {
  const posts = result.posts?.length
    ? result.posts
    : [legacySocialCardPost(result)]
  if (posts.length > 1) {
    return (
      <div className="growth-table-section">
        <Tabs
          items={posts.map((post, index) => ({
            key: post.key || `post-${index + 1}`,
            label: `第 ${index + 1} 篇`,
            children: (
              <SocialCardPostPanel
                jobId={jobId}
                post={post}
              />
            ),
          }))}
        />
      </div>
    )
  }
  return (
    <div className="growth-table-section">
      <SocialCardPostPanel jobId={jobId} post={posts[0]} />
    </div>
  )
}

function SocialCardPostPanel({
  jobId,
  post,
}: {
  jobId: string
  post: SocialCardPost
}) {
  return (
    <Tabs
      items={[
        {
          key: 'images',
          label: '图文卡',
          children: <SocialCardImageList jobId={jobId} assets={post.images} />,
        },
        {
          key: 'post',
          label: '图文正文',
          children: (
            <SocialCardMarkdown
              jobId={jobId}
              markdown={post.markdown}
              assets={post.images}
            />
          ),
        },
      ]}
    />
  )
}

function SocialCardImageList({
  jobId,
  assets,
}: {
  jobId: string
  assets: SocialCardAsset[]
}) {
  if (!assets.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无图文卡图片" />
  }
  return (
    <div className="growth-artwork-grid">
      {assets.map((asset) => (
        <div key={asset.key} className="growth-artwork-card">
          <AuthenticatedSocialCardImage jobId={jobId} asset={asset} maxHeight={520} />
        </div>
      ))}
    </div>
  )
}

function SocialCardMarkdown({
  jobId,
  markdown,
  assets,
}: {
  jobId: string
  markdown: string
  assets: SocialCardAsset[]
}) {
  const assetByKey = useMemo(
    () => new Map(assets.map((asset) => [asset.key, asset])),
    [assets],
  )
  const components = useMemo<Components>(() => ({
    img: ({ src, alt }) => {
      const key = parseSocialCardImageKey(src)
      const asset = key ? assetByKey.get(key) : null
      if (asset) {
        return (
          <figure style={{ margin: '22px 0' }}>
            <AuthenticatedSocialCardImage jobId={jobId} asset={asset} maxHeight={560} />
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
        urlTransform={socialCardMarkdownUrlTransform}
      >
        {markdown}
      </ReactMarkdown>
    </article>
  )
}

function AuthenticatedSocialCardImage({
  jobId,
  asset,
  maxHeight = 320,
}: {
  jobId: string
  asset: SocialCardAsset
  maxHeight?: number
}) {
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false
    setSrc(null)
    setFailed(false)
    getSocialCardImageBlob(jobId, asset.key)
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

function RunDetails({ job }: { job: WorkflowRunJob }) {
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

function socialCardJobCountLabel(job: SocialCardJob | SocialCardJobSummary): string {
  const postCount = Number(job.summary.post_count ?? job.params.post_count ?? 1)
  const cardsPerPost = Number(
    job.summary.cards_per_post
      ?? job.params.cards_per_post
      ?? job.params.card_count
      ?? job.summary.requested_count
      ?? 0,
  )
  if (postCount > 1) {
    return `${postCount} 篇 · ${cardsPerPost} 张/篇`
  }
  return `${cardsPerPost} 张`
}

function legacySocialCardPost(result: SocialCardResult): SocialCardPost {
  return {
    key: 'post_01',
    title: '主图文',
    images: result.images,
    markdown: result.markdown,
    main_path: result.main_path,
    manifest_path: result.manifest_path,
    index_path: result.index_path,
    plan_path: result.plan_path,
    summary: result.summary,
  }
}

function latestProgressSummary(job: WorkflowRunJob): string {
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

function statusColor(status: SocialCardJob['status']) {
  if (status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  return 'blue'
}

function parseSocialCardImageKey(src: unknown): string | null {
  if (typeof src !== 'string') return null
  return src.startsWith(SOCIAL_CARD_IMAGE_PREFIX) ? src.slice(SOCIAL_CARD_IMAGE_PREFIX.length) : null
}

const socialCardMarkdownUrlTransform: UrlTransform = (url, key, node) => {
  if (key === 'src' && node.tagName === 'img' && url.startsWith(SOCIAL_CARD_IMAGE_PREFIX)) {
    return url
  }
  return defaultUrlTransform(url)
}
