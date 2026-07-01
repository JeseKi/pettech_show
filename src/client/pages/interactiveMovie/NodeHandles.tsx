import type { PointerEvent as ReactPointerEvent } from 'react'
import type { NodeHandleSide, NodeLinkEndpoint } from './interactiveMovieTypes'

export function NodeHandles({
  hidden = false,
  node,
  highlightedSide,
  onBegin,
}: {
  hidden?: boolean
  node: Pick<NodeLinkEndpoint, 'type' | 'id'>
  highlightedSide?: NodeHandleSide
  onBegin: (event: ReactPointerEvent<HTMLButtonElement>, endpoint: NodeLinkEndpoint) => void
}) {
  if (hidden) return null

  const sides: NodeHandleSide[] = ['top', 'right', 'bottom', 'left']
  return (
    <div className="movie-node-handles" aria-hidden="true">
      {sides.map((side) => {
        const endpoint: NodeLinkEndpoint = { ...node, handle: side }
        return (
          <button
            key={side}
            type="button"
            className={[
              'movie-node-handle',
              `is-${side}`,
              highlightedSide === side ? 'is-snap-target' : '',
            ].filter(Boolean).join(' ')}
            data-node-type={node.type}
            data-node-id={node.id}
            data-handle={side}
            onPointerDown={(event) => onBegin(event, endpoint)}
            title="拖拽连接节点"
          />
        )
      })}
    </div>
  )
}
