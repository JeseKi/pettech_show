import { useState } from 'react'
import { Button, Collapse, Flex, Input, Modal, Select, Space, Tag, Typography, Upload } from 'antd'
import { BranchesOutlined, DeleteOutlined, PictureOutlined, PlayCircleOutlined, PlusOutlined, UploadOutlined, VideoCameraOutlined } from '@ant-design/icons'
import type { PromptTemplate } from '../../lib/interactiveMovie'
import type { AssetNode, ChoiceEdge, SceneNode, SceneScript, ScriptLine, VideoPromptParts } from './interactiveMovieTypes'
import { buildVideoPrompt, defaultPromptParts } from './interactiveMovieProject'
import { getScenePosterUrl, getSceneVideoUrl } from './interactiveMovieCanvas'
import { AssetPickerList } from './AssetPickerList'

export function SceneEditor({
  scene,
  outgoingChoices,
  videoNodes,
  imageNodes,
  assetMap,
  promptTemplate,
  activePanelKeys,
  onActivePanelKeysChange,
  onChange,
  onAddLine,
  onDeleteLine,
  onSelectChoice,
  onDeleteChoice,
  onUploadSceneAsset,
  onPreview,
  onDeleteScene,
}: {
  scene: SceneNode
  outgoingChoices: ChoiceEdge[]
  videoNodes: AssetNode[]
  imageNodes: AssetNode[]
  assetMap: Map<string, AssetNode>
  promptTemplate: PromptTemplate | null
  activePanelKeys: string[]
  onActivePanelKeysChange: (keys: string[]) => void
  onChange: (updater: (scene: SceneNode) => SceneNode) => void
  onAddLine: () => void
  onDeleteLine: (lineId: string) => void
  onSelectChoice: (choiceId: string) => void
  onDeleteChoice: (choiceId: string) => void
  onUploadSceneAsset: (type: 'image' | 'video', file: File) => Promise<void>
  onPreview: () => void
  onDeleteScene: () => void
}) {
  const promptParts = scene.script.promptParts ?? defaultPromptParts(scene.title)
  const generatedPrompt = buildVideoPrompt(scene)
  const [videoPreviewOpen, setVideoPreviewOpen] = useState(false)
  const [assetPickerType, setAssetPickerType] = useState<'image' | 'video' | null>(null)
  const [sceneUploadingType, setSceneUploadingType] = useState<'image' | 'video' | null>(null)
  const sceneVideoUrl = getSceneVideoUrl(scene, assetMap)
  const scenePosterUrl = getScenePosterUrl(scene, assetMap)
  const selectedVideoNode = scene.media.videoNodeId ? assetMap.get(scene.media.videoNodeId) : null
  const selectedImageNode = scene.media.coverImageNodeId ? assetMap.get(scene.media.coverImageNodeId) : null

  const updateScript = (script: Partial<SceneScript>) => {
    onChange((current) => ({
      ...current,
      script: { ...current.script, ...script },
    }))
  }

  const updatePromptParts = (patch: Partial<VideoPromptParts>) => {
    onChange((current) => ({
      ...current,
      script: {
        ...current.script,
        promptParts: {
          ...(current.script.promptParts ?? defaultPromptParts(current.title)),
          ...patch,
        },
      },
    }))
  }

  const updateLine = (lineId: string, patch: Partial<ScriptLine>) => {
    onChange((current) => ({
      ...current,
      script: {
        ...current.script,
        lines: current.script.lines.map((line) => (line.id === lineId ? { ...line, ...patch } : line)),
      },
    }))
  }

  const configPanel = (
    <Flex vertical gap={14}>
      <Flex align="flex-start" justify="space-between" gap={12}>
        <div className="movie-panel-title-block">
          <Typography.Text className="movie-panel-kicker">当前场景</Typography.Text>
          <Input
            value={scene.title}
            onChange={(event) => onChange((current) => ({ ...current, title: event.target.value }))}
            className="movie-panel-title-input"
          />
        </div>
        <Button danger type="text" icon={<DeleteOutlined />} onClick={onDeleteScene} aria-label={`删除场景 ${scene.title}`} />
      </Flex>
      <Flex gap={8}>
        <Select
          value={scene.role}
          onChange={(role) => onChange((current) => ({ ...current, role }))}
          options={[
            { value: 'start', label: '开场' },
            { value: 'middle', label: '过场' },
            { value: 'ending', label: '结局' },
          ]}
          className="movie-panel-select"
        />
        <Button icon={<PlayCircleOutlined />} onClick={onPreview}>从这里预览</Button>
      </Flex>
      <section className="movie-panel-section">
        <Flex align="center" justify="space-between">
          <Typography.Text className="movie-panel-label">场景结束后的选择</Typography.Text>
          <Tag className="movie-choice-count-tag">{outgoingChoices.length}</Tag>
        </Flex>
        {outgoingChoices.length > 0 ? (
          <Flex vertical gap={8}>
            {outgoingChoices.map((choice) => (
              <div key={choice.id} className="movie-choice-row">
                <button type="button" className="movie-choice-row-main" onClick={() => onSelectChoice(choice.id)}>
                  <BranchesOutlined />
                  <span>{choice.label}</span>
                </button>
                <button
                  type="button"
                  className="movie-choice-row-delete"
                  title="删除选择"
                  aria-label={`删除选择 ${choice.label}`}
                  onClick={() => onDeleteChoice(choice.id)}
                >
                  <DeleteOutlined />
                </button>
              </div>
            ))}
          </Flex>
        ) : (
          <div className="movie-choice-note">这个场景还没有后续选择，可以用底部工具栏添加。</div>
        )}
      </section>
      <section className="movie-panel-section">
        <Typography.Text className="movie-panel-label">剧情摘要</Typography.Text>
        <Input.TextArea
          value={scene.script.synopsis}
          autoSize={{ minRows: 3, maxRows: 5 }}
          onChange={(event) => updateScript({ synopsis: event.target.value })}
        />
      </section>
      <section className="movie-panel-section">
        <Flex align="center" justify="space-between">
          <Typography.Text className="movie-panel-label">角色对白 / 屏幕字幕</Typography.Text>
          <Button size="small" icon={<PlusOutlined />} onClick={onAddLine}>添加</Button>
        </Flex>
        <div className="movie-choice-note">旁白默认内置在生成视频里，这里只编辑需要单独显示的角色对白或字幕。</div>
        <Flex vertical gap={10} className="movie-line-list">
          {scene.script.lines.map((line, index) => (
            <div key={line.id} className="movie-line-editor">
              <Flex align="center" gap={8}>
                <span className="movie-line-index">{index + 1}</span>
                <Input
                  value={line.speaker}
                  onChange={(event) => updateLine(line.id, { speaker: event.target.value })}
                  className="movie-line-speaker"
                  placeholder="说话人"
                />
                <Button
                  type="text"
                  icon={<DeleteOutlined />}
                  onClick={() => onDeleteLine(line.id)}
                  disabled={scene.script.lines.length <= 1}
                />
              </Flex>
              <Input.TextArea
                value={line.text}
                autoSize={{ minRows: 2, maxRows: 4 }}
                onChange={(event) => updateLine(line.id, { text: event.target.value })}
              />
            </div>
          ))}
        </Flex>
      </section>
      <section className="movie-panel-section">
        <Typography.Text className="movie-panel-label">画面描述</Typography.Text>
        <Input.TextArea
          value={scene.script.visualDescription}
          autoSize={{ minRows: 3, maxRows: 5 }}
          onChange={(event) => updateScript({ visualDescription: event.target.value })}
        />
      </section>
    </Flex>
  )

  const mediaPanel = (
    <section className="movie-panel-section">
      <Typography.Text className="movie-panel-label">画面占位</Typography.Text>
      <div className="movie-panel-media" tabIndex={0}>
        {scenePosterUrl ? (
          <img src={scenePosterUrl} alt={`${scene.title} 封面`} className="movie-panel-poster" draggable={false} />
        ) : sceneVideoUrl ? (
          <video src={sceneVideoUrl} muted preload="metadata" className="movie-panel-video" draggable={false} />
        ) : (
          <div className="movie-panel-media-empty">
            <VideoCameraOutlined />
            <span>选择视频和封面素材</span>
          </div>
        )}
        <div className="movie-panel-media-overlay">
          {sceneVideoUrl && (
            <Button icon={<PlayCircleOutlined />} onClick={() => setVideoPreviewOpen(true)}>
              预览
            </Button>
          )}
        </div>
      </div>
      <Flex vertical gap={10} style={{ marginTop: 12 }}>
        <div className="movie-scene-asset-row">
          <div>
            <Typography.Text className="movie-panel-label">画面视频</Typography.Text>
            <div className="movie-scene-asset-name">{selectedVideoNode?.title ?? '未选择视频'}</div>
          </div>
          <Space>
            <Upload
              accept="video/*"
              showUploadList={false}
              beforeUpload={(file) => {
                setSceneUploadingType('video')
                void onUploadSceneAsset('video', file).finally(() => setSceneUploadingType(null))
                return Upload.LIST_IGNORE
              }}
            >
              <Button size="small" icon={<UploadOutlined />} loading={sceneUploadingType === 'video'}>上传</Button>
            </Upload>
            <Button size="small" icon={<VideoCameraOutlined />} onClick={() => setAssetPickerType('video')}>选择</Button>
          </Space>
        </div>
        <div className="movie-scene-asset-row">
          <div>
            <Typography.Text className="movie-panel-label">封面图片</Typography.Text>
            <div className="movie-scene-asset-name">{selectedImageNode?.title ?? '未选择图片'}</div>
          </div>
          <Space>
            <Upload
              accept="image/*"
              showUploadList={false}
              beforeUpload={(file) => {
                setSceneUploadingType('image')
                void onUploadSceneAsset('image', file).finally(() => setSceneUploadingType(null))
                return Upload.LIST_IGNORE
              }}
            >
              <Button size="small" icon={<UploadOutlined />} loading={sceneUploadingType === 'image'}>上传</Button>
            </Upload>
            <Button size="small" icon={<PictureOutlined />} onClick={() => setAssetPickerType('image')}>选择</Button>
          </Space>
        </div>
      </Flex>
    </section>
  )

  const promptPanel = (
    <section className="movie-panel-section">
      <Typography.Text className="movie-panel-label">视频提示词</Typography.Text>
      <div className="movie-prompt-template">
        <Typography.Text className="movie-panel-label">结构化视频提示词</Typography.Text>
        <div className="movie-prompt-tips">
          {(promptTemplate?.sections ?? [
            '主体：谁或什么是画面核心。',
            '动作：主体正在做什么。',
            '场景：空间、天气、道具、情绪氛围。',
            '镜头：景别、机位、运镜。',
            '时序：按秒描述关键动作变化。',
            '风格：色彩、光线、材质和影片类型。',
            '约束：不希望出现的内容。',
          ]).map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      </div>
      <Input value={promptParts.subject} onChange={(event) => updatePromptParts({ subject: event.target.value })} placeholder="主体：例如，年轻女性林夏站在老式公寓走廊" />
      <Input.TextArea value={promptParts.action} autoSize={{ minRows: 2, maxRows: 4 }} onChange={(event) => updatePromptParts({ action: event.target.value })} placeholder="动作：主体做什么，尽量聚焦一组主要动作" />
      <Input.TextArea value={promptParts.scene} autoSize={{ minRows: 2, maxRows: 4 }} onChange={(event) => updatePromptParts({ scene: event.target.value })} placeholder="场景：空间、时代、天气、道具、情绪氛围" />
      <Input.TextArea value={promptParts.camera} autoSize={{ minRows: 2, maxRows: 4 }} onChange={(event) => updatePromptParts({ camera: event.target.value })} placeholder="镜头：景别、机位、运镜或镜头切换" />
      <Input.TextArea value={promptParts.timeline} autoSize={{ minRows: 2, maxRows: 4 }} onChange={(event) => updatePromptParts({ timeline: event.target.value })} placeholder="时序：例如 [0-2s] 建立场景；[2-5s] 完成关键动作" />
      <Input.TextArea value={promptParts.style} autoSize={{ minRows: 2, maxRows: 4 }} onChange={(event) => updatePromptParts({ style: event.target.value })} placeholder="风格：电影感、写实、低饱和、高对比、细腻光影" />
      <Input.TextArea value={promptParts.constraints} autoSize={{ minRows: 2, maxRows: 4 }} onChange={(event) => updatePromptParts({ constraints: event.target.value })} placeholder="约束：不出现文字水印，不切换主角，主体一致" />
      <Typography.Text className="movie-panel-label">最终提示词</Typography.Text>
      <Input.TextArea
        value={scene.script.videoPrompt || generatedPrompt}
        autoSize={{ minRows: 3, maxRows: 6 }}
        onChange={(event) => updateScript({ videoPrompt: event.target.value })}
      />
    </section>
  )

  return (
    <>
      <Collapse
        className="movie-scene-collapse"
        activeKey={activePanelKeys}
        onChange={(keys) => onActivePanelKeysChange(Array.isArray(keys) ? keys.map(String) : [String(keys)])}
        items={[
          { key: 'config', label: '节点配置', children: configPanel },
          { key: 'media', label: '画面选择', children: mediaPanel },
          { key: 'prompt', label: '提示词编辑', children: promptPanel },
        ]}
      />
      <Modal
        title={scene.title}
        open={videoPreviewOpen}
        footer={null}
        centered
        width={860}
        onCancel={() => setVideoPreviewOpen(false)}
        className="movie-video-preview-modal"
      >
        {sceneVideoUrl && (
          <video src={sceneVideoUrl} controls autoPlay className="movie-video-preview-player" draggable={false} />
        )}
      </Modal>
      <Modal
        title={assetPickerType === 'video' ? '选择画面视频' : '选择封面图片'}
        open={assetPickerType !== null}
        footer={null}
        width={620}
        onCancel={() => setAssetPickerType(null)}
        className="movie-video-preview-modal"
      >
        <AssetPickerList
          assets={assetPickerType === 'video' ? videoNodes : imageNodes}
          emptyText={assetPickerType === 'video' ? '还没有连接的视频素材' : '还没有图片素材'}
          onSelect={(assetId) => {
            onChange((current) => ({
              ...current,
              media: {
                ...current.media,
                kind: assetPickerType === 'video' ? 'video' : current.media.kind,
                videoNodeId: assetPickerType === 'video' ? assetId : current.media.videoNodeId,
                coverImageNodeId: assetPickerType === 'image' ? assetId : current.media.coverImageNodeId,
              },
            }))
            setAssetPickerType(null)
          }}
        />
      </Modal>
    </>
  )
}
