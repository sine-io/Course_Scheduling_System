import { apiGet } from '@/api/client'

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
