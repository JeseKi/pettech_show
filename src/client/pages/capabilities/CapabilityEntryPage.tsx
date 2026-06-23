import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Col,
  Empty,
  Flex,
  Form,
  Input,
  List,
  Modal,
  Popconfirm,
  Progress,
  Row,
  Space,
  Tabs,
  Tag,
  Typography,
  theme,
} from 'antd'
import { DeleteOutlined, DownloadOutlined, FileTextOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  createCapabilityJob,
  deleteCapabilityJob,
  downloadCapabilityResult,
  getCapabilityJob,
  getCapabilityResult,
  listCapabilityJobs,
  type CapabilityJob,
  type CapabilityJobSummary,
  type CapabilityResult,
} from '../../lib/capabilityJobs'
import { resolveErrorMessage } from '../../lib/errorMessage'
import { formatDateTime, progressEventColor, statusMeta } from '../aiwiki/helpers'
import type { CapabilityEntryConfig } from '../../lib/workflowModes'

const ACTIVE_STATUSES = new Set(['queued', 'running'])

export default function CapabilityEntryPage({ entry }: { entry: CapabilityEntryConfig }) {
  const { token } = theme.useToken()
  const { message } = App.useApp()
  const [form] = Form.useForm<Record<string, string>>()
  const [jobs, setJobs] = useState<CapabilityJobSummary[]>([])
  const [activeJob, setActiveJob] = useState<CapabilityJob | null>(null)
  const [result, setResult] = useState<CapabilityResult | null>(null)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exampleOpen, setExampleOpen] = useState(false)

  const sectionStyle = {
    background: token.colorBgContainer,
    border: `1px solid ${token.colorBorderSecondary}`,
    borderRadius: 8,
    padding: 16,
  }

  const markdownComponents: Components = {
    table: ({ children }) => (
      <div style={{ overflowX: 'auto', margin: '16px 0' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 640 }}>
          {children}
        </table>
      </div>
    ),
    th: ({ children }) => (
      <th
        style={{
          border: `1px solid ${token.colorBorderSecondary}`,
          padding: '8px 10px',
          background: token.colorFillAlter,
          textAlign: 'left',
          whiteSpace: 'nowrap',
        }}
      >
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td
        style={{
          border: `1px solid ${token.colorBorderSecondary}`,
          padding: '8px 10px',
          verticalAlign: 'top',
        }}
      >
        {children}
      </td>
    ),
  }

  const loadJobs = useCallback(async () => {
    setLoadingHistory(true)
    try {
      const data = await listCapabilityJobs({ limit: 50, offset: 0, capability_key: entry.key })
      setJobs(data.items)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingHistory(false)
    }
  }, [entry.key])

  const refreshJob = useCallback(async (jobId: string, silent = false) => {
    if (!silent) setRefreshing(true)
    try {
      const job = await getCapabilityJob(jobId)
      setActiveJob(job)
      setError(null)
      if (job.status === 'completed') {
        setResult(await getCapabilityResult(jobId))
        void loadJobs()
      } else if (job.status === 'failed') {
        setResult(null)
        void loadJobs()
      }
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      if (!silent) message.error(text)
    } finally {
      if (!silent) setRefreshing(false)
    }
  }, [loadJobs, message])

  useEffect(() => {
    setActiveJob(null)
    setResult(null)
    setError(null)
    setExampleOpen(false)
    form.resetFields()
    void loadJobs()
  }, [entry.key, form, loadJobs])

  useEffect(() => {
    if (!activeJob?.id || !ACTIVE_STATUSES.has(activeJob.status)) return
    const timer = window.setInterval(() => {
      void refreshJob(activeJob.id, true)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [activeJob?.id, activeJob?.status, refreshJob])

  const submit = async () => {
    setSubmitting(true)
    setError(null)
    setResult(null)
    try {
      const values = await form.validateFields()
      const created = await createCapabilityJob({
        capability_key: entry.key,
        inputs: values,
      })
      setActiveJob(created)
      message.success('任务已提交')
      void loadJobs()
      void refreshJob(created.id, true)
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    } finally {
      setSubmitting(false)
    }
  }

  const selectJob = async (jobId: string) => {
    setRefreshing(true)
    setResult(null)
    try {
      const job = await getCapabilityJob(jobId)
      setActiveJob(job)
      if (job.status === 'completed') {
        setResult(await getCapabilityResult(jobId))
      }
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
      await deleteCapabilityJob(jobId)
      message.success('任务已删除')
      setJobs((items) => items.filter((item) => item.id !== jobId))
      if (activeJob?.id === jobId) {
        setActiveJob(null)
        setResult(null)
      }
      void loadJobs()
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    }
  }

  const fillExample = () => {
    if (!entry.example) return
    form.setFieldsValue(entry.example.values)
    setExampleOpen(false)
    message.success('已填入模板信息')
  }

  return (
    <Row gutter={[16, 16]} align="stretch">
      <Col xs={24} xl={16}>
        <Flex vertical gap={16}>
          <section style={sectionStyle}>
            <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
              <div>
                <Typography.Title level={3} style={{ margin: 0 }}>{entry.title}</Typography.Title>
                <Typography.Text type="secondary">{entry.description}</Typography.Text>
              </div>
              <Space wrap>
                {entry.example && (
                  <Button icon={<FileTextOutlined />} onClick={() => setExampleOpen(true)}>
                    查看输入示例
                  </Button>
                )}
                <Button type="primary" icon={<PlayCircleOutlined />} loading={submitting} onClick={() => void submit()}>
                  {entry.buttonText}
                </Button>
              </Space>
            </Flex>
            <Form form={form} layout="vertical" style={{ marginTop: 16 }} requiredMark={false}>
              <Row gutter={12}>
                {entry.inputs.map((input) => (
                  <Col key={input.key} xs={24} md={input.type === 'textarea' ? 24 : 12}>
                    <Form.Item
                      label={input.label}
                      name={input.key}
                      rules={input.required ? [{ required: true, message: `请填写${input.label}` }] : undefined}
                    >
                      {input.type === 'textarea' ? (
                        <Input.TextArea autoSize={{ minRows: 4, maxRows: 10 }} placeholder={input.placeholder} />
                      ) : (
                        <Input placeholder={input.placeholder} allowClear />
                      )}
                    </Form.Item>
                  </Col>
                ))}
              </Row>
            </Form>
            {error && <Alert type="error" showIcon message={error} style={{ marginTop: 12 }} />}
          </section>

          <section style={sectionStyle}>
            <Row gutter={[12, 12]}>
              <Col xs={24} md={12}>
                <Typography.Title level={5}>输出内容</Typography.Title>
                <List size="small" dataSource={entry.outputs} renderItem={(item) => <List.Item>{item}</List.Item>} />
              </Col>
              <Col xs={24} md={12}>
                <Typography.Title level={5}>执行流程</Typography.Title>
                <List size="small" dataSource={entry.steps} renderItem={(item, index) => <List.Item>{index + 1}. {item}</List.Item>} />
              </Col>
            </Row>
          </section>

          <section style={{ ...sectionStyle, minHeight: 360 }}>
            {result ? (
              <Tabs
                tabBarExtraContent={(
                  <Button icon={<DownloadOutlined />} onClick={() => activeJob && void downloadCapabilityResult(activeJob.id)}>
                    下载
                  </Button>
                )}
                items={[
                  {
                    key: 'markdown',
                    label: '报告',
                    children: (
                      <article style={{ maxWidth: 960 }}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{result.markdown}</ReactMarkdown>
                      </article>
                    ),
                  },
                  {
                    key: 'json',
                    label: 'JSON',
                    children: (
                      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', overflow: 'auto' }}>
                        {JSON.stringify(result.data, null, 2)}
                      </pre>
                    ),
                  },
                ]}
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="任务完成后，这里会展示 Markdown 报告和结构化 JSON" />
            )}
          </section>
        </Flex>
      </Col>
      <Col xs={24} xl={8}>
        <TaskPanel
          activeJob={activeJob}
          jobs={jobs}
          loading={loadingHistory}
          refreshing={refreshing}
          onRefreshHistory={loadJobs}
          onRefreshActive={() => activeJob && void refreshJob(activeJob.id)}
          onSelectJob={(jobId) => void selectJob(jobId)}
          onDeleteJob={(jobId) => void deleteJob(jobId)}
        />
      </Col>
      {entry.example && (
        <Modal
          title={entry.example.title}
          open={exampleOpen}
          onCancel={() => setExampleOpen(false)}
          width={760}
          footer={(
            <Space>
              <Button onClick={() => setExampleOpen(false)}>关闭</Button>
              <Button type="primary" onClick={fillExample}>
                点击填入模板信息
              </Button>
            </Space>
          )}
        >
          <Flex vertical gap={14}>
            <Typography.Text type="secondary">{entry.example.description}</Typography.Text>
            {entry.inputs.map((input) => {
              const value = entry.example?.values[input.key]
              if (!value) return null
              return (
                <div key={input.key}>
                  <Typography.Text strong>{input.label}</Typography.Text>
                  <pre
                    style={{
                      margin: '8px 0 0',
                      padding: 12,
                      borderRadius: 8,
                      border: `1px solid ${token.colorBorderSecondary}`,
                      background: token.colorFillQuaternary,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      maxHeight: 220,
                      overflow: 'auto',
                    }}
                  >
                    {value}
                  </pre>
                </div>
              )
            })}
          </Flex>
        </Modal>
      )}
    </Row>
  )
}

function TaskPanel({
  activeJob,
  jobs,
  loading,
  refreshing,
  onRefreshHistory,
  onRefreshActive,
  onSelectJob,
  onDeleteJob,
}: {
  activeJob: CapabilityJob | null
  jobs: CapabilityJobSummary[]
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
          <Typography.Title level={5} style={{ margin: 0 }}>任务记录</Typography.Title>
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
          dataSource={jobs}
          locale={{ emptyText: '暂无任务' }}
          style={{ maxHeight: 280, overflow: 'auto' }}
          renderItem={(item) => (
            <List.Item
              onClick={() => onSelectJob(item.id)}
              style={{ cursor: 'pointer', background: item.id === activeJob?.id ? token.colorFillSecondary : undefined, borderRadius: 6, paddingInline: 8 }}
            >
              <Flex vertical gap={4} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color={item.status === 'completed' ? 'green' : item.status === 'failed' ? 'red' : 'blue'}>{statusMeta(item.status).label}</Tag>
                  <Popconfirm
                    title="删除任务"
                    description="会删除该任务记录和生成文件。"
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
                <Typography.Text strong ellipsis>{String(item.summary.title || item.id)}</Typography.Text>
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
