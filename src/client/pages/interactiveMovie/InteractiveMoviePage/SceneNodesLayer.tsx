import { BorderOuterOutlined, DeleteOutlined, VideoCameraOutlined } from '@ant-design/icons'
import { Flex, Typography } from 'antd'
import { roleLabels } from '../interactiveMovieConstants'
import { getScenePosterUrl } from '../interactiveMovieCanvas'
import { NodeHandles } from '../NodeHandles'
import { useInteractiveMoviePageContext } from './useInteractiveMoviePageContext'

export function SceneNodesLayer() {
  const { assetMap, beginLinkDrag, beginNodeDrag, confirmDeleteScene, linkDraft, scenes, selectCanvasScene, selectedObject } = useInteractiveMoviePageContext()

  return (
    <>
      {scenes.map((scene) => {
        const selected = selectedObject.type === 'scene' && selectedObject.id === scene.id
        const posterUrl = getScenePosterUrl(scene, assetMap)
        return (
          <div
            key={scene.id}
            className={selected ? 'movie-scene-node is-selected' : 'movie-scene-node'}
            style={{ left: scene.position.x, top: scene.position.y }}
            onPointerDown={(event) => beginNodeDrag(event, 'scene', scene.id)}
            onClick={(event) => {
              event.stopPropagation()
              selectCanvasScene(scene.id)
            }}
          >
            <Flex align="center" justify="space-between" className="movie-node-header">
              <div>
                <Typography.Text className="movie-node-eyebrow">Scene · {roleLabels[scene.role]}</Typography.Text>
                <Typography.Text className="movie-node-title">{scene.title}</Typography.Text>
              </div>
              <div className="movie-node-actions">
                <BorderOuterOutlined />
                <button
                  type="button"
                  className="movie-node-delete"
                  title="删除场景"
                  aria-label={`删除场景 ${scene.title}`}
                  onPointerDown={(event) => event.stopPropagation()}
                  onClick={(event) => {
                    event.stopPropagation()
                    confirmDeleteScene(scene.id)
                  }}
                >
                  <DeleteOutlined />
                </button>
              </div>
            </Flex>
            <div className="movie-node-preview">
              {posterUrl ? (
                <img src={posterUrl} alt="" className="movie-node-preview-poster" draggable={false} />
              ) : (
                <>
                  <div className="movie-node-preview-grid" />
                  <VideoCameraOutlined />
                </>
              )}
            </div>
            <Typography.Paragraph ellipsis={{ rows: 2 }} className="movie-node-synopsis">
              {scene.script.synopsis}
            </Typography.Paragraph>
            <Flex align="center" justify="space-between">
              <span className="movie-node-meta">{scene.script.lines.length} 句对白 · {scene.media.url ? '视频已上传' : '视频待上传'}</span>
              <span className="movie-node-dot" />
            </Flex>
            <NodeHandles
              node={{ type: 'scene', id: scene.id }}
              highlightedSide={linkDraft?.target?.type === 'scene' && linkDraft.target.id === scene.id ? linkDraft.target.handle : undefined}
              onBegin={beginLinkDrag}
            />
          </div>
        )
      })}
    </>
  )
}
