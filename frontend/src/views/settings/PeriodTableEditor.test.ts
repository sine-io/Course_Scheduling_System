import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { Period } from '@/api/semesters'
import PeriodTableEditor from './PeriodTableEditor.vue'

const mocks = vi.hoisted(() => ({
  getSemesterContext: vi.fn(),
  listSemesters: vi.fn(),
  getPeriodTable: vi.fn(),
  replacePeriods: vi.fn(),
}))

vi.mock('@/api/semesters', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/semesters')>()
  return { ...actual, ...mocks }
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

const fakeTable = {
  id: 1,
  semester_id: 1,
  name: '测试作息时间表',
  num_weekdays: 3,
  is_default: true,
  periods: [
    { id: 1, weekday: 1, period_no: 1, name: '第一节', start_time: '08:00:00', end_time: '08:40:00', type: 'regular' as const },
    { id: 2, weekday: 2, period_no: 1, name: '第一节', start_time: '08:00:00', end_time: '08:40:00', type: 'regular' as const },
    { id: 3, weekday: 3, period_no: 1, name: '第一节', start_time: '08:00:00', end_time: '08:40:00', type: 'regular' as const },
    { id: 4, weekday: 3, period_no: 2, name: '第二节', start_time: '08:50:00', end_time: '09:30:00', type: 'reserved' as const },
  ],
}

async function mountEditor(componentProps: Record<string, unknown> = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/settings/period-tables/:id', name: 'period-table-editor', component: PeriodTableEditor },
      { path: '/settings/semesters', name: 'semesters', component: { template: '<main />' } },
    ],
  })
  await router.push('/settings/period-tables/1')
  await router.isReady()
  const Host = {
    render: () => h(NMessageProvider, null, { default: () => h(PeriodTableEditor, componentProps) }),
  }
  return mount(Host, { global: { plugins: [createPinia(), router] } })
}

describe('PeriodTableEditor', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.getSemesterContext.mockResolvedValue({
      current_semester: { id: 1, label: '当前学期' }, revision: 1, can_switch: false,
    })
    mocks.listSemesters.mockResolvedValue([fakeTable])
    mocks.getPeriodTable.mockResolvedValue(fakeTable)
    mocks.replacePeriods.mockResolvedValue(fakeTable)
  })

  it('加载期间显示明确状态，完成后渲染名称与周次表头', async () => {
    const request = deferred<typeof fakeTable>()
    mocks.getPeriodTable.mockReturnValue(request.promise)

    const wrapper = await mountEditor()
    await nextTick()
    expect(wrapper.get('[data-testid="period-table-loading"]').text()).toContain('正在读取作息时间表')

    request.resolve(fakeTable)
    await flushPromises()
    expect(wrapper.text()).toContain('测试作息时间表')
    expect(wrapper.text()).toContain('周一')
    expect(wrapper.text()).toContain('周三')
    expect(wrapper.text()).toContain('固定用途')
  })

  it('读取失败时显示原因并提供重试入口', async () => {
    mocks.getPeriodTable.mockRejectedValue({ detail: '作息表暂时不可用' })

    const wrapper = await mountEditor()
    await flushPromises()

    expect(wrapper.get('[data-testid="period-table-error"]').text()).toContain('作息表暂时不可用')
    expect(wrapper.find('[data-testid="period-table-retry"]').exists()).toBe(true)
  })

  it('嵌入工作台时使用传入的作息表并将返回动作交给父页面', async () => {
    const onBack = vi.fn()
    const wrapper = await mountEditor({ embedded: true, embeddedTableId: 9, onBack })
    await flushPromises()

    expect(mocks.getPeriodTable).toHaveBeenCalledWith(9)
    expect(wrapper.get('[data-testid="period-table-back"]').text()).toContain('返回排课工作台')
    await wrapper.get('[data-testid="period-table-back"]').trigger('click')
    expect(onBack).toHaveBeenCalledOnce()
  })

  it('把宽表限制在独立工作面内滚动，并保留新增行入口', async () => {
    const wrapper = await mountEditor()
    await flushPromises()

    expect(wrapper.get('[data-testid="period-grid-scroll"]').classes()).toContain('settings-table-scroll')
    expect(wrapper.get('[data-testid="period-add-row"]').text()).toContain('新增节次行')
  })

  it('保存前把单数字小时归一化为 API 可接受的时间格式', async () => {
    const wrapper = await mountEditor()
    await flushPromises()

    await wrapper.get('[aria-label="第一节开始时间"] input').setValue('8:00')
    await wrapper.get('[aria-label="第一节结束时间"] input').setValue('8:40')
    await wrapper.get('[data-testid="period-table-save"]').trigger('click')
    await flushPromises()

    expect(mocks.replacePeriods).toHaveBeenCalledOnce()
    const periods = mocks.replacePeriods.mock.calls[0][1] as Period[]
    expect(periods.filter((period) => period.period_no === 1)).toHaveLength(3)
    expect(periods.filter((period) => period.period_no === 1).every((period) => (
      period.start_time === '08:00' && period.end_time === '08:40'
    ))).toBe(true)
  })

  it('时间无法解析时在页面内阻止提交', async () => {
    const wrapper = await mountEditor()
    await flushPromises()

    await wrapper.get('[aria-label="第一节开始时间"] input').setValue('上午八点')
    await wrapper.get('[data-testid="period-table-save"]').trigger('click')
    await flushPromises()

    expect(mocks.replacePeriods).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('第一节的开始时间格式不正确')
  })

  it('快捷模板生成可编辑的常规课和午休草稿', async () => {
    const wrapper = await mountEditor()
    await flushPromises()

    await wrapper.get('[data-testid="period-template-days"] input').setValue('5')
    await wrapper.get('[data-testid="period-template-morning"] input').setValue('2')
    await wrapper.get('[data-testid="period-template-afternoon"] input').setValue('1')
    await wrapper.get('[data-testid="period-template-apply"]').trigger('click')
    await nextTick()

    expect(wrapper.get('[data-testid="period-capacity-summary"]').text()).toContain('15 节')
    expect(wrapper.get('[data-testid="period-capacity-summary"]').text()).toContain('5 格')

    await wrapper.get('[data-testid="period-table-save"]').trigger('click')
    await flushPromises()

    const periods = mocks.replacePeriods.mock.calls[0][1] as Period[]
    expect(periods).toHaveLength(20)
    expect(periods.filter((period) => period.type === 'regular')).toHaveLength(15)
    expect(periods.filter((period) => period.type === 'lunch')).toHaveLength(5)
  })

  it('旧链接指向历史学期时显示只读并禁用保存入口', async () => {
    mocks.getSemesterContext.mockResolvedValue({
      current_semester: { id: 2, label: '当前学期' }, revision: 3, can_switch: false,
    })

    const wrapper = await mountEditor()
    await flushPromises()

    expect(wrapper.get('[data-testid="period-table-readonly"]').text()).toContain('历史学期')
    expect(wrapper.get('[data-testid="period-table-save"]').classes()).toContain('n-button--disabled')
    expect(wrapper.get('[data-testid="period-add-row"]').classes()).toContain('n-button--disabled')
    expect(mocks.replacePeriods).not.toHaveBeenCalled()
  })
})
