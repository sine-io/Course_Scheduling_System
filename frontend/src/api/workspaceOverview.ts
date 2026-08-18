import { apiGet } from '@/api/client'

export type OverviewTone = 'critical' | 'warning' | 'info'

export interface WorkspaceTimetable {
  id: number | null
  name: string
  status: string
  updated_at: string | null
  required_periods: number
  placed_periods: number
  remaining_periods: number
  completion_rate: number | null
}

export interface WorkspacePreflight {
  available: boolean
  error_count: number
  warning_count: number
  unavailable_message: string
}

export interface WorkspaceMetrics {
  active_teacher_count: number
  class_count: number
  weekly_affected_periods: number
  week_start: string
  week_end: string
}

export interface WorkspaceActionItem {
  code: string
  title: string
  description: string
  tone: OverviewTone
  target: string
  count: number | null
}

export interface WorkspaceOverview {
  semester_id: number
  semester_label: string
  generated_at: string
  metrics: WorkspaceMetrics
  timetable: WorkspaceTimetable
  preflight: WorkspacePreflight
  today_pending_periods: number
  unacknowledged_notifications: number
  focus_items: WorkspaceActionItem[]
  recommendations: WorkspaceActionItem[]
}

export const getWorkspaceOverview = (semesterId: number): Promise<WorkspaceOverview> =>
  apiGet(`/workspace-overview?semester_id=${semesterId}`)
