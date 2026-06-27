import { Empty } from 'antd'
import { PictureOutlined, VideoCameraOutlined } from '@ant-design/icons'
import type { AssetNode } from './interactiveMovieTypes'

export function AssetPickerList({
  assets,
  emptyText,
  onSelect,
}: {
  assets: AssetNode[]
  emptyText: string
  onSelect: (assetId: string) => void
}) {
  if (assets.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />
  }
  return (
    <div className="movie-asset-picker-list">
      {assets.map((asset) => (
        <button key={asset.id} type="button" className="movie-asset-picker-item" onClick={() => onSelect(asset.id)}>
          <span className="movie-asset-picker-thumb">
            {asset.type === 'image' && asset.media.url ? (
              <img src={asset.media.url} alt="" draggable={false} />
            ) : asset.type === 'video' && asset.media.url ? (
              <video src={asset.media.url} muted preload="metadata" draggable={false} />
            ) : asset.type === 'image' ? (
              <PictureOutlined />
            ) : (
              <VideoCameraOutlined />
            )}
          </span>
          <span className="movie-asset-picker-main">
            <span className="movie-asset-picker-title">{asset.title}</span>
            <span className="movie-asset-picker-meta">{asset.media.status === 'ready' ? '可用素材' : '未上传'}</span>
          </span>
        </button>
      ))}
    </div>
  )
}
