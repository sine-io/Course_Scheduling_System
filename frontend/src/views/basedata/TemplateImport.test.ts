import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { TeacherArrangementPreview } from '@/api/imports'
import TemplateImport from './TemplateImport.vue'

const mocks = vi.hoisted(() => ({
  commitTeacherArrangementImport: vi.fn(),
  confirmSemesterReadiness: vi.fn(),
  downloadTeacherArrangementTemplate: vi.fn(),
  getSemesterReadiness: vi.fn(),
  previewTeacherArrangementImport: vi.fn(),
}))

vi.mock('@/api/imports', () => ({ ...mocks }))
vi.mock('@/api/calendar', () => ({ ...mocks }))

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
  counts: {
    new: 5,
    changed: 0,
    unchanged: 0,
    conflict: 0,
    disappeared: 0,
    blocker: 0,
    warning: 0,
  },
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
          decision: null,
        },
      ],
    },
  ],
  issues: [],
}

const warningPreview = {
  ...preview,
  can_commit: true,
  counts: {
    new: 5,
    changed: 0,
    unchanged: 0,
    conflict: 0,
    disappeared: 0,
    blocker: 0,
    warning: 1,
  },
  issues: [
    {
      code: 'assignment_teacher_missing',
      severity: 'warning' as const,
      sheet: '教学任务',
      row: 4,
      field: '主讲教师',
      value: null,
      message: '教学任务尚未指定主讲教师',
      suggestion: '填写教师学校编码或目标学期内唯一姓名',
    },
  ],
}

const decisionPreview: TeacherArrangementPreview = {
  ...preview,
  can_commit: false,
  counts: {
    new: 0,
    changed: 0,
    unchanged: 3,
    conflict: 1,
    disappeared: 1,
    blocker: 0,
    warning: 0,
  },
  sheets: [
    {
      key: 'teachers' as const,
      label: '教师',
      rows: [
        {
          sheet: '教师',
          row: 4,
          source_key: 'code:T-001',
          identity: 'T-001',
          status: 'conflict' as const,
          changes: [
            {
              field: 'base_periods',
              before: 19,
              after: 19,
              baseline: 18,
              current: 19,
              incoming: 20,
              resolution: 'conflict',
            },
          ],
          issues: [],
          decision: {
            key: 'teachers:code:T-001',
            kind: 'conflict' as const,
            selected: null,
            options: ['incoming', 'current'],
            removal_allowed: false,
            reason: null,
          },
        },
      ],
    },
    {
      key: 'source_records' as const,
      label: '来源记录',
      rows: [
        {
          sheet: '来源记录',
          row: 4,
          source_key: 'SRC-001',
          identity: 'SRC-001',
          status: 'disappeared' as const,
          changes: [],
          issues: [],
          decision: {
            key: 'source_records:SRC-001',
            kind: 'disappeared' as const,
            selected: null,
            options: ['keep', 'remove'],
            removal_allowed: true,
            reason: null,
          },
        },
      ],
    },
  ],
  issues: [],
}

function previewWithDecisions(
  selected: Record<string, 'incoming' | 'current' | 'keep' | 'remove'>,
): TeacherArrangementPreview {
  const result = structuredClone(decisionPreview)
  result.fingerprint = `decision-${Object.values(selected).join('-')}`
  const conflict = result.sheets[0]!.rows[0]!
  const disappeared = result.sheets[1]!.rows[0]!
  const conflictSelection = selected['teachers:code:T-001']
  const disappearedSelection = selected['source_records:SRC-001']
  if (conflict.decision && conflictSelection) {
    conflict.decision.selected = conflictSelection
    conflict.status = conflictSelection === 'incoming' ? 'changed' : 'unchanged'
    result.counts.conflict = 0
    result.counts[conflict.status] += 1
  }
  if (disappeared.decision && disappearedSelection) {
    disappeared.decision.selected = disappearedSelection
  }
  result.can_commit = Boolean(conflictSelection && disappearedSelection)
  return result
}

const readyPreview = {
  ...preview,
  mode: 'scheduling_ready' as const,
  counts: {
    ...preview.counts,
    new: 7,
  },
}

const emptyPreview = {
  ...preview,
  has_changes: false,
  counts: {
    new: 0,
    changed: 0,
    unchanged: 0,
    conflict: 0,
    disappeared: 0,
    blocker: 0,
    warning: 0,
  },
  sheets: [],
}

