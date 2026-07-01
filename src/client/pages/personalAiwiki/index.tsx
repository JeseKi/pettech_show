import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Descriptions,
  Empty,
  Flex,
  Form,
  Input,
  List,
  Modal,
  Pagination,
  Progress,
  Space,
  Statistic,
  Tag,
  Timeline,
  Typography,
  Upload,
  theme,
  type UploadFile,
} from 'antd'
import {
  BookOutlined,
  CloudUploadOutlined,
  DeleteOutlined,
  FileTextOutlined,
  PlusOutlined,
  ReloadOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons'
import {
  createPersonalAiwikiJob,
  deletePersonalAiwikiJob,
  getPersonalAiwikiJob,
  getPersonalAiwikiResult,
  getPersonalAiwikiWorkspace,
  listPersonalAiwikiJobs,
  type PersonalAiwikiJob,
  type PersonalAiwikiJobSummary,
  type PersonalAiwikiResult,
} from '../../lib/personalAiwiki'
import type { AiwikiWikiEntry } from '../../lib/aiwiki'
import { resolveErrorMessage } from '../../lib/errorMessage'
import ResultView from '../aiwiki/ResultView'
import KeywordModal from '../aiwiki/KeywordModal'
import { ACTIVE_STATUSES, entryTypeLabel, formatDateTime, progressEventColor, statusMeta } from '../aiwiki/helpers'

type FormValues = {
  title?: string
  description?: string
  input_text?: string
}

const ACCEPTED_TYPES = '.md,.markdown,.txt,.xlsx,.csv,.pdf'
const TASK_PAGE_SIZE = 5
const PERSONAL_ENTRY_FILTER_OPTIONS = ['全部', '实体', '概念', '对比', '问答', '笔记']

const operationLabels: Record<string, string> = {
  ingest: '资料整理',
  query: '旧版任务',
  lint: '旧版任务',
}

export default function PersonalAiwikiPage() {
  const { message, modal } = App.useApp()
  const { token } = theme.useToken()
  const [form] = Form.useForm<FormValues>()
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [history, setHistory] = useState<PersonalAiwikiJobSummary[]>([])
  const [historyPage, setHistoryPage] = useState(1)
  const [historyTotal, setHistoryTotal] = useState(0)
  const [detailJob, setDetailJob] = useState<PersonalAiwikiJob | null>(null)
  const [workspaceResult, setWorkspaceResult] = useState<PersonalAiwikiResult | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [workspaceLoading, setWorkspaceLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [taskListOpen, setTaskListOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)
  const [selectedTerms, setSelectedTerms] = useState<string[]>([])
  const [entryFilter, setEntryFilter] = useState('全部')
  const [activeEntrySlug, setActiveEntrySlug] = useState<string | null>(null)
  const [keywordModalOpen, setKeywordModalOpen] = useState(false)
  const [keywordSearch, setKeywordSearch] = useState('')

  const loadHistory = useCallback(async (showLoading = true, page = historyPage) => {
    if (showLoading) setHistoryLoading(true)
    try {
      const list = await listPersonalAiwikiJobs({
        limit: TASK_PAGE_SIZE,
        offset: (page - 1) * TASK_PAGE_SIZE,
      })
      setHistory(list.items)
      setHistoryTotal(list.total)
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      if (showLoading) setHistoryLoading(false)
    }
  }, [historyPage, message])

  const loadWorkspace = useCallback(async (showLoading = false) => {
    if (showLoading) setWorkspaceLoading(true)
    try {
      setWorkspaceResult(await getPersonalAiwikiWorkspace())
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      if (showLoading) setWorkspaceLoading(false)
    }
  }, [message])

  const loadJob = useCallback(async (jobId: string, silent = false) => {
    try {
      const latest = await getPersonalAiwikiJob(jobId)
      setDetailJob(latest)
      setHistory((items) => upsertHistory(items, latest))
      if (latest.status === 'completed') {
        const nextResult = await getPersonalAiwikiResult(jobId)
        setWorkspaceResult(nextResult)
      }
      return latest
    } catch (err) {
      if (!silent) message.error(resolveErrorMessage(err))
      return null
    }
  }, [message])

  useEffect(() => {
    void loadHistory()
    void loadWorkspace(true)
  }, [loadHistory, loadWorkspace])

  const hasActiveJob = useMemo(() => (
    history.some((item) => ACTIVE_STATUSES.has(item.status))
    || (detailJob ? ACTIVE_STATUSES.has(detailJob.status) : false)
  ), [detailJob, history])

  useEffect(() => {
    if (!hasActiveJob) return
    const timer = window.setInterval(() => {
      void loadHistory(false)
      void loadWorkspace(false)
      if (detailJob?.id) {
        void loadJob(detailJob.id, true)
      }
    }, 2200)
    return () => window.clearInterval(timer)
  }, [detailJob?.id, hasActiveJob, loadHistory, loadJob, loadWorkspace])

  const activeJob = useMemo(() => (
    history.find((item) => ACTIVE_STATUSES.has(item.status))
    ?? (detailJob && ACTIVE_STATUSES.has(detailJob.status) ? detailJob : null)
  ), [detailJob, history])

  const entriesBySlug = useMemo(() => (
    new Map((workspaceResult?.wiki_entries ?? []).map((entry) => [entry.slug, entry]))
  ), [workspaceResult?.wiki_entries])

  const activeEntry = useMemo(() => (
    activeEntrySlug ? entriesBySlug.get(activeEntrySlug) ?? null : null
  ), [activeEntrySlug, entriesBySlug])

  const availableTerms = useMemo(() => workspaceResult?.highlight_terms ?? [], [workspaceResult?.highlight_terms])

  const filteredEntries = useMemo<AiwikiWikiEntry[]>(() => {
    if (!workspaceResult) return []
    return entryFilter === '全部'
      ? workspaceResult.wiki_entries
      : workspaceResult.wiki_entries.filter((entry) => entryTypeLabel(entry.type) === entryFilter)
  }, [entryFilter, workspaceResult])

  const summaryItems = useMemo(() => {
    const entries = workspaceResult?.wiki_entries ?? []
    return [
      { title: '知识条目', value: entries.length },
      { title: '关键词', value: workspaceResult?.highlight_terms.length ?? 0 },
      { title: '关联页面', value: entries.reduce((count, entry) => count + entry.reference_links.length, 0) },
      { title: '整理任务', value: history.filter((item) => item.operation === 'ingest').length },
    ]
  }, [history, workspaceResult])

  useEffect(() => {
    setSelectedTerms([])
  }, [availableTerms])

  const submitJob = async () => {
    const values = await form.validateFields()
    const files = fileList
      .map((file) => file.originFileObj)
      .filter((file): file is NonNullable<UploadFile['originFileObj']> => Boolean(file))
    const inputText = values.input_text?.trim()
    if (!inputText && files.length === 0) {
      message.warning('请上传文件或填写要整理的资料')
      return
    }

    setSubmitting(true)
    setUploadProgress(1)
    try {
      const created = await createPersonalAiwikiJob(
        {
          operation: 'ingest',
          title: values.title?.trim(),
          description: values.description?.trim(),
          input_text: inputText,
          files,
        },
        setUploadProgress,
      )
      form.resetFields()
      setFileList([])
      setCreateOpen(false)
      setDetailJob(created)
      setDetailOpen(true)
      message.success('已开始整理个人知识库')
      await loadHistory()
      void loadJob(created.id, true)
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setSubmitting(false)
      setUploadProgress(0)
    }
  }

  const openDetail = (target: PersonalAiwikiJobSummary) => {
    openDetailById(target.id)
  }

  const openDetailById = (jobId: string) => {
    setDetailOpen(true)
    setDetailJob(null)
    void loadJob(jobId)
  }

  const closeCreateModal = () => {
    if (submitting) return
    setCreateOpen(false)
    form.resetFields()
    setFileList([])
    setUploadProgress(0)
  }

  const confirmDelete = (target: PersonalAiwikiJobSummary) => {
    modal.confirm({
      title: `删除任务「${target.title}」？`,
      content: '只删除本次任务记录，不会删除已经整理好的个人知识库内容。',
      okText: '确认删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        try {
          await deletePersonalAiwikiJob(target.id)
          if (detailJob?.id === target.id) {
            setDetailJob(null)
            setDetailOpen(false)
          }
          message.success('任务已删除')
          await loadHistory()
        } catch (err) {
          message.error(resolveErrorMessage(err))
        }
      },
    })
  }

  const sectionStyle = {
    background: token.colorBgContainer,
    border: `1px solid ${token.colorBorderSecondary}`,
    borderRadius: 8,
    padding: 18,
  }

  return (
    <Flex vertical gap={18}>
      <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
        <Space>
          <BookOutlined style={{ fontSize: 22 }} />
          <div>
            <Typography.Title level={2} style={{ margin: 0 }}>个人 AI Wiki</Typography.Title>
            <Typography.Text type="secondary">把零散资料整理成可检索、可追问、可复用的个人知识库。</Typography.Text>
          </div>
        </Space>
        <Space wrap>
          <Button icon={<ReloadOutlined />} loading={workspaceLoading} onClick={() => { void loadHistory(); void loadWorkspace(true) }}>
            刷新
          </Button>
          <Button type="primary" icon={<UnorderedListOutlined />} onClick={() => setTaskListOpen(true)}>
            任务列表
          </Button>
        </Space>
      </Flex>

      {activeJob && (
        <Alert
          showIcon
          type="info"
          message={`正在整理：${activeJob.title}`}
          description={activeJob.message ?? '任务运行中，完成后个人知识库会自动刷新。'}
          action={<Button size="small" onClick={() => openDetailById(activeJob.id)}>查看任务</Button>}
        />
      )}

      <section style={sectionStyle}>
        <Flex wrap="wrap" gap={24}>
          {summaryItems.map((item) => (
            <Statistic key={item.title} title={item.title} value={item.value} />
          ))}
        </Flex>
      </section>

      {workspaceResult && (workspaceResult.wiki_home || workspaceResult.wiki_entries.length > 0) ? (
        <ResultView
          result={workspaceResult}
          selectedTerms={selectedTerms}
          entryFilter={entryFilter}
          entryFilterOptions={PERSONAL_ENTRY_FILTER_OPTIONS}
          summaryItems={summaryItems}
          filteredEntries={filteredEntries}
          entriesBySlug={entriesBySlug}
          activeEntry={activeEntry}
          onOpenKeywordModal={() => setKeywordModalOpen(true)}
          onEntryFilterChange={setEntryFilter}
          onOpenEntry={setActiveEntrySlug}
          onCloseEntry={() => setActiveEntrySlug(null)}
        />
      ) : (
        <section style={sectionStyle}>
          <Empty description="暂无可用知识条目" />
        </section>
      )}

      <Modal
        open={taskListOpen}
        title="任务列表"
        footer={null}
        width={820}
        onCancel={() => setTaskListOpen(false)}
      >
        <Flex vertical gap={14}>
          <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
            <Typography.Text type="secondary">整理任务会把上传资料沉淀到同一个个人知识库。</Typography.Text>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              新建任务
            </Button>
          </Flex>
          <List
            loading={historyLoading}
            dataSource={history}
            locale={{ emptyText: '暂无任务' }}
            renderItem={(item) => (
              <List.Item
                style={{ cursor: 'pointer' }}
                onClick={() => openDetail(item)}
                actions={[
                  <Button
                    key="delete"
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={(event) => {
                      event.stopPropagation()
                      confirmDelete(item)
                    }}
                  />,
                ]}
              >
                <List.Item.Meta
                  avatar={<FileTextOutlined />}
                  title={(
                    <Space wrap>
                      <Typography.Text strong>{item.title}</Typography.Text>
                      <Tag>{operationLabels[item.operation] ?? item.operation}</Tag>
                      <StatusTag status={item.status} />
                    </Space>
                  )}
                  description={(
                    <Flex vertical gap={4}>
                      <Typography.Text type="secondary">{formatDateTime(item.created_at)}</Typography.Text>
                      {item.description && <Typography.Text type="secondary">{item.description}</Typography.Text>}
                    </Flex>
                  )}
                />
              </List.Item>
            )}
          />
          {historyTotal > TASK_PAGE_SIZE && (
            <Pagination
              size="small"
              simple
              current={historyPage}
              pageSize={TASK_PAGE_SIZE}
              total={historyTotal}
              onChange={(page) => {
                setHistoryPage(page)
                void loadHistory(true, page)
              }}
            />
          )}
        </Flex>
      </Modal>

      <Modal
        open={createOpen}
        title="新建整理任务"
        footer={null}
        width={720}
        destroyOnClose
        onCancel={closeCreateModal}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="title" label="标题">
            <Input placeholder="可选，例如：竞品调研资料、产品 FAQ、客户反馈整理" maxLength={120} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="可选，补充这次希望整理的重点" rows={2} maxLength={1000} />
          </Form.Item>
          <Form.Item name="input_text" label="正文资料">
            <Input.TextArea
              rows={6}
              placeholder="可选，直接粘贴要整理的资料、会议记录、调研摘录或想法"
            />
          </Form.Item>
          <Form.Item label="文件">
            <Upload.Dragger
              multiple
              accept={ACCEPTED_TYPES}
              beforeUpload={() => false}
              fileList={fileList}
              onChange={({ fileList: nextFileList }) => setFileList(nextFileList)}
            >
              <p className="ant-upload-drag-icon"><CloudUploadOutlined /></p>
              <p className="ant-upload-text">上传文档、表格或 PDF</p>
              <p className="ant-upload-hint">适合整理调研资料、会议记录、客户反馈、FAQ 和项目文档</p>
            </Upload.Dragger>
          </Form.Item>
          {submitting && <Progress percent={uploadProgress} size="small" style={{ marginBottom: 12 }} />}
          <Button block type="primary" icon={<PlusOutlined />} loading={submitting} onClick={() => { void submitJob() }}>
            开始整理
          </Button>
        </Form>
      </Modal>

      <TaskDetailModal
        job={detailJob}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
      />

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
    </Flex>
  )
}

