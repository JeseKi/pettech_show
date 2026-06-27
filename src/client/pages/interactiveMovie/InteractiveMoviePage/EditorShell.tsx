import { MovieCanvas } from './MovieCanvas'
import { MovieTopbar } from './MovieTopbar'

export function EditorShell() {
  return (
    <main className="movie-editor-shell">
      <MovieTopbar />
      <MovieCanvas />
    </main>
  )
}
