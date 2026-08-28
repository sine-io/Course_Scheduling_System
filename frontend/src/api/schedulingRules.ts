import { apiDelete, apiGet, apiPost, apiPut } from './client'

export type RuleStrength = 'hard' | 'soft' | 'informational'
export type RulePriority = 'high' | 'medium' | 'low'

export interface RuleTarget {
  entity_type: string
  ids: number[]
}

export interface RuleTiming {
  weekdays: number[]
  period_nos: number[]
  period_table_ids: number[]
  week_pattern?: string | null
}

export interface RuleTemplate {
  key: string
  label: string
  description: string
  supported: boolean
  target_types: string[]
  operators: string[]
  strengths: RuleStrength[]
  operator_strengths: Record<string, RuleStrength[]>
  unavailable_reason?: string | null
}

export interface RuleRevision {
  id: number
  revision_no: number
  status: string
  note: string
  created_by_name: string
  created_at: string
  activated_at?: string | null
}

export interface SchedulingRule {
  id: number
  rule_key: string
  revision_id: number
  name: string
  template: string
  template_label: string
  target: RuleTarget
  timing: RuleTiming
  operator: string
  strength: RuleStrength
  priority: RulePriority
  source_kind: string
  source_text: string
  enabled: boolean
  status: string
  compiler_version: string
  compiler_status: string
  summary: string
}

export interface RuleOption {
  id: number
  name: string
  grade?: number
  periods_per_week?: number
}

export interface PeriodTableOption {
  id: number
  name: string
  num_weekdays: number
  slots: Array<{ weekday: number; period_no: number; name: string; type: string }>
}

export interface SchedulingRuleWorkspace {
  semester_id: number
  active_revision: RuleRevision | null
  draft_revision: RuleRevision | null
  rules: SchedulingRule[]
  builtin_rules: Array<{
    rule_key: string
    name: string
    summary: string
    strength: 'hard' | 'soft'
    source_kind: 'builtin'
    status: 'active'
  }>
  options: {
    subjects: RuleOption[]
    teachers: RuleOption[]
    classes: RuleOption[]
    grades: RuleOption[]
    assignments: RuleOption[]
    period_tables: PeriodTableOption[]
  }
}

export interface SchedulingRulePayload {
  name: string
  template: string
  target: RuleTarget
  timing: RuleTiming
  operator: string
  strength: RuleStrength
  priority: RulePriority
  source_text: string
  enabled: boolean
}

export interface RuleValidation {
  revision_id: number | null
  valid: boolean
  diagnostics: Array<{ level: 'error' | 'warning'; code: string; message: string; rule_key: string }>
  matched_assignment_count: number
  excluded_candidate_count: number
}

export const listRuleTemplates = (): Promise<RuleTemplate[]> => apiGet('/scheduling-rules/templates')
export const getRuleWorkspace = (semesterId: number): Promise<SchedulingRuleWorkspace> =>
  apiGet(`/scheduling-rules?semester_id=${semesterId}`)
export const createSchedulingRule = (semesterId: number, body: SchedulingRulePayload): Promise<SchedulingRule> =>
  apiPost(`/scheduling-rules?semester_id=${semesterId}`, body)
export const updateSchedulingRule = (semesterId: number, ruleKey: string, body: SchedulingRulePayload): Promise<SchedulingRule> =>
  apiPut(`/scheduling-rules/${encodeURIComponent(ruleKey)}?semester_id=${semesterId}`, body)
export const deleteSchedulingRule = (semesterId: number, ruleKey: string): Promise<void> =>
  apiDelete(`/scheduling-rules/${encodeURIComponent(ruleKey)}?semester_id=${semesterId}`)
export const validateSchedulingRules = (semesterId: number): Promise<RuleValidation> =>
  apiPost(`/scheduling-rules/validate?semester_id=${semesterId}`)
export const activateSchedulingRules = (semesterId: number, note: string): Promise<SchedulingRuleWorkspace> =>
  apiPost(`/scheduling-rules/activate?semester_id=${semesterId}`, { note })
