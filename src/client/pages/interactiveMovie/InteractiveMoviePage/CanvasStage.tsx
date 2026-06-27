import { AssetNodesLayer } from './AssetNodesLayer'
import { EdgeLayer } from './EdgeLayer'
import { SceneNodesLayer } from './SceneNodesLayer'

export function CanvasStage() {
  return (
    <>
      <EdgeLayer />
      <SceneNodesLayer />
      <AssetNodesLayer />
    </>
  )
}
