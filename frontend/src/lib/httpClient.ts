import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { refreshSessionToken } from './authSession'
import { useAppStore } from '../store/appStore'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export const httpClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

httpClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAppStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let refreshPromise: Promise<string | null> | null = null

httpClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const status = error.response?.status
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined

    if (status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true

      try {
        if (!refreshPromise) {
          refreshPromise = (async () => {
            try {
              const refreshed = await refreshSessionToken()
              return refreshed ?? null
            } catch (err) {
              // surface refresh errors to callers
              throw err
            } finally {
              refreshPromise = null
            }
          })()
        }

        const refreshedToken = await refreshPromise
        if (refreshedToken) {
          originalRequest.headers = originalRequest.headers ?? {}
          originalRequest.headers.Authorization = `Bearer ${refreshedToken}`
          return httpClient(originalRequest)
        }
      } catch (refreshErr) {
        // clear session and propagate error so callers can react
        try {
          useAppStore.getState().clearSession()
        } finally {
          return Promise.reject(refreshErr)
        }
      }
    }

    if (status === 401) {
      useAppStore.getState().clearSession()
    }

    return Promise.reject(error)
  },
)
