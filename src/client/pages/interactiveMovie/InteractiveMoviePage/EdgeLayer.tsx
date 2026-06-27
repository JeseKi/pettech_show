import { DeleteOutlined } from '@ant-design/icons'
import { NODE_HEIGHT, NODE_WIDTH } from '../interactiveMovieConstants'
import { handleAnchor, linkPath, resolveFloatingEndpoint } from '../interactiveMovieCanvas'
import { useInteractiveMoviePageContext } from './useInteractiveMoviePageContext'

export function EdgeLayer() {
  const {
    assetMap,
    beginChoiceDrag,
    beginNodeLinkEndpointDrag,
    beginNodeLinkRouteDrag,
    choices,
    confirmDeleteChoice,
    deleteNodeLink,
    linkDraft,
    nodeLinks,
    sceneMap,
    selectedObject,
    setSelectedObject,
  } = useInteractiveMoviePageContext()

  return (
    <svg className="movie-edge-layer">
      {nodeLinks.map((link) => {
        const fromEndpoint = resolveFloatingEndpoint(link.from, link.to, sceneMap, assetMap)
        const toEndpoint = resolveFloatingEndpoint(link.to, link.from, sceneMap, assetMap)
        const start = handleAnchor(fromEndpoint, sceneMap, assetMap)
        const end = handleAnchor(toEndpoint, sceneMap, assetMap)
        if (!start || !end) return null
        const selected = selectedObject.type === 'nodeLink' && selectedObject.id === link.id
        const routeOffset = { x: link.offsetX ?? 0, y: link.offsetY ?? 0 }
        const path = linkPath(start, end, fromEndpoint.handle, toEndpoint.handle, routeOffset)
        const midX = (start.x + end.x) / 2 + routeOffset.x
        const midY = (start.y + end.y) / 2 + routeOffset.y
        return (
          <g key={link.id} className={selected ? 'movie-node-link is-selected' : 'movie-node-link'}>
            <path
              className="movie-node-link-hit"
              d={path}
              onPointerDown={(event) => beginNodeLinkRouteDrag(event, link)}
            />
            <path className="movie-node-link-line" d={path} />
            {selected && (
              <>
                <circle
                  className="movie-node-link-endpoint"
                  cx={start.x}
                  cy={start.y}
                  r={8}
                  onPointerDown={(event) => beginNodeLinkEndpointDrag(event, link, 'from')}
                />
                <circle
                  className="movie-node-link-endpoint"
                  cx={end.x}
                  cy={end.y}
                  r={8}
                  onPointerDown={(event) => beginNodeLinkEndpointDrag(event, link, 'to')}
                />
                <foreignObject x={midX - 17} y={midY - 17} width="34" height="34">
                  <button
                    type="button"
                    className="movie-node-link-delete"
                    title="删除连接"
                    aria-label="删除连接"
                    onPointerDown={(event) => event.stopPropagation()}
                    onClick={(event) => {
                      event.stopPropagation()
                      deleteNodeLink(link.id)
                    }}
                  >
                    <DeleteOutlined />
                  </button>
                </foreignObject>
              </>
            )}
          </g>
        )
      })}
      {linkDraft && (() => {
        if (linkDraft.mode === 'create') {
          const source = linkDraft.target
            ? resolveFloatingEndpoint(linkDraft.source, linkDraft.target, sceneMap, assetMap)
            : linkDraft.source
          const start = handleAnchor(source, sceneMap, assetMap)
          if (!start) return null
          const endHandle = linkDraft.target?.handle ?? 'left'
          return (
            <g className="movie-node-link is-draft">
              <path className="movie-node-link-line" d={linkPath(start, linkDraft.current, source.handle, endHandle)} />
            </g>
          )
        }
        const movingTarget = linkDraft.target
        const fixed = movingTarget
          ? resolveFloatingEndpoint(linkDraft.fixedEndpoint, movingTarget, sceneMap, assetMap)
          : linkDraft.fixedEndpoint
        const fixedAnchor = handleAnchor(fixed, sceneMap, assetMap)
        if (!fixedAnchor) return null
        const movingHandle = movingTarget?.handle ?? (linkDraft.activeEnd === 'from' ? 'right' : 'left')
        const start = linkDraft.activeEnd === 'from' ? linkDraft.current : fixedAnchor
        const end = linkDraft.activeEnd === 'from' ? fixedAnchor : linkDraft.current
        const startHandle = linkDraft.activeEnd === 'from' ? movingHandle : fixed.handle
        const endHandle = linkDraft.activeEnd === 'from' ? fixed.handle : movingHandle
        return (
          <g className="movie-node-link is-draft">
            <path className="movie-node-link-line" d={linkPath(start, end, startHandle, endHandle)} />
          </g>
        )
      })()}
      {choices.map((choice) => {
        const fromScene = sceneMap.get(choice.fromSceneId)
        const toScene = sceneMap.get(choice.toSceneId)
        if (!fromScene || !toScene) return null
        const siblingChoices = choices.filter((item) => (
          item.fromSceneId === choice.fromSceneId && item.toSceneId === choice.toSceneId
        ))
        const siblingIndex = siblingChoices.findIndex((item) => item.id === choice.id)
        const siblingOffset = (siblingIndex - (siblingChoices.length - 1) / 2) * 46
        const choiceOffsetX = choice.offsetX ?? 0
        const choiceOffsetY = siblingOffset + (choice.offsetY ?? 0)
        const start = {
          x: fromScene.position.x + NODE_WIDTH,
          y: fromScene.position.y + NODE_HEIGHT * 0.5 + siblingOffset * 0.28,
        }
        const end = {
          x: toScene.position.x,
          y: toScene.position.y + NODE_HEIGHT * 0.5 + siblingOffset * 0.28,
        }
        const midX = (start.x + end.x) / 2 + choiceOffsetX
        const midY = (start.y + end.y) / 2 + choiceOffsetY
        const controlOffset = Math.max(150, Math.abs(end.x - start.x) * 0.34)
        const direction = end.x >= start.x ? 1 : -1
        const selected = selectedObject.type === 'choice' && selectedObject.id === choice.id
        return (
          <g key={choice.id} className={selected ? 'movie-edge is-selected' : 'movie-edge'}>
            <path
              d={[
                `M ${start.x} ${start.y}`,
                `C ${start.x + controlOffset * direction} ${start.y}, ${midX - controlOffset * 0.28 * direction} ${midY}, ${midX} ${midY}`,
                `C ${midX + controlOffset * 0.28 * direction} ${midY}, ${end.x - controlOffset * direction} ${end.y}, ${end.x} ${end.y}`,
              ].join(' ')}
              onClick={(event) => {
                event.stopPropagation()
                setSelectedObject({ type: 'choice', id: choice.id })
              }}
            />
            <foreignObject x={midX - 88} y={midY - 22} width="176" height="44">
              <div className="movie-choice-pill">
                <button
                  type="button"
                  className="movie-choice-label"
                  onPointerDown={(event) => beginChoiceDrag(event, choice.id)}
                  onClick={() => setSelectedObject({ type: 'choice', id: choice.id })}
                >
                  {choice.label}
                </button>
                <button
                  type="button"
                  className="movie-choice-delete"
                  title="删除选择"
                  aria-label={`删除选择 ${choice.label}`}
                  onPointerDown={(event) => event.stopPropagation()}
                  onClick={(event) => {
                    event.stopPropagation()
                    confirmDeleteChoice(choice.id)
                  }}
                >
                  <DeleteOutlined />
                </button>
              </div>
            </foreignObject>
          </g>
        )
      })}
    </svg>
  )
}
