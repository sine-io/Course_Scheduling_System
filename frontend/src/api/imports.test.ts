import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { downloadTeacherArrangementTemplate } from './imports'

describe('downloadTeacherArrangementTemplate', () => {
  const downloads: string[] = []

  beforeEach(() => {
    downloads.length = 0
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      ok: true,
      blob: () => Promise.resolve(new Blob(['xlsx'])),
    })))
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:teacher-arrangement'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function click(
      this: HTMLAnchorElement,
    ) {
      downloads.push(this.download)
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it.each([
    ['standard', '教师安排标准模板_v1.0.xlsx'],
    ['scheduling_ready', '自动排课准备模板_v1.0.xlsx'],
  ] as const)('requests and names the %s template', async (mode, filename) => {
    await downloadTeacherArrangementTemplate(17, mode)

    expect(fetch).toHaveBeenCalledWith(
      `/api/import/teacher-arrangements/template?semester_id=17&mode=${mode}`,
      { credentials: 'include' },
    )
    expect(downloads).toEqual([filename])
  })
})
