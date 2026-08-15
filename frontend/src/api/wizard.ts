// 设置向导 API。

import { apiGet, request } from '@/api/client'

export type WizardRoute = 'demo' | 'formal'

export interface WizardState {
  current_step: number
  completed: boolean
  semester_id: number | null
  total_steps: number
  has_semesters: boolean
  route?: WizardRoute | null
}

export interface SemesterSummary {
  subjects: number
  teachers: number
  classes: number
  rooms: number
}

export const getWizardState = () => apiGet<WizardState>('/wizard/state')
export const updateWizardState = (body: {
  current_step?: number
  completed?: boolean
  semester_id?: number | null
  route?: WizardRoute
}) => request<WizardState>('PATCH', '/wizard/state', body)
export const resetWizard = () => request<WizardState>('POST', '/wizard/reset')
export const getSemesterSummary = (id: number) =>
  apiGet<SemesterSummary>(`/semesters/${id}/summary`)
