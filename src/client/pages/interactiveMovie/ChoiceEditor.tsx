import { Button, Flex, Input, Select, Typography } from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import type { ChoiceEdge, SceneNode } from './interactiveMovieTypes'
import { CREATE_SCENE_SELECT_VALUE } from './interactiveMovieConstants'

export function ChoiceEditor({
  choice,
  scenes,
  onChange,
  onCreateScene,
  onDeleteChoice,
}: {
  choice: ChoiceEdge
  scenes: SceneNode[]
  onChange: (updater: (choice: ChoiceEdge) => ChoiceEdge) => void
  onCreateScene: (endpoint: 'from' | 'to') => void
  onDeleteChoice: () => void
}) {
  const createSceneOption = { value: CREATE_SCENE_SELECT_VALUE, label: '创建新场景' }
  const fromSceneOptions = [
    createSceneOption,
    ...scenes
      .filter((scene) => scene.id !== choice.toSceneId)
      .map((scene) => ({ value: scene.id, label: scene.title })),
  ]
  const toSceneOptions = [
    createSceneOption,
    ...scenes
      .filter((scene) => scene.id !== choice.fromSceneId)
      .map((scene) => ({ value: scene.id, label: scene.title })),
  ]

  const changeFromScene = (fromSceneId: string) => {
    if (fromSceneId === CREATE_SCENE_SELECT_VALUE) {
      onCreateScene('from')
      return
    }
    onChange((current) => {
      const fallbackTarget = scenes.find((scene) => scene.id !== fromSceneId)?.id
      return {
        ...current,
        fromSceneId,
        toSceneId: current.toSceneId === fromSceneId && fallbackTarget ? fallbackTarget : current.toSceneId,
      }
    })
  }

  const changeToScene = (toSceneId?: string) => {
    if (toSceneId === CREATE_SCENE_SELECT_VALUE) {
      onCreateScene('to')
      return
    }
    onChange((current) => {
      const nextToSceneId = toSceneId ?? ''
      const fallbackSource = scenes.find((scene) => scene.id !== nextToSceneId)?.id
      return {
        ...current,
        fromSceneId: nextToSceneId && current.fromSceneId === nextToSceneId && fallbackSource
          ? fallbackSource
          : current.fromSceneId,
        toSceneId: nextToSceneId,
      }
    })
  }

  return (
    <Flex vertical gap={16}>
      <Flex align="flex-start" justify="space-between" gap={12}>
        <div className="movie-panel-title-block">
          <Typography.Text className="movie-panel-kicker">当前选择</Typography.Text>
          <Input
            value={choice.label}
            onChange={(event) => onChange((current) => ({ ...current, label: event.target.value }))}
            className="movie-panel-title-input"
          />
        </div>
        <Button danger type="text" icon={<DeleteOutlined />} onClick={onDeleteChoice} aria-label={`删除选择 ${choice.label}`} />
      </Flex>

      <section className="movie-panel-section">
        <Typography.Text className="movie-panel-label">来源场景</Typography.Text>
        <Select
          value={choice.fromSceneId}
          onChange={changeFromScene}
          options={fromSceneOptions}
          className="movie-panel-wide-control"
        />
      </section>

      <section className="movie-panel-section">
        <Typography.Text className="movie-panel-label">目标场景</Typography.Text>
        <Select
          value={choice.toSceneId || undefined}
          onChange={changeToScene}
          options={toSceneOptions}
          allowClear
          placeholder="未选择目标场景"
          className="movie-panel-wide-control"
        />
      </section>

      <section className="movie-panel-section">
        <Typography.Text className="movie-panel-label">触发时机</Typography.Text>
        <Input value="场景播放结束后" disabled />
      </section>

      <div className="movie-choice-note">
        来源场景和目标场景必须不同。MVP 先把 Choice 固定为场景结束后出现。
      </div>
    </Flex>
  )
}
