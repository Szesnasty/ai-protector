import { api } from './api'
import type { HealthResponse } from '~/types/api'

export const healthService = {
  getHealth: (): Promise<HealthResponse> =>
    api.get<HealthResponse>('/health').then((r) => r.data),
}
