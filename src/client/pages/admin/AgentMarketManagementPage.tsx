import { useCallback, useEffect, useState } from 'react'
import { Alert, Button, Form, Input, Modal, Select, Space, Switch, Table, Tabs, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import {
  createAdminAgent,
  createAdminAgentCategory,
  createAdminAgentTag,
  deleteAdminAgent,
  deleteAdminAgentCategory,
  deleteAdminAgentTag,
  getAdminAgent,
  listAdminAgentCategories,
  listAdminAgents,
  listAdminAgentTags,
  updateAdminAgent,
  updateAdminAgentCategory,
  updateAdminAgentTag,
  type AgentCategory,
  type AgentCreatePayload,
  type AgentMarketItem,
  type AgentTag,
  type AgentUpdatePayload,
} from '../../lib/agentMarket'
import { resolveErrorMessage } from '../../lib/errorMessage'

type AgentFormValues = AgentCreatePayload & {
  enabled: boolean
}

type CategoryFormValues = {
  id: string
  name: string
  description: string
  visibility: 'public' | 'admin'
  enabled: boolean
}

type TagFormValues = {
  id: string
  name: string
  enabled: boolean
}

const emptyAgentFormValues: AgentFormValues = {
  id: '',
  name: '',
  description: '',
  category_id: '',
  tag_ids: [],
  visibility: 'public',
  system_prompt: '',
  change_note: '',
  enabled: true,
}

const emptyCategoryFormValues: CategoryFormValues = {
  id: '',
  name: '',
  description: '',
  visibility: 'public',
  enabled: true,
}

const emptyTagFormValues: TagFormValues = {
  id: '',
  name: '',
  enabled: true,
}

export default function AgentMarketManagementPage() {
  const [agentForm] = Form.useForm<AgentFormValues>()
  const [categoryForm] = Form.useForm<CategoryFormValues>()
  const [tagForm] = Form.useForm<TagFormValues>()
  const [agents, setAgents] = useState<AgentMarketItem[]>([])
  const [categories, setCategories] = useState<AgentCategory[]>([])
  const [tags, setTags] = useState<AgentTag[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [agentModalOpen, setAgentModalOpen] = useState(false)
  const [categoryModalOpen, setCategoryModalOpen] = useState(false)
  const [tagModalOpen, setTagModalOpen] = useState(false)
  const [editingAgent, setEditingAgent] = useState<AgentMarketItem | null>(null)
  const [editingCategory, setEditingCategory] = useState<AgentCategory | null>(null)
  const [editingTag, setEditingTag] = useState<AgentTag | null>(null)
  const [lastError, setLastError] = useState<string | null>(null)

  const showRequestError = useCallback((title: string, error: unknown) => {
    const text = resolveErrorMessage(error)
    setLastError(`${title}：${text}`)
    Modal.error({ title, content: text })
  }, [])

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [nextAgents, nextCategories, nextTags] = await Promise.all([
        listAdminAgents(),
        listAdminAgentCategories(),
        listAdminAgentTags(),
      ])
      setAgents(nextAgents)
      setCategories(nextCategories)
      setTags(nextTags)
      setLastError(null)
    } catch (error) {
      showRequestError('加载 Agent 市场失败', error)
    } finally {
      setLoading(false)
    }
  }, [showRequestError])

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  const openCreateAgent = () => {
    setEditingAgent(null)
    agentForm.setFieldsValue(emptyAgentFormValues)
    setAgentModalOpen(true)
  }

  const openEditAgent = async (agent: AgentMarketItem) => {
    setLoading(true)
    try {
      const detail = await getAdminAgent(agent.id)
      setEditingAgent(detail)
      agentForm.setFieldsValue({
        id: detail.id,
        name: detail.name,
        description: detail.description,
        category_id: detail.category_id,
        tag_ids: detail.tag_ids,
        visibility: detail.visibility,
        system_prompt: detail.system_prompt ?? '',
        change_note: '',
        enabled: detail.enabled,
      })
      setAgentModalOpen(true)
    } catch (error) {
      showRequestError('加载 Agent 详情失败', error)
    } finally {
      setLoading(false)
    }
  }

  const saveAgent = async () => {
    const values = await agentForm.validateFields()
    setSaving(true)
    try {
      if (editingAgent) {
        const payload: AgentUpdatePayload = {
          name: values.name,
          description: values.description,
          category_id: values.category_id,
          tag_ids: values.tag_ids,
          visibility: values.visibility,
          enabled: values.enabled,
        }
        if (values.system_prompt !== (editingAgent.system_prompt ?? '')) {
          payload.system_prompt = values.system_prompt
          payload.change_note = values.change_note || '管理员更新'
        }
        await updateAdminAgent(editingAgent.id, payload)
      } else {
        await createAdminAgent({
          id: values.id,
          name: values.name,
          description: values.description,
          category_id: values.category_id,
          tag_ids: values.tag_ids,
          visibility: values.visibility,
          system_prompt: values.system_prompt,
          change_note: values.change_note || '初始版本',
        })
      }
      setAgentModalOpen(false)
      setLastError(null)
      await loadAll()
    } finally {
      setSaving(false)
    }
  }

  const openCreateCategory = () => {
    setEditingCategory(null)
    categoryForm.setFieldsValue(emptyCategoryFormValues)
    setCategoryModalOpen(true)
  }

  const openEditCategory = (category: AgentCategory) => {
    setEditingCategory(category)
    categoryForm.setFieldsValue(category)
    setCategoryModalOpen(true)
  }

  const saveCategory = async () => {
    const values = await categoryForm.validateFields()
    setSaving(true)
    try {
      if (editingCategory) {
        await updateAdminAgentCategory(editingCategory.id, {
          name: values.name,
          description: values.description,
          visibility: values.visibility,
          enabled: values.enabled,
        })
      } else {
        await createAdminAgentCategory({
          id: values.id,
          name: values.name,
          description: values.description,
          visibility: values.visibility,
        })
      }
      setCategoryModalOpen(false)
      setLastError(null)
      await loadAll()
    } finally {
      setSaving(false)
    }
  }

  const openCreateTag = () => {
    setEditingTag(null)
    tagForm.setFieldsValue(emptyTagFormValues)
    setTagModalOpen(true)
  }

  const openEditTag = (tag: AgentTag) => {
    setEditingTag(tag)
    tagForm.setFieldsValue(tag)
    setTagModalOpen(true)
  }

  const saveTag = async () => {
    const values = await tagForm.validateFields()
    setSaving(true)
    try {
      if (editingTag) {
        await updateAdminAgentTag(editingTag.id, {
          name: values.name,
          enabled: values.enabled,
        })
      } else {
        await createAdminAgentTag({
          id: values.id,
          name: values.name,
        })
      }
      setTagModalOpen(false)
      setLastError(null)
      await loadAll()
    } finally {
      setSaving(false)
    }
  }

  const confirmDeleteAgent = (agent: AgentMarketItem) => {
    Modal.confirm({
      title: `停用 Agent「${agent.name}」？`,
      content: 'Agent 会从用户市场隐藏，已有会话仍会保留已锁定的 Prompt 版本。',
      okText: '确认停用',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        try {
          await deleteAdminAgent(agent.id)
          await loadAll()
        } catch (error) {
          showRequestError('停用 Agent 失败', error)
          throw error
        }
      },
    })
  }

  const confirmDeleteCategory = (category: AgentCategory) => {
    Modal.confirm({
      title: `删除分类「${category.name}」？`,
      content: '如果已有 Agent 使用这个分类，删除会被拒绝。',
      okText: '确认删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        try {
          await deleteAdminAgentCategory(category.id)
          await loadAll()
        } catch (error) {
          showRequestError('删除分类失败', error)
          throw error
        }
      },
    })
  }

  const confirmDeleteTag = (tag: AgentTag) => {
    Modal.confirm({
      title: `删除标签「${tag.name}」？`,
      content: '会从已关联的 Agent 上移除这个标签。',
      okText: '确认删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        try {
          await deleteAdminAgentTag(tag.id)
          await loadAll()
        } catch (error) {
          showRequestError('删除标签失败', error)
          throw error
        }
      },
    })
  }

  const categoryOptions = categories.map((category) => ({
    label: `${category.name}${category.visibility === 'admin' ? '（老板）' : ''}`,
    value: category.id,
    disabled: !category.enabled && category.id !== editingAgent?.category_id,
  }))

  const tagOptions = tags.map((tag) => ({
    label: tag.name,
    value: tag.id,
    disabled: !tag.enabled && !editingAgent?.tag_ids.includes(tag.id),
  }))

  const agentColumns: ColumnsType<AgentMarketItem> = [
    {
      title: 'Agent',
      dataIndex: 'name',
      key: 'name',
      render: (_value, record) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{record.name}</Typography.Text>
          <Typography.Text type="secondary">{record.id}</Typography.Text>
        </Space>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category_label',
      key: 'category_label',
      render: (_value, record) => <Tag color={record.visibility === 'admin' ? 'warning' : 'blue'}>{record.category_label}</Tag>,
    },
    {
      title: '版本',
      dataIndex: 'current_version',
      key: 'current_version',
      width: 90,
      render: (value: number | null) => `v${value ?? 1}`,
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 150,
      render: (_value, record) => (
        <Space size={4}>
          <Tag color={record.enabled ? 'success' : 'default'}>{record.enabled ? '启用' : '停用'}</Tag>
          {record.protected && <Tag color="processing">默认</Tag>}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_value, record) => (
        <Space>
          <Button icon={<EditOutlined />} size="small" onClick={() => void openEditAgent(record)} />
          <Button
            danger
            disabled={record.protected || record.is_default}
            icon={<DeleteOutlined />}
            size="small"
            onClick={() => confirmDeleteAgent(record)}
          />
        </Space>
      ),
    },
  ]

  const categoryColumns: ColumnsType<AgentCategory> = [
    { title: '分类', dataIndex: 'name', key: 'name' },
    {
      title: '可见性',
      dataIndex: 'visibility',
      key: 'visibility',
      render: (value: AgentCategory['visibility']) => <Tag color={value === 'admin' ? 'warning' : 'blue'}>{value === 'admin' ? '老板' : '员工'}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (value: boolean) => <Tag color={value ? 'success' : 'default'}>{value ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_value, record) => (
        <Space>
          <Button icon={<EditOutlined />} size="small" onClick={() => openEditCategory(record)} />
          <Button danger icon={<DeleteOutlined />} size="small" onClick={() => confirmDeleteCategory(record)} />
        </Space>
      ),
    },
  ]

  const tagColumns: ColumnsType<AgentTag> = [
    { title: '标签', dataIndex: 'name', key: 'name' },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (value: boolean) => <Tag color={value ? 'success' : 'default'}>{value ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_value, record) => (
        <Space>
          <Button icon={<EditOutlined />} size="small" onClick={() => openEditTag(record)} />
          <Button danger icon={<DeleteOutlined />} size="small" onClick={() => confirmDeleteTag(record)} />
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
        <div>
          <Typography.Title level={4} style={{ margin: 0 }}>Agent 市场</Typography.Title>
          <Typography.Text type="secondary">
            维护会话级 System Prompt；Skill 仍通过 @ 在单轮消息中混用。
          </Typography.Text>
        </div>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void loadAll()}>
          刷新
        </Button>
      </Space>

      {lastError && <Alert closable message={lastError} onClose={() => setLastError(null)} type="error" />}

      <Tabs
        items={[
          {
            key: 'agents',
            label: 'Agent',
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Button type="primary" icon={<PlusOutlined />} onClick={openCreateAgent}>
                  添加 Agent
                </Button>
                <Table rowKey="id" columns={agentColumns} dataSource={agents} loading={loading} pagination={false} />
              </Space>
            ),
          },
          {
            key: 'categories',
            label: '分类',
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Button type="primary" icon={<PlusOutlined />} onClick={openCreateCategory}>
                  添加分类
                </Button>
                <Table rowKey="id" columns={categoryColumns} dataSource={categories} loading={loading} pagination={false} />
              </Space>
            ),
          },
          {
            key: 'tags',
            label: '标签',
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Button type="primary" icon={<PlusOutlined />} onClick={openCreateTag}>
                  添加标签
                </Button>
                <Table rowKey="id" columns={tagColumns} dataSource={tags} loading={loading} pagination={false} />
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editingAgent ? `编辑 Agent：${editingAgent.name}` : '添加 Agent'}
        open={agentModalOpen}
        confirmLoading={saving}
        width={760}
        onCancel={() => setAgentModalOpen(false)}
        onOk={() => {
          void saveAgent().catch((error) => showRequestError('保存 Agent 失败', error))
        }}
      >
        <Form form={agentForm} layout="vertical" initialValues={emptyAgentFormValues}>
          <Form.Item label="Agent ID" name="id" rules={[{ required: true, message: '请输入 Agent ID' }]}>
            <Input disabled={Boolean(editingAgent)} placeholder="例如 pet-content-director" />
          </Form.Item>
          <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如 宠物内容总监" />
          </Form.Item>
          <Form.Item label="描述" name="description" rules={[{ required: true, message: '请输入描述' }]}>
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} placeholder="说明这个 Agent 的角色、适用对象和任务边界" />
          </Form.Item>
          <Form.Item label="分类" name="category_id" rules={[{ required: true, message: '请选择分类' }]}>
            <Select options={categoryOptions} placeholder="选择分类" />
          </Form.Item>
          <Form.Item label="标签" name="tag_ids">
            <Select mode="multiple" options={tagOptions} placeholder="选择标签" />
          </Form.Item>
          <Form.Item label="可见性" name="visibility" rules={[{ required: true }]}>
            <Select
              options={[
                { label: '员工可见', value: 'public' },
                { label: '老板可见', value: 'admin' },
              ]}
            />
          </Form.Item>
          {editingAgent && (
            <Form.Item label="启用" name="enabled" valuePropName="checked">
              <Switch disabled={editingAgent.protected || editingAgent.is_default} />
            </Form.Item>
          )}
          <Form.Item label="System Prompt" name="system_prompt" rules={[{ required: true, message: '请输入 System Prompt' }]}>
            <Input.TextArea autoSize={{ minRows: 12, maxRows: 22 }} placeholder="写入这个 Agent 的身份、目标、边界、输出要求和风格..." />
          </Form.Item>
          <Form.Item label="版本备注" name="change_note">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} placeholder={editingAgent ? '说明这次 Prompt 更新的原因' : '初始版本'} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingCategory ? `编辑分类：${editingCategory.name}` : '添加分类'}
        open={categoryModalOpen}
        confirmLoading={saving}
        onCancel={() => setCategoryModalOpen(false)}
        onOk={() => {
          void saveCategory().catch((error) => showRequestError('保存分类失败', error))
        }}
      >
        <Form form={categoryForm} layout="vertical" initialValues={emptyCategoryFormValues}>
          <Form.Item label="分类 ID" name="id" rules={[{ required: true, message: '请输入分类 ID' }]}>
            <Input disabled={Boolean(editingCategory)} placeholder="例如 owner-agents" />
          </Form.Item>
          <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
          </Form.Item>
          <Form.Item label="可见性" name="visibility" rules={[{ required: true }]}>
            <Select
              options={[
                { label: '员工可见', value: 'public' },
                { label: '老板可见', value: 'admin' },
              ]}
            />
          </Form.Item>
          {editingCategory && (
            <Form.Item label="启用" name="enabled" valuePropName="checked">
              <Switch />
            </Form.Item>
          )}
        </Form>
      </Modal>

      <Modal
        title={editingTag ? `编辑标签：${editingTag.name}` : '添加标签'}
        open={tagModalOpen}
        confirmLoading={saving}
        onCancel={() => setTagModalOpen(false)}
        onOk={() => {
          void saveTag().catch((error) => showRequestError('保存标签失败', error))
        }}
      >
        <Form form={tagForm} layout="vertical" initialValues={emptyTagFormValues}>
          <Form.Item label="标签 ID" name="id" rules={[{ required: true, message: '请输入标签 ID' }]}>
            <Input disabled={Boolean(editingTag)} placeholder="例如 content-creation" />
          </Form.Item>
          <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          {editingTag && (
            <Form.Item label="启用" name="enabled" valuePropName="checked">
              <Switch />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </Space>
  )
}

