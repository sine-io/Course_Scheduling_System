// 数据库备份与恢复(M5-2,管理员专用)。

import { apiDelete, apiErrorFromResponse, apiGet, apiPost } from '@/api/client'
import type { HighRiskConfirmation } from '@/api/highRisk'

export interface Backup {
  name: string
  size_bytes: number
  created_at: string
  reason: string
  reason_label: string
}

export interface RestoreResult {
  restored_from: string
  presafe_backup: string
  warnings: string[]
}

export const listBackups = (): Promise<Backup[]> => apiGet('/backups')
export const createBackup = (confirmation: HighRiskConfirmation): Promise<Backup> =>
  apiPost('/backups', confirmation)
export const deleteBackup = (
  name: string,
  confirmation: HighRiskConfirmation,
): Promise<{ deleted: string }> => apiDelete(`/backups/${encodeURIComponent(name)}`, confirmation)
export const restoreBackup = (
  name: string,
  confirmation: HighRiskConfirmation,
): Promise<RestoreResult> => apiPost(`/backups/${encodeURIComponent(name)}/restore`, confirmation)

export async function restoreUpload(
  file: File,
  confirmation: HighRiskConfirmation,
): Promise<RestoreResult> {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('operation_id', confirmation.operation_id)
  fd.append('confirmed', String(confirmation.confirmed))
  fd.append('target', confirmation.target)
  const resp = await fetch('/api/backups/restore-upload',
    { method: 'POST', credentials: 'include', body: fd })
  if (!resp.ok) {
    throw await apiErrorFromResponse(resp, `恢复失败(${resp.status})`)
  }
  return resp.json()
}

export async function downloadBackup(name: string): Promise<void> {
  const resp = await fetch(`/api/backups/${encodeURIComponent(name)}/download`,
    { credentials: 'include' })
  if (!resp.ok) throw new Error(`下载失败(${resp.status})`)
  const blob = await resp.blob()
  const href = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = href
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(href)
}
