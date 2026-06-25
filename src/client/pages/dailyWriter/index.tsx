import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Col,
  Empty,
  Flex,
  Image,
  Input,
  InputNumber,
  List,
  Popconfirm,
  Progress,
  Row,
  Space,
  Statistic,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  theme,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  DeleteOutlined,
  DownloadOutlined,
  FileTextOutlined,
  PlayCircleOutlined,
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
import { DAILY_WRITER_MODES, dailyWriterModeLabel, type DailyWriterModeId } from '../../lib/workflowModes'

type MatrixRow = Record<string, string>

const ACTIVE_STATUSES = new Set(['queued', 'running'])
const ARTWORK_IMAGE_PREFIX = 'daily-writer-artwork:'
export default function DailyWriterPage({
  mode = 'single',
  sourceAiwikiJobId,
}: {
  mode?: DailyWriterModeId
  sourceAiwikiJobId?: string | null
  embedded?: boolean
}) {
  const { token } = theme.useToken()
  const { message } = App.useApp()
  const modeConfig = DAILY_WRITER_MODES[mode]
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
  const [articleTotal, setArticleTotal] = useState(modeConfig.defaultTotal)
  const [generateArtwork, setGenerateArtwork] = useState(false)

  const sectionStyle = {
    background: token.colorBgContainer,
    border: `1px solid ${token.colorBorderSecondary}`,
    borderRadius: 8,
    padding: 16,
  }

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
      setMatrixResult(data)
      setSelectedSeedId(data.rows[0]?.seed_id ?? null)
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
    void loadMatrices()
    void loadWriterJobs()
  }, [loadMatrices, loadWriterJobs])

  useEffect(() => {
    setActiveJob(null)
    setResult(null)
    setMatrixResult(null)
    setSelectedMatrixId(null)
    setSelectedSeedId(null)
  }, [sourceAiwikiJobId])

  useEffect(() => {
    setArticleTotal(modeConfig.defaultTotal)
  }, [modeConfig.defaultTotal])

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

  const submit = async () => {
    if (!selectedMatrixId || !selectedSeedId) {
      setError('请先选择一个已完成的选题策略和 seed')
      return
    }
    setSubmitting(true)
    setError(null)
    setResult(null)
    try {
      const total = modeConfig.fixedTotal ?? articleTotal
      const variantCount = Math.max(0, total - 1)
      const created = await createDailyWriterJob({
        source_seed_matrix_job_id: selectedMatrixId,
        seed_id: selectedSeedId,
        generate_variants: variantCount > 0,
        variant_count: variantCount,
        generate_artwork: generateArtwork,
      })
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
    setRefreshing(true)
    setResult(null)
    try {
      const job = await getDailyWriterJob(jobId)
      setActiveJob(job)
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

  return (
    <>
      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} xl={5}>
        <section style={{ ...sectionStyle, height: '100%' }}>
          <Flex align="center" justify="space-between" gap={12} style={{ marginBottom: 12 }}>
            <Typography.Title level={5} style={{ margin: 0 }}>选题策略</Typography.Title>
            <Button size="small" icon={<ReloadOutlined />} loading={loadingMatrices} onClick={() => void loadMatrices()} />
          </Flex>
          <List
            size="small"
            loading={loadingMatrices}
            dataSource={matrixJobs}
            locale={{ emptyText: '暂无已完成选题策略' }}
            style={{ maxHeight: 'calc(100vh - 190px)', overflow: 'auto' }}
            renderItem={(item) => {
              const active = item.id === selectedMatrixId
              return (
                <List.Item
                  onClick={() => setSelectedMatrixId(item.id)}
                  style={{
                    cursor: 'pointer',
                    background: active ? token.colorFillSecondary : undefined,
                    borderRadius: 6,
                    paddingInline: 8,
                  }}
                >
                  <Flex vertical gap={4} style={{ width: '100%' }}>
                    <Typography.Text strong ellipsis>{item.id}</Typography.Text>
                    <Space wrap>
                      <Tag color="green">已完成</Tag>
                      <Tag>Seed {Number(item.summary.seed_count ?? 0)}</Tag>
                      <Tag>稿件 {Number(item.summary.expected_article_total ?? 0)}</Tag>
                    </Space>
                    <Typography.Text type="secondary">{formatDateTime(item.created_at)}</Typography.Text>
                  </Flex>
                </List.Item>
              )
            }}
          />
        </section>
        </Col>

        <Col xs={24} xl={13}>
        <Flex vertical gap={16}>
          <section style={sectionStyle}>
            <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
              <div>
                <Typography.Title level={3} style={{ margin: 0 }}>{modeConfig.title}</Typography.Title>
                <Typography.Text type="secondary">{modeConfig.description}</Typography.Text>
              </div>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={submitting}
                disabled={!selectedMatrixId || !selectedSeedId}
                onClick={() => void submit()}
              >
                {modeConfig.buttonText}
              </Button>
            </Flex>
            {error && <Alert type="error" showIcon message={error} style={{ marginTop: 12 }} />}
            {selectedRow && (
              <Row gutter={[12, 12]} style={{ marginTop: 14 }}>
                <Col xs={24} md={8}><Statistic title="当前 Seed" value={selectedRow.seed_id} /></Col>
                <Col xs={24} md={8}><Statistic title="账号类型" value={selectedRow.primary_account_type || '-'} /></Col>
                <Col xs={24} md={8}><Statistic title="预计篇数" value={selectedRow.expected_article_count || '-'} /></Col>
              </Row>
            )}
            <Row gutter={[12, 12]} style={{ marginTop: 14 }}>
              <Col xs={24} md={8}><Statistic title="入口模式" value={modeConfig.navLabel} /></Col>
              <Col xs={24} md={8}><Statistic title="主稿" value={1} suffix="篇" /></Col>
              <Col xs={24} md={8}>
                {modeConfig.fixedTotal ? (
                  <Statistic title="生产稿件总数" value={modeConfig.fixedTotal} suffix="篇" />
                ) : (
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Typography.Text type="secondary">生产稿件总数</Typography.Text>
                    <InputNumber
                      min={modeConfig.minTotal}
                      max={modeConfig.maxTotal}
                      value={articleTotal}
                      onChange={(value) => setArticleTotal(Number(value || modeConfig.defaultTotal))}
                      style={{ width: '100%' }}
                    />
                    <Typography.Text type="secondary">
                      1 篇主稿 + {Math.max(0, articleTotal - 1)} 篇变体
                    </Typography.Text>
                  </Space>
                )}
              </Col>
            </Row>
            <Flex align="center" wrap="wrap" gap={16} style={{ marginTop: 16 }}>
              <Space>
                <Switch checked={generateArtwork} onChange={setGenerateArtwork} />
                <Typography.Text>生成封面和插图</Typography.Text>
              </Space>
            </Flex>
          </section>

          <section style={sectionStyle}>
            <Flex align="center" justify="space-between" wrap="wrap" gap={12} style={{ marginBottom: 12 }}>
              <Typography.Title level={4} style={{ margin: 0 }}>选择 Seed</Typography.Title>
              <Input.Search
                placeholder="搜索 seed、选题、痛点、方案"
                allowClear
                onSearch={setQuery}
                onChange={(event) => setQuery(event.target.value)}
                style={{ width: 280 }}
              />
            </Flex>
            <Table
              size="small"
              loading={loadingRows}
              rowKey={(row) => row.seed_id}
              rowSelection={{
                type: 'radio',
                selectedRowKeys: selectedSeedId ? [selectedSeedId] : [],
                onChange: (keys) => setSelectedSeedId(String(keys[0] ?? '')),
              }}
              columns={columns}
              dataSource={filteredRows}
              scroll={{ x: 1300 }}
              pagination={{ pageSize: 8, showSizeChanger: false }}
              locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前策略没有可用 seed" /> }}
            />
          </section>

          <section style={{ ...sectionStyle, minHeight: 360 }}>
            {result ? (
              <ArticlePreviewTabs
                result={result}
                tabBarExtraContent={
                  <Button icon={<DownloadOutlined />} onClick={() => activeJob && void downloadDailyWriterResult(activeJob.id)}>
                    下载
                  </Button>
                }
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="生产完成后，这里会展示稿件正文和 metadata" />
            )}
          </section>
        </Flex>
        </Col>

        <Col xs={24} xl={6}>
        <TaskPanel
          activeJob={activeJob}
          writerJobs={writerJobs}
          loading={loadingHistory}
          refreshing={refreshing}
          onRefreshHistory={loadWriterJobs}
          onRefreshActive={() => activeJob && void refreshJob(activeJob.id)}
          onSelectJob={(jobId) => void selectWriterJob(jobId)}
          onDeleteJob={(jobId) => void deleteWriterJob(jobId)}
        />
        </Col>
      </Row>

    </>
  )
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
  const { token } = theme.useToken()
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
      <div style={{ columnCount: assets.length > 1 ? 2 : 1, columnGap: 12 }}>
        {assets.map((asset) => (
          <div
            key={asset.key}
            style={{
              breakInside: 'avoid',
              marginBottom: 12,
              border: `1px solid ${token.colorBorderSecondary}`,
              borderRadius: 8,
              overflow: 'hidden',
              background: token.colorBgElevated,
            }}
          >
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

function TaskPanel({
  activeJob,
  writerJobs,
  loading,
  refreshing,
  onRefreshHistory,
  onRefreshActive,
  onSelectJob,
  onDeleteJob,
}: {
  activeJob: DailyWriterJob | null
  writerJobs: DailyWriterJobSummary[]
  loading: boolean
  refreshing: boolean
  onRefreshHistory: () => void
  onRefreshActive: () => void
  onSelectJob: (jobId: string) => void
  onDeleteJob: (jobId: string) => void
}) {
  const { token } = theme.useToken()
  const meta = statusMeta(activeJob?.status)
  return (
    <aside style={{ background: token.colorBgContainer, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, padding: 14, height: '100%' }}>
      <Flex vertical gap={14}>
        <Flex align="center" justify="space-between" gap={12}>
          <Typography.Title level={5} style={{ margin: 0 }}>稿件任务</Typography.Title>
          <Space>
            <Button size="small" icon={<ReloadOutlined />} loading={refreshing} disabled={!activeJob} onClick={onRefreshActive} />
            <Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={() => void onRefreshHistory()} />
          </Space>
        </Flex>
        <Progress percent={meta.percent} status={meta.status} />
        {activeJob?.message && (
          <Alert
            type={activeJob.status === 'failed' ? 'error' : activeJob.status === 'partial_failed' ? 'warning' : 'info'}
            showIcon
            message={activeJob.message}
          />
        )}
        <List
          size="small"
          loading={loading}
          dataSource={writerJobs}
          locale={{ emptyText: '暂无稿件任务' }}
          style={{ maxHeight: 280, overflow: 'auto' }}
          renderItem={(item) => (
            <List.Item
              onClick={() => onSelectJob(item.id)}
              style={{ cursor: 'pointer', background: item.id === activeJob?.id ? token.colorFillSecondary : undefined, borderRadius: 6, paddingInline: 8 }}
            >
              <Flex vertical gap={4} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color={item.status === 'completed' ? 'green' : item.status === 'failed' ? 'red' : item.status === 'partial_failed' ? 'gold' : 'blue'}>{statusMeta(item.status).label}</Tag>
                  <Tag icon={<FileTextOutlined />}>{item.seed_id}</Tag>
                  <Tag>{dailyWriterModeLabel(item.params)}</Tag>
                  {item.summary.artwork_status === 'completed' && <Tag color="purple">含封面插图</Tag>}
                  {item.summary.artwork_status === 'failed' && <Tag color="red">封面插图失败</Tag>}
                  <Popconfirm
                    title="删除任务"
                    description="会删除该稿件任务记录和生成文件。"
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                    onConfirm={(event) => {
                      event?.stopPropagation()
                      onDeleteJob(item.id)
                    }}
                    onCancel={(event) => event?.stopPropagation()}
                  >
                    <Button
                      size="small"
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      disabled={item.status === 'queued' || item.status === 'running'}
                      onClick={(event) => event.stopPropagation()}
                    />
                  </Popconfirm>
                </Space>
                <Typography.Text strong ellipsis>{String(item.summary.title || item.row.topic || item.id)}</Typography.Text>
                <Typography.Text type="secondary">{formatDateTime(item.created_at)}</Typography.Text>
              </Flex>
            </List.Item>
          )}
        />
        <Typography.Text type="secondary">progress.json 进度事件</Typography.Text>
        <List
          size="small"
          dataSource={Array.isArray(activeJob?.progress?.events) ? activeJob.progress.events : []}
          locale={{ emptyText: '暂无进度事件' }}
          style={{ maxHeight: 220, overflow: 'auto' }}
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
        <pre style={{ margin: 0, minHeight: 140, maxHeight: 260, overflow: 'auto', whiteSpace: 'pre-wrap', color: token.colorTextSecondary }}>
          {activeJob?.log_tail.length ? activeJob.log_tail.join('\n') : '暂无日志'}
        </pre>
      </Flex>
    </aside>
  )
}
