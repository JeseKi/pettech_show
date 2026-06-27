import type { CSSProperties } from 'react'
import { BorderOuterOutlined, BranchesOutlined, DownOutlined, EditOutlined, FileTextOutlined, FullscreenOutlined, PictureOutlined, PlusOutlined, UpOutlined, VideoCameraOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons'
import { Button, Tooltip, Typography } from 'antd'
import { useInteractiveMoviePageContext } from './useInteractiveMoviePageContext'
import { CanvasStage } from './CanvasStage'
import { EditorFloatingPanel } from './EditorFloatingPanel'

export function MovieCanvas() {
  const {
    addAssetNode,
    addChoice,
    addScene,
    beginPan,
    bottomToolbarCollapsed,
    canvasContextMenu,
    canvasRef,
    endPointerInteraction,
    fitView,
    handlePointerMove,
    handleWheel,
    linkDraft,
    openCanvasContextMenu,
    runContextMenuAction,
    setBottomToolbarCollapsed,
    viewport,
    zoomBy,
  } = useInteractiveMoviePageContext()

  return (
    <section
      ref={canvasRef}
      className="movie-canvas"
      style={{
        '--movie-grid-x': String(viewport.x) + 'px',
        '--movie-grid-y': String(viewport.y) + 'px',
        '--movie-grid-size': String(24 * viewport.zoom) + 'px',
        '--movie-grid-major-size': String(120 * viewport.zoom) + 'px',
      } as CSSProperties}
      onPointerDown={beginPan}
      onPointerMove={handlePointerMove}
      onPointerUp={endPointerInteraction}
      onPointerCancel={endPointerInteraction}
      onWheel={handleWheel}
      onContextMenu={openCanvasContextMenu}
    >
      <div
        className={linkDraft ? 'movie-canvas-stage is-linking' : 'movie-canvas-stage'}
        style={{ transform: 'translate(' + viewport.x + 'px, ' + viewport.y + 'px) scale(' + viewport.zoom + ')' }}
      >
        <CanvasStage />
      </div>

      <div className="movie-canvas-hint">无限画布 · 拖拽空白移动 · 拖拽节点/Choice 调整结构 · 滚轮缩放</div>

      {canvasContextMenu && (
        <div
          className="movie-canvas-context-menu"
          style={{ left: canvasContextMenu.screenX, top: canvasContextMenu.screenY }}
          onPointerDown={(event) => event.stopPropagation()}
          onWheel={(event) => event.stopPropagation()}
        >
          <button type="button" onClick={() => runContextMenuAction(() => addScene(canvasContextMenu.canvasPosition))}>
            <BorderOuterOutlined />
            <span>创建场景</span>
          </button>
          <button type="button" onClick={() => runContextMenuAction(() => addAssetNode('text', canvasContextMenu.canvasPosition))}>
            <FileTextOutlined />
            <span>创建文本</span>
          </button>
          <button type="button" onClick={() => runContextMenuAction(() => addAssetNode('image', canvasContextMenu.canvasPosition))}>
            <PictureOutlined />
            <span>创建图片</span>
          </button>
          <button type="button" onClick={() => runContextMenuAction(() => addAssetNode('video', canvasContextMenu.canvasPosition))}>
            <VideoCameraOutlined />
            <span>创建视频</span>
          </button>
          <button type="button" onClick={() => runContextMenuAction(addChoice)}>
            <BranchesOutlined />
            <span>创建选择</span>
          </button>
        </div>
      )}

      <EditorFloatingPanel />

      <div
        className={bottomToolbarCollapsed ? 'movie-bottom-dock is-collapsed' : 'movie-bottom-dock'}
        onPointerDown={(event) => event.stopPropagation()}
        onWheel={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          className="movie-bottom-collapse"
          onClick={() => setBottomToolbarCollapsed((value) => !value)}
          aria-label={bottomToolbarCollapsed ? '展开底栏' : '折叠底栏'}
        >
          {bottomToolbarCollapsed ? <UpOutlined /> : <DownOutlined />}
        </button>
        <div className="movie-bottom-controls">
          <Tooltip title="选择 / 拖拽">
            <Button shape="circle" icon={<EditOutlined />} />
          </Tooltip>
          <Tooltip title="添加场景">
            <Button shape="circle" icon={<PlusOutlined />} onClick={() => addScene()} />
          </Tooltip>
          <Tooltip title="添加选择">
            <Button shape="circle" icon={<BranchesOutlined />} onClick={addChoice} />
          </Tooltip>
          <Tooltip title="添加文本">
            <Button shape="circle" icon={<FileTextOutlined />} onClick={() => addAssetNode('text')} />
          </Tooltip>
          <Tooltip title="添加图片">
            <Button shape="circle" icon={<PictureOutlined />} onClick={() => addAssetNode('image')} />
          </Tooltip>
          <Tooltip title="添加视频">
            <Button shape="circle" icon={<VideoCameraOutlined />} onClick={() => addAssetNode('video')} />
          </Tooltip>
          <span className="movie-bottom-divider" />
          <Tooltip title="缩小">
            <Button shape="circle" icon={<ZoomOutOutlined />} onClick={() => zoomBy(-0.1)} />
          </Tooltip>
          <Typography.Text className="movie-zoom-label">{Math.round(viewport.zoom * 100)}%</Typography.Text>
          <Tooltip title="放大">
            <Button shape="circle" icon={<ZoomInOutlined />} onClick={() => zoomBy(0.1)} />
          </Tooltip>
          <Tooltip title="适配视图">
            <Button icon={<FullscreenOutlined />} onClick={fitView}>适配</Button>
          </Tooltip>
        </div>
      </div>
    </section>
  )
}
