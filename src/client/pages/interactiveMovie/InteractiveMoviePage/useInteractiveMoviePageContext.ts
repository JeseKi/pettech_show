import { useContext } from 'react'
import { InteractiveMoviePageContext } from './pageContext'

export function useInteractiveMoviePageContext() {
  const value = useContext(InteractiveMoviePageContext)
  if (!value) throw new Error('InteractiveMoviePageContext is missing')
  return value
}
