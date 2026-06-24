import api from './api'

export type PromptTemplate = {
  sections: string[]
  example: string
}

export type InteractiveMovieVideoUpload = {
  url?: string | null
  storage_uri: string
  object_key: string
  filename: string
  content_type: string
  size: number
}

export async function getInteractiveMoviePromptTemplate(): Promise<PromptTemplate> {
  const response = await api.get<PromptTemplate>('/interactive-movie/prompt-template')
  return response.data
}

export async function uploadInteractiveMovieVideo(file: File): Promise<InteractiveMovieVideoUpload> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post<InteractiveMovieVideoUpload>('/interactive-movie/videos', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}
