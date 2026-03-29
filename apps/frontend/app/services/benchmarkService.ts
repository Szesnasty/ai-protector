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
  source_run_id?: string
}

export interface RunCreated {
  id: string
  status: string
  pack: string
  total_in_pack: number
  total_applicable: number
}

export interface RunDetail {
  id: string
  pack: string
  status: string
  target_type: string
  target_config: Record<string, string>
  score_simple: number | null
  score_weighted: number | null
  confidence: string | null
  total_in_pack: number
  total_applicable: number
  executed: number
  passed: number
  failed: number
  skipped: number
  skipped_reasons: Record<string, number>
  policy: string | null
  source_run_id: string | null
  error: string | null
  created_at: string | null
  completed_at: string | null
  protection_detected: boolean
  proxy_blocked_count: number
  target_label: string
}

export interface ScenarioResult {
  id: string
  scenario_id: string
  category: string
  severity: string
  prompt: string
  expected: string
  actual: string | null
  passed: boolean | null
  skipped: boolean
  skipped_reason: string | null
  detector_type: string | null
  detector_detail: Record<string, unknown> | null
  pipeline_result: Record<string, unknown> | null
  raw_response_body: string | null
  latency_ms: number | null
  // Enriched from pack metadata
  title: string | null
  description: string | null
  why_it_passes: string | null
  fix_hints: string[]
}

export interface CompareResult {
  run_a_id: string
  run_b_id: string
  score_delta: number
  weighted_delta: number
  warning: string | null
  run_a: RunDetail
  run_b: RunDetail
  fixed_failures: string[]
  new_failures: string[]
}

export const benchmarkService = {
  listPacks: (): Promise<PackInfo[]> =>
    api.get<PackInfo[]>('/v1/benchmark/packs').then((r) => r.data),

  createRun: (payload: CreateRunPayload): Promise<RunCreated> =>
    api.post<RunCreated>('/v1/benchmark/runs', payload).then((r) => r.data),

  getRun: (id: string): Promise<RunDetail> =>
    api.get<RunDetail>(`/v1/benchmark/runs/${id}`).then((r) => r.data),

  listRuns: (limit = 5): Promise<RunDetail[]> =>
    api.get<RunDetail[]>(`/v1/benchmark/runs?limit=${limit}`).then((r) => r.data),

  getScenarios: (id: string, limit = 1000): Promise<ScenarioResult[]> =>
    api.get<ScenarioResult[]>(`/v1/benchmark/runs/${id}/scenarios?limit=${limit}`).then((r) => r.data),

  getScenario: (runId: string, scenarioId: string): Promise<ScenarioResult> =>
    api.get<ScenarioResult>(`/v1/benchmark/runs/${runId}/scenarios/${scenarioId}`).then((r) => r.data),

  compareRuns: (runAId: string, runBId: string): Promise<CompareResult> =>
    api.get<CompareResult>(`/v1/benchmark/compare?a=${runAId}&b=${runBId}`).then((r) => r.data),
}
