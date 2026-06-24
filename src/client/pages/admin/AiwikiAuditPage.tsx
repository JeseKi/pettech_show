import { App, Button, Card, Flex, Input, Space, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import { FileSearchOutlined, ReloadOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { listAiwikiAuditLogs, type AiwikiAuditLog } from '../../lib/aiwiki'
import { resolveErrorMessage } from '../../lib/errorMessage'

export default function AiwikiAuditPage() {
  const { message } = App.useApp()
  const [logs, setLogs] = useState<AiwikiAuditLog[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listAiwikiAuditLogs({ scope: 'all', limit: 100, offset: 0 })
      setLogs(data.items)
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const filteredLogs = useMemo(() => {
    const trimmed = keyword.trim().toLowerCase()
    if (!trimmed) return logs
    return logs.filter((item) => [
      item.actor_username,
      item.action,
      item.job_id ?? '',
      item.target_filename,
      item.message,
      ...extractAuditFilenames(item),
    ].join(' ').toLowerCase().includes(trimmed))
  }, [keyword, logs])

  const columns: TableColumnsType<AiwikiAuditLog> = useMemo(() => [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 190,
      render: (value: string) => new Date(value).toLocaleString(),
    },
    {
      title: '操作者',
      dataIndex: 'actor_username',
      key: 'actor_username',
      width: 150,
      render: (value: string) => <Typography.Text strong>{value}</Typography.Text>,
    },
    {
      title: '动作',
      dataIndex: 'action',
      key: 'action',
      width: 120,
      render: (value: string) => <Tag color={auditActionColor(value)}>{auditActionLabel(value)}</Tag>,
    },
    {
      title: '任务',
      dataIndex: 'job_id',
      key: 'job_id',
      width: 260,
      render: (value: string | null) => value ? <Typography.Text code copyable>{value}</Typography.Text> : '-',
    },
    {
      title: '文件',
      key: 'files',
      render: (_, record) => (
        <Flex wrap="wrap" gap={6}>
          {extractAuditFilenames(record).map((filename) => (
            <Tag key={`${record.id}-${filename}`}>{filename}</Tag>
          ))}
        </Flex>
      ),
    },
    {
      title: '消息',
      dataIndex: 'message',
      key: 'message',
      render: (value: string) => <Typography.Text>{value}</Typography.Text>,
    },
  ], [])

  return (
    <Card>
      <Flex align="center" justify="space-between" wrap="wrap" gap={16} style={{ marginBottom: 16 }}>
        <Space>
          <FileSearchOutlined style={{ fontSize: 20 }} />
          <Typography.Title level={4} style={{ margin: 0 }}>知识库审计</Typography.Title>
        </Space>
        <Space wrap>
          <Input
            allowClear
            placeholder="搜索操作者 / 任务 / 文件 / 消息"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            style={{ width: 280 }}
          />
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void loadData()}>刷新</Button>
        </Space>
      </Flex>
      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={filteredLogs}
        pagination={{ pageSize: 20, showSizeChanger: true }}
        scroll={{ x: 1120 }}
      />
    </Card>
  )
}

function auditActionLabel(action: string): string {
  return {
    upload: '上传',
    execute: '执行任务',
    update: '更新任务',
    delete: '删除',
  }[action] ?? action
}

function auditActionColor(action: string): string {
  if (action === 'delete') return 'red'
  if (action === 'update') return 'gold'
  if (action === 'execute') return 'blue'
  return 'green'
}

function extractAuditFilenames(item: AiwikiAuditLog): string[] {
  const filenames = item.metadata?.filenames
  if (Array.isArray(filenames)) {
    return filenames.filter((filename): filename is string => typeof filename === 'string' && Boolean(filename.trim()))
  }
  return item.target_filename
    .split(',')
    .map((filename) => filename.trim())
    .filter(Boolean)
}
