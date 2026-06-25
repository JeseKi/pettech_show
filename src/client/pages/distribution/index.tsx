import { Alert, App, Button, Empty, Flex, List, Segmented, Space, Statistic, Tag, Typography } from 'antd'
import { FileMarkdownOutlined, PictureOutlined, ReloadOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useMemo, useState } from 'react'
import DistributionUploadPanel from '../../components/distribution/DistributionUploadPanel'
import {
  listDistributionUploads,
  type DistributionSourceType,
  type DistributionUploadJob,
} from '../../lib/distribution'
import {
  listDailyWriterJobs,
  type DailyWriterJobSummary,
} from '../../lib/dailyWriter'
import {
  listSocialCardJobs,
  type SocialCardJobSummary,
} from '../../lib/socialCards'
import { resolveErrorMessage } from '../../lib/errorMessage'
import { useAuth } from '../../hooks/useAuth'
import { formatDateTime } from '../aiwiki/helpers'
import '../seedMatrix/GrowthWorkflow.css'

type SourceIds = Record<DistributionSourceType, string | null>
type SourceItem = {
  id: string
  title: string
  status: string
  created_at: string
}

const initialSourceIds: SourceIds = {
  daily_writer: null,
  social_cards: null,
}

function firstString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

function dailyWriterTitle(job: DailyWriterJobSummary): string {
  return firstString(
    job.summary.title,
    job.summary.headline,
    job.row.title,
    job.row.topic,
    job.row['标题'],
    job.row['选题'],
    job.seed_id,
    job.id,
  )
}

function socialCardTitle(job: SocialCardJobSummary): string {
  return firstString(
    job.summary.title,
    job.summary.headline,
    job.source_daily_writer_job_id,
    job.id,
  )
}

function sourceLabel(sourceType: DistributionSourceType): string {
  return sourceType === 'daily_writer' ? '稿件' : '图文'
}

function uploadTypeLabel(uploadType: string): string {
  return uploadType === 'image_text' ? '图文' : '长文'
}

function uploadStatusColor(status: string): string {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'error'
  return 'processing'
}

