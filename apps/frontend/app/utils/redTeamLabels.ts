/**
 * Human-readable labels for Red Team categories, severities, packs, and scenario IDs.
 * Single source of truth — import from here in all Red Team pages.
 */

import type { RunDetail } from '~/services/benchmarkService'

// ---------------------------------------------------------------------------
// Run classification — baseline vs protected
// ---------------------------------------------------------------------------

export type RunType = 'baseline' | 'protected' | 'instrumented'

export interface RunClassification {
  type: RunType
  label: string
  icon: string
  color: string
  /** Short explanation shown in banners */
  explanation: string
}

/**
 * Classify a run based on available signals.
 *
 * - registered_agent → protected (routed through AI Protector proxy)
 * - Everything else → baseline (direct to model, no proxy protection)
 *
 * This heuristic will improve as the backend adds explicit run_type fields.
 */
export function classifyRun(run: RunDetail): RunClassification {
  if (run.target_type === 'registered_agent') {
    return {
      type: 'protected',
      label: 'Protected',
      icon: 'mdi-shield-check',
      color: 'success',
      explanation: 'This run was routed through AI Protector. Results reflect active protection.',
    }
  }
  return {
    type: 'baseline',
    label: 'Baseline',
    icon: 'mdi-shield-off-outline',
    color: 'grey',
    explanation: 'This run went directly to the model without AI Protector. Results show baseline behavior only.',
  }
}

// ---------------------------------------------------------------------------
// Category labels
// ---------------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  prompt_injection_jailbreak: 'Prompt Injection / Jailbreak',
  prompt_injection: 'Prompt Injection',
  data_leakage_pii: 'Data Leakage / PII',
  pii_disclosure: 'PII Disclosure',
  secrets_detection: 'Secrets Detection',
  improper_output: 'Improper Output',
  obfuscation: 'Obfuscation & Encoding',
  tool_abuse: 'Tool Abuse',
  access_control: 'Access Control',
  safe_allow: 'Safe / Allow (False Positive)',
}

