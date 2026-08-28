import { apiGet, apiPost, request } from '@/api/client'

export type CalendarExceptionKind = 'no_instruction' | 'makeup_instruction'

export interface CalendarException {
  id: number
  semester_id: number
  date: string
  kind: CalendarExceptionKind
  makeup_weekday: number | null
  note: string
  created_by_name: string
  created_at: string | null
}

export interface SemesterReadiness {
  semester_id: number
  readiness: 'draft' | 'ready'
  ready: boolean
  issues: ReadinessIssue[]
  checks: ReadinessCheck[]
  calendar_exception_count: number
}

export interface ReadinessIssue {
  level?: 'error' | 'warning'
  code: string
  message: string
  subject_type?: string
  subject_id?: number
  detail?: Record<string, unknown>
}

export interface ReadinessCheck {
  key: 'data_integrity' | 'solver_preflight'
  label: string
  ok: boolean
  error_count: number
  warning_count: number
  issues: ReadinessIssue[]
}

export const listCalendarExceptions = (semesterId: number) =>
  apiGet<CalendarException[]>(`/semesters/${semesterId}/calendar-exceptions`)
export const createCalendarException = (
  semesterId: number,
  body: { date: string; kind: CalendarExceptionKind; makeup_weekday?: number | null; note?: string },
) => apiPost<CalendarException>(`/semesters/${semesterId}/calendar-exceptions`, body)
export const deleteCalendarException = (id: number) => request<void>('DELETE', `/calendar-exceptions/${id}`)
export const updateCalendarException = (
  id: number,
  body: Partial<{ date: string; kind: CalendarExceptionKind; makeup_weekday: number | null; note: string }>,
) => request<CalendarException>('PATCH', `/calendar-exceptions/${id}`, body)
export const getSemesterReadiness = (semesterId: number) =>
  apiGet<SemesterReadiness>(`/semesters/${semesterId}/readiness`)
export const confirmSemesterReadiness = (semesterId: number) =>
  apiPost<SemesterReadiness>(`/semesters/${semesterId}/readiness`)
export const revokeSemesterReadiness = (semesterId: number) =>
  request<SemesterReadiness>('DELETE', `/semesters/${semesterId}/readiness`)
