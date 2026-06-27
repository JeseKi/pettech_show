import type { CSSProperties } from 'react'
import { Button, Typography } from 'antd'
import { CloseOutlined } from '@ant-design/icons'
import type { RouteTree } from './publicInteractiveMovieTypes'
import { sceneRoleLabel } from './publicInteractiveMovieUtils'

export function RouteTreePanel({
  currentSceneId,
  onClose,
  onSelectScene,
  totalSceneCount,
  tree,
  unlockedSceneCount,
}: {
  currentSceneId: string
  onClose: () => void
  onSelectScene: (sceneId: string) => void
  totalSceneCount: number
  tree: RouteTree
  unlockedSceneCount: number
}) {
  return (
    <aside className="movie-route-tree-panel" aria-label="互动影游路线图">
      <div className="movie-route-tree-header">
        <div>
          <Typography.Text className="movie-public-kicker">路线探索</Typography.Text>
          <Typography.Title level={5}>已解锁 {unlockedSceneCount}/{totalSceneCount}</Typography.Title>
        </div>
        <Button
          shape="circle"
          icon={<CloseOutlined />}
          aria-label="关闭路线图"
          onClick={onClose}
        />
      </div>
      <div className="movie-route-tree-scroll">
        <div
          className="movie-route-tree-canvas"
          style={{
            width: tree.width,
            height: tree.height,
          }}
        >
          <svg className="movie-route-tree-edges" width={tree.width} height={tree.height}>
            {tree.edges.map((edge) => (
              <g key={edge.id} className={`movie-route-tree-edge is-${edge.status}`}>
                <path d={edge.path} />
              </g>
            ))}
          </svg>
          {tree.nodes.map((node) => {
            const isUnlocked = node.status !== 'locked'
            return (
              <button
                key={node.scene.id}
                type="button"
                className={`movie-route-tree-node is-${node.status}`}
                style={{
                  '--route-node-x': `${node.x}px`,
                  '--route-node-y': `${node.y}px`,
                } as CSSProperties}
                disabled={!isUnlocked}
                aria-current={node.scene.id === currentSceneId ? 'step' : undefined}
                onClick={() => onSelectScene(node.scene.id)}
              >
                <span className="movie-route-node-role">{sceneRoleLabel(node.scene.role)}</span>
                <span className="movie-route-node-title">{isUnlocked ? node.scene.title : '未解锁节点'}</span>
              </button>
            )
          })}
          {tree.choiceNodes.map((node) => {
            const isLocked = node.status === 'locked'
            return (
              <div
                key={node.choice.id}
                className={`movie-route-tree-choice is-${node.status}`}
                style={{
                  '--route-choice-x': `${node.x}px`,
                  '--route-choice-y': `${node.y}px`,
                } as CSSProperties}
                aria-label={`选择：${node.choice.label}`}
              >
                <span className="movie-route-choice-kicker">选择</span>
                <span className="movie-route-choice-title">{isLocked ? '未解锁选择' : node.choice.label}</span>
              </div>
            )
          })}
        </div>
      </div>
    </aside>
  )
}
