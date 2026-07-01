import { DeleteOutlined, DoubleLeftOutlined, DoubleRightOutlined } from '@ant-design/icons'
import { Button, Empty, Typography } from 'antd'
import { AssetEditor } from '../AssetEditor'
import { ChoiceEditor } from '../ChoiceEditor'
import { NodeLinkEditor } from '../NodeLinkEditor'
import { SceneEditor } from '../SceneEditor'
import { useInteractiveMoviePageContext } from './useInteractiveMoviePageContext'

export function EditorFloatingPanel() {
  const {
    addLine,
    assetMap,
    choices,
    confirmDeleteAssetNode,
    confirmDeleteChoice,
    confirmDeleteScene,
    confirmDeleteSelectedCanvasNodes,
    createSceneForChoice,
    deleteLine,
    deleteNodeLink,
    imageNodes,
    nodeLinks,
    promptTemplate,
    rightPanelCollapsed,
    sceneMap,
    scenePanelState,
    scenes,
    selectedAsset,
    selectedCanvasNodes,
    selectedChoice,
    selectedNodeLink,
    selectedScene,
    setRightPanelCollapsed,
    setScenePanelState,
    setSelectedObject,
    startPreview,
    updateAsset,
    updateChoice,
    updateScene,
    uploadAssetFile,
    uploadByAssetId,
    uploadSceneAsset,
    videoNodes,
  } = useInteractiveMoviePageContext()

  const connectedVideoNodes = selectedScene
    ? videoNodes.filter((asset) => nodeLinks.some((link) => {
      const sceneEndpoint = { type: 'scene', id: selectedScene.id }
      const videoEndpoint = { type: 'video', id: asset.id }
      const fromSceneToVideo = link.from.type === sceneEndpoint.type
        && link.from.id === sceneEndpoint.id
        && link.to.type === videoEndpoint.type
        && link.to.id === videoEndpoint.id
      const fromVideoToScene = link.from.type === videoEndpoint.type
        && link.from.id === videoEndpoint.id
        && link.to.type === sceneEndpoint.type
        && link.to.id === sceneEndpoint.id
      return fromSceneToVideo || fromVideoToScene
    }))
    : []
  const hasMultiSelection = selectedCanvasNodes.length > 1
  const selectedSceneCount = selectedCanvasNodes.filter((item) => item.type === 'scene').length
  const selectedAssetCount = selectedCanvasNodes.length - selectedSceneCount

  return (
    <div className={rightPanelCollapsed ? 'movie-floating-panel is-collapsed' : 'movie-floating-panel'}>
      <button
        type="button"
        className="movie-panel-collapse"
        onPointerDown={(event) => event.stopPropagation()}
        onClick={() => setRightPanelCollapsed((value) => !value)}
        aria-label={rightPanelCollapsed ? '展开右侧栏' : '折叠右侧栏'}
      >
        {rightPanelCollapsed ? <DoubleLeftOutlined /> : <DoubleRightOutlined />}
      </button>
      <aside
        className="movie-right-panel"
        onPointerDown={(event) => event.stopPropagation()}
        onWheel={(event) => event.stopPropagation()}
      >
        {hasMultiSelection && (
          <section className="movie-panel-section movie-multi-selection-panel">
            <div className="movie-panel-title-block">
              <Typography.Text className="movie-panel-kicker">多选节点</Typography.Text>
              <Typography.Title level={3}>{selectedCanvasNodes.length} 个节点已选中</Typography.Title>
            </div>
            <Typography.Text className="movie-panel-muted">
              {selectedSceneCount} 个场景 · {selectedAssetCount} 个素材
            </Typography.Text>
            <Button
              danger
              icon={<DeleteOutlined />}
              onClick={confirmDeleteSelectedCanvasNodes}
            >
              删除已选节点
            </Button>
          </section>
        )}
        {!hasMultiSelection && selectedScene && (
            <SceneEditor
              scene={selectedScene}
              outgoingChoices={choices.filter((choice) => choice.fromSceneId === selectedScene.id)}
              videoNodes={connectedVideoNodes}
              imageNodes={imageNodes}
              assetMap={assetMap}
              promptTemplate={promptTemplate}
              activePanelKeys={scenePanelState[selectedScene.id] ?? []}
              onActivePanelKeysChange={(keys) => setScenePanelState((current) => ({
                ...current,
                [selectedScene.id]: keys,
              }))}
              onChange={(updater) => updateScene(selectedScene.id, updater)}
              onAddLine={() => addLine(selectedScene.id)}
              onDeleteLine={(lineId) => deleteLine(selectedScene.id, lineId)}
              onSelectChoice={(choiceId) => setSelectedObject({ type: 'choice', id: choiceId })}
              onDeleteChoice={confirmDeleteChoice}
              onUploadSceneAsset={(type, file) => uploadSceneAsset(selectedScene, type, file)}
              onPreview={() => startPreview(selectedScene.id)}
              onDeleteScene={() => confirmDeleteScene(selectedScene.id)}
            />
        )}
        {!hasMultiSelection && selectedChoice && (
          <ChoiceEditor
            choice={selectedChoice}
            scenes={scenes}
            onChange={(updater) => updateChoice(selectedChoice.id, updater)}
            onCreateScene={(endpoint) => createSceneForChoice(selectedChoice.id, endpoint)}
            onDeleteChoice={() => confirmDeleteChoice(selectedChoice.id)}
          />
        )}
        {!hasMultiSelection && selectedAsset && (
          <AssetEditor
            asset={selectedAsset}
            uploadState={uploadByAssetId[selectedAsset.id] ?? { status: 'idle' }}
            onChange={(updater) => updateAsset(selectedAsset.id, updater)}
            onUpload={(file) => void uploadAssetFile(selectedAsset, file)}
            onDelete={() => confirmDeleteAssetNode(selectedAsset.id)}
          />
        )}
        {!hasMultiSelection && selectedNodeLink && (
          <NodeLinkEditor
            link={selectedNodeLink}
            sceneMap={sceneMap}
            assetMap={assetMap}
            onDelete={() => deleteNodeLink(selectedNodeLink.id)}
          />
        )}
        {!hasMultiSelection && !selectedScene && !selectedChoice && !selectedAsset && !selectedNodeLink && (
          <Empty description="选择一个场景或选择连线开始编辑" />
        )}
      </aside>
    </div>
  )
}