function TaskDetailModal({
  job,
  open,
  onClose,
}: {
  job: PersonalAiwikiJob | null
  open: boolean
  onClose: () => void
}) {
  const meta = statusMeta(job?.status)
  return (
    <Modal
      open={open}
      title={job?.title ?? '任务详情'}
      width={820}
      footer={<Button onClick={onClose}>关闭</Button>}
      onCancel={onClose}
    >
      {job ? (
        <Flex vertical gap={16}>
          <Space wrap>
            <Tag>{operationLabels[job.operation] ?? job.operation}</Tag>
            <StatusTag status={job.status} />
            {job.queue_position ? <Tag>队列：{job.queue_position}</Tag> : null}
          </Space>
          <Descriptions
            size="small"
            column={2}
            items={[
              { key: 'created', label: '创建时间', children: formatDateTime(job.created_at) },
              { key: 'finished', label: '完成时间', children: job.finished_at ? formatDateTime(job.finished_at) : '未完成' },
              { key: 'message', label: '状态说明', children: job.message || '暂无' },
              { key: 'files', label: '文件数量', children: job.files.length },
              { key: 'description', label: '描述', span: 2, children: job.description || '暂无' },
            ]}
          />
          <Progress percent={meta.percent} status={meta.status} />
          <Timeline
            items={(job.progress?.events ?? []).map((event, index) => ({
              key: `${event.step}-${index}`,
              color: progressEventColor(event.event),
              children: `${event.step}：${event.summary}`,
            }))}
          />
          {job.status === 'failed' && <Alert type="error" showIcon message={job.message || '任务失败'} />}
          <List
            size="small"
            header="本次资料"
            dataSource={job.files}
            locale={{ emptyText: '没有上传文件' }}
            renderItem={(file) => (
              <List.Item>
                <Space wrap>
                  <FileTextOutlined />
                  <Typography.Text>{file.filename}</Typography.Text>
                  <Typography.Text type="secondary">{Math.ceil(file.size_bytes / 1024)} KB</Typography.Text>
                </Space>
              </List.Item>
            )}
          />
          {job.log_tail.length > 0 && (
            <div>
              <Typography.Text strong>运行日志</Typography.Text>
              <pre style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>{job.log_tail.join('\n')}</pre>
            </div>
          )}
        </Flex>
      ) : (
        <Empty description="正在加载任务详情" />
      )}
    </Modal>
  )
}

function StatusTag({ status }: { status?: string }) {
  const meta = statusMeta(status)
  const color = status === 'completed'
    ? 'green'
    : status === 'failed'
      ? 'red'
      : ACTIVE_STATUSES.has(status ?? '')
        ? 'blue'
        : 'default'
  return <Tag color={color}>{meta.label}</Tag>
}

function upsertHistory(
  items: PersonalAiwikiJobSummary[],
  job: PersonalAiwikiJob,
): PersonalAiwikiJobSummary[] {
  const summary: PersonalAiwikiJobSummary = {
    id: job.id,
    owner_user_id: job.owner_user_id,
    owner_username: job.owner_username,
    operation: job.operation,
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
  const index = items.findIndex((item) => item.id === job.id)
  if (index < 0) return [summary, ...items]
  const next = [...items]
  next[index] = summary
  return next
}
