import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { DeleteOutlined, FileTextOutlined, PictureOutlined, VideoCameraOutlined } from '@ant-design/icons'
import { Flex, Typography } from 'antd'
import { assetTypeLabel } from '../interactiveMovieCanvas'
import { NodeHandles } from '../NodeHandles'
import { useInteractiveMoviePageContext } from './useInteractiveMoviePageContext'

export function AssetNodesLayer() {
  const { assetNodes, beginLinkDrag, beginNodeDrag, confirmDeleteAssetNode, linkDraft, selectedObject, setSelectedObject } = useInteractiveMoviePageContext()

  return (
    <>
      {assetNodes.map((asset) => {
        const selected = selectedObject.type === asset.type && selectedObject.id === asset.id
        const icon = asset.type === 'text'
          ? <FileTextOutlined />
          : asset.type === 'image'
            ? <PictureOutlined />
            : <VideoCameraOutlined />
        return (
          <div
            key={asset.id}
            className={[
              'movie-asset-node',
              `is-${asset.type}`,
              selected ? 'is-selected' : '',
            ].filter(Boolean).join(' ')}
            style={{ left: asset.position.x, top: asset.position.y }}
            onPointerDown={(event) => beginNodeDrag(event, asset.type, asset.id)}
            onClick={(event) => {
              event.stopPropagation()
              setSelectedObject({ type: asset.type, id: asset.id })
            }}
          >
            <Flex align="center" justify="space-between" className="movie-asset-header">
              <div className="movie-asset-heading">
                <span className="movie-asset-icon">{icon}</span>
                <div>
                  <Typography.Text className="movie-node-eyebrow">{assetTypeLabel(asset.type)}</Typography.Text>
                  <Typography.Text className="movie-asset-title">{asset.title}</Typography.Text>
                </div>
              </div>
              <div className="movie-node-actions">
                <button
                  type="button"
                  className="movie-node-delete"
                  title="删除素材"
                  aria-label={`删除素材 ${asset.title}`}
                  onPointerDown={(event) => event.stopPropagation()}
                  onClick={(event) => {
                    event.stopPropagation()
                    confirmDeleteAssetNode(asset.id)
                  }}
                >
                  <DeleteOutlined />
                </button>
              </div>
            </Flex>
            {asset.type === 'text' ? (
              <div className="movie-asset-text-body">
                {asset.text?.trim() ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {asset.text}
                  </ReactMarkdown>
                ) : (
                  '空文本'
                )}
              </div>
            ) : (
              <div className="movie-asset-media-preview">
                {asset.type === 'image' && asset.media.url ? (
                  <img src={asset.media.url} alt="" draggable={false} />
                ) : asset.type === 'video' && asset.media.url ? (
                  <video src={asset.media.url} muted preload="metadata" draggable={false} />
                ) : (
                  <div className="movie-asset-media-empty">{icon}</div>
                )}
              </div>
            )}
            <Flex align="center" justify="space-between">
              <span className="movie-node-meta">{asset.media.status === 'ready' ? '已上传' : asset.type === 'text' ? 'Markdown' : '待上传'}</span>
              <span className="movie-node-dot" />
            </Flex>
            <NodeHandles
              node={{ type: asset.type, id: asset.id }}
              highlightedSide={linkDraft?.target?.type === asset.type && linkDraft.target.id === asset.id ? linkDraft.target.handle : undefined}
              onBegin={beginLinkDrag}
            />
          </div>
        )
      })}
    </>
  )
}
