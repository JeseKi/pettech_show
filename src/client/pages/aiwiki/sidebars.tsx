import { Alert, Button, Col, Divider, Empty, Flex, List, Popconfirm, Progress, Row, Space, Statistic, Tag, Typography, theme } from 'antd'
import { DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import type { AiwikiJob, AiwikiJobSummary, AiwikiResult } from '../../lib/aiwiki'
import { firstFileName, formatDateTime, progressEventColor, statusMeta } from './helpers'

const ACTIVE_STATUSES = new Set(['queued', 'running'])

export function HistorySidebar({
  history,
  activeJobId,
  loading,
  isAdmin,
  onRefresh,
  onSelect,
  onDelete,
}: {
  history: AiwikiJobSummary[]
  activeJobId?: string
  loading: boolean
  isAdmin: boolean
  onRefresh: () => void
  onSelect: (jobId: string) => void
  onDelete: (jobId: string) => void
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
                  <Space size={4}>
                    <Tag color={item.status === 'completed' ? 'green' : item.status === 'failed' ? 'red' : 'blue'}>
                      {itemMeta.label}
                    </Tag>
                    <Popconfirm
                      title="删除任务"
                      description="会删除该任务记录和生成文件。"
                      okText="删除"
                      cancelText="取消"
                      okButtonProps={{ danger: true }}
                      onConfirm={(event) => {
                        event?.stopPropagation()
                        onDelete(item.id)
                      }}
                      onCancel={(event) => event?.stopPropagation()}
                    >
                      <Button
                        size="small"
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(event) => event.stopPropagation()}
                      />
                    </Popconfirm>
                  </Space>
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

export function TaskSidebar({
  job,
  result,
  meta,
  refreshing,
  onRefresh,
}: {
  job: AiwikiJob | null
  result: AiwikiResult | null
  meta: ReturnType<typeof statusMeta>
  refreshing: boolean
  onRefresh: () => void
}) {
  const { token } = theme.useToken()

  if (job?.status === 'completed' && result) {
    const directory = [
      { key: 'overview', label: '概览', count: null as number | null, indent: 0 },
      ...(result.wiki_home?.headings.map((item) => ({
        key: item.id,
        label: item.title,
        count: null as number | null,
        indent: Math.max(0, Number(item.level ?? 2) - 1),
      })) ?? []),
      { key: 'entries', label: '词条预览', count: result.wiki_entries.length, indent: 0 },
    ]
    return (
      <aside style={{ background: token.colorBgContainer, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, padding: 14, height: '100%' }}>
        <Flex vertical gap={14}>
          <Typography.Title level={5} style={{ margin: 0 }}>目录</Typography.Title>
          <List
            size="small"
            dataSource={directory}
            renderItem={(item) => (
              <List.Item>
                <a href={`#${item.key}`}>
                  <Flex align="center" justify="space-between" style={{ width: '100%', paddingLeft: item.indent * 10 }} gap={8}>
                    <Typography.Text>{item.label}</Typography.Text>
                    {item.count !== null && <Tag>{item.count}</Tag>}
                  </Flex>
                </a>
              </List.Item>
            )}
          />
          <Divider style={{ margin: '8px 0' }} />
          <Typography.Title level={5} style={{ margin: 0 }}>素材</Typography.Title>
          {job.files.length ? (
            <SourceFileList files={job.files} />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无素材" />
          )}
        </Flex>
      </aside>
    )
  }

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
          <SourceFileList files={job.files} />
        ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未选择任务" />}
        <Divider style={{ margin: '8px 0' }} />
        <Flex align="center" justify="space-between" wrap="wrap" gap={8}>
          <Typography.Text type="secondary">progress.json 进度事件</Typography.Text>
          {visibleProgressStep(job) && <Tag color="blue">{visibleProgressStep(job)}</Tag>}
        </Flex>
        <List
          size="small"
          dataSource={visibleProgressEvents(job)}
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

function visibleProgressStep(job: AiwikiJob | null | undefined): string {
  if (!job?.progress?.current_step) return ''
  if (hasTerminalProgressWhileActive(job)) return ''
  return job.progress.current_step
}

function visibleProgressEvents(job: AiwikiJob | null | undefined) {
  const events = Array.isArray(job?.progress?.events) ? job.progress.events : []
  if (!hasTerminalProgressWhileActive(job)) return events
  return events.filter((item) => item.summary !== '任务完成' && item.event !== '失败')
}

function hasTerminalProgressWhileActive(job: AiwikiJob | null | undefined): boolean {
  if (!job || !ACTIVE_STATUSES.has(job.status)) return false
  const progressStatus = String(job.progress.status || '')
  const events = Array.isArray(job.progress.events) ? job.progress.events : []
  const latest = events.at(-1)
  return progressStatus === 'completed'
    || progressStatus === 'failure'
    || progressStatus === 'failed'
    || latest?.summary === '任务完成'
    || latest?.event === '失败'
}

function SourceFileList({ files }: { files: AiwikiJob['files'] }) {
  return (
    <List
      size="small"
      dataSource={files}
      renderItem={(item) => (
        <List.Item>
          <Space direction="vertical" size={0}>
            <Typography.Text type="secondary">素材</Typography.Text>
            <Typography.Text strong>{item.filename}</Typography.Text>
            <Typography.Text type="secondary">{item.raw_path}</Typography.Text>
          </Space>
        </List.Item>
      )}
    />
  )
}
