import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Button, Flex, Input, Space, Tooltip, Typography, Upload } from 'antd'
import { BorderOuterOutlined, DeleteOutlined, EditOutlined, ItalicOutlined, OrderedListOutlined, PictureOutlined, PlayCircleOutlined, UnorderedListOutlined, UploadOutlined, VideoCameraOutlined } from '@ant-design/icons'
import type { AssetNode, AssetUploadState } from './interactiveMovieTypes'
import { assetTypeLabel } from './interactiveMovieCanvas'

export function AssetEditor({
  asset,
  uploadState,
  onChange,
  onUpload,
  onDelete,
}: {
  asset: AssetNode
  uploadState: AssetUploadState
  onChange: (updater: (asset: AssetNode) => AssetNode) => void
  onUpload: (file: File) => void
  onDelete: () => void
}) {
  const [markdownPreview, setMarkdownPreview] = useState(false)
  const isUploading = uploadState.status === 'uploading'
  const isText = asset.type === 'text'
  const isImage = asset.type === 'image'

  const updateText = (text: string) => {
    onChange((current) => ({ ...current, text }))
  }

  const appendMarkdown = (prefix: string, suffix = '') => {
    const currentText = asset.text ?? ''
    updateText(`${currentText}${currentText.endsWith('\n') || !currentText ? '' : '\n'}${prefix}${suffix}`)
  }

  return (
    <Flex vertical gap={16}>
      <Flex align="flex-start" justify="space-between" gap={12}>
        <div className="movie-panel-title-block">
          <Typography.Text className="movie-panel-kicker">{assetTypeLabel(asset.type)}</Typography.Text>
          <Input
            value={asset.title}
            onChange={(event) => onChange((current) => ({ ...current, title: event.target.value }))}
            className="movie-panel-title-input"
          />
        </div>
        <Button danger type="text" icon={<DeleteOutlined />} onClick={onDelete} aria-label={`删除素材 ${asset.title}`} />
      </Flex>

      {isText ? (
        <section className="movie-panel-section">
          <Flex align="center" justify="space-between">
            <Typography.Text className="movie-panel-label">文本内容</Typography.Text>
            <Space>
              <Tooltip title="加粗">
                <Button size="small" icon={<BorderOuterOutlined />} onClick={() => appendMarkdown('**加粗文本**')} />
              </Tooltip>
              <Tooltip title="斜体">
                <Button size="small" icon={<ItalicOutlined />} onClick={() => appendMarkdown('*斜体文本*')} />
              </Tooltip>
              <Tooltip title="无序列表">
                <Button size="small" icon={<UnorderedListOutlined />} onClick={() => appendMarkdown('- 列表项')} />
              </Tooltip>
              <Tooltip title="有序列表">
                <Button size="small" icon={<OrderedListOutlined />} onClick={() => appendMarkdown('1. 列表项')} />
              </Tooltip>
              <Button size="small" icon={<EditOutlined />} onClick={() => setMarkdownPreview((value) => !value)}>
                {markdownPreview ? '编辑' : '预览'}
              </Button>
            </Space>
          </Flex>
          {markdownPreview ? (
            <div className="movie-markdown-preview">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{asset.text ?? ''}</ReactMarkdown>
            </div>
          ) : (
            <Input.TextArea
              value={asset.text ?? ''}
              autoSize={{ minRows: 10, maxRows: 18 }}
              onChange={(event) => updateText(event.target.value)}
            />
          )}
        </section>
      ) : (
        <section className="movie-panel-section">
          <Typography.Text className="movie-panel-label">{isImage ? '图片文件' : '视频文件'}</Typography.Text>
          <div className="movie-panel-media" tabIndex={0}>
            {isImage && asset.media.url ? (
              <img src={asset.media.url} alt={asset.title} className="movie-panel-poster" draggable={false} />
            ) : !isImage && asset.media.url ? (
              <video src={asset.media.url} muted preload="metadata" className="movie-panel-video" draggable={false} />
            ) : (
              <div className="movie-panel-media-empty">
                {isImage ? <PictureOutlined /> : <VideoCameraOutlined />}
                <span>{isImage ? '图片待上传' : '视频待上传'}</span>
              </div>
            )}
            <div className="movie-panel-media-overlay">
              <Upload
                accept={isImage ? 'image/*' : 'video/*'}
                showUploadList={false}
                beforeUpload={(file) => {
                  onUpload(file)
                  return Upload.LIST_IGNORE
                }}
              >
                <Button icon={<UploadOutlined />} loading={isUploading}>
                  上传
                </Button>
              </Upload>
              {asset.media.url && !isImage && (
                <Button icon={<PlayCircleOutlined />} onClick={() => window.open(asset.media.url, '_blank', 'noreferrer')}>
                  预览
                </Button>
              )}
            </div>
          </div>
          {uploadState.message && (
            <div className={uploadState.status === 'failed' ? 'movie-generation-message is-error' : 'movie-generation-message'}>
              {uploadState.message}
            </div>
          )}
        </section>
      )}
    </Flex>
  )
}
