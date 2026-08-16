// Excel 导入 API:模板下载、上传导入。

import type { HighRiskConfirmation } from '@/api/highRisk'

export type ImportEntity = 'subjects' | 'teachers' | 'classes' | 'assignments'

export interface ImportResult {
  imported: number
  accounts_created?: number
  errors: string[]
}

export const ENTITY_LABELS: Record<ImportEntity, string> = {
  subjects: '科目',
  teachers: '教师',
  classes: '班级',
  assignments: '教学任务',
}

/** 下载模板档并触发浏览器存储。 */
export async function downloadTemplate(entity: ImportEntity): Promise<void> {
  const resp = await fetch(`/api/import/templates/${entity}`, { credentials: 'include' })
  if (!resp.ok) throw new Error('模板下载失败')
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${entity}_template.xlsx`
  a.click()
  URL.revokeObjectURL(url)
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
    let detail = '导入失败'
    try {
      detail = (await resp.json())?.detail ?? detail
    } catch {
      /* 无需处理解析失败，调用方会显示原始错误。 */
    }
    throw new Error(detail)
  }
  return resp.json() as Promise<ImportResult>
}
