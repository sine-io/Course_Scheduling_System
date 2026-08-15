import { apiGet, apiPut } from '@/api/client'

export interface NavigationPreferencePayload {
  fixed: string[]
  recent: string[]
}

export const getUserNavigationPreference = (): Promise<NavigationPreferencePayload | null> =>
  apiGet('/navigation-preference')

export const updateUserNavigationPreference = (
  preference: NavigationPreferencePayload,
): Promise<NavigationPreferencePayload> =>
  apiPut('/navigation-preference', preference)
