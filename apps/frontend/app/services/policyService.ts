import { api } from './api'
import type { Policy } from '~/types/api'

export const policyService = {
  listActive: (): Promise<Policy[]> =>
    api.get<Policy[]>('/v1/policies', { params: { active_only: true } })
      .then((r) => r.data),
}
