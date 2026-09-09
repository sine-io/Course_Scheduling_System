import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import {
  commitClassBatch,
  listClassUnits,
  listTeachers,
  previewClassBatch,
} from '@/api/basedata'
import ClassesTab from './ClassesTab.vue'

const basedataMocks = vi.hoisted(() => ({
  commitClassBatch: vi.fn(),
  createClassUnit: vi.fn(),
  deleteClassUnit: vi.fn(),
  listClassUnits: vi.fn(),
  listTeachers: vi.fn(),
  previewClassBatch: vi.fn(),
  updateClassUnit: vi.fn(),
}))

vi.mock('@/api/basedata', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/basedata')>()),
  ...basedataMocks,
}))
vi.mock('@/api/highRisk', () => ({ highRiskConfirmation: vi.fn(() => ({ confirmed: true })) }))

const batchPreview = {
  semester_id: 1,
  grade: 1,
  track: 'elementary' as const,
  grade_label: '一年级',
  fingerprint: 'a'.repeat(64),
  candidates: [
    {
      row_id: 1,
      name: '一年级1班',
      default_name: '一年级1班',
      department: null,
      student_count: null,
      homeroom_teacher_id: null,
      conflict: null,
    },
    {
      row_id: 2,
      name: '一年级2班',
      default_name: '一年级2班',
      department: null,
      student_count: null,
      homeroom_teacher_id: null,
      conflict: null,
    },
  ],
}

async function mountClasses() {
  const Host = {
    render: () => h(NMessageProvider, null, { default: () => h(ClassesTab, {
      semesterId: 1,
      canEdit: true,
      canDelete: false,
    }) }),
  }
  return mount(Host, { global: { plugins: [createPinia()] } })
}

describe('ClassesTab batch setup', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    basedataMocks.listClassUnits.mockResolvedValue([])
    basedataMocks.listTeachers.mockResolvedValue([])
    basedataMocks.previewClassBatch.mockResolvedValue(batchPreview)
    basedataMocks.commitClassBatch.mockResolvedValue({
      semester_id: 1,
      idempotent: false,
      classes: [],
    })
  })

  it('generates editable candidates and saves the whole batch once', async () => {
    const wrapper = await mountClasses()
    await flushPromises()

    await wrapper.get('[data-testid="class-add-batch"]').trigger('click')
    await flushPromises()
    const previewButton = document.body.querySelector<HTMLButtonElement>('[data-testid="class-batch-preview"]')
    expect(previewButton).not.toBeNull()
    previewButton?.click()
    await flushPromises()

    const batchTable = document.body.querySelector('[data-testid="class-batch-table"]')
    expect(batchTable).not.toBeNull()
    const nameInput = document.body.querySelector<HTMLInputElement>('[data-testid="class-batch-name-1"] input')
    expect(nameInput).not.toBeNull()
    expect(nameInput?.value).toBe('一年级1班')
    if (nameInput) {
      nameInput.value = '一年级实验班'
      nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    }
    await flushPromises()
    const saveButton = document.body.querySelector<HTMLButtonElement>('[data-testid="class-batch-save"]')
    expect(saveButton).not.toBeNull()
    saveButton?.click()
    await flushPromises()

    expect(basedataMocks.commitClassBatch).toHaveBeenCalledOnce()
    expect(commitClassBatch).toHaveBeenCalledWith(1, expect.objectContaining({
      grade: 1,
      track: 'elementary',
      preview_fingerprint: 'a'.repeat(64),
      candidates: expect.arrayContaining([
        expect.objectContaining({ row_id: 1, name: '一年级实验班' }),
      ]),
    }))
    expect(listClassUnits).toHaveBeenCalled()
    expect(listTeachers).toHaveBeenCalledWith(1)
    expect(previewClassBatch).toHaveBeenCalledWith(1, expect.objectContaining({
      grade: 1,
      track: 'elementary',
    }))
  })

  it('班级设置不显示作息时间表字段', async () => {
    const wrapper = await mountClasses()
    await flushPromises()

    await wrapper.get('[data-testid="class-add"]').trigger('click')
    await flushPromises()

    expect(document.body.querySelector('[data-testid="class-name"]')).not.toBeNull()
    expect(document.body.querySelector('[data-testid="class-period-table"]')).toBeNull()
  })
})
