import api from './api'

interface DevFrontendConfigResponse {
  turnstile?: {
    enabled?: boolean
    site_key?: string
    script_url?: string
  }
}

interface FrontendConfigResponse {
  info_distribution?: {
    base_url?: string
  }
}

export async function fetchFrontendConfig(): Promise<FrontendConfigResponse | null> {
  try {
    const response = await api.get<FrontendConfigResponse>('/frontend-config')
    return response.data
  } catch {
    return null
  }
}

export async function fetchDevFrontendConfig(): Promise<DevFrontendConfigResponse | null> {
  try {
    const response = await api.get<DevFrontendConfigResponse>('/dev/providers/frontend-config')
    return response.data
  } catch {
    return null
  }
}
