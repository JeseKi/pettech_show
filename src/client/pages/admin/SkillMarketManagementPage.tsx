import { useCallback, useEffect, useState } from 'react'
import { Alert, Button, Form, Input, Modal, Select, Space, Switch, Table, Tabs, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import {
  createAdminAgentSkill,
  createAdminAgentSkillCategory,
  createAdminAgentSkillTag,
  deleteAdminAgentSkill,
  deleteAdminAgentSkillCategory,
  deleteAdminAgentSkillTag,
  getAdminAgentSkill,
  listAdminAgentSkillCategories,
  listAdminAgentSkills,
  listAdminAgentSkillTags,
  updateAdminAgentSkill,
  updateAdminAgentSkillCategory,
  updateAdminAgentSkillTag,
  type AgentSkill,
  type AgentSkillCategory,
  type AgentSkillCreatePayload,
  type AgentSkillTag,
} from '../../lib/agentSkills'
import { resolveErrorMessage } from '../../lib/errorMessage'

type SkillFormValues = AgentSkillCreatePayload

type CategoryFormValues = {
  id: string
  name: string
  description: string
  enabled: boolean
}

type TagFormValues = {
  id: string
  name: string
  enabled: boolean
}

const emptySkillFormValues: SkillFormValues = {
  id: '',
  name: '',
  description: '',
  category_id: '',
  tag_ids: [],
  visibility: 'public',
  skill_markdown: '',
}

const emptyCategoryFormValues: CategoryFormValues = {
  id: '',
  name: '',
  description: '',
  enabled: true,
}

const emptyTagFormValues: TagFormValues = {
  id: '',
  name: '',
  enabled: true,
}

export default function SkillMarketManagementPage() {
  const [skillForm] = Form.useForm<SkillFormValues>()
  const [categoryForm] = Form.useForm<CategoryFormValues>()
  const [tagForm] = Form.useForm<TagFormValues>()
  const [skills, setSkills] = useState<AgentSkill[]>([])
  const [categories, setCategories] = useState<AgentSkillCategory[]>([])
  const [tags, setTags] = useState<AgentSkillTag[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [skillModalOpen, setSkillModalOpen] = useState(false)
  const [categoryModalOpen, setCategoryModalOpen] = useState(false)
  const [tagModalOpen, setTagModalOpen] = useState(false)
  const [editingSkill, setEditingSkill] = useState<AgentSkill | null>(null)
  const [editingCategory, setEditingCategory] = useState<AgentSkillCategory | null>(null)
  const [editingTag, setEditingTag] = useState<AgentSkillTag | null>(null)
  const [lastError, setLastError] = useState<string | null>(null)

  const showRequestError = useCallback((title: string, error: unknown) => {
    const text = resolveErrorMessage(error)
    setLastError(`${title}：${text}`)
    Modal.error({ title, content: text })
  }, [])

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [nextSkills, nextCategories, nextTags] = await Promise.all([
        listAdminAgentSkills(),
        listAdminAgentSkillCategories(),
        listAdminAgentSkillTags(),
      ])
      setSkills(nextSkills)
      setCategories(nextCategories)
      setTags(nextTags)
      setLastError(null)
    } catch (error) {
      showRequestError('加载 Skill 市场失败', error)
    } finally {
      setLoading(false)
    }
  }, [showRequestError])

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  const openCreateSkill = () => {
    setEditingSkill(null)
    skillForm.setFieldsValue(emptySkillFormValues)
    setSkillModalOpen(true)
  }

  const openEditSkill = async (skill: AgentSkill) => {
    setLoading(true)
    try {
      const detail = await getAdminAgentSkill(skill.id)
      setEditingSkill(detail)
      skillForm.setFieldsValue({
        id: detail.id,
        name: detail.name,
        description: detail.description,
        category_id: detail.category_id,
        tag_ids: detail.tag_ids,
        visibility: detail.visibility,
        skill_markdown: detail.skill_markdown ?? '',
      })
      setSkillModalOpen(true)
    } finally {
      setLoading(false)
    }
  }

  const saveSkill = async () => {
    const values = await skillForm.validateFields()
    setSaving(true)
    try {
      if (editingSkill) {
        await updateAdminAgentSkill(editingSkill.id, {
          name: values.name,
          description: values.description,
          category_id: values.category_id,
          tag_ids: values.tag_ids,
          visibility: values.visibility,
          skill_markdown: values.skill_markdown,
        })
      } else {
        await createAdminAgentSkill(values)
      }
      setSkillModalOpen(false)
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

  const openEditCategory = (category: AgentSkillCategory) => {
    setEditingCategory(category)
    categoryForm.setFieldsValue(category)
    setCategoryModalOpen(true)
  }

  const saveCategory = async () => {
    const values = await categoryForm.validateFields()
    setSaving(true)
    try {
      if (editingCategory) {
        await updateAdminAgentSkillCategory(editingCategory.id, {
          name: values.name,
          description: values.description,
          enabled: values.enabled,
        })
      } else {
        await createAdminAgentSkillCategory({
          id: values.id,
          name: values.name,
          description: values.description,
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

  const openEditTag = (tag: AgentSkillTag) => {
    setEditingTag(tag)
    tagForm.setFieldsValue(tag)
    setTagModalOpen(true)
  }

  const saveTag = async () => {
    const values = await tagForm.validateFields()
    setSaving(true)
    try {
      if (editingTag) {
        await updateAdminAgentSkillTag(editingTag.id, {
          name: values.name,
          enabled: values.enabled,
        })
      } else {
        await createAdminAgentSkillTag({
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

  const confirmDeleteSkill = (skill: AgentSkill) => {
    Modal.confirm({
      title: `删除 Skill「${skill.name}」？`,
      content: '会同时删除 data/skill_market 下的文件，并从所有用户智能体中移除。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        try {
          await deleteAdminAgentSkill(skill.id)
          setLastError(null)
          await loadAll()
        } catch (error) {
          showRequestError('删除 Skill 失败', error)
          throw error
        }
      },
    })
  }

  const confirmDeleteCategory = (category: AgentSkillCategory) => {
    Modal.confirm({
      title: `删除分类「${category.name}」？`,
      content: '如果已有 Skill 使用这个分类，删除会被拒绝。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        try {
          await deleteAdminAgentSkillCategory(category.id)
          setLastError(null)
          await loadAll()
        } catch (error) {
          showRequestError('删除分类失败', error)
          throw error
        }
      },
    })
  }

  const confirmDeleteTag = (tag: AgentSkillTag) => {
    Modal.confirm({
      title: `删除标签「${tag.name}」？`,
      content: '会从已关联的 Skill 上移除这个标签。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        try {
          await deleteAdminAgentSkillTag(tag.id)
          setLastError(null)
          await loadAll()
        } catch (error) {
          showRequestError('删除标签失败', error)
          throw error
        }
      },
    })
  }

  const skillColumns: ColumnsType<AgentSkill> = [
    {
      dataIndex: 'id',
      title: 'ID',
      width: 220,
      render: (value: string, record) => (
        <Space direction="vertical" size={0}>
          <Typography.Text code>{value}</Typography.Text>
          <Typography.Text type="secondary">{record.mention}</Typography.Text>
        </Space>
      ),
    },
    {
      dataIndex: 'name',
      title: '名称',
      render: (_, record) => (
        <Space direction="vertical" size={4}>
          <Typography.Text strong>{record.name}</Typography.Text>
          <Typography.Text type="secondary">{record.description}</Typography.Text>
        </Space>
      ),
    },
    {
      dataIndex: 'category_label',
      title: '系统分类',
      width: 180,
      render: (value: string, record) => (
        <Space direction="vertical" size={4}>
          <Tag color="blue">{value}</Tag>
          <Typography.Text type="secondary">
            {record.visibility === 'admin' ? '管理员可见' : '公开'}
          </Typography.Text>
        </Space>
      ),
    },
    {
      dataIndex: 'tags',
      title: '标签',
      width: 220,
      render: (skillTags: string[]) => (
        <Space wrap size={[4, 4]}>
          {skillTags.map((tag) => <Tag key={tag}>{tag}</Tag>)}
        </Space>
      ),
    },
    {
      key: 'actions',
      title: '操作',
      width: 120,
      render: (_, record) => (
        <Space>
          <Button icon={<EditOutlined />} size="small" onClick={() => void openEditSkill(record)} />
          <Button danger icon={<DeleteOutlined />} size="small" onClick={() => confirmDeleteSkill(record)} />
        </Space>
      ),
    },
  ]

  const categoryColumns: ColumnsType<AgentSkillCategory> = [
    { dataIndex: 'id', title: 'ID', width: 220, render: (value: string) => <Typography.Text code>{value}</Typography.Text> },
    { dataIndex: 'name', title: '分类名称', width: 180 },
    { dataIndex: 'description', title: '描述' },
    {
      dataIndex: 'enabled',
      title: '状态',
      width: 100,
      render: (enabled: boolean) => <Tag color={enabled ? 'green' : 'default'}>{enabled ? '启用' : '停用'}</Tag>,
    },
    {
      key: 'actions',
      title: '操作',
      width: 120,
      render: (_, record) => (
        <Space>
          <Button icon={<EditOutlined />} size="small" onClick={() => openEditCategory(record)} />
          <Button danger icon={<DeleteOutlined />} size="small" onClick={() => confirmDeleteCategory(record)} />
        </Space>
      ),
    },
  ]

  const tagColumns: ColumnsType<AgentSkillTag> = [
    { dataIndex: 'id', title: 'ID', width: 220, render: (value: string) => <Typography.Text code>{value}</Typography.Text> },
    { dataIndex: 'name', title: '标签名称' },
    {
      dataIndex: 'enabled',
      title: '状态',
      width: 100,
      render: (enabled: boolean) => <Tag color={enabled ? 'green' : 'default'}>{enabled ? '启用' : '停用'}</Tag>,
    },
    {
      key: 'actions',
      title: '操作',
      width: 120,
      render: (_, record) => (
        <Space>
          <Button icon={<EditOutlined />} size="small" onClick={() => openEditTag(record)} />
          <Button danger icon={<DeleteOutlined />} size="small" onClick={() => confirmDeleteTag(record)} />
        </Space>
      ),
    },
  ]

  const activeCategoryOptions = categories.map((category) => ({
    label: `${category.name}${category.enabled ? '' : '（停用）'}`,
    value: category.id,
    disabled: !category.enabled && category.id !== editingSkill?.category_id,
  }))

  const activeTagOptions = tags.map((tag) => ({
    label: `${tag.name}${tag.enabled ? '' : '（停用）'}`,
    value: tag.id,
    disabled: !tag.enabled && !editingSkill?.tag_ids.includes(tag.id),
  }))

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
        <div>
          <Typography.Title level={4} style={{ margin: 0 }}>Skill 市场</Typography.Title>
          <Typography.Text type="secondary">
            分类、标签和可见度由管理员维护；保存 Skill 时会同步写入 data/skill_market/&lt;id&gt;/agents/openai.yaml。
          </Typography.Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => void loadAll()}>刷新</Button>
      </Space>

      {lastError && (
        <Alert
          closable
          message={lastError}
          onClose={() => setLastError(null)}
          showIcon
          type="error"
        />
      )}

      <Tabs
        items={[
          {
            key: 'skills',
            label: 'Skill',
            children: (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
                  <Button type="primary" icon={<PlusOutlined />} onClick={openCreateSkill}>
                    添加 Skill
                  </Button>
                </Space>
                <Table
                  columns={skillColumns}
                  dataSource={skills}
                  loading={loading}
                  rowKey="id"
                  pagination={{ pageSize: 10 }}
                />
              </Space>
            ),
          },
          {
            key: 'categories',
            label: '系统分类',
            children: (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
                  <Button type="primary" icon={<PlusOutlined />} onClick={openCreateCategory}>
                    添加分类
                  </Button>
                </Space>
                <Table
                  columns={categoryColumns}
                  dataSource={categories}
                  loading={loading}
                  rowKey="id"
                  pagination={{ pageSize: 10 }}
                />
              </Space>
            ),
          },
          {
            key: 'tags',
            label: '标签',
            children: (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
                  <Button type="primary" icon={<PlusOutlined />} onClick={openCreateTag}>
                    添加标签
                  </Button>
                </Space>
                <Table
                  columns={tagColumns}
                  dataSource={tags}
                  loading={loading}
                  rowKey="id"
                  pagination={{ pageSize: 10 }}
                />
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editingSkill ? `编辑 Skill：${editingSkill.name}` : '添加 Skill'}
        open={skillModalOpen}
        okText="保存"
        confirmLoading={saving}
        onCancel={() => setSkillModalOpen(false)}
        onOk={() => {
          void saveSkill().catch((error) => showRequestError('保存 Skill 失败', error))
        }}
        width={860}
        destroyOnClose
      >
        <Form form={skillForm} layout="vertical" initialValues={emptySkillFormValues}>
          <Form.Item
            label="ID"
            name="id"
            rules={[
              { required: true, message: '请输入 Skill ID' },
              { pattern: /^[A-Za-z0-9][A-Za-z0-9_-]{1,60}$/, message: '只能包含字母、数字、下划线或连字符，长度 2-61' },
            ]}
          >
            <Input disabled={Boolean(editingSkill)} placeholder="例如 pet-review-reply" />
          </Form.Item>
          <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如 宠物客户评价回复" />
          </Form.Item>
          <Form.Item label="描述" name="description" rules={[{ required: true, message: '请输入描述' }]}>
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} placeholder="说明这个 Skill 适合谁、解决什么问题" />
          </Form.Item>
          <Form.Item label="系统分类" name="category_id" rules={[{ required: true, message: '请选择系统分类' }]}>
            <Select options={activeCategoryOptions} placeholder="选择管理员维护的系统分类" />
          </Form.Item>
          <Form.Item label="标签" name="tag_ids">
            <Select
              mode="multiple"
              options={activeTagOptions}
              placeholder="选择管理员维护的标签"
            />
          </Form.Item>
          <Form.Item label="可见度" name="visibility" rules={[{ required: true, message: '请选择可见度' }]}>
            <Select
              options={[
                { label: '公开', value: 'public' },
                { label: '管理员可见', value: 'admin' },
              ]}
            />
          </Form.Item>
          <Form.Item label="SKILL.md 正文" name="skill_markdown" rules={[{ required: true, message: '请输入 SKILL.md 正文' }]}>
            <Input.TextArea autoSize={{ minRows: 12, maxRows: 22 }} placeholder="# Skill 标题&#10;&#10;写入具体工作规范..." />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingCategory ? `编辑分类：${editingCategory.name}` : '添加系统分类'}
        open={categoryModalOpen}
        okText="保存"
        confirmLoading={saving}
        onCancel={() => setCategoryModalOpen(false)}
        onOk={() => {
          void saveCategory().catch((error) => showRequestError('保存分类失败', error))
        }}
        destroyOnClose
      >
        <Form form={categoryForm} layout="vertical" initialValues={emptyCategoryFormValues}>
          <Form.Item
            label="ID"
            name="id"
            rules={[
              { required: true, message: '请输入分类 ID' },
              { pattern: /^[A-Za-z0-9][A-Za-z0-9_-]{1,60}$/, message: '只能包含字母、数字、下划线或连字符，长度 2-61' },
            ]}
          >
            <Input disabled={Boolean(editingCategory)} placeholder="例如 store-operations" />
          </Form.Item>
          <Form.Item label="分类名称" name="name" rules={[{ required: true, message: '请输入分类名称' }]}>
            <Input placeholder="例如 门店运营" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
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
        okText="保存"
        confirmLoading={saving}
        onCancel={() => setTagModalOpen(false)}
        onOk={() => {
          void saveTag().catch((error) => showRequestError('保存标签失败', error))
        }}
        destroyOnClose
      >
        <Form form={tagForm} layout="vertical" initialValues={emptyTagFormValues}>
          <Form.Item
            label="ID"
            name="id"
            rules={[
              { required: true, message: '请输入标签 ID' },
              { pattern: /^[A-Za-z0-9][A-Za-z0-9_-]{1,60}$/, message: '只能包含字母、数字、下划线或连字符，长度 2-61' },
            ]}
          >
            <Input disabled={Boolean(editingTag)} placeholder="例如 store-operations" />
          </Form.Item>
          <Form.Item label="标签名称" name="name" rules={[{ required: true, message: '请输入标签名称' }]}>
            <Input placeholder="例如 门店运营" />
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
