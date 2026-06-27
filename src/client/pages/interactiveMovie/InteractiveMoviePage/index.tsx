import { useInteractiveMoviePageModel } from './useInteractiveMoviePageModel'
import { InteractiveMoviePageProvider } from './InteractiveMoviePageProvider'
import { WorkspaceSidebar } from './WorkspaceSidebar'
import { EditorShell } from './EditorShell'
import { PreviewModal } from './PreviewModal'
import { PublishModal } from './PublishModal'
import '../InteractiveMoviePage.css'

export default function InteractiveMoviePage() {
  const model = useInteractiveMoviePageModel()

  return (
    <InteractiveMoviePageProvider value={model}>
      <div className={model.workspaceCollapsed ? 'interactive-movie-page workspace-collapsed' : 'interactive-movie-page'}>
        <WorkspaceSidebar />
        <EditorShell />
        <PreviewModal />
        <PublishModal />
      </div>
    </InteractiveMoviePageProvider>
  )
}
