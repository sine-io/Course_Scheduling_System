import { afterEach, describe, expect, it, vi } from 'vitest'
import { restoreUpload } from './backups'
import type { HighRiskConfirmation } from './highRisk'
import { uploadImport } from './imports'

const confirmation: HighRiskConfirmation = {
  operation_id: 'operation-1',
  confirmed: true,
  target: '测试目标',
}

function failedResponse(message: string): Response {
  return {
    ok: false,
    status: 409,
    json: () => Promise.resolve({
      detail: { code: 'confirmation_required', message },
    }),
  } as Response
}

describe('multipart API errors', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('上传备份恢复时显示结构化的中文错误', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(failedResponse('请重新确认恢复目标。'))))

    await expect(restoreUpload(
      new File(['backup'], 'backup.tar.gz'),
      confirmation,
    )).rejects.toThrow('请重新确认恢复目标。')
  })

  it('批量导入时显示结构化的中文错误', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(failedResponse('请确认批量创建教师账号。'))))

    await expect(uploadImport(
      'teachers',
      8,
      new File(['teachers'], 'teachers.xlsx'),
      true,
      confirmation,
    )).rejects.toThrow('请确认批量创建教师账号。')
  })
})
