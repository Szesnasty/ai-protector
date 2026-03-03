import { api } from '~/services/api'
import type { Rule, RuleCreate, RuleTestResult, RuleUpdate } from '~/types/api'

export function useRulesApi() {
  const listRules = (params?: { category?: string, action?: string, search?: string }) =>
    api.get<Rule[]>('/v1/rules', { params })
      .then(r => r.data)

  const createRule = (data: RuleCreate) =>
    api.post<Rule>('/v1/rules', data)
      .then(r => r.data)

  const updateRule = (ruleId: string, data: RuleUpdate) =>
    api.patch<Rule>(`/v1/rules/${ruleId}`, data)
      .then(r => r.data)

  const deleteRule = (ruleId: string) =>
    api.delete(`/v1/rules/${ruleId}`)

  const bulkImport = (rules: RuleCreate[]) =>
    api.post<{ created: number, skipped: number }>(
      '/v1/rules/import',
      { rules },
    ).then(r => r.data)

  const exportRules = () =>
    api.get<Rule[]>('/v1/rules/export')
      .then(r => r.data)

  const testRules = (text: string) =>
    api.post<RuleTestResult[]>(
      '/v1/rules/test',
      { text },
    ).then(r => r.data)

  return { listRules, createRule, updateRule, deleteRule, bulkImport, exportRules, testRules }
}
