import { apiGet, apiPost, request } from '@/api/client'
import type { HighRiskConfirmation } from '@/api/highRisk'

export const ACCOUNT_ROLES = ['admin', 'director', 'scheduler', 'teacher'] as const
export type AccountRole = typeof ACCOUNT_ROLES[number]

export interface Account {
  id: number
  username: string
  display_name: string
  roles: AccountRole[]
  is_active: boolean
  must_change_password: boolean
  auth_provider: string
}

export interface AccountCreatePayload {
  username: string
  display_name: string
  temporary_password: string
  roles: AccountRole[]
  confirmation: HighRiskConfirmation
}

export interface AccountUpdatePayload {
  display_name?: string
  temporary_password?: string
  roles?: AccountRole[]
  is_active?: boolean
  confirmation: HighRiskConfirmation
}

export const listAccounts = () => apiGet<Account[]>('/accounts')
export const createAccount = (body: AccountCreatePayload) => apiPost<Account>('/accounts', body)
export const updateAccount = (id: number, body: AccountUpdatePayload) =>
  request<Account>('PATCH', `/accounts/${id}`, body)
