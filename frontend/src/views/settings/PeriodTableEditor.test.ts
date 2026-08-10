import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import PeriodTableEditor from './PeriodTableEditor.vue'

const mocks = vi.hoisted(() => ({
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

async function mountEditor() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/settings/period-tables/:id', name: 'period-table-editor', component: PeriodTableEditor },
      { path: '/settings/semesters', name: 'semesters', component: { template: '<main />' } },
    ],
  })
  await router.push('/settings/period-tables/1')
  await router.isReady()
  const Host = { render: () => h(NMessageProvider, null, { default: () => h(PeriodTableEditor) }) }
  return mount(Host, { global: { plugins: [router] } })
}

describe('PeriodTableEditor', () => {
  beforeEach(() => {
    vi.resetAllMocks()
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

  it('把宽表限制在独立工作面内滚动，并保留新增行入口', async () => {
    const wrapper = await mountEditor()
    await flushPromises()

    expect(wrapper.get('[data-testid="period-grid-scroll"]').classes()).toContain('settings-table-scroll')
    expect(wrapper.get('[data-testid="period-add-row"]').text()).toContain('新增节次行')
  })
})
