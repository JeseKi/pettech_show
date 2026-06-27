import { DoubleLeftOutlined, DoubleRightOutlined } from '@ant-design/icons'
import { Empty } from 'antd'
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
    createSceneForChoice,
    deleteLine,
    deleteNodeLink,
    imageNodes,
    promptTemplate,
    rightPanelCollapsed,
    sceneMap,
    scenePanelState,
    scenes,
    selectedAsset,
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
        {selectedScene && (
            <SceneEditor
              scene={selectedScene}
              outgoingChoices={choices.filter((choice) => choice.fromSceneId === selectedScene.id)}
              videoNodes={videoNodes}
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
        {selectedChoice && (
          <ChoiceEditor
            choice={selectedChoice}
            scenes={scenes}
            onChange={(updater) => updateChoice(selectedChoice.id, updater)}
            onCreateScene={(endpoint) => createSceneForChoice(selectedChoice.id, endpoint)}
            onDeleteChoice={() => confirmDeleteChoice(selectedChoice.id)}
          />
        )}
        {selectedAsset && (
          <AssetEditor
            asset={selectedAsset}
            uploadState={uploadByAssetId[selectedAsset.id] ?? { status: 'idle' }}
            onChange={(updater) => updateAsset(selectedAsset.id, updater)}
            onUpload={(file) => void uploadAssetFile(selectedAsset, file)}
            onDelete={() => confirmDeleteAssetNode(selectedAsset.id)}
          />
        )}
        {selectedNodeLink && (
          <NodeLinkEditor
            link={selectedNodeLink}
            sceneMap={sceneMap}
            assetMap={assetMap}
            onDelete={() => deleteNodeLink(selectedNodeLink.id)}
          />
        )}
        {!selectedScene && !selectedChoice && !selectedAsset && !selectedNodeLink && (
          <Empty description="选择一个场景或选择连线开始编辑" />
        )}
      </aside>
    </div>
  )
}
