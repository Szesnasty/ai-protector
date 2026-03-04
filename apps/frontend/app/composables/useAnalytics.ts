import { useQuery } from '@tanstack/vue-query'
import { api } from '~/services/api'
import type {
  AnalyticsSummary,
  TimelineBucket,
  PolicyStatsRow,
  RiskFlagCount,
  IntentCount,
} from '~/types/api'

export function useAnalytics() {
  const selectedRange = ref(1)

  const timeRanges = [
    { label: '5m', value: 5 / 60 },
    { label: '15m', value: 0.25 },
    { label: '1h', value: 1 },
    { label: '24h', value: 24 },
    { label: '7d', value: 168 },
    { label: '30d', value: 720 },
  ]

  /** Adaptive polling interval: shorter ranges → faster refresh. */
  const pollInterval = computed(() => {
    const h = selectedRange.value
    if (h <= 0.25) return 5_000   // 5m/15m → poll every 5s
    if (h <= 1) return 10_000     // 1h     → poll every 10s
    return 30_000                 // 24h+   → poll every 30s
  })

  const { data: summary, isLoading: summaryLoading, refetch: refetchSummary } = useQuery<AnalyticsSummary>({
    queryKey: ['analytics', 'summary', selectedRange],
    queryFn: () => api.get<AnalyticsSummary>(`/v1/analytics/summary?hours=${selectedRange.value}`).then(r => r.data),
    refetchInterval: pollInterval,
    refetchIntervalInBackground: false,
  })

  const { data: timeline, isLoading: timelineLoading, refetch: refetchTimeline } = useQuery<TimelineBucket[]>({
    queryKey: ['analytics', 'timeline', selectedRange],
    queryFn: () => api.get<TimelineBucket[]>(`/v1/analytics/timeline?hours=${selectedRange.value}`).then(r => r.data),
    refetchInterval: pollInterval,
    refetchIntervalInBackground: false,
  })

  const { data: byPolicy, isLoading: byPolicyLoading, refetch: refetchByPolicy } = useQuery<PolicyStatsRow[]>({
    queryKey: ['analytics', 'by-policy', selectedRange],
    queryFn: () => api.get<PolicyStatsRow[]>(`/v1/analytics/by-policy?hours=${selectedRange.value}`).then(r => r.data),
    refetchInterval: pollInterval,
    refetchIntervalInBackground: false,
  })

  const { data: topFlags, isLoading: topFlagsLoading, refetch: refetchTopFlags } = useQuery<RiskFlagCount[]>({
    queryKey: ['analytics', 'top-flags', selectedRange],
    queryFn: () => api.get<RiskFlagCount[]>(`/v1/analytics/top-flags?hours=${selectedRange.value}`).then(r => r.data),
    refetchInterval: pollInterval,
    refetchIntervalInBackground: false,
  })

  const { data: intents, isLoading: intentsLoading, refetch: refetchIntents } = useQuery<IntentCount[]>({
    queryKey: ['analytics', 'intents', selectedRange],
    queryFn: () => api.get<IntentCount[]>(`/v1/analytics/intents?hours=${selectedRange.value}`).then(r => r.data),
    refetchInterval: pollInterval,
    refetchIntervalInBackground: false,
  })

  function refreshAll() {
    refetchSummary()
    refetchTimeline()
    refetchByPolicy()
    refetchTopFlags()
    refetchIntents()
  }

  const isRefreshing = computed(() =>
    summaryLoading.value || timelineLoading.value || byPolicyLoading.value
    || topFlagsLoading.value || intentsLoading.value,
  )

  return {
    selectedRange,
    timeRanges,
    summary,
    summaryLoading,
    timeline,
    timelineLoading,
    byPolicy,
    byPolicyLoading,
    topFlags,
    topFlagsLoading,
    intents,
    intentsLoading,
    refreshAll,
    isRefreshing,
  }
}
