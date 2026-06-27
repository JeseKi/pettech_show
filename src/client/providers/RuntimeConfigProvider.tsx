import { type ReactNode, useEffect, useMemo, useState } from 'react'
import {
  RuntimeConfigContext,
  type InfoDistributionRuntimeConfig,
  type RuntimeConfigValue,
  type TurnstileRuntimeConfig,
} from '../contexts/RuntimeConfigContext'
import { fetchDevFrontendConfig, fetchFrontendConfig } from '../lib/runtimeConfig'

const fallbackTurnstileConfig: TurnstileRuntimeConfig = {
  enabled: Boolean((import.meta.env.VITE_TURNSTILE_SITE_KEY ?? '').trim()),
  siteKey: (import.meta.env.VITE_TURNSTILE_SITE_KEY ?? '').trim(),
}

const fallbackInfoDistributionConfig: InfoDistributionRuntimeConfig = {
  baseUrl: (import.meta.env.VITE_INFO_DISTRIBUTION_BASE_URL ?? '').trim(),
}

export function RuntimeConfigProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [infoDistribution, setInfoDistribution] = useState<InfoDistributionRuntimeConfig>(fallbackInfoDistributionConfig)
  const [turnstile, setTurnstile] = useState<TurnstileRuntimeConfig>(fallbackTurnstileConfig)

  useEffect(() => {
    let alive = true

    const load = async () => {
      try {
        const [config, devConfig] = await Promise.all([
          fetchFrontendConfig(),
          fetchDevFrontendConfig(),
        ])

        if (!alive) {
          return
        }

        const infoDistributionBaseUrl = (config?.info_distribution?.base_url ?? '').trim()
          || fallbackInfoDistributionConfig.baseUrl
        setInfoDistribution({ baseUrl: infoDistributionBaseUrl })

        const devTurnstile = devConfig?.turnstile
        if (!alive || !devTurnstile) {
          return
        }

        const siteKey = (devTurnstile.site_key ?? '').trim() || fallbackTurnstileConfig.siteKey
        const scriptUrl = (devTurnstile.script_url ?? '').trim() || undefined
        setTurnstile({
          enabled: Boolean(devTurnstile.enabled && siteKey),
          siteKey,
          scriptUrl,
        })
      } finally {
        if (alive) {
          setLoading(false)
        }
      }
    }

    void load()

    return () => {
      alive = false
    }
  }, [])

  const value = useMemo<RuntimeConfigValue>(
    () => ({
      loading,
      infoDistribution,
      turnstile,
    }),
    [infoDistribution, loading, turnstile],
  )

  return (
    <RuntimeConfigContext.Provider value={value}>
      {children}
    </RuntimeConfigContext.Provider>
  )
}
