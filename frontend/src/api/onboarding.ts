import { apiGet, apiPut, apiPost } from '@/api/client'
import type { WizardRoute } from '@/api/wizard'

export type { WizardRoute }

export interface OnboardingRouteStatus {
  route: WizardRoute | null
  demo_available: boolean
  demo_school_name: string
  has_demo_semester: boolean
  has_formal_semester: boolean
  can_reselect: boolean
  resume_step: number
  resume_semester_id: number | null
}

export interface OnboardingAction {
  stage: string
  label: string
  href: string
  blocking_reason?: string
}

export interface P0Stage {
  key: string
  label: string
  complete: boolean
  status: 'complete' | 'blocked' | 'pending'
  blocking_reason: string
  next_action: OnboardingAction | null
  details: Record<string, unknown>
}

export interface OnboardingStatus {
  first_success: boolean
  wizard_completed: boolean
  current_semester: {
    id: number
    label: string
    is_demo: boolean
  } | null
  stages: P0Stage[]
  p0_todos: P0Stage[]
  next_action: OnboardingAction | null
}

export const getOnboardingStatus = () => apiGet<OnboardingStatus>('/onboarding/status')
export const getOnboardingRoute = () => apiGet<OnboardingRouteStatus>('/onboarding/route')
export const chooseOnboardingRoute = (route: WizardRoute) =>
  apiPut<OnboardingRouteStatus>('/onboarding/route', { route })
// POST keeps the entry point usable for clients that submit a first-use form.
export const chooseOnboardingRoutePost = (route: WizardRoute) =>
  apiPost<OnboardingRouteStatus>('/onboarding/route', { route })
