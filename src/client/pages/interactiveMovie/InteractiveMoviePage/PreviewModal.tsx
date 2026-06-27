import { Button, Modal } from 'antd'
import { useInteractiveMoviePageContext } from './useInteractiveMoviePageContext'

export function PreviewModal() {
  const {
    advancePreview,
    choosePreviewEdge,
    currentPreviewLine,
    finishPreviewScene,
    outgoingPreviewChoices,
    previewChoicesVisible,
    previewHasVideo,
    previewOpen,
    previewPosterUrl,
    previewScene,
    previewVideoUrl,
    setPreviewOpen,
  } = useInteractiveMoviePageContext()

  return (
    <Modal
      title="互动预览"
      open={previewOpen}
      onCancel={() => setPreviewOpen(false)}
      footer={null}
      width={920}
      className="movie-preview-modal"
      destroyOnClose
    >
      {previewScene && (
        <div className="movie-preview-player">
          <div className={previewHasVideo ? 'movie-preview-scene has-video' : 'movie-preview-scene'}>
            {previewVideoUrl && (
              <video
                key={previewScene.id}
                src={previewVideoUrl}
                poster={previewPosterUrl}
                className="movie-preview-video"
                controls
                autoPlay
                playsInline
                draggable={false}
                onEnded={finishPreviewScene}
              />
            )}
            <div className="movie-preview-vignette" />
            <div className="movie-preview-title">{previewScene.title}</div>
            {previewChoicesVisible && (
              <div className="movie-preview-choices">
                {outgoingPreviewChoices.map((choice) => (
                  <Button key={choice.id} size="large" onClick={() => choosePreviewEdge(choice)}>
                    {choice.label}
                  </Button>
                ))}
              </div>
            )}
            {!previewChoicesVisible && !previewHasVideo && currentPreviewLine && (
              <button type="button" className="movie-dialogue-box" onClick={advancePreview}>
                <span className="movie-dialogue-speaker">{currentPreviewLine.speaker || '角色'}</span>
                <span className="movie-dialogue-text">{currentPreviewLine.text}</span>
                <span className="movie-dialogue-next">点击继续</span>
              </button>
            )}
            {!previewChoicesVisible && !previewHasVideo && !currentPreviewLine && (
              <div className="movie-preview-choices">
                <Button size="large" onClick={advancePreview}>继续</Button>
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}
