import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
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

httpClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const status = error.response?.status
    if (status === 401) {
      useAppStore.getState().clearSession()
    }
    return Promise.reject(error)
  },
)