const readiness = {
  semester_id: 17,
  readiness: 'draft' as const,
  ready: false,
  issues: [],
  checks: [
    {
      key: 'data_integrity',
      label: '数据完整性',
      ok: true,
      error_count: 0,
      warning_count: 0,
      issues: [],
    },
    {
      key: 'solver_preflight',
      label: '求解预检',
      ok: true,
      error_count: 0,
      warning_count: 0,
      issues: [],
    },
  ],
  calendar_exception_count: 0,
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
    mocks.getSemesterReadiness.mockResolvedValue(readiness)
    mocks.confirmSemesterReadiness.mockResolvedValue({
      ...readiness,
      readiness: 'ready',
      ready: true,
    })
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

  afterEach(() => {
    vi.restoreAllMocks()
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

    expect(mocks.previewTeacherArrangementImport).toHaveBeenCalledWith(17, 'standard', file, {})
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
      false,
      {},
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

  it('shows a review queue, exports issues, and requires warning confirmation', async () => {
    mocks.previewTeacherArrangementImport.mockResolvedValueOnce(warningPreview)
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:issues'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    })
    const downloads: string[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function click(
      this: HTMLAnchorElement,
    ) {
      downloads.push(this.download)
    })
    const wrapper = mountWorkspace()
    const file = new File(['xlsx'], '教师安排标准模板.xlsx')

    await chooseWorkbook(wrapper, file)
    await wrapper.get('[data-testid="template-preview"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="review-filter-warning"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.get('[data-testid="review-queue-item-0"]').text()).toContain('主讲教师')
    expect(wrapper.get('[data-testid="review-detail"]').text()).toContain('填写教师学校编码')
    expect(wrapper.get('[data-testid="template-commit"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="export-issues"]').trigger('click')
    expect(downloads).toEqual(['教师安排模板问题.csv'])

    await wrapper.get('[data-testid="confirm-warnings"]').setValue(true)
    await wrapper.get('[data-testid="template-commit"]').trigger('click')
    await flushPromises()

    expect(mocks.commitTeacherArrangementImport).toHaveBeenCalledWith(
      17,
      'standard',
      file,
      'preview-fingerprint',
      false,
      true,
      {},
    )
    wrapper.unmount()
  })

  it('requires conflict and disappeared decisions before committing a reimport', async () => {
    const finalPreview = previewWithDecisions({
      'teachers:code:T-001': 'incoming',
      'source_records:SRC-001': 'keep',
    })
    let resolveFinalPreview: (value: TeacherArrangementPreview) => void = () => undefined
    mocks.previewTeacherArrangementImport
      .mockResolvedValueOnce(decisionPreview)
      .mockResolvedValueOnce(previewWithDecisions({
        'teachers:code:T-001': 'incoming',
      }))
      .mockReturnValueOnce(new Promise((resolve) => {
        resolveFinalPreview = resolve
      }))
    const wrapper = mountWorkspace()
    const file = new File(['xlsx'], '教师安排重导入.xlsx')

    await chooseWorkbook(wrapper, file)
    await wrapper.get('[data-testid="template-preview"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="review-filter-conflict"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.get('[data-testid="template-commit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="decision-incoming"]').text()).toContain('模板')
    await wrapper.get('[data-testid="decision-incoming"]').trigger('click')
    await flushPromises()

    await wrapper.get('[data-testid="review-filter-disappeared"]').trigger('click')
    expect(wrapper.get('[data-testid="decision-keep"]').text()).toContain('保留')
    await wrapper.get('[data-testid="confirm-changes"]').setValue(true)
    await wrapper.get('[data-testid="decision-keep"]').trigger('click')
    expect(wrapper.get('[data-testid="template-commit"]').attributes('disabled')).toBeDefined()

    resolveFinalPreview(finalPreview)
    await flushPromises()
    expect(wrapper.get('[data-testid="template-commit"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="confirm-changes"]').setValue(true)
    expect(wrapper.get('[data-testid="template-commit"]').attributes('disabled')).toBeUndefined()
    await wrapper.get('[data-testid="template-commit"]').trigger('click')
    await flushPromises()

    expect(mocks.commitTeacherArrangementImport).toHaveBeenCalledWith(
      17,
      'standard',
      file,
      'decision-incoming-keep',
      true,
      false,
      {
        'teachers:code:T-001': 'incoming',
        'source_records:SRC-001': 'keep',
      },
    )
    expect(mocks.previewTeacherArrangementImport).toHaveBeenNthCalledWith(
      2,
      17,
      'standard',
      file,
      { 'teachers:code:T-001': 'incoming' },
    )
    expect(mocks.previewTeacherArrangementImport).toHaveBeenNthCalledWith(
      3,
      17,
      'standard',
      file,
      {
        'teachers:code:T-001': 'incoming',
        'source_records:SRC-001': 'keep',
      },
    )
    wrapper.unmount()
  })

  it('keeps the workbook ready for a fresh preview after a stale commit', async () => {
    mocks.commitTeacherArrangementImport.mockRejectedValueOnce(new Error('预览已过期，请重新预览'))
    const wrapper = mountWorkspace()
    const file = new File(['xlsx'], '教师安排标准模板.xlsx')

    await chooseWorkbook(wrapper, file)
    await wrapper.get('[data-testid="template-preview"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="template-commit"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('预览已过期，请重新预览')
    await wrapper.get('[data-testid="template-preview"]').trigger('click')
    await flushPromises()
    expect(mocks.previewTeacherArrangementImport).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('预览已过期，请重新预览')
    wrapper.unmount()
  })

  it('shows validation progress and an explicit empty review state', async () => {
    let resolvePreview: (value: typeof emptyPreview) => void = () => undefined
    mocks.previewTeacherArrangementImport.mockReturnValueOnce(new Promise((resolve) => {
      resolvePreview = resolve
    }))
    const wrapper = mountWorkspace()
    const file = new File(['xlsx'], '空模板.xlsx')

    await chooseWorkbook(wrapper, file)
    await wrapper.get('[data-testid="template-preview"]').trigger('click')

    expect(wrapper.get('[data-testid="template-preview-loading"]').text()).toContain('正在校验模板')

    resolvePreview(emptyPreview)
    await flushPromises()

    expect(wrapper.get('[data-testid="review-empty"]').text()).toContain('当前分类没有记录')
    wrapper.unmount()
  })

  it('clears the old preview when the user replaces the workbook', async () => {
    const wrapper = mountWorkspace()
    const first = new File(['first'], '第一次.xlsx')
    const replacement = new File(['replacement'], '修正后.xlsx')

    await chooseWorkbook(wrapper, first)
    await wrapper.get('[data-testid="template-preview"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="preview-count-new"]').exists()).toBe(true)

    await chooseWorkbook(wrapper, replacement)

    expect(wrapper.find('[data-testid="preview-count-new"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('修正后.xlsx')

    await wrapper.get('[data-testid="template-preview"]').trigger('click')
    await flushPromises()
    expect(mocks.previewTeacherArrangementImport).toHaveBeenLastCalledWith(
      17,
      'standard',
      replacement,
      {},
    )
    wrapper.unmount()
  })

  it('offers a direct retry after preview loading fails', async () => {
    mocks.previewTeacherArrangementImport
      .mockRejectedValueOnce(new Error('校验服务暂时不可用'))
      .mockResolvedValueOnce(preview)
    const wrapper = mountWorkspace()
    const file = new File(['xlsx'], '待重试.xlsx')

    await chooseWorkbook(wrapper, file)
    await wrapper.get('[data-testid="template-preview"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="template-import-error"]').text()).toContain('校验服务暂时不可用')
    await wrapper.get('[data-testid="template-error-retry"]').trigger('click')
    await flushPromises()

    expect(mocks.previewTeacherArrangementImport).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="preview-count-new"]').text()).toContain('5')
    wrapper.unmount()
  })

  it('confirms readiness after both checks pass and opens the rule editor next', async () => {
    mocks.previewTeacherArrangementImport.mockResolvedValueOnce(readyPreview)
    const wrapper = mountWorkspace()
    const file = new File(['xlsx'], '自动排课准备模板.xlsx')

    await wrapper.get('[data-testid="template-mode-ready"]').trigger('click')
    await chooseWorkbook(wrapper, file)
    await wrapper.get('[data-testid="template-preview"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="template-commit"]').trigger('click')
    await flushPromises()

    expect(mocks.getSemesterReadiness).toHaveBeenCalledWith(17)
    expect(wrapper.get('[data-testid="template-readiness"]').text()).toContain('数据完整性')
    expect(wrapper.get('[data-testid="template-readiness"]').text()).toContain('求解预检')
    expect(wrapper.get('[data-testid="readiness-confirm"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).toContain('确认就绪')

    await wrapper.get('[data-testid="readiness-confirm"]').trigger('click')
    await flushPromises()

    expect(mocks.confirmSemesterReadiness).toHaveBeenCalledWith(17)
    expect(wrapper.get('[data-testid="readiness-next"]').attributes('href')).toBe('/scheduling/flow?step=start&semester=17')
    expect(wrapper.get('[data-testid="readiness-next"]').text()).toContain('继续排课工作台')
    wrapper.unmount()
  })

  it('keeps readiness confirmation blocked when a check fails', async () => {
    mocks.previewTeacherArrangementImport.mockResolvedValueOnce(readyPreview)
    mocks.getSemesterReadiness.mockResolvedValueOnce({
      ...readiness,
      issues: [{ code: 'teacher_overload', message: '教师可排时段不足' }],
      checks: [
        readiness.checks[0],
        {
          ...readiness.checks[1],
          ok: false,
          error_count: 1,
          issues: [{ code: 'teacher_overload', message: '教师可排时段不足' }],
        },
      ],
    })
    const wrapper = mountWorkspace()
    const file = new File(['xlsx'], '自动排课准备模板.xlsx')

    await wrapper.get('[data-testid="template-mode-ready"]').trigger('click')
    await chooseWorkbook(wrapper, file)
    await wrapper.get('[data-testid="template-preview"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="template-commit"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="readiness-confirm"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="template-readiness"]').text()).toContain('教师可排时段不足')
    expect(wrapper.find('[data-testid="readiness-next"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