export function humanCategory(slug: string): string {
  return CATEGORY_LABELS[slug] ?? slug.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

// ---------------------------------------------------------------------------
// Severity labels + colors
// ---------------------------------------------------------------------------

const SEVERITY_META: Record<string, { label: string; color: string; icon: string }> = {
  critical: { label: 'Critical', color: 'error', icon: 'mdi-alert-circle' },
  high: { label: 'High', color: 'orange-darken-2', icon: 'mdi-alert' },
  medium: { label: 'Medium', color: 'warning', icon: 'mdi-alert-outline' },
  low: { label: 'Low', color: 'info', icon: 'mdi-information-outline' },
  info: { label: 'Info', color: 'grey', icon: 'mdi-information-variant' },
}

export function severityMeta(sev: string) {
  return SEVERITY_META[sev] ?? { label: sev, color: 'grey', icon: 'mdi-help-circle' }
}

// ---------------------------------------------------------------------------
// Pack labels
// ---------------------------------------------------------------------------

const PACK_LABELS: Record<string, string> = {
  core_security: 'Core Security',
  agent_threats: 'Agent Threats',
  full_suite: 'Full Suite',
  jailbreakbench: 'JailbreakBench',
}

export function humanPack(slug: string): string {
  return PACK_LABELS[slug] ?? slug.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

// ---------------------------------------------------------------------------
// Score status label
// ---------------------------------------------------------------------------

export interface ScoreLabel {
  label: string
  color: string
  vuetifyColor: string
}

export function scoreLabel(score: number): ScoreLabel {
  if (score >= 90) return { label: 'Strong', color: '#2e7d32', vuetifyColor: 'green-darken-2' }
  if (score >= 80) return { label: 'Good', color: '#4caf50', vuetifyColor: 'success' }
  if (score >= 60) return { label: 'Needs Hardening', color: '#fb8c00', vuetifyColor: 'warning' }
  if (score >= 40) return { label: 'Weak', color: '#ff9800', vuetifyColor: 'orange' }
  return { label: 'Critical', color: '#d32f2f', vuetifyColor: 'error' }
}

/**
 * Score label for baseline (unprotected) runs.
 * Uses muted colors and honest framing — avoids implying the endpoint is "secure".
 */
export function baselineScoreLabel(score: number): ScoreLabel {
  if (score >= 90) return { label: 'No Active Protection', color: '#546e7a', vuetifyColor: 'blue-grey' }
  if (score >= 80) return { label: 'No Active Protection', color: '#546e7a', vuetifyColor: 'blue-grey' }
  if (score >= 60) return { label: 'No Active Protection', color: '#fb8c00', vuetifyColor: 'warning' }
  if (score >= 40) return { label: 'No Active Protection', color: '#ff9800', vuetifyColor: 'orange' }
  return { label: 'Highly Exposed — No Protection', color: '#d32f2f', vuetifyColor: 'error' }
}

// ---------------------------------------------------------------------------
// Live scenario result labels (used in run progress view)
// ---------------------------------------------------------------------------

export type LiveResultStatus = 'blocked' | 'got_through' | 'model_resisted' | 'no_breach' | 'skipped' | 'inconclusive' | 'running'

export interface LiveResultMeta {
  label: string
  baselineLabel: string
  icon: string
  mdiIcon: string
  color: string
  vuetifyColor: string
}

const LIVE_RESULT_META: Record<LiveResultStatus, LiveResultMeta> = {
  blocked: {
    label: 'Blocked by AI Protector',
    baselineLabel: 'No breach detected',
    icon: '🛡️',
    mdiIcon: 'mdi-shield-check',
    color: '#2e7d32',
    vuetifyColor: 'success',
  },
  got_through: {
    label: 'Attack got through',
    baselineLabel: 'Attack got through',
    icon: '🔴',
    mdiIcon: 'mdi-alert-circle',
    color: '#d32f2f',
    vuetifyColor: 'error',
  },
  model_resisted: {
    label: 'Model resisted the attack',
    baselineLabel: 'Model resisted the attack',
    icon: '🔵',
    mdiIcon: 'mdi-shield-half-full',
    color: '#1565c0',
    vuetifyColor: 'blue-darken-3',
  },
  no_breach: {
    label: 'No breach detected',
    baselineLabel: 'No breach detected',
    icon: '🔹',
    mdiIcon: 'mdi-check-circle-outline',
    color: '#546e7a',
    vuetifyColor: 'blue-grey',
  },
  skipped: {
    label: 'Skipped',
    baselineLabel: 'Skipped',
    icon: '⚠️',
    mdiIcon: 'mdi-skip-next-circle-outline',
    color: '#9e9e9e',
    vuetifyColor: 'grey',
  },
  inconclusive: {
    label: 'Inconclusive',
    baselineLabel: 'Inconclusive',
    icon: '❔',
    mdiIcon: 'mdi-help-circle-outline',
    color: '#9e9e9e',
    vuetifyColor: 'grey',
  },
  running: {
    label: 'Running...',
    baselineLabel: 'Running...',
    icon: '⏳',
    mdiIcon: 'mdi-loading',
    color: '#1976d2',
    vuetifyColor: 'primary',
  },
}

/**
 * Get human-readable label and visual meta for a live scenario result.
 * When isBaseline is true, uses neutral language that does not imply active protection.
 */
export function liveResultMeta(status: LiveResultStatus): LiveResultMeta {
  return LIVE_RESULT_META[status] ?? LIVE_RESULT_META.inconclusive
}

/**
 * Map raw SSE passed/actual values to a LiveResultStatus.
 */
export function classifyScenarioResult(passed: boolean, _actual?: string | null): LiveResultStatus {
  if (passed) return 'blocked'
  return 'got_through'
}

/**
 * Human-readable skip reason.
 */
export function humanSkipReason(reason: string): string {
  const MAP: Record<string, string> = {
    timeout: 'Timed out',
    safe_mode: 'Skipped (safe mode)',
    not_applicable: 'Not applicable',
  }
  return MAP[reason] ?? reason
}
