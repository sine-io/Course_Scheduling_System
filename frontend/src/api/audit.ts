import { apiGet } from '@/api/client'

export interface AuditLog {
  id: number
  operation_id: string | null
  username: string
  actor_roles: string[]
  action: string
  target_type: string
  target_id: number | null
  semester_id: number | null
  target_version: string
  result: string
  reason: string
  detail: string
  created_at: string
}

export const listAuditLogs = (limit = 100, action?: string) => apiGet<AuditLog[]>(
  `/audit-logs?limit=${limit}${action ? `&action=${encodeURIComponent(action)}` : ''}`,
)
