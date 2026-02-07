import axios from 'axios'
import { httpClient } from '../lib/httpClient'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type TokenPayload = {
  accessToken: string
  refreshToken?: string | null
  expiresInSeconds?: number | null
}

export type LoginRequest = {
  email: string
  password: string
}

export type SignupRequest = {
  fullName: string
  email: string
  password: string
}

export type MagicLinkVerifyRequest = {
  email: string
  code: string
}

export type TwoFactorSetupResponse = {
  secret: string
  otpauthUrl: string
  qrCodeDataUrl?: string
}

function normalizeTokenPayload(payload: any): TokenPayload {
  const accessToken = payload?.accessToken ?? payload?.access_token
  if (!accessToken) {
    throw new Error('normalizeTokenPayload: missing access token in response payload')
  }
  return {
    accessToken,
    refreshToken: payload?.refreshToken ?? payload?.refresh_token ?? null,
    expiresInSeconds: payload?.expiresInSeconds ?? payload?.expires_in ?? null,
  }
}

export const authService = {
  async login(request: LoginRequest): Promise<TokenPayload> {
    const response = await httpClient.post('/auth/login', request)
    return normalizeTokenPayload(response.data)
  },

  async signup(request: SignupRequest): Promise<TokenPayload> {
    const response = await httpClient.post('/auth/signup', request)
    return normalizeTokenPayload(response.data)
  },

  async requestPasswordReset(email: string): Promise<void> {
    await httpClient.post('/auth/forgot-password', { email })
  },

  async requestMagicLink(email: string): Promise<void> {
    await httpClient.post('/auth/magic-link', { email })
  },

  async verifyMagicLink(request: MagicLinkVerifyRequest): Promise<TokenPayload> {
    const response = await httpClient.post('/auth/magic-link/verify', request)
    return normalizeTokenPayload(response.data)
  },

  async verifyOAuthCallback(provider: string, params: Record<string, string>): Promise<TokenPayload> {
    const response = await httpClient.post(`/auth/oauth/${provider}/callback`, params)
    return normalizeTokenPayload(response.data)
  },

  async refresh(refreshToken: string): Promise<TokenPayload> {
    const response = await axios.post(
      `${API_BASE_URL}/auth/refresh`,
      { refreshToken },
      { headers: { 'Content-Type': 'application/json' }, timeout: 15_000 },
    )
    return normalizeTokenPayload(response.data)
  },

  async setupTwoFactor(): Promise<TwoFactorSetupResponse> {
    const response = await httpClient.post('/auth/2fa/setup')
    const payload = response.data ?? {}
    const secret = payload.secret
    const otpauthUrl = payload.otpauthUrl ?? payload.otpauth_url
    if (!secret || !otpauthUrl) {
      throw new Error('setupTwoFactor: invalid response from server; missing secret or otpauth URL')
    }
    return {
      secret,
      otpauthUrl,
      qrCodeDataUrl: payload.qrCodeDataUrl ?? payload.qr_code_data_url,
    }
  },

  async verifyTwoFactor(code: string): Promise<void> {
    await httpClient.post('/auth/2fa/verify', { code })
  },
}
