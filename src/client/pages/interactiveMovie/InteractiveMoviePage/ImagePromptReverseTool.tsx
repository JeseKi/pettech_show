import { useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { App, Button, Tabs, Typography } from 'antd'
import { CloseOutlined, CopyOutlined, DeleteOutlined, DragOutlined, HistoryOutlined, InboxOutlined, ReloadOutlined, SnippetsOutlined, UploadOutlined } from '@ant-design/icons'
import {
  deleteInteractiveMovieImagePromptHistory,
  listInteractiveMovieImagePromptHistory,
  reverseInteractiveMovieImagePrompt,
  type ImagePromptReverseRecord,
  type ImagePromptReverseResult,
} from '../../../lib/interactiveMovie'
import { resolveErrorMessage } from '../../../lib/errorMessage'
import { confirmAgentOperationLeave, useAgentOperationLeaveGuard } from '../../../hooks/useAgentOperationLeaveGuard'
import { useInteractiveMoviePageContext } from './useInteractiveMoviePageContext'

type PanelGeometry = {
  height: number
  width: number
  x: number
  y: number
}

type PanelInteraction =
  | {
    type: 'drag'
    pointerId: number
    startClient: { x: number; y: number }
    startGeometry: PanelGeometry
  }
  | {
    type: 'resize'
    pointerId: number
    startClient: { x: number; y: number }
    startGeometry: PanelGeometry
  }

const PANEL_GEOMETRY_KEY = 'interactiveMovie.imagePromptReverse.panelGeometry'

const defaultPanelGeometry = (): PanelGeometry => {
  const width = 520
  const height = 640
  return {
    width,
    height,
    x: Math.max(16, (window.innerWidth - width) / 2),
    y: Math.max(72, (window.innerHeight - height) / 2),
  }
}

const clampPanelGeometry = (geometry: PanelGeometry): PanelGeometry => {
  const maxWidth = Math.max(340, window.innerWidth - 24)
  const maxHeight = Math.max(360, window.innerHeight - 72)
  const width = Math.min(Math.max(340, geometry.width), maxWidth)
  const height = Math.min(Math.max(360, geometry.height), maxHeight)
  return {
    width,
    height,
    x: Math.min(Math.max(12, geometry.x), Math.max(12, window.innerWidth - width - 12)),
    y: Math.min(Math.max(56, geometry.y), Math.max(56, window.innerHeight - height - 12)),
  }
}

const loadPanelGeometry = () => {
  try {
    const raw = localStorage.getItem(PANEL_GEOMETRY_KEY)
    if (!raw) return defaultPanelGeometry()
    const parsed = JSON.parse(raw) as Partial<PanelGeometry>
    if (
      typeof parsed.width === 'number'
      && typeof parsed.height === 'number'
      && typeof parsed.x === 'number'
      && typeof parsed.y === 'number'
    ) {
      return clampPanelGeometry(parsed as PanelGeometry)
    }
  } catch {
    // ignore invalid local state
  }
  return defaultPanelGeometry()
}

const visualBreakdownItems: Array<{ key: keyof ImagePromptReverseResult['visual_breakdown']; label: string }> = [
  { key: 'subject', label: '主体' },
  { key: 'scene', label: '场景' },
  { key: 'composition', label: '构图' },
  { key: 'lighting', label: '光线' },
  { key: 'color', label: '色彩' },
  { key: 'style_medium', label: '风格/媒介' },
  { key: 'texture', label: '质感' },
  { key: 'ai_generation_trace', label: 'AI 生成痕迹' },
]

const formatRecordTime = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function PromptTextBlock({ text, onCopy }: { text: string; onCopy: (text: string) => void }) {
  return (
    <div className="movie-prompt-text-block">
      <Button size="small" icon={<CopyOutlined />} onClick={() => onCopy(text)}>复制</Button>
      <pre>{text}</pre>
    </div>
  )
}

function SdPromptColumns({
  negativePrompt,
  onCopy,
  positivePrompt,
}: {
  negativePrompt: string
  onCopy: (text: string) => void
  positivePrompt: string
}) {
  return (
    <div className="movie-prompt-sd-columns">
      <section className="movie-prompt-sd-column">
        <div className="movie-prompt-sd-heading">
          <strong>正面提示词</strong>
          <Button size="small" icon={<CopyOutlined />} onClick={() => onCopy(positivePrompt)}>复制</Button>
        </div>
        <pre>{positivePrompt}</pre>
      </section>
      <section className="movie-prompt-sd-column">
        <div className="movie-prompt-sd-heading">
          <strong>反面提示词</strong>
          <Button size="small" icon={<CopyOutlined />} onClick={() => onCopy(negativePrompt)}>复制</Button>
        </div>
        <pre>{negativePrompt}</pre>
      </section>
    </div>
  )
}

export function ImagePromptReverseTool({
  open,
  onClose,
  onBusyChange,
}: {
  open: boolean
  onClose: () => void
  onBusyChange?: (busy: boolean) => void
}) {
  const { message, modal } = App.useApp()
  const { activeProject, closeCanvasContextMenu } = useInteractiveMoviePageContext()
  const [geometry, setGeometry] = useState<PanelGeometry>(() => loadPanelGeometry())
  const [history, setHistory] = useState<ImagePromptReverseRecord[]>([])
  const [activeRecord, setActiveRecord] = useState<ImagePromptReverseRecord | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [error, setError] = useState('')
  const interactionRef = useRef<PanelInteraction | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  useAgentOperationLeaveGuard(loading)

  useEffect(() => {
    onBusyChange?.(loading)
  }, [loading, onBusyChange])

  useEffect(() => {
    localStorage.setItem(PANEL_GEOMETRY_KEY, JSON.stringify(geometry))
  }, [geometry])

  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl(null)
      return
    }
    const objectUrl = URL.createObjectURL(selectedFile)
    setPreviewUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [selectedFile])

  useEffect(() => {
    if (!open) return
    void refreshHistory()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const refreshHistory = async () => {
    setHistoryLoading(true)
    try {
      const records = await listInteractiveMovieImagePromptHistory()
      setHistory(records)
      if (!activeRecord && records.length > 0) setActiveRecord(records[0])
    } catch (requestError) {
      setError(resolveErrorMessage(requestError))
    } finally {
      setHistoryLoading(false)
    }
  }

  const requestClose = () => {
    if (loading && !confirmAgentOperationLeave()) return
    onClose()
  }

  const chooseFile = (file: File | null) => {
    setError('')
    setSelectedFile(file)
    if (file) setActiveRecord(null)
  }

  const chooseImageFile = (files: FileList | File[] | null | undefined) => {
    const file = Array.from(files ?? []).find((item) => item.type.startsWith('image/'))
    if (!file) {
      setError('请选择图片文件。')
      return
    }
    chooseFile(file)
  }

  const readClipboardImage = async () => {
    if (loading) return
    if (!navigator.clipboard?.read) {
      setError('当前浏览器不支持主动读取剪切板图片，请使用上传。')
      return
    }
    try {
      const items = await navigator.clipboard.read()
      for (const item of items) {
        const imageType = item.types.find((type) => type.startsWith('image/'))
        if (!imageType) continue
        const blob = await item.getType(imageType)
        const extension = imageType.split('/')[1]?.replace('jpeg', 'jpg') || 'png'
        chooseFile(new File([blob], `clipboard-image-${Date.now()}.${extension}`, { type: imageType }))
        message.success('已读取剪切板图片')
        return
      }
      setError('剪切板里没有可读取的图片。')
    } catch (clipboardError) {
      setError(resolveErrorMessage(clipboardError) || '无法读取剪切板，请允许浏览器权限后重试。')
    }
  }

  const runReverse = async () => {
    if (!selectedFile || loading) return
    setLoading(true)
    setError('')
    try {
      const record = await reverseInteractiveMovieImagePrompt(selectedFile, activeProject?.id)
      setActiveRecord(record)
      setSelectedFile(null)
      setHistory((current) => [record, ...current.filter((item) => item.id !== record.id)])
      message.success('提示词反推完成')
    } catch (requestError) {
      setError(resolveErrorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }

  const copyText = (text: string) => {
    void navigator.clipboard.writeText(text)
      .then(() => message.success('已复制'))
      .catch(() => message.error('复制失败'))
  }

  const confirmDelete = (record: ImagePromptReverseRecord) => {
    modal.confirm({
      title: '删除这条提示词反推记录？',
      content: '会同时删除对应的图片文件。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        await deleteInteractiveMovieImagePromptHistory(record.id)
        setHistory((current) => current.filter((item) => item.id !== record.id))
        setActiveRecord((current) => (current?.id === record.id ? null : current))
        message.success('记录已删除')
      },
    })
  }

  const beginDrag = (event: ReactPointerEvent<HTMLButtonElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'drag',
      pointerId: event.pointerId,
      startClient: { x: event.clientX, y: event.clientY },
      startGeometry: geometry,
    }
  }

  const beginResize = (event: ReactPointerEvent<HTMLButtonElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    interactionRef.current = {
      type: 'resize',
      pointerId: event.pointerId,
      startClient: { x: event.clientX, y: event.clientY },
      startGeometry: geometry,
    }
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const interaction = interactionRef.current
    if (!interaction || interaction.pointerId !== event.pointerId) return
    const dx = event.clientX - interaction.startClient.x
    const dy = event.clientY - interaction.startClient.y
    if (interaction.type === 'drag') {
      setGeometry(clampPanelGeometry({
        ...interaction.startGeometry,
        x: interaction.startGeometry.x + dx,
        y: interaction.startGeometry.y + dy,
      }))
      return
    }
    setGeometry(clampPanelGeometry({
      ...interaction.startGeometry,
      width: interaction.startGeometry.width + dx,
      height: interaction.startGeometry.height + dy,
    }))
  }

  const endPointerInteraction = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (interactionRef.current?.pointerId === event.pointerId) interactionRef.current = null
  }

  const displayImageUrl = previewUrl || activeRecord?.image_url || null
  const result = activeRecord?.result ?? null

  if (!open) return null

  return (
    <div
      className="movie-canvas-agent-panel movie-prompt-tool-panel"
      style={{ left: geometry.x, top: geometry.y, width: geometry.width, height: geometry.height }}
      onPointerMove={handlePointerMove}
      onPointerUp={endPointerInteraction}
      onPointerCancel={endPointerInteraction}
      onPointerDown={(event) => {
        closeCanvasContextMenu()
        event.stopPropagation()
      }}
      onContextMenu={(event) => {
        closeCanvasContextMenu()
        event.preventDefault()
        event.stopPropagation()
      }}
      onWheel={(event) => event.stopPropagation()}
    >
      <div className="movie-agent-panel-header movie-prompt-tool-header">
        <button type="button" className="movie-agent-drag" onPointerDown={beginDrag} aria-label="移动提示词反推栏">
          <DragOutlined />
        </button>
        <div className="movie-agent-heading">
          <Typography.Text className="movie-panel-kicker">图片提示词反推</Typography.Text>
          <Typography.Title level={5} className="movie-prompt-tool-title">视觉拆解与生成提示词</Typography.Title>
        </div>
        <Button
          icon={<HistoryOutlined />}
          type={historyOpen ? 'primary' : 'default'}
          disabled={loading}
          onClick={() => {
            setHistoryOpen((value) => !value)
            void refreshHistory()
          }}
          aria-label={historyOpen ? '关闭历史记录' : '打开历史记录'}
        />
        <Button icon={<CloseOutlined />} onClick={requestClose} aria-label="关闭提示词反推栏" />
      </div>

      <div className={historyOpen ? 'movie-prompt-tool-shell has-history' : 'movie-prompt-tool-shell'}>
        <div className="movie-prompt-tool-body">
          <section className="movie-prompt-upload-zone">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              hidden
              onChange={(event) => {
                chooseImageFile(event.target.files)
                event.currentTarget.value = ''
              }}
            />
            <div
              className={selectedFile ? 'movie-prompt-upload-dropzone has-file' : 'movie-prompt-upload-dropzone'}
              tabIndex={0}
              role="button"
              aria-label="上传或粘贴提示词反推图片"
              onClick={() => fileInputRef.current?.click()}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  fileInputRef.current?.click()
                }
              }}
              onDragOver={(event) => {
                event.preventDefault()
                event.dataTransfer.dropEffect = 'copy'
              }}
              onDrop={(event) => {
                event.preventDefault()
                chooseImageFile(event.dataTransfer.files)
              }}
              onPaste={(event) => {
                const files = event.clipboardData.files
                if (files.length > 0) {
                  event.preventDefault()
                  chooseImageFile(files)
                }
              }}
            >
              <InboxOutlined className="movie-prompt-upload-icon" />
              <div className="movie-prompt-upload-copy">
                <strong>{selectedFile ? selectedFile.name : '选择一张图片进行提示词反推'}</strong>
                <span>{selectedFile ? '可重新上传、拖入新图片，或从剪切板替换。' : '支持点击上传、拖拽图片到这里，或在框内直接粘贴图片。'}</span>
              </div>
              <div className="movie-prompt-upload-actions">
                <Button
                  icon={<UploadOutlined />}
                  disabled={loading}
                  onClick={(event) => {
                    event.stopPropagation()
                    fileInputRef.current?.click()
                  }}
                >
                  上传
                </Button>
                <Button
                  icon={<SnippetsOutlined />}
                  disabled={loading}
                  onClick={(event) => {
                    event.stopPropagation()
                    void readClipboardImage()
                  }}
                >
                  从剪切板读取
                </Button>
              </div>
            </div>
            <Button type="primary" disabled={!selectedFile} loading={loading} onClick={() => void runReverse()}>
              开始反推
            </Button>
          </section>

          {error && <div className="movie-prompt-error">{error}</div>}

          {displayImageUrl || result ? (
            <div className={displayImageUrl && result ? 'movie-prompt-result-layout' : 'movie-prompt-result-layout only-preview'}>
              {displayImageUrl && (
                <aside className="movie-prompt-preview">
                  <img src={displayImageUrl} alt={activeRecord?.filename || selectedFile?.name || '提示词反推图片'} />
                </aside>
              )}

              {result ? (
                <Tabs
                  className="movie-prompt-tabs"
                  items={[
                    {
                      key: 'prompts',
                      label: '提示词选择',
                      children: (
                        <Tabs
                          size="small"
                          items={[
                            {
                              key: 'generic',
                              label: '通用英文提示词',
                              children: <PromptTextBlock text={result.prompt_choices.generic_english_prompt} onCopy={copyText} />,
                            },
                            {
                              key: 'gpt',
                              label: 'GPT Image 提示词',
                              children: <PromptTextBlock text={result.prompt_choices.gpt_image_prompt} onCopy={copyText} />,
                            },
                            {
                              key: 'sd',
                              label: 'SD 提示词',
                              children: (
                                <SdPromptColumns
                                  positivePrompt={result.prompt_choices.sd_prompt.positive_prompt}
                                  negativePrompt={result.prompt_choices.sd_prompt.negative_prompt}
                                  onCopy={copyText}
                                />
                              ),
                            },
                          ]}
                        />
                      ),
                    },
                    {
                      key: 'breakdown',
                      label: '视觉拆解',
                      children: (
                        <div className="movie-prompt-breakdown">
                          {visualBreakdownItems.map((item) => (
                            <div key={item.key} className="movie-prompt-breakdown-item">
                              <strong>{item.label}</strong>
                              <p>{result.visual_breakdown[item.key]}</p>
                            </div>
                          ))}
                        </div>
                      ),
                    },
                    {
                      key: 'advanced',
                      label: '高级',
                      children: (
                        <Tabs
                          size="small"
                          className="movie-prompt-advanced-tabs"
                          items={[
                            {
                              key: 'parameters',
                              label: '参数建议',
                              children: <PromptTextBlock text={result.advanced.parameter_suggestions} onCopy={copyText} />,
                            },
                            {
                              key: 'style',
                              label: '可复用风格模板',
                              children: <PromptTextBlock text={result.advanced.reusable_style_template} onCopy={copyText} />,
                            },
                          ]}
                        />
                      ),
                    },
                  ]}
                />
              ) : (
                <div className="movie-agent-empty">上传图片后生成视觉拆解、提示词和风格模板。</div>
              )}
            </div>
          ) : (
            <div className="movie-agent-empty">上传图片后生成视觉拆解、提示词和风格模板。</div>
          )}
        </div>

        {historyOpen && (
          <aside className="movie-prompt-history">
            <div className="movie-prompt-history-heading">
              <HistoryOutlined />
              <span>历史记录</span>
              <Button size="small" icon={<ReloadOutlined />} disabled={historyLoading || loading} onClick={() => void refreshHistory()} aria-label="刷新历史" />
            </div>
            <div className="movie-prompt-history-list">
              {history.length === 0 ? (
                <p className="movie-prompt-history-empty">{historyLoading ? '加载中...' : '暂无记录'}</p>
              ) : history.map((record) => (
                <button
                  type="button"
                  key={record.id}
                  className={activeRecord?.id === record.id ? 'movie-prompt-history-item is-active' : 'movie-prompt-history-item'}
                  onClick={() => {
                    setSelectedFile(null)
                    setActiveRecord(record)
                  }}
                >
                  {record.image_url ? <img src={record.image_url} alt="" /> : <span className="movie-prompt-history-thumb" />}
                  <span>
                    <strong>{record.filename}</strong>
                    <small>{formatRecordTime(record.created_at)}</small>
                  </span>
                  <Button
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={(event) => {
                      event.stopPropagation()
                      confirmDelete(record)
                    }}
                    aria-label="删除记录"
                  />
                </button>
              ))}
            </div>
          </aside>
        )}
      </div>
      <button type="button" className="movie-agent-resize" onPointerDown={beginResize} aria-label="调整提示词反推栏大小" />
    </div>
  )
}
