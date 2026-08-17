// 学期与作息时间表 API 类型与调用封装。

import { apiGet, apiPost, apiPut, request } from '@/api/client'
import type { HighRiskConfirmation } from '@/api/highRisk'

export type PeriodType = 'regular' | 'morning' | 'lunch' | 'homeroom' | 'reserved'

export interface Period {
  id?: number
  weekday: number
  period_no: number
  name: string
  start_time: string | null
  end_time: string | null
  type: PeriodType
}

export interface PeriodTable {
  id: number
  semester_id?: number
  name: string
  num_weekdays: number
  is_default: boolean
  periods: Period[]
}

export interface PeriodSetupClass {
  id: number
  name: string
  grade: number
  track: string
  track_label: string
  period_table_id: number | null
}

export interface PeriodSetupPattern {
  period_no: number
  weekdays: number[]
  name: string
  type: PeriodType
  start_time: string | null
  end_time: string | null
}

export interface PeriodSetupGroup {
  key: string
  table_id: number | null
  name: string
  num_weekdays: number
  is_default: boolean
  class_ids: number[]
  periods: PeriodSetupPattern[]
}

export interface PeriodSetupDraft {
  fingerprint: string
  source: 'suggested' | 'existing'
  classes: PeriodSetupClass[]
  groups: PeriodSetupGroup[]
  unresolved_class_ids: number[]
  ready: boolean
  blockers: string[]
  warnings: string[]
}

export interface SemesterListItem {
  id: number
  academic_year: number
  term: number
  label: string
  status: 'preparing' | 'active' | 'archived'
  readiness: 'draft' | 'ready'
  start_date: string | null
  end_date: string | null
  is_current?: boolean
}

export interface Semester extends SemesterListItem {
  period_tables: PeriodTable[]
}

export const PERIOD_TYPE_LABELS: Record<PeriodType, string> = {
  regular: '一般课',
  morning: '早自习',
  lunch: '午休',
  homeroom: '班主任时间',
  reserved: '固定用途',
}

export const STATUS_LABELS: Record<SemesterListItem['status'], string> = {
  preparing: '准备中',
  active: '进行中',
  archived: '已归档',
}

export const listSemesters = () => apiGet<SemesterListItem[]>('/semesters')
export const getSemester = (id: number) => apiGet<Semester>(`/semesters/${id}`)

export interface SemesterContext {
  current_semester: SemesterListItem | null
  revision: number
  can_switch: boolean
}

export const getSemesterContext = () => apiGet<SemesterContext>('/semester-context')
export const switchSemesterContext = (semesterId: number, expectedRevision: number) =>
  apiPut<SemesterContext>('/semester-context', {
    semester_id: semesterId,
    expected_revision: expectedRevision,
  })
export const createSemester = (body: {
  academic_year: number
  term: number
  start_date?: string | null
  end_date?: string | null
}) => apiPost<Semester>('/semesters', body)
export const updateSemester = (
  id: number,
  body: { status?: string; readiness?: string; start_date?: string | null; end_date?: string | null },
) => request<Semester>('PATCH', `/semesters/${id}`, body)
export const deleteSemester = (id: number, confirmation: HighRiskConfirmation) =>
  request<void>('DELETE', `/semesters/${id}`, confirmation)

export interface CopyOptions {
  academic_year: number
  term: number
  // 新学期的起止日:少了它,请假展开与今日看板的判定会失准,且页面上看不出哪里不对
  start_date: string | null
  end_date: string | null
  period_tables: boolean
  subjects: boolean
  teachers: boolean
  rooms: boolean
  classes: boolean
  grade_promotion: boolean
  constraint_config: boolean  // 软约束权重(不带则新学期回到默认值)
}
export const copySemester = (id: number, body: CopyOptions) =>
  apiPost<Semester>(`/semesters/${id}/copy`, body)

export const createPeriodTable = (
  semesterId: number,
  body: { name: string; num_weekdays?: number; is_default?: boolean },
) => apiPost<PeriodTable>(`/semesters/${semesterId}/period-tables`, body)
export const getPeriodTable = (id: number) => apiGet<PeriodTable>(`/period-tables/${id}`)

export interface AvailableSlot {
  weekday: number
  period_no: number
  name: string
  start_time: string | null
  end_time: string | null
}
export const getAvailableSlots = (tableId: number) =>
  apiGet<AvailableSlot[]>(`/period-tables/${tableId}/available-slots`)
export const updatePeriodTable = (id: number, body: { name?: string; is_default?: boolean }) =>
  request<PeriodTable>('PATCH', `/period-tables/${id}`, body)
export const deletePeriodTable = (id: number, confirmation: HighRiskConfirmation) =>
  request<void>('DELETE', `/period-tables/${id}`, confirmation)
export const replacePeriods = (id: number, periods: Period[]) =>
  request<PeriodTable>('PUT', `/period-tables/${id}/periods`, periods)

export const getPeriodSetup = (semesterId: number) =>
  apiGet<PeriodSetupDraft>(`/semesters/${semesterId}/period-setup`)
export const applyPeriodSetup = (
  semesterId: number,
  fingerprint: string,
  groups: PeriodSetupGroup[],
) => apiPut<PeriodSetupDraft>(`/semesters/${semesterId}/period-setup`, {
  fingerprint,
  groups,
})
