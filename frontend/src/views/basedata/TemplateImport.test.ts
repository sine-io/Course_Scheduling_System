import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TemplateImport from './TemplateImport.vue'

const mocks = vi.hoisted(() => ({
  commitTeacherArrangementImport: vi.fn(),
  downloadTeacherArrangementTemplate: vi.fn(),
  previewTeacherArrangementImport: vi.fn(),
}))

vi.mock('@/api/imports', () => ({ ...mocks }))

const semester = {
  id: 17,
  academic_year: 2026,
  term: 1,
  label: '2026-2027学年第一学期',
  status: 'preparing' as const,
  readiness: 'draft' as const,
  start_date: '2026-09-01',
  end_date: '2027-01-20',
  is_current: true,
}

const preview = {
  fingerprint: 'preview-fingerprint',
  template_version: '1.0',
  mode: 'standard' as const,
  semester_id: 17,
  can_commit: true,
  has_changes: true,
  counts: { new: 5, changed: 0, unchanged: 0, blocker: 0, warning: 0 },
  sheets: [
    {
      key: 'assignments' as const,
      label: '教学任务',
      rows: [
        {
          sheet: '教学任务',
          row: 4,
          source_key: 'TASK-701-MATH',
          identity: 'TASK-701-MATH',
          status: 'new' as const,
          changes: [],
          issues: [],
        },
      ],
    },
  ],
  issues: [],
}

function mountWorkspace(canEdit = true) {
  return mount(TemplateImport, {
    props: { semester, canEdit },
    attachTo: document.body,
  })
}

async function chooseWorkbook(wrapper: ReturnType<typeof mountWorkspace>, file: File) {
  const input = wrapper.get('[data-testid="template-file"]')
  Object.defineProperty(input.element, 'files', {
    configurable: true,
    value: [file],
  })
  await input.trigger('change')
}

describe('TemplateImport', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.downloadTeacherArrangementTemplate.mockResolvedValue(undefined)
    mocks.previewTeacherArrangementImport.mockResolvedValue(preview)
    mocks.commitTeacherArrangementImport.mockResolvedValue({
      batch_id: 31,
      fingerprint: 'preview-fingerprint',
      created: {
        subjects: 1,
        teachers: 1,
        classes: 1,
        assignments: 1,
        source_records: 1,
      },
      updated: {
        subjects: 0,
        teachers: 0,
        classes: 0,
        assignments: 0,
        source_records: 0,
      },
      unchanged: {
        subjects: 0,
        teachers: 0,
        classes: 0,
        assignments: 0,
        source_records: 0,
      },
      idempotent: false,
    })
  })

  it('uses the selected mode when downloading the bound template', async () => {
    const wrapper = mountWorkspace()

    await wrapper.get('[data-testid="template-mode-ready"]').trigger('click')
    await wrapper.get('[data-testid="template-download"]').trigger('click')
    await flushPromises()

    expect(mocks.downloadTeacherArrangementTemplate).toHaveBeenCalledWith(
      17,
      'scheduling_ready',
    )
    expect(wrapper.get('[data-testid="template-semester"]').text()).toContain(semester.label)
    wrapper.unmount()
  })

  it('previews and commits one uploaded workbook through the full workspace', async () => {
    const wrapper = mountWorkspace()
    const file = new File(['xlsx'], '教师安排标准模板.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })

    await chooseWorkbook(wrapper, file)
    await wrapper.get('[data-testid="template-preview"]').trigger('click')
    await flushPromises()

    expect(mocks.previewTeacherArrangementImport).toHaveBeenCalledWith(17, 'standard', file)
    expect(wrapper.get('[data-testid="preview-count-new"]').text()).toContain('5')
    expect(wrapper.text()).toContain('TASK-701-MATH')

    await wrapper.get('[data-testid="template-commit"]').trigger('click')
    await flushPromises()

    expect(mocks.commitTeacherArrangementImport).toHaveBeenCalledWith(
      17,
      'standard',
      file,
      'preview-fingerprint',
      false,
    )
    expect(wrapper.get('[data-testid="template-import-success"]').text()).toContain('已导入')
    wrapper.unmount()
  })

  it('allows read-only users to preview but not commit', async () => {
    const wrapper = mountWorkspace(false)
    const file = new File(['xlsx'], '教师安排标准模板.xlsx')

    await chooseWorkbook(wrapper, file)
    await wrapper.get('[data-testid="template-preview"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="template-commit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('只能预览')
    wrapper.unmount()
  })
})
