import { Alert, Button, Flex, Typography, Upload } from 'antd'
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
  title,
  description,
  buttonText,
  onSubmit,
}: {
  error: string | null
  job: AiwikiJob | null
  meta: ReturnType<typeof statusMeta>
  submitting: boolean
  token: NonNullable<ThemeConfig['token']>
  uploadProps: UploadProps
  title: string
  description: string
  buttonText: string
  onSubmit: () => void
}) {
  return (
    <section style={{ background: token.colorBgContainer, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, minHeight: 560, padding: 24 }}>
      <Flex vertical gap={18}>
        <div>
          <Typography.Title level={2} style={{ marginTop: 0 }}>{title}</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ maxWidth: 720 }}>
            {description}
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
        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          loading={submitting}
          disabled={!uploadProps.fileList?.length}
          onClick={onSubmit}
          style={{ alignSelf: 'flex-start' }}
        >
          {buttonText}
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
