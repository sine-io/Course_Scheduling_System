// Excel 导入 API:模板下载、上传导入。

import type { HighRiskConfirmation } from '@/api/highRisk'
import { apiErrorFromResponse } from '@/api/client'

export type ImportEntity = 'subjects' | 'teachers' | 'classes' | 'assignments'

export interface ImportResult {
  imported: number
  accounts_created?: number
  errors: string[]
}

export type CombinedImportEntity = 'subjects' | 'teachers' | 'classes' | 'rooms'
export type CombinedImportStatus = 'new' | 'unchanged' | 'changed' | 'conflict'

export interface CombinedImportError {
  sheet: string
  row: number
  field: string
  message: string
}

export interface CombinedImportChange {
  field: string
  before: unknown
  after: unknown
}

export interface CombinedImportRow {
  sheet: string
  row: number
  identity: string
  status: CombinedImportStatus
  changes: CombinedImportChange[]
  errors: CombinedImportError[]
}

export interface CombinedImportSheet {
  key: CombinedImportEntity
  label: string
  rows: CombinedImportRow[]
}

export interface CombinedImportPreview {
  fingerprint: string
  can_commit: boolean
  has_changes: boolean
  counts: Record<CombinedImportStatus, number>
  sheets: CombinedImportSheet[]
  errors: CombinedImportError[]
}

export interface CombinedImportCommitResult {
  created: Record<CombinedImportEntity, number>
  updated: Record<CombinedImportEntity, number>
  unchanged: Record<CombinedImportEntity, number>
  total_created: number
  total_updated: number
  total_unchanged: number
}

export const ENTITY_LABELS: Record<ImportEntity, string> = {
  subjects: '科目',
  teachers: '教师',
  classes: '班级',
  assignments: '教学任务',
}

async function downloadResponse(path: string, filename: string, fallback: string): Promise<void> {
  const resp = await fetch(path, { credentials: 'include' })
  if (!resp.ok) throw await apiErrorFromResponse(resp, fallback)
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

/** 下载模板档并触发浏览器存储。 */
export async function downloadTemplate(entity: ImportEntity): Promise<void> {
  await downloadResponse(
    `/api/import/templates/${entity}`,
    `${entity}_template.xlsx`,
    '模板下载失败',
  )
}

/** 下载设置向导使用的四表组合模板。 */
export async function downloadSetupTemplate(): Promise<void> {
  await downloadResponse(
    '/api/import/setup/template',
    'school_setup_template.xlsx',
    '组合模板下载失败',
  )
}

async function postSetupWorkbook<T>(
  action: 'preview' | 'commit',
  semesterId: number,
  file: File,
  extra?: { fingerprint: string, confirmChanges: boolean },
): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  if (extra) {
    form.append('fingerprint', extra.fingerprint)
    form.append('confirm_changes', String(extra.confirmChanges))
  }
  const resp = await fetch(`/api/import/setup/${action}?semester_id=${semesterId}`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  })
  if (!resp.ok) throw await apiErrorFromResponse(resp, action === 'preview' ? '预览失败' : '导入失败')
  return resp.json() as Promise<T>
}

export function previewSetupImport(
  semesterId: number,
  file: File,
): Promise<CombinedImportPreview> {
  return postSetupWorkbook<CombinedImportPreview>('preview', semesterId, file)
}

export function commitSetupImport(
  semesterId: number,
  file: File,
  fingerprint: string,
  confirmChanges: boolean,
): Promise<CombinedImportCommitResult> {
  return postSetupWorkbook<CombinedImportCommitResult>('commit', semesterId, file, {
    fingerprint,
    confirmChanges,
  })
}

/** 上传 Excel 文件导入。返回导入结果(含错误列表)。 */
export async function uploadImport(
  entity: ImportEntity,
  semesterId: number,
  file: File,
  createAccounts = false,
  confirmation?: HighRiskConfirmation,
): Promise<ImportResult> {
  const form = new FormData()
  form.append('file', file)
  if (createAccounts && confirmation) {
    form.append('operation_id', confirmation.operation_id)
    form.append('confirmed', String(confirmation.confirmed))
    form.append('target', confirmation.target)
  }
  let url = `/api/import/${entity}?semester_id=${semesterId}`
  if (createAccounts) url += '&create_accounts=true'
  const resp = await fetch(url, { method: 'POST', credentials: 'include', body: form })
  if (!resp.ok) {
    throw await apiErrorFromResponse(resp, '导入失败')
  }
  return resp.json() as Promise<ImportResult>
}
