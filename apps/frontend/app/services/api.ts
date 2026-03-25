import axios from 'axios'
import type { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import type { ApiError } from '~/types/api'

export interface AppError {
  message: string
  status: number | null
  code: string
  raw?: unknown
}

function mapApiError(error: AxiosError<ApiError>): AppError {
  if (!error.response) {
    return {
      message: 'Cannot reach AI Protector service',
      status: null,
      code: 'NETWORK_ERROR',
    }
  }

  const { status, data } = error.response
  const serverMessage = data?.error?.message

  const map: Record<number, AppError> = {
    403: {
      message: serverMessage ?? 'Request blocked by policy',
      status: 403,
      code: 'BLOCKED',
      raw: data,
    },
    404: { message: 'Resource not found', status: 404, code: 'NOT_FOUND' },
    502: { message: 'LLM provider unavailable', status: 502, code: 'LLM_DOWN' },
    504: { message: 'LLM request timed out', status: 504, code: 'LLM_TIMEOUT' },
  }

  return map[status] ?? {
    message: serverMessage ?? `Server error (${status})`,
    status,
    code: 'SERVER_ERROR',
  }
}

const baseURL = import.meta.env.NUXT_PUBLIC_API_BASE ?? 'http://localhost:8000'

// Block insecure API base in production — auth tokens must not travel over plain HTTP.
if (import.meta.env.PROD && !baseURL.startsWith('https://')) {
  console.error('[api] NUXT_PUBLIC_API_BASE must use https:// in production')
}

const api: AxiosInstance = axios.create({
  baseURL,
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor — attach correlation ID
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  config.headers['x-correlation-id'] = crypto.randomUUID()
  return config
})

// Response interceptor — map errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    const mapped = mapApiError(error)
    return Promise.reject(mapped)
  },
)

export { api }
