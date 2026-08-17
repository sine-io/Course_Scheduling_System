import { apiGet } from '@/api/client'
import type { Page } from '@/api/pagination'

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

export interface AuditLogQuery {
  page?: number
  pageSize?: number
  q?: string
  action?: string
}

export const listAuditLogs = (query: AuditLogQuery = {}): Promise<Page<AuditLog>> => {
  const params = new URLSearchParams({
    page: String(query.page ?? 1),
    page_size: String(query.pageSize ?? 20),
  })
  if (query.q) params.set('q', query.q)
  if (query.action) params.set('action', query.action)
  return apiGet(`/audit-logs?${params.toString()}`)
}
