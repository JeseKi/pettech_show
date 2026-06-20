import { Alert, Button, Checkbox, Collapse, Flex, Typography, Upload } from 'antd'
import type { ThemeConfig } from 'antd'
import type { UploadProps } from 'antd'
import { CloudUploadOutlined, PlayCircleOutlined } from '@ant-design/icons'
import type { AiwikiJob } from '../../lib/aiwiki'
import type { statusMeta } from './helpers'

export default function UploadPanel({
  error,
  job,
  meta,
  submitting,
  token,
  uploadProps,
  generateSearchAssets,
  onGenerateSearchAssetsChange,
  onSubmit,
}: {
  error: string | null
  job: AiwikiJob | null
  meta: ReturnType<typeof statusMeta>
  submitting: boolean
  token: NonNullable<ThemeConfig['token']>
  uploadProps: UploadProps
  generateSearchAssets: boolean
  onGenerateSearchAssetsChange: (checked: boolean) => void
  onSubmit: () => void
}) {
  return (
    <section style={{ background: token.colorBgContainer, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, minHeight: 560, padding: 24 }}>
      <Flex vertical gap={18}>
        <div>
          <Typography.Title level={2} style={{ marginTop: 0 }}>对标文章生文材料整理</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ maxWidth: 720 }}>
            选择 DOCX、Markdown 或 TXT 文件，生成热点、痛点、解决方案、关键词池、选题和可跳转 AI Wiki。
          </Typography.Paragraph>
        </div>
        <Upload.Dragger {...uploadProps} style={{ background: token.colorFillQuaternary }}>
          <p className="ant-upload-drag-icon">
            <CloudUploadOutlined />
          </p>
          <Typography.Text strong>选择文件，支持 DOCX、Markdown、TXT</Typography.Text>
          <Typography.Paragraph type="secondary" style={{ margin: '8px auto 0', maxWidth: 420 }}>
            可一次上传多个文件，系统会统一整理成同一份 AI Wiki 资产。
          </Typography.Paragraph>
        </Upload.Dragger>
        <Collapse
          size="small"
          ghost
          items={[
            {
              key: 'advanced',
              label: '高级设置',
              children: (
                <Checkbox
                  checked={generateSearchAssets}
                  onChange={(event) => onGenerateSearchAssetsChange(event.target.checked)}
                >
                  生成搜索入口和关键词池
                </Checkbox>
              ),
            },
          ]}
        />
        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          loading={submitting}
          disabled={!uploadProps.fileList?.length}
          onClick={onSubmit}
          style={{ alignSelf: 'flex-start' }}
        >
          开始生成
        </Button>
        {error && <Alert type="error" showIcon message={error} />}
        {job && !error && (
          <Alert
            type={job.status === 'failed' ? 'error' : 'info'}
            showIcon
            message={job.message || meta.label}
            description={job.status === 'completed' ? '任务已完成，结果正在加载。' : '任务状态和 OpenCode 日志可在右侧查看。'}
          />
        )}
      </Flex>
    </section>
  )
}
