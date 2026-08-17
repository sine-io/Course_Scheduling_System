import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import type { PeriodSetupDraft } from '@/api/semesters'
import PeriodSetup from './PeriodSetup.vue'

const mocks = vi.hoisted(() => ({
  applyPeriodSetup: vi.fn(),
  getPeriodSetup: vi.fn(),
}))

vi.mock('@/api/semesters', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/api/semesters')>(),
  ...mocks,
}))

const draft: PeriodSetupDraft = {
  fingerprint: 'period-draft-1',
  source: 'suggested',
  classes: [
    { id: 11, name: '初一1班', grade: 7, track: 'junior_high', track_label: '初中', period_table_id: null },
    { id: 12, name: '高一1班', grade: 10, track: 'senior_high', track_label: '普通高中', period_table_id: null },
  ],
  groups: [
    {
      key: 'track-junior_high',
      table_id: null,
      name: '初中作息',
      num_weekdays: 5,
      is_default: true,
      class_ids: [11],
      periods: [{
        period_no: 1,
        weekdays: [1, 2, 3, 4, 5],
        name: '第一节',
        type: 'regular',
        start_time: null,
        end_time: null,
      }],
    },
    {
      key: 'track-senior_high',
      table_id: null,
      name: '普通高中作息',
      num_weekdays: 5,
      is_default: false,
      class_ids: [12],
      periods: [{
        period_no: 1,
        weekdays: [1, 2, 3, 4, 5],
        name: '第一节',
        type: 'regular',
        start_time: null,
        end_time: null,
      }],
    },
  ],
  unresolved_class_ids: [],
  ready: true,
  blockers: [],
  warnings: ['有节次尚未填写完整的开始和结束时间'],
}

async function mountSetup(canEdit = true) {
  const Host = {
    render: () => h(NMessageProvider, null, {
      default: () => h(PeriodSetup, { semesterId: 8, canEdit }),
    }),
  }
  const wrapper = mount(Host)
  await flushPromises()
  return wrapper
}

describe('PeriodSetup', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.getPeriodSetup.mockResolvedValue(structuredClone(draft))
    mocks.applyPeriodSetup.mockImplementation((_semesterId, _fingerprint, groups) => Promise.resolve({
      ...structuredClone(draft),
      fingerprint: 'period-draft-2',
      source: 'existing',
      groups,
    }))
  })

  it('只显示按学制生成的可编辑建议，不会自行写入', async () => {
    const wrapper = await mountSetup()

    expect(wrapper.get('[data-testid="period-setup-source"]').text()).toContain('尚未写入')
    expect((wrapper.get('[data-testid="period-group-name-track-junior_high"] input').element as HTMLInputElement).value).toBe('初中作息')
    expect((wrapper.get('[data-testid="period-group-name-track-senior_high"] input').element as HTMLInputElement).value).toBe('普通高中作息')
    expect(wrapper.get('[data-testid="period-preview-track-junior_high-1-1"]').text()).toContain('第一节')
    expect(mocks.applyPeriodSetup).not.toHaveBeenCalled()
  })

  it('支持拆分、批量合并、重命名，并让周预览即时变化', async () => {
    const wrapper = await mountSetup()

    await wrapper.get('[data-testid="period-split-track-junior_high"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-period-group="true"]')).toHaveLength(3)

    await wrapper.get('[data-testid="period-merge-select-track-junior_high"]').trigger('click')
    await wrapper.get('[data-testid="period-merge-select-track-senior_high"]').trigger('click')
    await wrapper.get('[data-testid="period-merge"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="period-group-track-senior_high"]').exists()).toBe(false)

    const nameInput = wrapper.get('[data-testid="period-group-name-track-junior_high"] input')
    await nameInput.setValue('共同作息')
    const periodName = wrapper.get('[data-testid="period-name-track-junior_high-0"] input')
    await periodName.setValue('晨间第一节')
    await flushPromises()
    expect(wrapper.get('[data-testid="period-preview-track-junior_high-1-1"]').text()).toContain('晨间第一节')

    await wrapper.get('[data-testid="period-setup-apply"]').trigger('click')
    await flushPromises()
    expect(mocks.applyPeriodSetup).toHaveBeenCalledWith(
      8,
      'period-draft-1',
      expect.arrayContaining([
        expect.objectContaining({ name: '共同作息', class_ids: [11, 12] }),
      ]),
    )
  })

  it('只读角色能检查分组，但不能拆分或应用', async () => {
    const wrapper = await mountSetup(false)

    expect(wrapper.get('[data-testid="period-setup-readonly"]').text()).toContain('只能查看')
    expect(wrapper.find('[data-testid="period-split-track-junior_high"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="period-setup-apply"]').exists()).toBe(false)
    expect(mocks.applyPeriodSetup).not.toHaveBeenCalled()
  })

  it('没有任何常规课节次时阻止应用', async () => {
    const wrapper = await mountSetup()

    await wrapper.get('[data-testid="period-remove-track-junior_high-0"]').trigger('click')
    await wrapper.get('[data-testid="period-remove-track-senior_high-0"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('.period-setup-review').text()).toContain('至少需要一个常规课节次')
    expect(wrapper.get('[data-testid="period-setup-apply"]').attributes('disabled')).toBeDefined()
    expect(mocks.applyPeriodSetup).not.toHaveBeenCalled()
  })
})
