import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { App, Alert, Button, Col, Divider, Empty, Flex, Input, List, Modal, Progress, Row, Segmented, Space, Statistic, Table, Tag, Typography, Upload, theme } from 'antd'
import type { UploadFile, UploadProps } from 'antd'
import { CloudUploadOutlined, FileTextOutlined, FilterOutlined, LinkOutlined, PlayCircleOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { useAuth } from '../../hooks/useAuth'
import { createAiwikiJob, getAiwikiJob, getAiwikiResult, listAiwikiJobs, type AiwikiJob, type AiwikiJobSummary, type AiwikiProgressEvent, type AiwikiResult, type AiwikiWikiEntry } from '../../lib/aiwiki'
import { resolveErrorMessage } from '../dashboard/ExamplePage/utils'

const ACCEPTED_TYPES = '.docx,.md,.txt'
const ACTIVE_STATUSES = new Set(['queued', 'running'])

function textOf(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function titleOf(item: Record<string, unknown>): string {
  return textOf(item.title) || textOf(item['关键词']) || textOf(item['标题']) || ''
}

function descriptionOf(item: Record<string, unknown>): string {
  return textOf(item.description) || textOf(item['搜索意图']) || textOf(item['说明']) || textOf(item['适合文章角度']) || ''
}

function priorityColor(priority: unknown): string {
  if (priority === '高') return 'red'
  if (priority === '中') return 'gold'
  if (priority === '低') return 'default'
  return 'blue'
}

function entryTypeLabel(type: string): string {
  return {
    hotspot: '热点',
    pain_point: '痛点',
    solution: '解决方案',
    topic: '选题',
    search_intent: '搜索入口',
    article: '文章',
    index: '索引',
  }[type] ?? type
}

function statusMeta(status?: string) {
  if (status === 'queued') return { label: '排队中', percent: 15, status: 'active' as const }
  if (status === 'running') return { label: '生成中', percent: 55, status: 'active' as const }
  if (status === 'completed') return { label: '已完成', percent: 100, status: 'success' as const }
  if (status === 'failed') return { label: '失败', percent: 100, status: 'exception' as const }
  return { label: '未选择', percent: 0, status: 'normal' as const }
}

function formatDateTime(value?: string | null): string {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function firstFileName(job: AiwikiJobSummary | AiwikiJob): string {
  return job.files[0]?.filename ?? job.id
}

function progressEvents(job: AiwikiJob | null): AiwikiProgressEvent[] {
  return Array.isArray(job?.progress?.events) ? job.progress.events : []
}

function progressEventColor(event: string): string {
  if (event === 'completed') return 'green'
  if (event === 'failed') return 'red'
  if (event === 'started') return 'blue'
  return 'default'
}

export default function AiwikiPage() {
  const { message } = App.useApp()
  const { token } = theme.useToken()
  const { user } = useAuth()
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [job, setJob] = useState<AiwikiJob | null>(null)
  const [history, setHistory] = useState<AiwikiJobSummary[]>([])
  const [result, setResult] = useState<AiwikiResult | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedTerm, setSelectedTerm] = useState<string | null>(null)
  const [entryFilter, setEntryFilter] = useState<string>('全部')
  const [keywordModalOpen, setKeywordModalOpen] = useState(false)
  const [keywordSearch, setKeywordSearch] = useState('')

  const isAdmin = user?.role === 'admin'
  const meta = statusMeta(job?.status)

  const files = useMemo(
    () => fileList.map((item) => item.originFileObj).filter(Boolean) as File[],
    [fileList],
  )

  const uploadProps: UploadProps = {
    multiple: true,
    accept: ACCEPTED_TYPES,
    fileList,
    beforeUpload: () => false,
    onChange: ({ fileList: nextList }) => {
      setFileList(nextList.slice(0, 10))
      setError(null)
    },
    onRemove: (file) => {
      setFileList((current) => current.filter((item) => item.uid !== file.uid))
    },
  }

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const list = await listAiwikiJobs({ limit: 50, offset: 0 })
      setHistory(list.items)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  const refreshJob = useCallback(async (jobId: string, silent = false) => {
    if (!silent) setRefreshing(true)
    try {
      const latest = await getAiwikiJob(jobId)
      setJob(latest)
      setError(null)
      if (latest.status === 'completed') {
        setResult(await getAiwikiResult(jobId))
        void loadHistory()
      } else if (latest.status === 'failed') {
        setResult(null)
        void loadHistory()
      }
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      if (!silent) message.error(text)
    } finally {
      if (!silent) setRefreshing(false)
    }
  }, [loadHistory, message])

  const selectHistoryJob = useCallback(async (jobId: string) => {
    setRefreshing(true)
    setError(null)
    setResult(null)
    setSelectedTerm(null)
    try {
      const latest = await getAiwikiJob(jobId)
      setJob(latest)
      if (latest.status === 'completed') {
        setResult(await getAiwikiResult(jobId))
      }
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    } finally {
      setRefreshing(false)
    }
  }, [message])

  useEffect(() => {
    void loadHistory()
  }, [loadHistory])

  useEffect(() => {
    if (!job?.id || !ACTIVE_STATUSES.has(job.status)) return
    const timer = window.setInterval(() => {
      void refreshJob(job.id, true)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [job?.id, job?.status, refreshJob])

  const handleSubmit = async () => {
    if (!files.length) {
      setError('请先选择文件')
      return
    }
    setSubmitting(true)
    setError(null)
    setResult(null)
    setSelectedTerm(null)
    try {
      const created = await createAiwikiJob(files)
      setJob(created)
      message.success('任务已提交')
      void loadHistory()
      void refreshJob(created.id, true)
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    } finally {
      setSubmitting(false)
    }
  }

  const filteredSearchIntents = useMemo(() => {
    if (!result) return []
    if (!selectedTerm) return result.search_intents
    return result.search_intents.filter((item) => JSON.stringify(item).includes(selectedTerm))
  }, [result, selectedTerm])

  const filteredEntries = useMemo(() => {
    if (!result) return []
    if (entryFilter === '全部') return result.wiki_entries
    return result.wiki_entries.filter((entry) => entryTypeLabel(entry.type) === entryFilter)
  }, [entryFilter, result])

  const filteredTerms = useMemo(() => {
    const terms = result?.highlight_terms ?? []
    if (!keywordSearch.trim()) return terms
    return terms.filter((term) => term.includes(keywordSearch.trim()))
  }, [keywordSearch, result?.highlight_terms])

  return (
    <>
      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} xl={5}>
          <HistorySidebar
            history={history}
            activeJobId={job?.id}
            loading={historyLoading}
            isAdmin={isAdmin}
            onRefresh={loadHistory}
            onSelect={selectHistoryJob}
          />
        </Col>
        <Col xs={24} xl={13}>
          {result ? (
            <ResultView
              result={result}
              selectedTerm={selectedTerm}
              entryFilter={entryFilter}
              filteredSearchIntents={filteredSearchIntents}
              filteredEntries={filteredEntries}
              onOpenKeywordModal={() => setKeywordModalOpen(true)}
              onClearTerm={() => setSelectedTerm(null)}
              onEntryFilterChange={setEntryFilter}
            />
          ) : (
            <UploadPanel
              error={error}
              fileList={fileList}
              job={job}
              meta={meta}
              submitting={submitting}
              token={token}
              uploadProps={uploadProps}
              onSubmit={handleSubmit}
            />
          )}
        </Col>
        <Col xs={24} xl={6}>
          <TaskSidebar
            job={job}
            meta={meta}
            refreshing={refreshing}
            onRefresh={() => job && void refreshJob(job.id)}
          />
        </Col>
      </Row>

      <KeywordModal
        open={keywordModalOpen}
        terms={filteredTerms}
        selectedTerm={selectedTerm}
        keywordSearch={keywordSearch}
        onSearch={setKeywordSearch}
        onSelect={(term) => {
          setSelectedTerm(term)
          setKeywordModalOpen(false)
        }}
        onClear={() => {
          setSelectedTerm(null)
          setKeywordModalOpen(false)
        }}
        onClose={() => setKeywordModalOpen(false)}
      />
    </>
  )
}

function HistorySidebar({
  history,
  activeJobId,
  loading,
  isAdmin,
  onRefresh,
  onSelect,
}: {
  history: AiwikiJobSummary[]
  activeJobId?: string
  loading: boolean
  isAdmin: boolean
  onRefresh: () => void
  onSelect: (jobId: string) => void
}) {
  const { token } = theme.useToken()
  return (
    <aside style={{ background: token.colorBgContainer, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, padding: 14, height: '100%' }}>
      <Flex align="center" justify="space-between" gap={12} style={{ marginBottom: 12 }}>
        <Typography.Title level={5} style={{ margin: 0 }}>历史任务</Typography.Title>
        <Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={() => void onRefresh()} />
      </Flex>
      <List
        size="small"
        loading={loading}
        dataSource={history}
        locale={{ emptyText: '暂无历史任务' }}
        style={{ maxHeight: 'calc(100vh - 190px)', overflow: 'auto' }}
        renderItem={(item) => {
          const itemMeta = statusMeta(item.status)
          const active = item.id === activeJobId
          return (
            <List.Item
              style={{
                cursor: 'pointer',
                background: active ? token.colorFillSecondary : undefined,
                borderRadius: 6,
                paddingInline: 8,
              }}
              onClick={() => onSelect(item.id)}
            >
              <Flex vertical gap={4} style={{ width: '100%' }}>
                <Flex align="center" justify="space-between" gap={8}>
                  <Typography.Text strong ellipsis style={{ maxWidth: 160 }}>
                    {firstFileName(item)}
                  </Typography.Text>
                  <Tag color={item.status === 'completed' ? 'green' : item.status === 'failed' ? 'red' : 'blue'}>
                    {itemMeta.label}
                  </Tag>
                </Flex>
                {isAdmin && item.owner_username && <Typography.Text type="secondary">归属：{item.owner_username}</Typography.Text>}
                <Typography.Text type="secondary" ellipsis>{item.id}</Typography.Text>
                <Typography.Text type="secondary">{formatDateTime(item.created_at)}</Typography.Text>
              </Flex>
            </List.Item>
          )
        }}
      />
    </aside>
  )
}

function UploadPanel({
  error,
  job,
  meta,
  submitting,
  token,
  uploadProps,
  onSubmit,
}: {
  error: string | null
  fileList: UploadFile[]
  job: AiwikiJob | null
  meta: ReturnType<typeof statusMeta>
  submitting: boolean
  token: ReturnType<typeof theme.useToken>['token']
  uploadProps: UploadProps
  onSubmit: () => void
}) {
  return (
    <section style={{ background: token.colorBgContainer, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, minHeight: 560, padding: 24 }}>
      <Flex vertical gap={18}>
        <div>
          <Typography.Title level={2} style={{ marginTop: 0 }}>对标文章生文材料整理</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ maxWidth: 720 }}>
            选择 DOCX、Markdown 或 TXT 文件，生成热点、痛点、解决方案、关键词池、选题和可跳转 AI Wiki。
          </Typography.Paragraph>
        </div>
        <Upload.Dragger {...uploadProps} style={{ background: token.colorFillQuaternary }}>
          <p className="ant-upload-drag-icon">
            <CloudUploadOutlined />
          </p>
          <Typography.Text strong>选择文件，支持 DOCX、Markdown、TXT</Typography.Text>
          <Typography.Paragraph type="secondary" style={{ margin: '8px auto 0', maxWidth: 420 }}>
            可一次上传多个文件，系统会统一整理成同一份 AI Wiki 资产。
          </Typography.Paragraph>
        </Upload.Dragger>
        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          loading={submitting}
          disabled={!uploadProps.fileList?.length}
          onClick={onSubmit}
          style={{ alignSelf: 'flex-start' }}
        >
          开始生成
        </Button>
        {error && <Alert type="error" showIcon message={error} />}
        {job && !error && (
          <Alert
            type={job.status === 'failed' ? 'error' : 'info'}
            showIcon
            message={job.message || meta.label}
            description={job.status === 'completed' ? '任务已完成，结果正在加载。' : '任务状态和 OpenCode 日志可在右侧查看。'}
          />
        )}
      </Flex>
    </section>
  )
}

function TaskSidebar({
  job,
  meta,
  refreshing,
  onRefresh,
}: {
  job: AiwikiJob | null
  meta: ReturnType<typeof statusMeta>
  refreshing: boolean
  onRefresh: () => void
}) {
  const { token } = theme.useToken()
  return (
    <aside style={{ background: token.colorBgContainer, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, padding: 14, height: '100%' }}>
      <Flex vertical gap={14}>
        <Flex align="center" justify="space-between" gap={12}>
          <Typography.Title level={5} style={{ margin: 0 }}>任务状态</Typography.Title>
          <Button size="small" icon={<ReloadOutlined />} disabled={!job} loading={refreshing} onClick={onRefresh} />
        </Flex>
        <Progress percent={meta.percent} status={meta.status} />
        <Row gutter={[12, 12]}>
          <Col span={12}><Statistic title="状态" value={meta.label} /></Col>
          <Col span={12}><Statistic title="队列位置" value={job?.queue_position ?? '-'} /></Col>
        </Row>
        {job?.message && <Alert type={job.status === 'failed' ? 'error' : 'info'} showIcon message={job.message} />}
        {job?.files.length ? (
          <List
            size="small"
            dataSource={job.files}
            renderItem={(item) => (
              <List.Item>
                <Space direction="vertical" size={0}>
                  <Typography.Text strong>{item.filename}</Typography.Text>
                  <Typography.Text type="secondary">{item.raw_path}</Typography.Text>
                </Space>
              </List.Item>
            )}
          />
        ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未选择任务" />}
        <Divider style={{ margin: '8px 0' }} />
        <Flex align="center" justify="space-between" wrap="wrap" gap={8}>
          <Typography.Text type="secondary">progress.json 进度事件</Typography.Text>
          {job?.progress?.current_step && <Tag color="blue">{job.progress.current_step}</Tag>}
        </Flex>
        <List
          size="small"
          dataSource={progressEvents(job)}
          locale={{ emptyText: '暂无进度事件' }}
          style={{ maxHeight: 260, overflow: 'auto' }}
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
        <Divider style={{ margin: '8px 0' }} />
        <Typography.Text type="secondary">OpenCode 原始日志</Typography.Text>
        <pre style={{ margin: 0, minHeight: 160, maxHeight: 320, overflow: 'auto', whiteSpace: 'pre-wrap', color: token.colorTextSecondary }}>
          {job?.log_tail.length ? job.log_tail.join('\n') : '暂无日志'}
        </pre>
      </Flex>
    </aside>
  )
}

interface ResultViewProps {
  result: AiwikiResult
  selectedTerm: string | null
  entryFilter: string
  filteredSearchIntents: Array<Record<string, unknown>>
  filteredEntries: AiwikiWikiEntry[]
  onOpenKeywordModal: () => void
  onClearTerm: () => void
  onEntryFilterChange: (value: string) => void
}

function ResultView({
  result,
  selectedTerm,
  entryFilter,
  filteredSearchIntents,
  filteredEntries,
  onOpenKeywordModal,
  onClearTerm,
  onEntryFilterChange,
}: ResultViewProps) {
  const { token } = theme.useToken()
  const sectionStyle = {
    background: token.colorBgContainer,
    border: `1px solid ${token.colorBorderSecondary}`,
    borderRadius: 8,
    padding: 18,
  }

  return (
    <Flex vertical gap={16}>
      <section id="materials" style={sectionStyle}>
        <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
          <Typography.Title level={3} style={{ margin: 0 }}>AI Wiki 资产</Typography.Title>
          <Space wrap>
            {selectedTerm && <Tag closable onClose={onClearTerm}>筛选：{selectedTerm}</Tag>}
            <Button icon={<FilterOutlined />} onClick={onOpenKeywordModal}>
              关键词高亮筛选
            </Button>
          </Space>
        </Flex>
        <Divider />
        <Row gutter={[16, 16]}>
          <Col xs={12} md={6}><Statistic title="素材" value={Number(result.summary.material_count ?? 0)} /></Col>
          <Col xs={12} md={6}><Statistic title="词条" value={Number(result.summary.wiki_entry_count ?? 0)} /></Col>
          <Col xs={12} md={6}><Statistic title="关键词" value={Number(result.summary.search_intent_count ?? 0)} /></Col>
          <Col xs={12} md={6}><Statistic title="选题" value={Number(result.summary.topic_count ?? 0)} /></Col>
        </Row>
      </section>

      <AssetSection id="hotspot" title="热点" items={result.hotspots} selectedTerm={selectedTerm} />
      <AssetSection id="pain_point" title="痛点" items={result.pain_points} selectedTerm={selectedTerm} />
      <AssetSection id="solution" title="解决方案" items={result.solutions} selectedTerm={selectedTerm} />

      <section id="topic" style={sectionStyle}>
        <Typography.Title level={4} style={{ marginTop: 0 }}>选题矩阵</Typography.Title>
        <Row gutter={[12, 12]}>
          {result.topics.map((topic, index) => (
            <Col key={`${titleOf(topic)}-${index}`} xs={24} md={12}>
              <div style={{ border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, padding: 14, height: '100%' }}>
                <Space direction="vertical" size={8}>
                  <Tag color="purple">{textOf(topic.status) || 'idea'}</Tag>
                  <Typography.Text strong>{highlight(titleOf(topic), selectedTerm)}</Typography.Text>
                  {descriptionOf(topic) && <Typography.Paragraph type="secondary" style={{ margin: 0 }}>{highlight(descriptionOf(topic), selectedTerm)}</Typography.Paragraph>}
                </Space>
              </div>
            </Col>
          ))}
        </Row>
      </section>

      <section id="search_intent" style={sectionStyle}>
        <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
          <Typography.Title level={4} style={{ margin: 0 }}>搜索入口与关键词池</Typography.Title>
          <Tag icon={<SearchOutlined />}>{filteredSearchIntents.length} 条</Tag>
        </Flex>
        <Table
          size="small"
          rowKey={(record, index) => `${record['关键词']}-${index}`}
          dataSource={filteredSearchIntents}
          pagination={{ pageSize: 8 }}
          scroll={{ x: 900 }}
          columns={[
            {
              title: '意图',
              dataIndex: '意图类型',
              width: 110,
              render: (value) => <Tag>{String(value ?? '-')}</Tag>,
            },
            {
              title: '关键词',
              dataIndex: '关键词',
              width: 220,
              render: (value) => <Typography.Text strong>{highlight(String(value ?? ''), selectedTerm)}</Typography.Text>,
            },
            {
              title: '搜索意图',
              dataIndex: '搜索意图',
              render: (value) => highlight(String(value ?? ''), selectedTerm),
            },
            {
              title: '优先级',
              dataIndex: '优先级',
              width: 90,
              render: (value) => <Tag color={priorityColor(value)}>{String(value ?? '-')}</Tag>,
            },
          ]}
        />
      </section>

      <section style={sectionStyle}>
        <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
          <Typography.Title level={4} style={{ margin: 0 }}>Wiki 词条</Typography.Title>
          <Segmented
            value={entryFilter}
            onChange={(value) => onEntryFilterChange(String(value))}
            options={['全部', '热点', '痛点', '解决方案', '选题', '搜索入口']}
          />
        </Flex>
        <List
          dataSource={filteredEntries}
          locale={{ emptyText: '暂无词条' }}
          renderItem={(entry) => (
            <List.Item id={entry.slug}>
              <Flex vertical gap={8} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color="blue">{entryTypeLabel(entry.type)}</Tag>
                  <Typography.Text strong>{highlight(entry.title, selectedTerm)}</Typography.Text>
                  <Typography.Text type="secondary"><FileTextOutlined /> {entry.path}</Typography.Text>
                </Space>
                {entry.sections.slice(0, 2).map((section) => (
                  <div key={section.title}>
                    <Typography.Text type="secondary">{section.title}</Typography.Text>
                    <Typography.Paragraph style={{ margin: '4px 0 0' }}>
                      {highlight(section.content, selectedTerm)}
                    </Typography.Paragraph>
                  </div>
                ))}
                {entry.references.length > 0 && (
                  <Space wrap>
                    {entry.references.slice(0, 8).map((ref) => (
                      <Tag key={ref} icon={<LinkOutlined />}>{ref}</Tag>
                    ))}
                  </Space>
                )}
              </Flex>
            </List.Item>
          )}
        />
      </section>
    </Flex>
  )
}

function KeywordModal({
  open,
  terms,
  selectedTerm,
  keywordSearch,
  onSearch,
  onSelect,
  onClear,
  onClose,
}: {
  open: boolean
  terms: string[]
  selectedTerm: string | null
  keywordSearch: string
  onSearch: (value: string) => void
  onSelect: (term: string) => void
  onClear: () => void
  onClose: () => void
}) {
  return (
    <Modal
      title="关键词高亮筛选"
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="clear" onClick={onClear}>清除筛选</Button>,
        <Button key="close" type="primary" onClick={onClose}>完成</Button>,
      ]}
    >
      <Input
        allowClear
        prefix={<SearchOutlined />}
        placeholder="搜索关键词"
        value={keywordSearch}
        onChange={(event) => onSearch(event.target.value)}
        style={{ marginBottom: 16 }}
      />
      <Space wrap>
        {terms.map((term) => (
          <Tag
            key={term}
            color={selectedTerm === term ? 'blue' : 'default'}
            style={{ cursor: 'pointer', padding: '4px 8px' }}
            onClick={() => onSelect(term)}
          >
            {term}
          </Tag>
        ))}
      </Space>
      {!terms.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无匹配关键词" />}
    </Modal>
  )
}

function AssetSection({ id, title, items, selectedTerm }: { id: string; title: string; items: Array<Record<string, unknown>>; selectedTerm: string | null }) {
  const { token } = theme.useToken()
  return (
    <section id={id} style={{ background: token.colorBgContainer, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, padding: 18 }}>
      <Typography.Title level={4} style={{ marginTop: 0 }}>{title}</Typography.Title>
      <Row gutter={[12, 12]}>
        {items.map((item, index) => (
          <Col key={`${titleOf(item)}-${index}`} xs={24} md={12} xl={8}>
            <div style={{ border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, padding: 14, height: '100%' }}>
              <Typography.Text strong>{highlight(titleOf(item), selectedTerm)}</Typography.Text>
              {descriptionOf(item) && (
                <Typography.Paragraph type="secondary" style={{ margin: '8px 0 0' }}>
                  {highlight(descriptionOf(item), selectedTerm)}
                </Typography.Paragraph>
              )}
            </div>
          </Col>
        ))}
      </Row>
    </section>
  )
}

function highlight(text: string, term: string | null): ReactNode {
  if (!term || !text.includes(term)) return text
  const parts = text.split(term)
  return parts.map((part, index) => (
    <span key={`${part}-${index}`}>
      {part}
      {index < parts.length - 1 && <mark>{term}</mark>}
    </span>
  ))
}
