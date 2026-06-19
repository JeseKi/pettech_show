import { Alert, Button, Col, Divider, Empty, Flex, List, Progress, Row, Space, Statistic, Tag, Typography, theme } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import type { AiwikiJob, AiwikiJobSummary } from '../../lib/aiwiki'
import { firstFileName, formatDateTime, progressEventColor, progressEvents, statusMeta } from './helpers'

export function HistorySidebar({
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

export function TaskSidebar({
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
