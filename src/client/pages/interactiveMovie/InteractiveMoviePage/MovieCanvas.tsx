import type { CSSProperties } from 'react'
import { useState } from 'react'
import { BorderOuterOutlined, BranchesOutlined, DownOutlined, DragOutlined, EditOutlined, FileTextOutlined, FullscreenOutlined, MessageOutlined, PictureOutlined, PlusOutlined, UpOutlined, VideoCameraOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons'
import { Button, Tooltip, Typography } from 'antd'
import { useInteractiveMoviePageContext } from './useInteractiveMoviePageContext'
import { CanvasStage } from './CanvasStage'
import { CanvasAgentChat } from './CanvasAgentChat'
import { EditorFloatingPanel } from './EditorFloatingPanel'

export function MovieCanvas() {
  const [agentChatOpen, setAgentChatOpen] = useState(false)
  const {
    addAssetNode,
    addChoice,
    addScene,
    beginPan,
    bottomToolbarCollapsed,
    canvasContextMenu,
    canvasMarquee,
    canvasPointerMode,
    canvasRef,
    endPointerInteraction,
    fitView,
    handlePointerMove,
    handleWheel,
    linkDraft,
    openCanvasContextMenu,
    runContextMenuAction,
    setBottomToolbarCollapsed,
    setCanvasPointerMode,
    viewport,
    zoomBy,
  } = useInteractiveMoviePageContext()

  const marqueeRect = canvasMarquee
    ? {
      left: Math.min(canvasMarquee.start.x, canvasMarquee.current.x),
      top: Math.min(canvasMarquee.start.y, canvasMarquee.current.y),
      width: Math.abs(canvasMarquee.current.x - canvasMarquee.start.x),
      height: Math.abs(canvasMarquee.current.y - canvasMarquee.start.y),
    }
    : null

  return (
    <section
      ref={canvasRef}
      className={`movie-canvas is-${canvasPointerMode}`}
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

      {marqueeRect && (
        <div
          className="movie-canvas-marquee"
          style={marqueeRect}
        />
      )}

      <div className="movie-canvas-hint">
        无限画布 · {canvasPointerMode === 'marquee' ? '拖拽空白框选' : '拖拽空白移动'} · 拖拽节点/Choice 调整结构 · 滚轮缩放
      </div>

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
      <CanvasAgentChat open={agentChatOpen} onClose={() => setAgentChatOpen(false)} />

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
          <Tooltip title={canvasPointerMode === 'marquee' ? '当前：框选节点，点击切换为空白拖动' : '当前：空白拖动画布，点击切换为框选'}>
            <Button
              shape="circle"
              type={canvasPointerMode === 'marquee' ? 'primary' : 'default'}
              icon={canvasPointerMode === 'marquee' ? <EditOutlined /> : <DragOutlined />}
              onClick={() => setCanvasPointerMode(canvasPointerMode === 'marquee' ? 'drag' : 'marquee')}
              aria-label={canvasPointerMode === 'marquee' ? '切换为空白拖动画布' : '切换为框选节点'}
            />
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
          <Tooltip title={agentChatOpen ? '关闭画布智能体' : '打开画布智能体'}>
            <Button
              shape="circle"
              type={agentChatOpen ? 'primary' : 'default'}
              icon={<MessageOutlined />}
              onClick={() => setAgentChatOpen((value) => !value)}
            />
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
