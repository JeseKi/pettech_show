import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Col,
  Drawer,
  Empty,
  Flex,
  Form,
  Input,
  List,
  Popconfirm,
  Progress,
  Row,
  Segmented,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  theme,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { DeleteOutlined, DownloadOutlined, PlusOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import { listAiwikiJobs, type AiwikiJobSummary } from '../../lib/aiwiki'
import {
  createSeedMatrixJob,
  deleteSeedMatrixJob,
  downloadSeedMatrixCsv,
  getSeedMatrixJob,
  getSeedMatrixResult,
  listSeedMatrixJobs,
  type SeedMatrixCreatePayload,
  type SeedMatrixJob,
  type SeedMatrixJobSummary,
  type SeedMatrixResult,
} from '../../lib/seedMatrix'
import { resolveErrorMessage } from '../../lib/errorMessage'
import { formatDateTime, progressEventColor, statusMeta } from '../aiwiki/helpers'
import { SEED_MATRIX_MODES, seedMatrixModeLabel, type SeedMatrixModeId } from '../../lib/workflowModes'

type MatrixRow = Record<string, string>

const ACTIVE_STATUSES = new Set(['queued', 'running'])

export default function SeedMatrixPage({
  mode = 'standard',
  sourceAiwikiJobId,
  embedded = false,
}: {
  mode?: SeedMatrixModeId
  sourceAiwikiJobId?: string | null
  embedded?: boolean
}) {
  const { token } = theme.useToken()
  const { message } = App.useApp()
  const modeConfig = SEED_MATRIX_MODES[mode]
  const [form] = Form.useForm<Omit<SeedMatrixCreatePayload, 'source_aiwiki_job_id'>>()
  const [aiwikiJobs, setAiwikiJobs] = useState<AiwikiJobSummary[]>([])
  const [matrixJobs, setMatrixJobs] = useState<SeedMatrixJobSummary[]>([])
  const [selectedAiwikiJobId, setSelectedAiwikiJobId] = useState<string | null>(null)
  const [activeJob, setActiveJob] = useState<SeedMatrixJob | null>(null)
  const [result, setResult] = useState<SeedMatrixResult | null>(null)
  const [activeRow, setActiveRow] = useState<MatrixRow | null>(null)
  const [loadingInputs, setLoadingInputs] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [dayFilter, setDayFilter] = useState<string>('全部')
  const [accountFilter, setAccountFilter] = useState<string>('全部')

  const sectionStyle = {
    background: token.colorBgContainer,
    border: `1px solid ${token.colorBorderSecondary}`,
    borderRadius: 8,
    padding: 16,
  }

  const loadAiwikiJobs = useCallback(async () => {
    if (embedded) return
    setLoadingInputs(true)
    try {
      const data = await listAiwikiJobs({ limit: 100, offset: 0, status: 'completed' })
      setAiwikiJobs(data.items)
      setSelectedAiwikiJobId((current) => current ?? data.items[0]?.id ?? null)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingInputs(false)
    }
  }, [embedded])

  const loadMatrixJobs = useCallback(async () => {
    if (embedded && !sourceAiwikiJobId) {
      setMatrixJobs([])
      return
    }
    setLoadingHistory(true)
    try {
      const data = await listSeedMatrixJobs({
        limit: 50,
        offset: 0,
        source_aiwiki_job_id: embedded ? sourceAiwikiJobId ?? undefined : undefined,
      })
      setMatrixJobs(data.items)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingHistory(false)
    }
  }, [embedded, sourceAiwikiJobId])

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
    if (embedded) {
      setSelectedAiwikiJobId(sourceAiwikiJobId ?? null)
    } else {
      void loadAiwikiJobs()
    }
    void loadMatrixJobs()
    form.setFieldsValue(modeConfig.defaults)
  }, [embedded, form, loadAiwikiJobs, loadMatrixJobs, modeConfig.defaults, sourceAiwikiJobId])

  useEffect(() => {
    if (!embedded) return
    setActiveJob(null)
    setResult(null)
    setActiveRow(null)
  }, [embedded, sourceAiwikiJobId])

  useEffect(() => {
    if (!activeJob?.id || !ACTIVE_STATUSES.has(activeJob.status)) return
    const timer = window.setInterval(() => {
      void refreshJob(activeJob.id, true)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [activeJob?.id, activeJob?.status, refreshJob])

  const submit = async () => {
    if (!selectedAiwikiJobId) {
      setError('请先选择一个已完成的内容资产任务')
      return
    }
    setSubmitting(true)
    setError(null)
    setResult(null)
    try {
      const values = modeConfig.showHooks ? await form.validateFields() : modeConfig.defaults
      const created = await createSeedMatrixJob({
        ...modeConfig.defaults,
        hooks: modeConfig.showHooks
          ? (values.hooks ?? []).map((item) => item.trim()).filter(Boolean)
          : modeConfig.defaults.hooks,
        source_aiwiki_job_id: selectedAiwikiJobId,
      })
      setActiveJob(created)
      message.success('选题策略任务已提交')
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
    setRefreshing(true)
    setResult(null)
    setActiveRow(null)
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
      message.success('策略任务已删除')
      setMatrixJobs((items) => items.filter((item) => item.id !== jobId))
      if (activeJob?.id === jobId) {
        setActiveJob(null)
        setResult(null)
        setActiveRow(null)
      }
      void loadMatrixJobs()
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    }
  }

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
    { title: 'Slot', dataIndex: 'slot', width: 72 },
    { title: 'Seed', dataIndex: 'seed_id', width: 96 },
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

  const sourcePanel = (
    <Col xs={24} xl={5}>
      <section style={{ ...sectionStyle, height: '100%' }}>
        <Flex align="center" justify="space-between" gap={12} style={{ marginBottom: 12 }}>
          <Typography.Title level={5} style={{ margin: 0 }}>内容资产输入</Typography.Title>
          <Button size="small" icon={<ReloadOutlined />} loading={loadingInputs} onClick={() => void loadAiwikiJobs()} />
        </Flex>
        <List
          size="small"
          loading={loadingInputs}
          dataSource={aiwikiJobs}
          locale={{ emptyText: '暂无已完成内容资产任务' }}
          style={{ maxHeight: 'calc(100vh - 190px)', overflow: 'auto' }}
          renderItem={(item) => {
            const active = item.id === selectedAiwikiJobId
            return (
              <List.Item
                onClick={() => setSelectedAiwikiJobId(item.id)}
                style={{
                  cursor: 'pointer',
                  background: active ? token.colorFillSecondary : undefined,
                  borderRadius: 6,
                  paddingInline: 8,
                }}
              >
                <Flex vertical gap={4} style={{ width: '100%' }}>
                  <Typography.Text strong ellipsis>{item.files[0]?.filename ?? item.id}</Typography.Text>
                  <Space wrap>
                    <Tag color="green">已完成</Tag>
                    <Tag>素材 {Number(item.summary.material_count ?? 0)}</Tag>
                    <Tag>选题 {Number(item.summary.topic_count ?? 0)}</Tag>
                  </Space>
                  <Typography.Text type="secondary">{formatDateTime(item.created_at)}</Typography.Text>
                </Flex>
              </List.Item>
            )
          }}
        />
      </section>
    </Col>
  )

  return (
    <>
      <Row gutter={[16, 16]} align="stretch">
        {!embedded && sourcePanel}
        <Col xs={24} xl={embedded ? 16 : 13}>
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
                  disabled={!selectedAiwikiJobId}
                  onClick={() => void submit()}
                >
                  {modeConfig.buttonText}
                </Button>
              </Flex>
              <Row gutter={[12, 12]} style={{ marginTop: 14 }}>
                <Col xs={12} md={8}><Statistic title="Seed 总量" value={modeConfig.defaults.expected_seed_count} /></Col>
                <Col xs={12} md={8}><Statistic title="每日 Slot" value={modeConfig.defaults.slots_per_day} /></Col>
                <Col xs={12} md={8}><Statistic title="入口模式" value={modeConfig.navLabel} /></Col>
              </Row>
              {modeConfig.showHooks && (
                <Form form={form} layout="vertical" initialValues={modeConfig.defaults} style={{ marginTop: 16 }}>
                  <Row gutter={12}>
                    <Col xs={24}>
                      <Form.List name="hooks">
                        {(fields, { add, remove }) => (
                          <Flex vertical gap={8}>
                            <Flex align="center" justify="space-between" gap={8}>
                              <Typography.Text>Hooks</Typography.Text>
                              <Button size="small" icon={<PlusOutlined />} onClick={() => add('')}>新增</Button>
                            </Flex>
                            {fields.map((field, index) => (
                              <Flex key={field.key} align="flex-start" gap={8}>
                                <Form.Item {...field} style={{ flex: 1, marginBottom: 0 }}>
                                  <Input.TextArea
                                    autoSize={{ minRows: 3, maxRows: 6 }}
                                    placeholder={`Hook ${index + 1}，可多行输入`}
                                  />
                                </Form.Item>
                                <Button
                                  danger
                                  type="text"
                                  icon={<DeleteOutlined />}
                                  disabled={fields.length <= 1}
                                  onClick={() => remove(field.name)}
                                />
                              </Flex>
                            ))}
                          </Flex>
                        )}
                      </Form.List>
                    </Col>
                  </Row>
                </Form>
              )}
              {error && <Alert type="error" showIcon message={error} style={{ marginTop: 12 }} />}
            </section>

            {result ? (
              <section id="matrix-result" style={sectionStyle}>
                <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
                  <Typography.Title level={4} style={{ margin: 0 }}>策略表结果</Typography.Title>
                  <Space wrap>
                    <Input.Search placeholder="搜索 seed、选题、痛点、方案" allowClear onSearch={setQuery} onChange={(event) => setQuery(event.target.value)} style={{ width: 260 }} />
                    <Segmented value={dayFilter} onChange={(value) => setDayFilter(String(value))} options={dayOptions} />
                    <Segmented value={accountFilter} onChange={(value) => setAccountFilter(String(value))} options={accountOptions} />
                    <Button icon={<DownloadOutlined />} onClick={() => activeJob && void downloadSeedMatrixCsv(activeJob.id)}>下载 CSV</Button>
                  </Space>
                </Flex>
                <Row gutter={[12, 12]} style={{ marginTop: 14, marginBottom: 14 }}>
                  <Col xs={12} md={6}><Statistic title="Seed" value={Number(result.summary.seed_count ?? 0)} /></Col>
                  <Col xs={12} md={6}><Statistic title="覆盖天数" value={Number(result.summary.day_count ?? 0)} /></Col>
                  <Col xs={12} md={6}><Statistic title="预计文章" value={Number(result.summary.expected_article_total ?? 0)} /></Col>
                  <Col xs={12} md={6}><Statistic title="账号类型" value={Number(result.summary.account_type_count ?? 0)} /></Col>
                </Row>
                <Table
                  size="small"
                  rowKey={(row) => row.seed_id}
                  columns={columns}
                  dataSource={filteredRows}
                  scroll={{ x: 1500 }}
                  pagination={{ pageSize: 10, showSizeChanger: true }}
                />
              </section>
            ) : (
              <section style={{ ...sectionStyle, minHeight: 260 }}>
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选择内容资产任务并生成策略表后，这里会展示表格结果" />
              </section>
            )}
          </Flex>
        </Col>
        <Col xs={24} xl={embedded ? 8 : 6}>
          <TaskPanel
            activeJob={activeJob}
            matrixJobs={matrixJobs}
            loading={loadingHistory}
            refreshing={refreshing}
            onRefreshHistory={loadMatrixJobs}
            onRefreshActive={() => activeJob && void refreshJob(activeJob.id)}
            onSelectJob={(jobId) => void selectMatrixJob(jobId)}
            onDeleteJob={(jobId) => void deleteMatrixJob(jobId)}
          />
        </Col>
      </Row>

      <Drawer
        title={activeRow?.topic ?? 'Seed 详情'}
        open={Boolean(activeRow)}
        onClose={() => setActiveRow(null)}
        width={620}
      >
        {activeRow && <SeedDetail row={activeRow} />}
      </Drawer>
    </>
  )
}

function TaskPanel({
  activeJob,
  matrixJobs,
  loading,
  refreshing,
  onRefreshHistory,
  onRefreshActive,
  onSelectJob,
  onDeleteJob,
}: {
  activeJob: SeedMatrixJob | null
  matrixJobs: SeedMatrixJobSummary[]
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
          <Typography.Title level={5} style={{ margin: 0 }}>策略任务</Typography.Title>
          <Space>
            <Button size="small" icon={<ReloadOutlined />} loading={refreshing} disabled={!activeJob} onClick={onRefreshActive} />
            <Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={() => void onRefreshHistory()} />
          </Space>
        </Flex>
        <Progress percent={meta.percent} status={meta.status} />
        {activeJob?.message && <Alert type={activeJob.status === 'failed' ? 'error' : 'info'} showIcon message={activeJob.message} />}
        <List
          size="small"
          loading={loading}
          dataSource={matrixJobs}
          locale={{ emptyText: '暂无策略任务' }}
          style={{ maxHeight: 280, overflow: 'auto' }}
          renderItem={(item) => (
            <List.Item
              onClick={() => onSelectJob(item.id)}
              style={{ cursor: 'pointer', background: item.id === activeJob?.id ? token.colorFillSecondary : undefined, borderRadius: 6, paddingInline: 8 }}
            >
              <Flex vertical gap={4} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color={item.status === 'completed' ? 'green' : item.status === 'failed' ? 'red' : 'blue'}>{statusMeta(item.status).label}</Tag>
                  <Tag>Seed {Number(item.summary.seed_count ?? 0)}</Tag>
                  <Tag>{seedMatrixModeLabel(item.params)}</Tag>
                  <Popconfirm
                    title="删除任务"
                    description="会删除该策略任务记录和 CSV 文件。"
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
                <Typography.Text strong ellipsis>{item.id}</Typography.Text>
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

function SeedDetail({ row }: { row: MatrixRow }) {
  const fields = [
    ['seed_id', 'Seed'],
    ['day', '天'],
    ['slot', 'Slot'],
    ['content_pool', '内容池'],
    ['topic', '选题'],
    ['pain_point', '痛点'],
    ['solution', '解决方案'],
    ['hook', '钩子'],
    ['mother_topic_prompt', '母题 Prompt'],
    ['variant_ids_to_generate', '变体 ID'],
    ['expected_article_count', '预计篇数'],
    ['primary_account_type', '主账号类型'],
    ['backup_account_types', '备选账号类型'],
    ['hook_package', 'Hook 包'],
    ['primary_hook_ids', 'Hook IDs'],
    ['cta_strategy', 'CTA 策略'],
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
