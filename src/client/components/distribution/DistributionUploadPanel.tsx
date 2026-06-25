import { Alert, Button, DatePicker, Empty, Flex, InputNumber, List, Select, Space, Switch, Tag, Typography } from 'antd'
import { CloudUploadOutlined, ReloadOutlined } from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createDistributionUpload,
  getDistributionDirectory,
  previewDistributionUploadPlan,
  type DistributionAccount,
  type DistributionDirectory,
  type DistributionProject,
  type DistributionSourceType,
  type DistributionTheme,
  type DistributionUploadPlan,
  type DistributionUploadResult,
  type DistributionUploadType,
} from '../../lib/distribution'
import { resolveErrorMessage } from '../../lib/errorMessage'
import { useAuth } from '../../hooks/useAuth'

function flattenAccounts(directory: DistributionDirectory | null): Array<DistributionAccount & { user_name: string }> {
  if (!directory) return []
  return directory.accounts.flatMap((user) => (
    (user.accounts ?? []).map((account) => ({ ...account, user_name: user.name }))
  ))
}

function projectThemeIds(project: DistributionProject | null): number[] {
  if (!project) return []
  if (Array.isArray(project.theme_ids) && project.theme_ids.length) return project.theme_ids
  return (project.themes ?? []).map((theme) => theme.id)
}

function accountProjectIds(account: DistributionAccount): number[] {
  if (Array.isArray(account.project_ids) && account.project_ids.length) return account.project_ids
  return (account.projects ?? []).map((project) => project.id)
}

export default function DistributionUploadPanel({
  onUploaded,
  sourceJobId,
  sourceType,
}: {
  onUploaded?: () => void
  sourceJobId: string
  sourceType: DistributionSourceType
}) {
  const { user } = useAuth()
  const uploadType: DistributionUploadType = sourceType === 'daily_writer'
    ? 'article'
    : sourceType === 'social_card_videos'
      ? 'video'
      : 'image_text'
  const [directory, setDirectory] = useState<DistributionDirectory | null>(null)
  const [loadingDirectory, setLoadingDirectory] = useState(false)
  const [planning, setPlanning] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [projectId, setProjectId] = useState<number | null>(null)
  const [themeId, setThemeId] = useState<number | null>(null)
  const [accountIds, setAccountIds] = useState<number[]>([])
  const [scheduledDate, setScheduledDate] = useState<Dayjs>(dayjs())
  const [perAccountCount, setPerAccountCount] = useState(1)
  const [ignoreHistory, setIgnoreHistory] = useState(false)
  const [plan, setPlan] = useState<DistributionUploadPlan | null>(null)
  const [uploadResult, setUploadResult] = useState<DistributionUploadResult | null>(null)

  const projects = useMemo(() => directory?.project_themes.projects ?? [], [directory])
  const themes = useMemo(() => directory?.project_themes.themes ?? [], [directory])
  const selectedProject = projects.find((project) => project.id === projectId) ?? null
  const themeIds = projectThemeIds(selectedProject)
  const themeOptions = themes.filter((theme) => !themeIds.length || themeIds.includes(theme.id))
  const accounts = flattenAccounts(directory)
  const accountOptions = accounts.filter((account) => (
    account.publication_type === uploadType
    && account.is_active
    && (!projectId || accountProjectIds(account).includes(projectId))
    && (!themeId || account.theme_id === themeId)
  ))

  const payload = useMemo(() => {
    if (!projectId || !themeId) return null
    return {
      source_type: sourceType,
      source_job_id: sourceJobId,
      project_id: projectId,
      theme_id: themeId,
      scheduled_date: scheduledDate.format('YYYY-MM-DD'),
      per_account_count: perAccountCount,
      ignore_history: ignoreHistory,
      account_ids: accountIds,
    }
  }, [accountIds, ignoreHistory, perAccountCount, projectId, scheduledDate, sourceJobId, sourceType, themeId])

  const loadDirectory = useCallback(async () => {
    setLoadingDirectory(true)
    try {
      const data = await getDistributionDirectory()
      setDirectory(data)
      const firstProject = data.project_themes.projects[0]
      setProjectId((current) => current ?? firstProject?.id ?? null)
      setError(null)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoadingDirectory(false)
    }
  }, [])

  useEffect(() => {
    if (user?.role !== 'admin') return
    void loadDirectory()
  }, [loadDirectory, user?.role])

  useEffect(() => {
    if (!selectedProject) return
    const availableThemeIds = projectThemeIds(selectedProject)
    const nextTheme = themes.find((theme) => availableThemeIds.includes(theme.id)) ?? themes[0]
    if (!themeId || !availableThemeIds.includes(themeId)) {
      setThemeId(nextTheme?.id ?? null)
      setAccountIds([])
      setPlan(null)
    }
  }, [selectedProject, themeId, themes])

  const previewPlan = async () => {
    if (!payload) {
      setError('请选择项目和主题')
      return
    }
    setPlanning(true)
    try {
      const nextPlan = await previewDistributionUploadPlan(payload)
      setPlan(nextPlan)
      setUploadResult(null)
      setError(null)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setPlanning(false)
    }
  }

  const upload = async () => {
    if (!payload) {
      setError('请选择项目和主题')
      return
    }
    setUploading(true)
    try {
      const result = await createDistributionUpload(payload)
      setPlan(result.plan)
      setUploadResult(result)
      setError(null)
      onUploaded?.()
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setUploading(false)
    }
  }

  if (user?.role !== 'admin') {
    return null
  }

  return (
    <section className="growth-config-section">
      <Flex align="center" justify="space-between" gap={12} wrap="wrap">
        <div>
          <Typography.Title level={5}>上传到分发平台</Typography.Title>
          <Typography.Text type="secondary">
            {uploadTypeLabel(uploadType)} · 手动上传
          </Typography.Text>
        </div>
        <Button icon={<ReloadOutlined />} loading={loadingDirectory} onClick={() => void loadDirectory()}>
          刷新目录
        </Button>
      </Flex>

      {error && <Alert type="error" showIcon message={error} />}

      <Flex gap={12} wrap="wrap" align="end">
        <label className="growth-number-field" style={{ minWidth: 220 }}>
          <span>项目</span>
          <Select
            loading={loadingDirectory}
            value={projectId ?? undefined}
            options={projects.map((project) => ({ label: project.name, value: project.id }))}
            onChange={(value) => {
              setProjectId(value)
              setAccountIds([])
              setPlan(null)
            }}
          />
        </label>
        <label className="growth-number-field" style={{ minWidth: 220 }}>
          <span>主题</span>
          <Select
            value={themeId ?? undefined}
            options={themeOptions.map((theme: DistributionTheme) => ({ label: theme.name, value: theme.id }))}
            onChange={(value) => {
              setThemeId(value)
              setAccountIds([])
              setPlan(null)
            }}
          />
        </label>
        <label className="growth-number-field" style={{ minWidth: 260 }}>
          <span>账号</span>
          <Select
            mode="multiple"
            allowClear
            maxTagCount="responsive"
            value={accountIds}
            placeholder="默认使用全部匹配账号"
            options={accountOptions.map((account) => ({
              label: `${account.platform} / ${account.account_name} / ${account.user_name}`,
              value: account.id,
            }))}
            onChange={(values) => {
              setAccountIds(values)
              setPlan(null)
            }}
          />
        </label>
        <label className="growth-number-field">
          <span>排期日期</span>
          <DatePicker value={scheduledDate} onChange={(value) => setScheduledDate(value ?? dayjs())} />
        </label>
        <label className="growth-number-field">
          <span>每账号数量</span>
          <InputNumber min={1} max={100} value={perAccountCount} onChange={(value) => setPerAccountCount(Number(value ?? 1))} />
        </label>
        <label className="growth-switch-field">
          <span>忽略历史</span>
          <Switch checked={ignoreHistory} onChange={setIgnoreHistory} />
        </label>
      </Flex>

      <Space wrap>
        <Button loading={planning} onClick={() => void previewPlan()}>预览计划</Button>
        <Button
          type="primary"
          icon={<CloudUploadOutlined />}
          loading={uploading}
          disabled={!payload}
          onClick={() => void upload()}
        >
          执行上传
        </Button>
      </Space>

      {plan ? (
        <div className="growth-readonly-summary is-compact">
          <ConfigItem label="账号" value={`${plan.account_count} 个`} />
          <ConfigItem label="批次" value={`${plan.batch_count} 个`} />
          <ConfigItem label="上传项" value={`${plan.item_count} 个`} />
          <ConfigItem label="跳过" value={`${plan.skipped.length} 个`} />
        </div>
      ) : null}

      {plan?.warnings.length ? (
        <Alert type="warning" showIcon message={plan.warnings.join('；')} />
      ) : null}

      {plan ? <PlanPreview plan={plan} /> : null}
      {uploadResult ? <UploadResult result={uploadResult} /> : null}
    </section>
  )
}

