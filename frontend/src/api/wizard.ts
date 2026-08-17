// 设置向导 API。

import { apiGet, request } from '@/api/client'

export interface WizardState {
  current_step: number
  resume_step: number
  completed: boolean
  paused: boolean
  semester_id: number | null
  total_steps: number
  has_semesters: boolean
}

export interface SemesterSummary {
  subjects: number
  teachers: number
  classes: number
  rooms: number
}

export interface SetupCheckItem {
  code: string
  message: string
  step: number
}

export interface SetupCheck {
  semester_id: number
  can_complete: boolean
  first_incomplete_step: number
  blockers: SetupCheckItem[]
  warnings: SetupCheckItem[]
  summary: SemesterSummary
}

export const getWizardState = () => apiGet<WizardState>('/wizard/state')
export const updateWizardState = (body: {
  current_step?: number
  paused?: boolean
  semester_id?: number | null
}) => request<WizardState>('PATCH', '/wizard/state', body)
export const getSetupCheck = (semesterId: number) =>
  apiGet<SetupCheck>(`/semesters/${semesterId}/setup-check`)
export const completeWizard = (semesterId: number, acknowledgeWarnings: boolean) =>
  request<WizardState>('POST', '/wizard/complete', {
    semester_id: semesterId,
    acknowledge_warnings: acknowledgeWarnings,
  })
export const reopenWizard = () => request<WizardState>('POST', '/wizard/reopen')
export const getSemesterSummary = (id: number) =>
  apiGet<SemesterSummary>(`/semesters/${id}/summary`)
