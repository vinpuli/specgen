import { useAppStore } from '../store/appStore'
import { authService } from '../services/authService'

let refreshTimer: ReturnType<typeof setTimeout> | null = null
let refreshPromise: Promise<string | null> | null = null
let unsubscribeStore: (() => void) | null = null

function clearRefreshTimer() {
  if (!refreshTimer) {
    return
  }
  clearTimeout(refreshTimer)
  refreshTimer = null
}

function scheduleRefresh() {
  clearRefreshTimer()
  const { refreshToken, tokenExpiresAt } = useAppStore.getState()
  if (!refreshToken || !tokenExpiresAt) {
    return
  }

  const msUntilRefresh = tokenExpiresAt - Date.now() - 60_000
  const timeoutMs = Math.max(msUntilRefresh, 1_000)
  refreshTimer = setTimeout(() => {
    void refreshSessionToken()
  }, timeoutMs)
}

export async function refreshSessionToken(): Promise<string | null> {
  if (refreshPromise) {
    return refreshPromise
  }

  const { refreshToken, clearSession, setTokens } = useAppStore.getState()
  if (!refreshToken) {
    return null
  }

  refreshPromise = (async () => {
    try {
      const refreshed = await authService.refresh(refreshToken)
      if (!refreshed.accessToken) {
        clearSession()
        return null
      }
      setTokens({
        accessToken: refreshed.accessToken,
        refreshToken: refreshed.refreshToken ?? refreshToken,
        expiresInSeconds: refreshed.expiresInSeconds ?? 30 * 60,
      })
      scheduleRefresh()
      return refreshed.accessToken
    } catch {
      clearSession()
      clearRefreshTimer()
      return null
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

export function initializeAuthSessionAutoRefresh(): () => void {
  if (unsubscribeStore) {
    return () => {
      unsubscribeStore?.()
      unsubscribeStore = null
      clearRefreshTimer()
    }
  }

  let prevRefreshToken = useAppStore.getState().refreshToken
  let prevTokenExpiry = useAppStore.getState().tokenExpiresAt

  scheduleRefresh()

  unsubscribeStore = useAppStore.subscribe((state) => {
    const refreshChanged = state.refreshToken !== prevRefreshToken
    const expiryChanged = state.tokenExpiresAt !== prevTokenExpiry
    if (refreshChanged || expiryChanged) {
      prevRefreshToken = state.refreshToken
      prevTokenExpiry = state.tokenExpiresAt
      scheduleRefresh()
    }
  })

  return () => {
    unsubscribeStore?.()
    unsubscribeStore = null
    clearRefreshTimer()
  }
}
