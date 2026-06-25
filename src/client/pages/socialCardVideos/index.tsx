import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Empty,
  Flex,
  Form,
  Input,
  List,
  Progress,
  Space,
  Tag,
  Typography,
  Upload,
} from 'antd'
import {
  DownloadOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons'
import {
  listSocialCardJobs,
  type SocialCardJobSummary,
} from '../../lib/socialCards'
import {
  createSocialCardVideoJob,
  downloadSocialCardVideoResult,
  getSocialCardVideoBlob,
  getSocialCardVideoJob,
  getSocialCardVideoResult,
  listSocialCardVideoJobs,
  type SocialCardVideoAsset,
  type SocialCardVideoJob,
  type SocialCardVideoJobSummary,
  type SocialCardVideoResult,
} from '../../lib/socialCardVideos'
import { resolveErrorMessage } from '../../lib/errorMessage'
import { formatDateTime, progressEventColor, statusMeta } from '../aiwiki/helpers'
import '../seedMatrix/GrowthWorkflow.css'

const ACTIVE_STATUSES = new Set(['queued', 'running'])

export default function SocialCardVideosPage() {
  const { message } = App.useApp()
  const [sourceJobs, setSourceJobs] = useState<SocialCardJobSummary[]>([])
  const [videoJobs, setVideoJobs] = useState<SocialCardVideoJobSummary[]>([])
  const [selectedSourceJobId, setSelectedSourceJobId] = useState<string | null>(null)
  const [activeJob, setActiveJob] = useState<SocialCardVideoJob | null>(null)
  const [result, setResult] = useState<SocialCardVideoResult | null>(null)
  const [title, setTitle] = useState('')
  const [voiceText, setVoiceText] = useState('')
  const [bgmStartText, setBgmStartText] = useState('0:00')
  const [bgmStartError, setBgmStartError] = useState<string | null>(null)
  const [bgmFile, setBgmFile] = useState<File | null>(null)
  const [creating, setCreating] = useState(true)
  const [loadingSources, setLoadingSources] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSourceJobs = useCallback(async () => {
    setLoadingSources(true)
    try {
      const data = await listSocialCardJobs({ limit: 100, offset: 0 })
      const completed = data.items.filter((item) => item.status === 'completed')
      setSourceJobs(completed)
      setSelectedSourceJobId((current) => current ?? completed[0]?.id ?? null)
      setError(null)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingSources(false)
    }
  }, [])

  const loadVideoJobs = useCallback(async () => {
    setLoadingHistory(true)
    try {
      const data = await listSocialCardVideoJobs({ limit: 50, offset: 0 })
      setVideoJobs(data.items)
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
      const job = await getSocialCardVideoJob(jobId)
      setActiveJob(job)
      setError(null)
      if (job.status === 'completed') {
        setResult(await getSocialCardVideoResult(jobId))
        void loadVideoJobs()
      } else if (job.status === 'failed') {
        setResult(null)
        void loadVideoJobs()
      }
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      if (!silent) message.error(text)
    } finally {
      if (!silent) setRefreshing(false)
    }
  }, [loadVideoJobs, message])

  useEffect(() => {
    void loadSourceJobs()
    void loadVideoJobs()
  }, [loadSourceJobs, loadVideoJobs])

  useEffect(() => {
    if (!activeJob?.id || !ACTIVE_STATUSES.has(activeJob.status)) return
    const timer = window.setInterval(() => {
      void refreshJob(activeJob.id, true)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [activeJob?.id, activeJob?.status, refreshJob])

  const selectedSourceJob = useMemo(
    () => sourceJobs.find((item) => item.id === selectedSourceJobId) ?? null,
    [selectedSourceJobId, sourceJobs],
  )

  const startCreate = () => {
    setCreating(true)
    setActiveJob(null)
    setResult(null)
    setError(null)
  }

  const submit = async () => {
    if (!selectedSourceJobId) {
      setError('请先选择一个已完成的图文任务')
      return
    }
    const bgmStart = parseMinuteSecondInput(bgmStartText)
    if (bgmStart === null) {
      setBgmStartError('请输入分:秒格式，例如 0:30 或 1:05；也可以直接输入秒数。')
      return
    }
    setSubmitting(true)
    setError(null)
    setBgmStartError(null)
    setResult(null)
    try {
      const created = await createSocialCardVideoJob({
        source_social_card_job_id: selectedSourceJobId,
        title: title || String(selectedSourceJob?.summary.title || '小红书轮播视频'),
        voice_text: voiceText,
        bgm_start: bgmStart,
        bgm_file: bgmFile,
      })
      setCreating(false)
      setActiveJob(created)
      message.success('轮播视频任务已提交')
      void loadVideoJobs()
      void refreshJob(created.id, true)
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    } finally {
      setSubmitting(false)
    }
  }

  const selectVideoJob = async (jobId: string) => {
    setCreating(false)
    setRefreshing(true)
    setResult(null)
    try {
      const job = await getSocialCardVideoJob(jobId)
      setActiveJob(job)
      setSelectedSourceJobId(job.source_social_card_job_id)
      if (job.status === 'completed') {
        setResult(await getSocialCardVideoResult(jobId))
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

  return (
    <div className="growth-workflow">
      <aside className="growth-task-rail">
        <Flex align="center" justify="space-between" gap={10} className="growth-task-rail-head">
          <div>
            <Typography.Text className="growth-eyebrow">Video</Typography.Text>
            <Typography.Title level={5} className="growth-rail-title">视频任务</Typography.Title>
          </div>
          <Button size="small" icon={<ReloadOutlined />} loading={loadingHistory} onClick={() => void loadVideoJobs()} />
        </Flex>
        <Button block type="primary" icon={<PlayCircleOutlined />} onClick={startCreate}>新建视频任务</Button>
        <List
          className="growth-task-list"
          loading={loadingHistory}
          dataSource={videoJobs}
          locale={{ emptyText: '暂无视频任务' }}
          renderItem={(job) => (
            <List.Item>
              <button
                type="button"
                className={job.id === activeJob?.id && !creating ? 'growth-task-card is-active' : 'growth-task-card'}
                onClick={() => void selectVideoJob(job.id)}
              >
                <span className="growth-task-card-title">{shortId(job.id)}</span>
                <span className="growth-task-card-meta">{formatDateTime(job.created_at)}</span>
                <span className="growth-task-card-tags">
                  <Tag color={statusColor(job.status)}>{statusMeta(job.status).label}</Tag>
                  {job.summary.video_count ? <Tag color="green">视频 {Number(job.summary.video_count)}</Tag> : null}
                </span>
              </button>
            </List.Item>
          )}
        />
      </aside>

      <main className="growth-main-stage">
        {creating ? (
          <CreateVideoTask
            sourceJobs={sourceJobs}
            selectedSourceJob={selectedSourceJob}
            selectedSourceJobId={selectedSourceJobId}
            title={title}
            voiceText={voiceText}
            bgmStartText={bgmStartText}
            bgmStartError={bgmStartError}
            bgmFile={bgmFile}
            loadingSources={loadingSources}
            submitting={submitting}
            error={error}
            onBgmFileChange={setBgmFile}
            onBgmStartTextChange={(value) => {
              setBgmStartText(value)
              setBgmStartError(null)
            }}
            onBgmStartTextBlur={() => {
              const parsed = parseMinuteSecondInput(bgmStartText)
              if (parsed === null) {
                setBgmStartError('请输入分:秒格式，例如 0:30 或 1:05；也可以直接输入秒数。')
                return
              }
              setBgmStartError(null)
              setBgmStartText(formatMinuteSecond(parsed))
            }}
            onRefreshSources={() => void loadSourceJobs()}
            onSelectSourceJob={setSelectedSourceJobId}
            onSubmit={() => void submit()}
            onTitleChange={setTitle}
            onVoiceTextChange={setVoiceText}
          />
        ) : activeJob && ACTIVE_STATUSES.has(activeJob.status) ? (
          <VideoGenerationStatus
            job={activeJob}
            refreshing={refreshing}
            onRefresh={() => void refreshJob(activeJob.id)}
          />
        ) : activeJob ? (
          <VideoTaskDetail
            job={activeJob}
            result={result}
            sourceJob={selectedSourceJob}
            error={error}
            onCreateFromCurrent={() => {
              setSelectedSourceJobId(activeJob.source_social_card_job_id)
              setCreating(true)
              setActiveJob(null)
              setResult(null)
            }}
            onDownload={() => void downloadSocialCardVideoResult(activeJob.id)}
            onRefresh={() => void refreshJob(activeJob.id)}
          />
        ) : (
          <div className="growth-empty-state">
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="新建一个视频任务，或从左侧选择历史任务" />
            <Button type="primary" icon={<PlayCircleOutlined />} onClick={startCreate}>新建视频任务</Button>
          </div>
        )}
      </main>
    </div>
  )
}

function CreateVideoTask({
  sourceJobs,
  selectedSourceJob,
  selectedSourceJobId,
  title,
  voiceText,
  bgmStartText,
  bgmStartError,
  bgmFile,
  loadingSources,
  submitting,
  error,
  onBgmFileChange,
  onBgmStartTextChange,
  onBgmStartTextBlur,
  onRefreshSources,
  onSelectSourceJob,
  onSubmit,
  onTitleChange,
  onVoiceTextChange,
}: {
  sourceJobs: SocialCardJobSummary[]
  selectedSourceJob: SocialCardJobSummary | null
  selectedSourceJobId: string | null
  title: string
  voiceText: string
  bgmStartText: string
  bgmStartError: string | null
  bgmFile: File | null
  loadingSources: boolean
  submitting: boolean
  error: string | null
  onBgmFileChange: (file: File | null) => void
  onBgmStartTextChange: (value: string) => void
  onBgmStartTextBlur: () => void
  onRefreshSources: () => void
  onSelectSourceJob: (jobId: string) => void
  onSubmit: () => void
  onTitleChange: (value: string) => void
  onVoiceTextChange: (value: string) => void
}) {
  return (
    <section className="growth-create-panel">
      <div className="growth-panel-heading">
        <Typography.Text className="growth-eyebrow">新建任务</Typography.Text>
        <Typography.Title level={3}>生成轮播视频</Typography.Title>
        <Typography.Paragraph>
          选择已完成的小红书图文卡，生成竖屏轮播视频，可上传 BGM 并指定起始时间。
        </Typography.Paragraph>
      </div>

      <div className="growth-create-grid">
        <section className="growth-config-section">
          <Flex align="center" justify="space-between" gap={12}>
            <Typography.Title level={5}>输入图文</Typography.Title>
            <Button size="small" icon={<ReloadOutlined />} loading={loadingSources} onClick={onRefreshSources} />
          </Flex>
          <List
            className="growth-input-source-list"
            loading={loadingSources}
            dataSource={sourceJobs}
            locale={{ emptyText: '暂无已完成图文任务' }}
            renderItem={(job) => (
              <List.Item>
                <button
                  type="button"
                  className={job.id === selectedSourceJobId ? 'growth-input-source is-active' : 'growth-input-source'}
                  onClick={() => onSelectSourceJob(job.id)}
                >
                  <span>{String(job.summary.title || job.id)}</span>
                  <small>{formatDateTime(job.created_at)} · {socialCardJobCountLabel(job)}</small>
                </button>
              </List.Item>
            )}
          />
          {selectedSourceJob && (
            <div className="growth-config-summary">
              <ConfigItem label="图文任务" value={shortId(selectedSourceJob.id)} />
              <ConfigItem label="图文数量" value={socialCardJobCountLabel(selectedSourceJob)} />
              <ConfigItem label="图片产出" value={`${Number(selectedSourceJob.summary.image_count ?? 0)} 张`} />
            </div>
          )}
        </section>

        <section className="growth-config-section">
          <Typography.Title level={5}>视频配置</Typography.Title>
          <Form layout="vertical" requiredMark={false}>
            <Form.Item label="顶部标题">
              <Input
                value={title}
                placeholder={String(selectedSourceJob?.summary.title || '小红书轮播视频')}
                onChange={(event) => onTitleChange(event.target.value)}
              />
            </Form.Item>
            <Form.Item label="配音文案">
              <Input.TextArea
                value={voiceText}
                rows={5}
                maxLength={2000}
                placeholder="可留空，Agent 会根据图文内容自动生成。"
                onChange={(event) => onVoiceTextChange(event.target.value)}
              />
            </Form.Item>
            <div className="growth-social-config-row">
              <Form.Item
                label="BGM 起始时间"
                validateStatus={bgmStartError ? 'error' : undefined}
                help={bgmStartError || '支持 1:30 或 90，留空按 0:00 处理。'}
                style={{ minWidth: 220, marginBottom: 0 }}
              >
                <Input
                  value={bgmStartText}
                  placeholder="0:00"
                  addonAfter="分:秒"
                  onBlur={onBgmStartTextBlur}
                  onChange={(event) => onBgmStartTextChange(event.target.value)}
                />
              </Form.Item>
              <Upload
                accept="audio/*"
                maxCount={1}
                beforeUpload={(file) => {
                  onBgmFileChange(file)
                  return false
                }}
                onRemove={() => onBgmFileChange(null)}
              >
                <Button>上传 BGM</Button>
              </Upload>
            </div>
            <div className="growth-config-summary">
              <ConfigItem label="比例" value="1080 x 1440" />
              <ConfigItem label="BGM 起始" value={formatMinuteSecond(parseMinuteSecondInput(bgmStartText) ?? 0)} />
              <ConfigItem label="BGM" value={bgmFile?.name || '未上传'} />
            </div>
          </Form>
        </section>
      </div>

      {error && <Alert type="error" showIcon message={error} />}
      <div className="growth-primary-action">
        <Button
          type="primary"
          size="large"
          icon={<VideoCameraOutlined />}
          loading={submitting}
          disabled={!selectedSourceJobId}
          onClick={onSubmit}
        >
          生成轮播视频
        </Button>
      </div>
    </section>
  )
}

function VideoGenerationStatus({
  job,
  refreshing,
  onRefresh,
}: {
  job: SocialCardVideoJob
  refreshing: boolean
  onRefresh: () => void
}) {
  const meta = statusMeta(job.status)
  return (
    <section className="growth-generation-panel">
      <div className="growth-generation-card">
        <Typography.Text className="growth-eyebrow">生成中</Typography.Text>
        <Typography.Title level={3}>正在生成轮播视频</Typography.Title>
        <Progress percent={meta.percent} status={meta.status} />
        <Typography.Text className="growth-generation-current">
          {latestProgressSummary(job) || job.message || '任务已进入队列，正在准备生成。'}
        </Typography.Text>
        <Space wrap>
          <Tag color="blue">{statusMeta(job.status).label}</Tag>
          {job.queue_position !== null && <Tag>排队 {job.queue_position}</Tag>}
        </Space>
        <Button icon={<ReloadOutlined />} loading={refreshing} onClick={onRefresh}>刷新状态</Button>
      </div>
      <RunDetails job={job} />
    </section>
  )
}

function VideoTaskDetail({
  job,
  result,
  sourceJob,
  error,
  onCreateFromCurrent,
  onDownload,
  onRefresh,
}: {
  job: SocialCardVideoJob
  result: SocialCardVideoResult | null
  sourceJob: SocialCardJobSummary | null
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
          <Typography.Text className="growth-eyebrow">视频任务详情</Typography.Text>
          <Typography.Title level={3}>{shortId(job.id)}</Typography.Title>
          <Typography.Paragraph>配置已锁定。你可以查看视频结果，或基于同一组图文重新生成。</Typography.Paragraph>
        </div>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={onRefresh}>刷新</Button>
          {result && <Button icon={<DownloadOutlined />} onClick={onDownload}>下载 ZIP</Button>}
          <Button type="primary" onClick={onCreateFromCurrent}>基于同一图文新建任务</Button>
        </Space>
      </Flex>

      <div className="growth-readonly-summary is-compact">
        <ConfigItem label="输入图文" value={shortId(job.source_social_card_job_id)} />
        <ConfigItem label="视频产出" value={`${Number(job.summary.video_count ?? 0)} 个`} />
        <ConfigItem label="BGM 起始" value={formatMinuteSecond(Number(job.params.bgm_start ?? 0))} />
        <ConfigItem label="源图文" value={sourceJob ? socialCardJobCountLabel(sourceJob) : '-'} />
        <ConfigItem label="创建时间" value={formatDateTime(job.created_at)} />
      </div>

      {error && <Alert type="error" showIcon message={error} />}
      {job.message && <Alert type={failed ? 'error' : 'info'} showIcon message={job.message} />}

      {result ? (
        <VideoResultPanel result={result} />
      ) : (
        <div className="growth-empty-state">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={failed ? '视频任务生成失败，可查看运行详情排查原因' : '任务完成后这里会展示视频结果'}
          />
        </div>
      )}

      <RunDetails job={job} />
    </section>
  )
}

function VideoResultPanel({ result }: { result: SocialCardVideoResult }) {
  if (!result.videos.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无轮播视频" />
  }
  return (
    <div className="growth-artwork-grid">
      {result.videos.map((video) => (
        <div key={video.key} className="growth-artwork-card">
          <AuthenticatedVideo jobId={result.job_id} asset={video} />
        </div>
      ))}
    </div>
  )
}

function AuthenticatedVideo({
  jobId,
  asset,
}: {
  jobId: string
  asset: SocialCardVideoAsset
}) {
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false
    setSrc(null)
    setFailed(false)
    getSocialCardVideoBlob(jobId, asset.key)
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
    return <Alert type="warning" showIcon message="视频加载失败" />
  }
  if (!src) {
    return <div style={{ height: 220 }} />
  }
  return (
    <video
      src={src}
      controls
      playsInline
      style={{ width: '100%', maxHeight: 560, background: '#000', display: 'block' }}
    />
  )
}

function RunDetails({ job }: { job: SocialCardVideoJob }) {
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

function socialCardJobCountLabel(job: SocialCardJobSummary): string {
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

function latestProgressSummary(job: SocialCardVideoJob): string {
  const events = Array.isArray(job.progress?.events) ? job.progress.events : []
  return events.at(-1)?.summary || job.progress?.current_step || ''
}

function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}...` : value
}

function formatMinuteSecond(value: number): string {
  const totalSeconds = Math.max(0, Math.floor(Number(value) || 0))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

function parseMinuteSecondInput(value: string): number | null {
  const text = value.trim()
  if (!text) return 0
  if (/^\d+$/.test(text)) return Number(text)

  const match = text.match(/^(\d+):(\d{1,2})$/)
  if (!match) return null

  const minutes = Number(match[1])
  const seconds = Number(match[2])
  if (!Number.isFinite(minutes) || !Number.isFinite(seconds) || seconds > 59) {
    return null
  }
  return minutes * 60 + seconds
}

function statusColor(status: SocialCardVideoJob['status']) {
  if (status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  return 'blue'
}
