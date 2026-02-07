import { create } from 'zustand'

export type SupportedLocale = 'en' | 'es'

type AppState = {
  locale: SupportedLocale
  accessToken: string | null
  refreshToken: string | null
  tokenExpiresAt: number | null
  setLocale: (locale: SupportedLocale) => void
  setAccessToken: (token: string | null) => void
  setTokens: (tokens: {
    accessToken: string
    refreshToken?: string | null
    expiresInSeconds?: number | null
  }) => void
  clearSession: () => void
}

const ACCESS_TOKEN_STORAGE_KEY = 'specgen_access_token'
const REFRESH_TOKEN_STORAGE_KEY = 'specgen_refresh_token'
const TOKEN_EXPIRES_AT_STORAGE_KEY = 'specgen_token_expires_at'

export const useAppStore = create<AppState>((set) => ({
  locale: 'en',
  accessToken: localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY),
  refreshToken: localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY),
  tokenExpiresAt: (() => {
    const raw = localStorage.getItem(TOKEN_EXPIRES_AT_STORAGE_KEY)
    if (!raw) {
      return null
    }
    const parsed = Number(raw)
    return Number.isFinite(parsed) ? parsed : null
  })(),
  setLocale: (locale) => set({ locale }),
  setAccessToken: (token) => {
    if (token) {
      localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token)
    } else {
      localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
      localStorage.removeItem(TOKEN_EXPIRES_AT_STORAGE_KEY)
    }
    const expiresAt = token ? Date.now() + 30 * 60_000 : null
    if (expiresAt) {
      localStorage.setItem(TOKEN_EXPIRES_AT_STORAGE_KEY, String(expiresAt))
    } else {
      localStorage.removeItem(TOKEN_EXPIRES_AT_STORAGE_KEY)
    }
    set({ accessToken: token, tokenExpiresAt: expiresAt })
  },
  setTokens: ({ accessToken, refreshToken, expiresInSeconds }) => {
    const tokenExpiresAt = Date.now() + Math.max(expiresInSeconds ?? 30 * 60, 60) * 1_000
    localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken)
    localStorage.setItem(TOKEN_EXPIRES_AT_STORAGE_KEY, String(tokenExpiresAt))
    if (refreshToken) {
      localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, refreshToken)
    } else {
      localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY)
    }
    set({
      accessToken,
      refreshToken: refreshToken ?? null,
      tokenExpiresAt,
    })
  },
  clearSession: () => {
    localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
    localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY)
    localStorage.removeItem(TOKEN_EXPIRES_AT_STORAGE_KEY)
    set({ accessToken: null, refreshToken: null, tokenExpiresAt: null })
  },
}))
