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
      width: 170,
      render: (value: string) => (
        <Typography.Text style={{ whiteSpace: 'nowrap' }}>{new Date(value).toLocaleString()}</Typography.Text>
      ),
    },
    {
      title: '操作者',
      dataIndex: 'actor_username',
      key: 'actor_username',
      width: 130,
      render: (value: string) => (
        <Typography.Text strong ellipsis={{ tooltip: value }} style={{ display: 'inline-block', maxWidth: 104 }}>
          {value}
        </Typography.Text>
      ),
    },
    {
      title: '动作',
      dataIndex: 'action',
      key: 'action',
      width: 110,
      align: 'center',
      render: (value: string) => (
        <Tag color={auditActionColor(value)} style={{ marginInlineEnd: 0 }}>
          {auditActionLabel(value)}
        </Tag>
      ),
    },
    {
      title: '对象',
      key: 'target',
      width: 470,
      render: (_, record) => {
        const filenames = extractAuditFilenames(record)
        return (
          <Flex vertical gap={8} style={{ minWidth: 0 }}>
            {record.job_id ? (
              <Flex align="center" gap={8} style={{ minWidth: 0 }}>
                <Typography.Text type="secondary" style={{ flex: 'none' }}>任务</Typography.Text>
                <Typography.Text code ellipsis={{ tooltip: record.job_id }} style={{ flex: 1, minWidth: 0 }}>
                  {record.job_id}
                </Typography.Text>
              </Flex>
            ) : null}
            <Flex wrap="wrap" gap={6}>
              {filenames.length ? filenames.map((filename, index) => (
                <Tag key={`${record.id}-${filename}-${index}`} style={{ maxWidth: 190, marginInlineEnd: 0 }}>
                  <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {filename}
                  </span>
                </Tag>
              )) : <Typography.Text type="secondary">-</Typography.Text>}
            </Flex>
          </Flex>
        )
      },
    },
    {
      title: '消息',
      dataIndex: 'message',
      key: 'message',
      width: 420,
      render: (value: string) => (
        <Typography.Paragraph
          ellipsis={{ rows: 2, tooltip: value }}
          style={{ marginBottom: 0, overflowWrap: 'anywhere' }}
        >
          {value}
        </Typography.Paragraph>
      ),
    },
  ], [])

  return (
    <Card>
      <Flex align="center" justify="space-between" wrap="wrap" gap={16} style={{ marginBottom: 16 }}>
        <Space>
          <FileSearchOutlined style={{ fontSize: 20 }} />
          <Typography.Title level={4} style={{ margin: 0 }}>知识库审计</Typography.Title>
          <Typography.Text type="secondary">共 {filteredLogs.length} 条记录</Typography.Text>
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
        scroll={{ x: 1300 }}
        tableLayout="fixed"
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
