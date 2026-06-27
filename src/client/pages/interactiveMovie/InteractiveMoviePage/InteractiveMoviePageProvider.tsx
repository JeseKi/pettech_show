import type { ReactNode } from 'react'
import type { InteractiveMoviePageModel } from './useInteractiveMoviePageModel'
import { InteractiveMoviePageContext } from './pageContext'

export function InteractiveMoviePageProvider({ children, value }: { children: ReactNode; value: InteractiveMoviePageModel }) {
  return (
    <InteractiveMoviePageContext.Provider value={value}>
      {children}
    </InteractiveMoviePageContext.Provider>
  )
}
