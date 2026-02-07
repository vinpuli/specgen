import { useCallback, useMemo } from 'react'
import { authService, type LoginRequest, type SignupRequest } from '../services/authService'
import { useAppStore } from '../store/appStore'

export function useAuth() {
  const accessToken = useAppStore((state) => state.accessToken)
  const refreshToken = useAppStore((state) => state.refreshToken)
  const tokenExpiresAt = useAppStore((state) => state.tokenExpiresAt)
  const setTokens = useAppStore((state) => state.setTokens)
  const clearSession = useAppStore((state) => state.clearSession)

  const isAuthenticated = useMemo(() => {
    if (!accessToken) return false
    if (!tokenExpiresAt) return true
    const expires = typeof tokenExpiresAt === 'string' ? Number(tokenExpiresAt) : Number(tokenExpiresAt)
    if (!Number.isFinite(expires)) return true
    return Date.now() < expires
  }, [accessToken, tokenExpiresAt])

  // placeholder flag for async auth resolution (refresh/session check).
  // If your app performs a background refresh, wire this to that state.
  const isAuthLoading = false

  const login = useCallback(async (request: LoginRequest): Promise<void> => {
    const payload = await authService.login(request)
    setTokens({
      accessToken: payload.accessToken,
      refreshToken: payload.refreshToken ?? null,
      expiresInSeconds: payload.expiresInSeconds ?? 30 * 60,
    })
  }, [setTokens])

  const signup = useCallback(async (request: SignupRequest): Promise<void> => {
    const payload = await authService.signup(request)
    setTokens({
      accessToken: payload.accessToken,
      refreshToken: payload.refreshToken ?? null,
      expiresInSeconds: payload.expiresInSeconds ?? 30 * 60,
    })
  }, [setTokens])

  const logout = useCallback(() => {
    clearSession()
  }, [clearSession])

  return {
    accessToken,
    refreshToken,
    tokenExpiresAt,
    isAuthenticated,
    isAuthLoading,
    login,
    signup,
    logout,
    clearSession,
  }
}