export default function DistributionStagePage() {
  const { message } = App.useApp()
  const { user } = useAuth()
  const [sourceType, setSourceType] = useState<DistributionSourceType>('daily_writer')
  const [selectedIds, setSelectedIds] = useState<SourceIds>(initialSourceIds)
  const [dailyWriterJobs, setDailyWriterJobs] = useState<DailyWriterJobSummary[]>([])
  const [socialCardJobs, setSocialCardJobs] = useState<SocialCardJobSummary[]>([])
  const [uploadJobs, setUploadJobs] = useState<DistributionUploadJob[]>([])
  const [loadingSources, setLoadingSources] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)

  const loadSources = useCallback(async () => {
    if (user?.role !== 'admin') return
    setLoadingSources(true)
    try {
      const [dailyWriters, socialCards] = await Promise.all([
        listDailyWriterJobs({ limit: 100, offset: 0 }),
        listSocialCardJobs({ limit: 100, offset: 0 }),
      ])
      setDailyWriterJobs(dailyWriters.items.filter((item) => item.status === 'completed' || item.status === 'partial_failed'))
      setSocialCardJobs(socialCards.items.filter((item) => item.status === 'completed'))
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setLoadingSources(false)
    }
  }, [message, user?.role])

  const loadUploadHistory = useCallback(async () => {
    if (user?.role !== 'admin') return
    setLoadingHistory(true)
    try {
      const list = await listDistributionUploads({ limit: 20, offset: 0 })
      setUploadJobs(list.items)
    } catch (err) {
      message.error(resolveErrorMessage(err))
    } finally {
      setLoadingHistory(false)
    }
  }, [message, user?.role])

  useEffect(() => {
    void loadSources()
    void loadUploadHistory()
  }, [loadSources, loadUploadHistory])

  useEffect(() => {
    setSelectedIds((current) => {
      const dailyId = current.daily_writer && dailyWriterJobs.some((item) => item.id === current.daily_writer)
        ? current.daily_writer
        : dailyWriterJobs[0]?.id ?? null
      const socialId = current.social_cards && socialCardJobs.some((item) => item.id === current.social_cards)
        ? current.social_cards
        : socialCardJobs[0]?.id ?? null
      if (dailyId === current.daily_writer && socialId === current.social_cards) return current
      return {
        daily_writer: dailyId,
        social_cards: socialId,
      }
    })
  }, [dailyWriterJobs, socialCardJobs])

  const sourceItems = useMemo<SourceItem[]>(() => (
    sourceType === 'daily_writer'
      ? dailyWriterJobs.map((job) => ({
        id: job.id,
        title: dailyWriterTitle(job),
        status: job.status,
        created_at: job.created_at,
      }))
      : socialCardJobs.map((job) => ({
        id: job.id,
        title: socialCardTitle(job),
        status: job.status,
        created_at: job.created_at,
      }))
  ), [dailyWriterJobs, socialCardJobs, sourceType])

  const selectedJobId = selectedIds[sourceType]
  const selectedJob = sourceItems.find((item) => item.id === selectedJobId) ?? null
  const totalSourceCount = dailyWriterJobs.length + socialCardJobs.length
  const completedUploadCount = uploadJobs.filter((item) => item.status === 'completed').length

  if (user?.role !== 'admin') {
    return (
      <div className="growth-generation-panel">
        <Alert
          type="warning"
          showIcon
          message="分发平台上传仅管理员可用"
        />
      </div>
    )
  }

  return (
    <div className="growth-workflow">
      <aside className="growth-task-rail">
        <Flex align="center" justify="space-between" gap={8} className="growth-task-rail-head">
          <div>
            <Typography.Text className="growth-eyebrow">Distribution</Typography.Text>
            <Typography.Title level={5} className="growth-rail-title">待分发内容</Typography.Title>
          </div>
          <Button
            icon={<ReloadOutlined />}
            loading={loadingSources}
            onClick={() => {
              void loadSources()
              void loadUploadHistory()
            }}
          />
        </Flex>
        <Segmented
          block
          value={sourceType}
          onChange={(value) => setSourceType(value as DistributionSourceType)}
          options={[
            { label: '稿件', value: 'daily_writer', icon: <FileMarkdownOutlined /> },
            { label: '图文', value: 'social_cards', icon: <PictureOutlined /> },
          ]}
        />
        <div className="growth-task-list">
          <List
            loading={loadingSources}
            dataSource={sourceItems}
            locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`暂无已完成${sourceLabel(sourceType)}`} /> }}
            renderItem={(job) => (
              <List.Item>
                <button
                  type="button"
                  className={job.id === selectedJobId ? 'growth-task-card is-active' : 'growth-task-card'}
                  onClick={() => setSelectedIds((current) => ({ ...current, [sourceType]: job.id }))}
                >
                  <span className="growth-task-card-title">{job.title}</span>
                  <span className="growth-task-card-meta">
                    {formatDateTime(job.created_at)}
                  </span>
                  <span className="growth-task-card-tags">
                    <Tag>{sourceLabel(sourceType)}</Tag>
                    <Tag color={job.status === 'completed' ? 'success' : 'warning'}>{job.status}</Tag>
                  </span>
                </button>
              </List.Item>
            )}
          />
        </div>
      </aside>

      <main className="growth-main-stage">
        <div className="growth-result-panel">
          <Flex align="center" justify="space-between" gap={12} wrap="wrap">
            <div className="growth-panel-heading">
              <Typography.Text className="growth-eyebrow">分发中心</Typography.Text>
              <Typography.Title level={4}>上传到 Info Distribution</Typography.Title>
              <Typography.Text type="secondary">集中处理稿件和图文的远端项目、主题、账号和排期。</Typography.Text>
            </div>
            <Button
              icon={<ReloadOutlined />}
              loading={loadingHistory}
              onClick={() => void loadUploadHistory()}
            >
              刷新历史
            </Button>
          </Flex>

          <div className="growth-readonly-summary is-compact">
            <ConfigItem label="待分发稿件" value={`${dailyWriterJobs.length}`} />
            <ConfigItem label="待分发图文" value={`${socialCardJobs.length}`} />
            <ConfigItem label="最近上传" value={`${uploadJobs.length}`} />
            <ConfigItem label="成功任务" value={`${completedUploadCount}`} />
          </div>

          {selectedJob ? (
            <DistributionUploadPanel
              key={`${sourceType}:${selectedJob.id}`}
              sourceType={sourceType}
              sourceJobId={selectedJob.id}
              onUploaded={() => void loadUploadHistory()}
            />
          ) : (
            <div className="growth-empty-state">
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={totalSourceCount ? '请选择左侧内容开始分发' : '暂无可分发内容'}
              />
            </div>
          )}

          <UploadHistory jobs={uploadJobs} loading={loadingHistory} />
        </div>
      </main>
    </div>
  )
}

function ConfigItem({ label, value }: { label: string; value: string }) {
  return (
    <span className="growth-config-item">
      <small>{label}</small>
      <strong>{value}</strong>
    </span>
  )
}

function UploadHistory({ jobs, loading }: { jobs: DistributionUploadJob[]; loading: boolean }) {
  return (
    <section className="growth-config-section">
      <Flex align="center" justify="space-between" gap={12} wrap="wrap">
        <div>
          <Typography.Title level={5}>上传历史</Typography.Title>
          <Typography.Text type="secondary">最近 20 次分发任务</Typography.Text>
        </div>
        <Statistic title="记录" value={jobs.length} />
      </Flex>
      <List
        loading={loading}
        dataSource={jobs}
        locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无上传历史" /> }}
        renderItem={(job) => (
          <List.Item>
            <Flex vertical gap={8} style={{ width: '100%' }}>
              <Flex align="center" justify="space-between" gap={12} wrap="wrap">
                <Space wrap>
                  <Tag color={uploadStatusColor(job.status)}>{job.status}</Tag>
                  <Tag>{uploadTypeLabel(job.upload_type)}</Tag>
                  <Typography.Text strong>{job.id}</Typography.Text>
                </Space>
                <Typography.Text type="secondary">{formatDateTime(job.created_at)}</Typography.Text>
              </Flex>
              <Typography.Text type="secondary">
                来源：{sourceLabel(job.source_type as DistributionSourceType)} / {job.source_job_id}
                {' · '}
                项目 {job.project_id} / 主题 {job.theme_id} / {job.scheduled_date}
              </Typography.Text>
              {job.message ? <Typography.Text type="secondary">{job.message}</Typography.Text> : null}
            </Flex>
          </List.Item>
        )}
      />
    </section>
  )
}
