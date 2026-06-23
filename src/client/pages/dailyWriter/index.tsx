import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Col,
  Empty,
  Flex,
  Input,
  InputNumber,
  List,
  Popconfirm,
  Progress,
  Row,
  Space,
  Statistic,
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
import ReactMarkdown from 'react-markdown'
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
  getDailyWriterJob,
  getDailyWriterResult,
  listDailyWriterJobs,
  type DailyWriterJob,
  type DailyWriterJobSummary,
  type DailyWriterResult,
} from '../../lib/dailyWriter'
import { resolveErrorMessage } from '../../lib/errorMessage'
import { formatDateTime, progressEventColor, statusMeta } from '../aiwiki/helpers'
import { DAILY_WRITER_MODES, dailyWriterModeLabel, type DailyWriterModeId } from '../../lib/workflowModes'

type MatrixRow = Record<string, string>

const ACTIVE_STATUSES = new Set(['queued', 'running'])
export default function DailyWriterPage({ mode = 'single' }: { mode?: DailyWriterModeId }) {
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

  const sectionStyle = {
    background: token.colorBgContainer,
    border: `1px solid ${token.colorBorderSecondary}`,
    borderRadius: 8,
    padding: 16,
  }

  const loadMatrices = useCallback(async () => {
    setLoadingMatrices(true)
    try {
      const data = await listSeedMatrixJobs({ limit: 100, offset: 0 })
      const completed = data.items.filter((item) => item.status === 'completed')
      setMatrixJobs(completed)
      setSelectedMatrixId((current) => current ?? completed[0]?.id ?? null)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingMatrices(false)
    }
  }, [])

  const loadWriterJobs = useCallback(async () => {
    setLoadingHistory(true)
    try {
      const data = await listDailyWriterJobs({ limit: 50, offset: 0 })
      setWriterJobs(data.items)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingHistory(false)
    }
  }, [])

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
      setError('请先选择一个已完成的选题矩阵和 seed')
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
      })
      setActiveJob(created)
      message.success('长文生成任务已提交')
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
      message.success('长文任务已删除')
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
            <Typography.Title level={5} style={{ margin: 0 }}>选题矩阵</Typography.Title>
            <Button size="small" icon={<ReloadOutlined />} loading={loadingMatrices} onClick={() => void loadMatrices()} />
          </Flex>
          <List
            size="small"
            loading={loadingMatrices}
            dataSource={matrixJobs}
            locale={{ emptyText: '暂无已完成选题矩阵' }}
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
                      <Tag>文章 {Number(item.summary.expected_article_total ?? 0)}</Tag>
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
                  <Statistic title="生成文章总数" value={modeConfig.fixedTotal} suffix="篇" />
                ) : (
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Typography.Text type="secondary">生成文章总数</Typography.Text>
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
              locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前矩阵没有可用 seed" /> }}
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
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="生成完成后，这里会展示长文正文和 metadata" />
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
  const articles = [
    {
      key: 'main',
      label: '主稿',
      markdown: result.markdown,
      metadata: result.metadata,
    },
    ...result.variants.map((variant, index) => ({
      key: variant.directory || `variant-${index + 1}`,
      label: variant.angle || `变体 ${index + 1}`,
      markdown: variant.markdown,
      metadata: variant.metadata,
    })),
  ]

  return (
    <Tabs
      tabBarExtraContent={tabBarExtraContent}
      items={articles.map((article) => ({
        key: article.key,
        label: article.label,
        children: (
          <Tabs
            size="small"
            items={[
              {
                key: 'article',
                label: '正文',
                children: (
                  <article style={{ maxWidth: 820 }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {article.markdown}
                    </ReactMarkdown>
                  </article>
                ),
              },
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
      }))}
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
          <Typography.Title level={5} style={{ margin: 0 }}>长文任务</Typography.Title>
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
          locale={{ emptyText: '暂无长文任务' }}
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
                  <Popconfirm
                    title="删除任务"
                    description="会删除该长文任务记录和生成文件。"
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