function uploadTypeLabel(uploadType: DistributionUploadType): string {
  if (uploadType === 'article') return '长文稿件'
  if (uploadType === 'video') return '轮播视频'
  return '小红书图文'
}

function ConfigItem({ label, value }: { label: string; value: string }) {
  return (
    <span className="growth-config-item">
      <small>{label}</small>
      <strong>{value || '-'}</strong>
    </span>
  )
}

function PlanPreview({ plan }: { plan: DistributionUploadPlan }) {
  const items = plan.batches.flatMap((batch) => (
    batch.items.map((item) => ({
      key: `${batch.account.id}-${item.source_key}`,
      account: `${batch.account.platform ?? ''} / ${batch.account.account_name ?? batch.account.id}`,
      title: item.title,
      source: item.source_label,
    }))
  ))
  if (!items.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前计划没有可上传项" />
  }
  return (
    <List
      size="small"
      dataSource={items.slice(0, 12)}
      header={<Typography.Text type="secondary">上传预览</Typography.Text>}
      renderItem={(item) => (
        <List.Item>
          <Flex justify="space-between" gap={12} style={{ width: '100%' }}>
            <Typography.Text ellipsis style={{ maxWidth: 520 }}>{item.title}</Typography.Text>
            <Space>
              <Tag>{item.source}</Tag>
              <Tag>{item.account}</Tag>
            </Space>
          </Flex>
        </List.Item>
      )}
    />
  )
}

function UploadResult({ result }: { result: DistributionUploadResult }) {
  const createdCount = result.results.reduce((sum, item) => sum + item.created_count, 0)
  return (
    <Alert
      type="success"
      showIcon
      message={result.job.message || `上传完成，共创建 ${createdCount} 篇内容`}
      description={`上传任务：${result.job.id}`}
    />
  )
}
