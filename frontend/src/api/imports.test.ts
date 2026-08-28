import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  commitTeacherArrangementImport,
  downloadTeacherArrangementTemplate,
} from './imports'

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

describe('commitTeacherArrangementImport', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('submits reimport decisions with the preview fingerprint', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      void input
      void init
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ batch_id: 9 }),
      } as Response)
    })
    vi.stubGlobal('fetch', fetchMock)
    const file = new File(['xlsx'], '教师安排.xlsx')

    await commitTeacherArrangementImport(
      17,
      'standard',
      file,
      'fingerprint',
      true,
      false,
      {
        'teachers:code:T-001': 'incoming',
        'source_records:SRC-001': 'keep',
      },
    )

    const [url, init] = fetchMock.mock.calls[0]!
    const form = init!.body as FormData
    expect(url).toBe('/api/import/teacher-arrangements/commit?semester_id=17&mode=standard')
    expect(form.get('fingerprint')).toBe('fingerprint')
    expect(form.get('confirm_changes')).toBe('true')
    expect(form.get('confirm_warnings')).toBe('false')
    expect(form.get('decisions')).toBe(JSON.stringify({
      'teachers:code:T-001': 'incoming',
      'source_records:SRC-001': 'keep',
    }))
  })
})
