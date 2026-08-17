import { flushPromises, mount } from '@vue/test-utils'
import { NDialogProvider, NMessageProvider, NUpload } from 'naive-ui'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import type { CombinedImportPreview } from '@/api/imports'
import ImportTab from './ImportTab.vue'

const mocks = vi.hoisted(() => ({
  commitSetupImport: vi.fn(),
  downloadSetupTemplate: vi.fn(),
  downloadTemplate: vi.fn(),
  previewSetupImport: vi.fn(),
  uploadImport: vi.fn(),
}))

vi.mock('@/api/imports', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/api/imports')>(),
  ...mocks,
}))

const preview: CombinedImportPreview = {
  fingerprint: 'preview-1',
  can_commit: true,
  has_changes: true,
  counts: { new: 1, unchanged: 1, changed: 1, conflict: 0 },
  errors: [],
  sheets: [
    {
      key: 'subjects',
      label: '科目',
      rows: [
        {
          sheet: '科目', row: 4, identity: '数学', status: 'unchanged', changes: [], errors: [],
        },
      ],
    },
    {
      key: 'teachers',
      label: '教师',
      rows: [
        {
          sheet: '教师',
          row: 4,
          identity: '王老师（1234）',
          status: 'changed',
          changes: [{ field: '基本课时', before: 16, after: 18 }],
          errors: [],
        },
      ],
    },
    {
      key: 'classes',
      label: '班级',
      rows: [
        {
          sheet: '班级', row: 4, identity: '七年级1班', status: 'new', changes: [], errors: [],
        },
      ],
    },
    { key: 'rooms', label: '教室', rows: [] },
  ],
}

async function mountTab(canEdit = true) {
  const Host = {
    render: () => h(NMessageProvider, null, {
      default: () => h(NDialogProvider, null, {
        default: () => h(ImportTab, { semesterId: 8, canEdit }),
      }),
    }),
  }
  const wrapper = mount(Host)
  await flushPromises()
  return wrapper
}

async function chooseCombinedFile(wrapper: Awaited<ReturnType<typeof mountTab>>) {
  const file = new File(['xlsx'], 'school-setup.xlsx', {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  await wrapper.findComponent(NUpload).vm.$emit('change', {
    fileList: [{ id: '1', name: file.name, status: 'pending', file }],
  })
  await flushPromises()
  return file
}

describe('ImportTab combined setup import', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.previewSetupImport.mockResolvedValue(preview)
    mocks.commitSetupImport.mockResolvedValue({
      created: { subjects: 0, teachers: 0, classes: 1, rooms: 0 },
      updated: { subjects: 0, teachers: 1, classes: 0, rooms: 0 },
      unchanged: { subjects: 1, teachers: 0, classes: 0, rooms: 0 },
      total_created: 1,
      total_updated: 1,
      total_unchanged: 1,
    })
  })

  it('默认展示四表组合工作簿且不包含账号创建', async () => {
    const wrapper = await mountTab()

    expect(wrapper.get('[data-testid="combined-import-panel"]').text()).toContain('组合工作簿')
    expect(wrapper.text()).toContain('科目')
    expect(wrapper.text()).toContain('教师')
    expect(wrapper.text()).toContain('班级')
    expect(wrapper.text()).toContain('教室')
    expect(wrapper.text()).not.toContain('创建教师登录账号')
  })

  it('预览逐行状态，修改项确认前不可提交', async () => {
    const wrapper = await mountTab()
    const file = await chooseCombinedFile(wrapper)

    await wrapper.get('[data-testid="combined-preview"]').trigger('click')
    await flushPromises()

    expect(mocks.previewSetupImport).toHaveBeenCalledWith(8, file)
    expect(wrapper.get('[data-testid="combined-preview-results"]').text()).toContain('新增 1')
    expect(wrapper.get('[data-testid="combined-preview-results"]').text()).toContain('未变化 1')
    expect(wrapper.get('[data-testid="combined-preview-results"]').text()).toContain('将修改 1')
    expect(wrapper.get('[data-testid="combined-row-teachers-4"]').text()).toContain('基本课时：16 → 18')
    expect(wrapper.get('[data-testid="combined-commit"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="combined-confirm-changes"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="combined-commit"]').attributes('disabled')).toBeUndefined()

    await wrapper.get('[data-testid="combined-commit"]').trigger('click')
    await flushPromises()
    expect(mocks.commitSetupImport).toHaveBeenCalledWith(8, file, 'preview-1', true)
    expect(wrapper.get('[data-testid="combined-import-success"]').text()).toContain('新增 1 条，更新 1 条')
  })

  it('冲突显示工作表、行和字段，并阻止提交', async () => {
    mocks.previewSetupImport.mockResolvedValue({
      ...preview,
      can_commit: false,
      has_changes: false,
      counts: { new: 0, unchanged: 0, changed: 0, conflict: 1 },
      errors: [{ sheet: '教师', row: 4, field: '任教科目', message: '科目「未知」不存在' }],
      sheets: preview.sheets.map((sheet) => ({ ...sheet, rows: [] })),
    })
    const wrapper = await mountTab()
    await chooseCombinedFile(wrapper)

    await wrapper.get('[data-testid="combined-preview"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="combined-conflicts"]').text()).toContain('教师 · 第 4 行 · 任教科目')
    expect(wrapper.get('[data-testid="combined-conflicts"]').text()).toContain('科目「未知」不存在')
    expect(wrapper.find('[data-testid="combined-commit"]').exists()).toBe(false)
  })
})
