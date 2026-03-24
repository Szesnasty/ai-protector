import { api } from './api'

export interface PackInfo {
  name: string
  display_name: string
  description: string
  version: string
  scenario_count: number
  applicable_to: string[]
}

export interface CreateRunPayload {
  target_type: string
  target_config?: Record<string, unknown>
  pack: string
  policy?: string
}

export interface RunCreated {
  id: string
  status: string
  pack: string
  total_in_pack: number
  total_applicable: number
}

export const benchmarkService = {
  listPacks: (): Promise<PackInfo[]> =>
    api.get<PackInfo[]>('/v1/benchmark/packs').then((r) => r.data),

  createRun: (payload: CreateRunPayload): Promise<RunCreated> =>
    api.post<RunCreated>('/v1/benchmark/runs', payload).then((r) => r.data),
}
