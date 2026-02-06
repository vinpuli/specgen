import { create } from 'zustand'

export type SupportedLocale = 'en' | 'es'

type AppState = {
  locale: SupportedLocale
  accessToken: string | null
  setLocale: (locale: SupportedLocale) => void
  setAccessToken: (token: string | null) => void
  clearSession: () => void
}

const STORAGE_KEY = 'specgen_access_token'

export const useAppStore = create<AppState>((set) => ({
  locale: 'en',
  accessToken: localStorage.getItem(STORAGE_KEY),
  setLocale: (locale) => set({ locale }),
  setAccessToken: (token) => {
    if (token) {
      localStorage.setItem(STORAGE_KEY, token)
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
    set({ accessToken: token })
  },
  clearSession: () => {
    localStorage.removeItem(STORAGE_KEY)
    set({ accessToken: null })
  },
}))
