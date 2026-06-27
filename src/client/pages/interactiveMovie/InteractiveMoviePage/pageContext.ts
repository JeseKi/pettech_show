import { createContext } from 'react'
import type { InteractiveMoviePageModel } from './useInteractiveMoviePageModel'

export const InteractiveMoviePageContext = createContext<InteractiveMoviePageModel | null>(null)
