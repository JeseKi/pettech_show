import { Button, Flex, Typography } from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import type { AssetNode, NodeLink, NodeLinkEndpoint, SceneNode } from './interactiveMovieTypes'
import { assetTypeLabel } from './interactiveMovieCanvas'

function endpointLabel(
  endpoint: NodeLinkEndpoint,
  sceneMap: Map<string, SceneNode>,
  assetMap: Map<string, AssetNode>,
) {
  if (endpoint.type === 'scene') {
    const scene = sceneMap.get(endpoint.id)
    return `场景：${scene?.title ?? endpoint.id} · ${endpoint.handle}`
  }
  const asset = assetMap.get(endpoint.id)
  return `${assetTypeLabel(endpoint.type)}：${asset?.title ?? endpoint.id} · ${endpoint.handle}`
}

export function NodeLinkEditor({
  link,
  sceneMap,
  assetMap,
  onDelete,
}: {
  link: NodeLink
  sceneMap: Map<string, SceneNode>
  assetMap: Map<string, AssetNode>
  onDelete: () => void
}) {
  return (
    <section className="movie-panel-section movie-node-link-editor">
      <Flex align="center" justify="space-between">
        <div>
          <Typography.Text className="movie-panel-label">节点连接</Typography.Text>
          <Typography.Title level={4}>连接关系</Typography.Title>
        </div>
        <Button danger icon={<DeleteOutlined />} onClick={onDelete}>删除</Button>
      </Flex>
      <div className="movie-link-endpoint-list">
        <div>
          <Typography.Text className="movie-panel-label">起点</Typography.Text>
          <Typography.Text>{endpointLabel(link.from, sceneMap, assetMap)}</Typography.Text>
        </div>
        <div>
          <Typography.Text className="movie-panel-label">终点</Typography.Text>
          <Typography.Text>{endpointLabel(link.to, sceneMap, assetMap)}</Typography.Text>
        </div>
      </div>
    </section>
  )
}
