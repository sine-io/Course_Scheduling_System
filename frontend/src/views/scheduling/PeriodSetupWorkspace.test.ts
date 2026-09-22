import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h, nextTick } from 'vue'
import type { Assignment } from '@/api/assignments'
import PeriodSetupWorkspace from './PeriodSetupWorkspace.vue'

const mocks = vi.hoisted(() => ({
  applyPeriodSetup: vi.fn(),
  getPeriodSetup: vi.fn(),
}))

vi.mock('@/api/semesters', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/semesters')>()
  return { ...actual, ...mocks }
})

const classItem = {
  id: 31,
  name: '701班',
  grade: 7,
  track: 'default',
  track_label: '普通班',
  period_table_id: 4,
}

const assignment = {
  id: 18,
  semester_id: 7,
  scheduling_unit: {
    id: 8,
    semester_id: 7,
    unit_type: 'single' as const,
    name: '701班',
    classes: [{ id: classItem.id, name: classItem.name, grade: classItem.grade }],
  },
  subject: { id: 2, name: '语文' },
  periods_per_week: 6,
  required_room_type: null,
  room_id: null,
  lock_room: false,
  teachers: [],
  block_rules: [],
} satisfies Assignment

function makeDraft(source: 'suggested' | 'existing' = 'existing') {
  return {
    fingerprint: 'a'.repeat(64),
    source,
    classes: [classItem],
    groups: [{
      key: 'table:4',
      table_id: source === 'existing' ? 4 : null,
      name: '默认作息',
      num_weekdays: 5,
      is_default: true,
      class_ids: [classItem.id],
      periods: [{
        period_no: 1,
        weekdays: [1, 2, 3, 4, 5],
        name: '第一节',
        type: 'regular' as const,
        start_time: null,
        end_time: null,
      }],
    }],
    unresolved_class_ids: [],
    ready: true,
    blockers: [],
    warnings: [],
  }
}

async function mountWorkspace(props: Record<string, unknown> = {}) {
  const Host = {
    render: () => h(
      NMessageProvider,
      null,
      { default: () => h(PeriodSetupWorkspace, { semesterId: 7, assignments: [assignment], ...props }) },
    ),
  }
  const wrapper = mount(Host, { attachTo: document.body })
  await flushPromises()
  return wrapper
}

describe('PeriodSetupWorkspace', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.getPeriodSetup.mockResolvedValue(makeDraft())
    mocks.applyPeriodSetup.mockImplementation(async (_semesterId: number, _fingerprint: string, groups: unknown[]) => ({
      ...makeDraft('existing'),
      groups,
    }))
  })

  it('显示课程总量与常规容量，并允许先保存超容量草稿', async () => {
    const wrapper = await mountWorkspace()

    expect(wrapper.get('[data-testid="period-capacity-warning"]').text()).toContain('超过常规课容量')
    expect(wrapper.get('[data-testid="period-capacity-preview"]').text()).toContain('6 / 5 节')

    await wrapper.get('[data-testid="period-setup-save"]').trigger('click')
    await flushPromises()

    expect(mocks.applyPeriodSetup).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('按上午和下午节数生成可编辑模板，并把午休标记为非任课时段', async () => {
    const wrapper = await mountWorkspace()

    await wrapper.get('[data-testid="period-template-morning"] input').setValue('2')
    await wrapper.get('[data-testid="period-template-afternoon"] input').setValue('1')
    await nextTick()
    expect(wrapper.get('[data-testid="period-group-editor"]').text()).toContain('常规容量 15 节/周')
    expect(wrapper.find('button[data-testid="period-template-apply"]').exists()).toBe(false)

    await wrapper.get('[data-testid="period-setup-save"]').trigger('click')
    await flushPromises()

    const groups = mocks.applyPeriodSetup.mock.calls[0][2] as Array<{ periods: Array<{ type: string; weekdays: number[] }> }>
    const periods = groups[0].periods
    expect(periods.filter((period) => period.type === 'regular').reduce((total, period) => total + period.weekdays.length, 0)).toBe(15)
    expect(periods.filter((period) => period.type === 'lunch').reduce((total, period) => total + period.weekdays.length, 0)).toBe(5)
    wrapper.unmount()
  })

  it('支持按年级或全校选班，并即时渲染周日和晚间节次', async () => {
    const secondClass = { ...classItem, id: 32, name: '702班' }
    const eighthGradeClass = { ...classItem, id: 41, name: '801班', grade: 8 }
    const draft = makeDraft()
    draft.classes = [classItem, secondClass, eighthGradeClass]
    mocks.getPeriodSetup.mockResolvedValue(draft)
    const wrapper = await mountWorkspace()

    expect(wrapper.get('[data-testid="period-class-all"]')).toBeTruthy()
    expect(wrapper.get('[data-testid="period-grade-7"]')).toBeTruthy()
    expect(wrapper.get('[data-testid="period-grade-8"]')).toBeTruthy()
    expect(wrapper.get('[data-testid="period-class-32"]')).toBeTruthy()

    await wrapper.get('[data-testid="period-grade-7"]').trigger('click')
    await nextTick()
    expect(wrapper.get('[data-testid="period-class-range"]').text()).toContain('2 / 3')

    await wrapper.get('[data-testid="period-class-all"]').trigger('click')
    await wrapper.get('[data-testid="period-weekday-7"]').trigger('click')
    await wrapper.get('[data-testid="period-template-evening"] input').setValue(1)
    await nextTick()

    expect(wrapper.get('[data-testid="period-class-range"]').text()).toContain('3 / 3')
    expect(wrapper.get('[data-testid="period-preview"]').text()).toContain('周日')
    expect(wrapper.findAll('input[placeholder="节次名称"]')
      .some((input) => (input.element as HTMLInputElement).value === '晚上第 1 节')).toBe(true)

    await wrapper.get('[data-testid="period-setup-save"]').trigger('click')
    await flushPromises()

    const groups = mocks.applyPeriodSetup.mock.calls[0][2] as Array<{
      class_ids: number[]
      num_weekdays: number
      periods: Array<{ name: string; weekdays: number[]; type: string }>
    }>
    expect(groups[0].class_ids.sort((left, right) => left - right)).toEqual([31, 32, 41])
    expect(groups[0].num_weekdays).toBe(7)
    expect(groups[0].periods.some((period) => period.name === '晚上第 1 节' && period.weekdays.includes(7))).toBe(true)
    wrapper.unmount()
  })

  it('在分组工作台内阻止结束时间早于开始时间', async () => {
    const wrapper = await mountWorkspace()

    const inputs = wrapper.findAll('.period-time-range input')
    await inputs[0].setValue('09:00')
    await inputs[1].setValue('08:00')
    await wrapper.get('[data-testid="period-setup-save"]').trigger('click')
    await flushPromises()

    expect(mocks.applyPeriodSetup).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('结束时间必须晚于开始时间')
    wrapper.unmount()
  })
})
