// Excel 导入 API:模板下载、上传导入。

import type { HighRiskConfirmation } from '@/api/highRisk'
import { apiErrorFromResponse } from '@/api/client'

export type ImportEntity = 'subjects' | 'teachers' | 'classes' | 'assignments'
export type TeacherArrangementMode = 'standard' | 'scheduling_ready'
export type TeacherArrangementEntity =
  | 'subjects'
  | 'teachers'
  | 'classes'
  | 'assignments'
  | 'source_records'
export type TeacherArrangementRowStatus = 'new' | 'changed' | 'unchanged'

export interface TeacherArrangementIssue {
  code: string
  severity: 'blocker' | 'warning'
  sheet: string
  row: number
  field: string
  value: unknown
  message: string
  suggestion: string
}

export interface TeacherArrangementPreviewRow {
  sheet: string
  row: number
  source_key: string
  identity: string
  status: TeacherArrangementRowStatus
  changes: Array<{ field: string, before: unknown, after: unknown }>
  issues: TeacherArrangementIssue[]
}

export interface TeacherArrangementPreviewSheet {
  key: TeacherArrangementEntity
  label: string
  rows: TeacherArrangementPreviewRow[]
}

export interface TeacherArrangementPreview {
  fingerprint: string
  template_version: string
  mode: TeacherArrangementMode
  semester_id: number
  can_commit: boolean
  has_changes: boolean
  counts: {
    new: number
    changed: number
    unchanged: number
    blocker: number
    warning: number
  }
  sheets: TeacherArrangementPreviewSheet[]
  issues: TeacherArrangementIssue[]
}

export interface TeacherArrangementCommitResult {
  batch_id: number
  fingerprint: string
  created: Record<TeacherArrangementEntity, number>
  updated: Record<TeacherArrangementEntity, number>
  unchanged: Record<TeacherArrangementEntity, number>
  idempotent: boolean
}

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

export interface ReferenceImportAssignment {
  class_name: string
  grade: number
  subject: string
  component: string
  periods: number
  teacher: string | null
  source_key: string
  notes: string
  required_room_type?: string | null
}

export interface ReferenceImportPreview {
  fingerprint: string
  adapter_version: string
  semester: {
    id: number
    academic_year: number
    term: number
    start_date: string
    end_date: string
  }
  can_commit: boolean
  has_changes: boolean
  counts: Record<string, number>
  changes: Array<Record<string, unknown>>
  assignments: ReferenceImportAssignment[]
  rules: Array<Record<string, unknown>>
  fixed_entries: Array<Record<string, unknown>>
  errors: Array<{ code: string, message: string, source?: string }>
  warnings: string[]
  source: {
    word_filename: string
    xlsx_filename: string
    word_sha256: string
    xlsx_sha256: string
  }
}

export interface ReferenceImportCommitResult {
  batch_id: number
  timetable_id: number | null
  created: Record<string, number>
  unchanged: Record<string, number>
  warnings: string[]
  idempotent: boolean
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

/** 下载基础数据使用的四表组合模板。 */
export async function downloadSetupTemplate(): Promise<void> {
  await downloadResponse(
    '/api/import/setup/template',
    'school_setup_template.xlsx',
    '组合模板下载失败',
  )
}

/** 下载绑定目标学期的教师安排标准化模板。 */
export async function downloadTeacherArrangementTemplate(
  semesterId: number,
  mode: TeacherArrangementMode,
): Promise<void> {
  const filename = mode === 'scheduling_ready'
    ? '自动排课准备模板_v1.0.xlsx'
    : '教师安排标准模板_v1.0.xlsx'
  const params = new URLSearchParams({ semester_id: String(semesterId), mode })
  await downloadResponse(
    `/api/import/teacher-arrangements/template?${params.toString()}`,
    filename,
    '教师安排模板下载失败',
  )
}

async function postTeacherArrangementWorkbook<T>(
  action: 'preview' | 'commit',
  semesterId: number,
  mode: TeacherArrangementMode,
  file: File,
  extra?: { fingerprint: string, confirmChanges: boolean, confirmWarnings: boolean },
): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  if (extra) {
    form.append('fingerprint', extra.fingerprint)
    form.append('confirm_changes', String(extra.confirmChanges))
    form.append('confirm_warnings', String(extra.confirmWarnings))
  }
  const params = new URLSearchParams({ semester_id: String(semesterId), mode })
  const response = await fetch(
    `/api/import/teacher-arrangements/${action}?${params.toString()}`,
    { method: 'POST', credentials: 'include', body: form },
  )
  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      action === 'preview' ? '教师安排模板预览失败' : '教师安排模板导入失败',
    )
  }
  return response.json() as Promise<T>
}

export function previewTeacherArrangementImport(
  semesterId: number,
  mode: TeacherArrangementMode,
  file: File,
): Promise<TeacherArrangementPreview> {
  return postTeacherArrangementWorkbook<TeacherArrangementPreview>(
    'preview',
    semesterId,
    mode,
    file,
  )
}

export function commitTeacherArrangementImport(
  semesterId: number,
  mode: TeacherArrangementMode,
  file: File,
  fingerprint: string,
  confirmChanges: boolean,
  confirmWarnings: boolean,
): Promise<TeacherArrangementCommitResult> {
  return postTeacherArrangementWorkbook<TeacherArrangementCommitResult>(
    'commit',
    semesterId,
    mode,
    file,
    { fingerprint, confirmChanges, confirmWarnings },
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

async function postReferenceFiles<T>(
  action: 'preview' | 'commit',
  semesterId: number,
  wordFile: File,
  xlsxFile: File,
  extra?: { fingerprint: string, confirmChanges: boolean, overrides?: Record<string, unknown> },
): Promise<T> {
  const form = new FormData()
  form.append('word_file', wordFile)
  form.append('xlsx_file', xlsxFile)
  if (extra) {
    form.append('fingerprint', extra.fingerprint)
    form.append('confirm_changes', String(extra.confirmChanges))
    if (extra.overrides) form.append('overrides', JSON.stringify(extra.overrides))
  }
  const response = await fetch(`/api/import/reference/${action}?semester_id=${semesterId}`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  })
  if (!response.ok) {
    throw await apiErrorFromResponse(response, action === 'preview' ? '参考文件预览失败' : '参考文件导入失败')
  }
  return response.json() as Promise<T>
}

export function previewReferenceImport(
  semesterId: number,
  wordFile: File,
  xlsxFile: File,
): Promise<ReferenceImportPreview> {
  return postReferenceFiles<ReferenceImportPreview>('preview', semesterId, wordFile, xlsxFile)
}

export function commitReferenceImport(
  semesterId: number,
  wordFile: File,
  xlsxFile: File,
  fingerprint: string,
  confirmChanges: boolean,
): Promise<ReferenceImportCommitResult> {
  return postReferenceFiles<ReferenceImportCommitResult>('commit', semesterId, wordFile, xlsxFile, {
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
