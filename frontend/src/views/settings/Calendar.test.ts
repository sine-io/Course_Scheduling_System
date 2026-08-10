import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import Calendar from './Calendar.vue'

const semesterMocks = vi.hoisted(() => ({
  listSemesters: vi.fn(),
}))
const calendarMocks = vi.hoisted(() => ({
  confirmSemesterReadiness: vi.fn(),
  createCalendarException: vi.fn(),
  deleteCalendarException: vi.fn(),
  getSemesterReadiness: vi.fn(),
  listCalendarExceptions: vi.fn(),
  updateCalendarException: vi.fn(),
}))

vi.mock('@/api/semesters', () => ({ ...semesterMocks }))
vi.mock('@/api/calendar', () => ({ ...calendarMocks }))

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

const semester = {
  id: 4,
  academic_year: 2042,
  term: 1,
  label: '2042-2043学年第一学期',
  status: 'preparing' as const,
  readiness: 'draft' as const,
  start_date: '2042-09-01',
  end_date: '2043-01-20',
}
const exception = {
  id: 9,
  semester_id: 4,
  date: '2042-10-01',
  kind: 'no_instruction' as const,
  makeup_weekday: null,
  note: '国庆节',
  created_by_name: '管理员',
  created_at: '2042-08-01T00:00:00Z',
}
const readiness = {
  semester_id: 4,
  readiness: 'draft' as const,
  ready: false,
  issues: [],
  calendar_exception_count: 1,
}

async function mountCalendar(options: Record<string, unknown> = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/settings/calendar', name: 'calendar', component: Calendar },
      { path: '/settings/semesters', name: 'semesters', component: { template: '<main />' } },
    ],
  })
  await router.push('/settings/calendar')
  await router.isReady()
  const Host = { render: () => h(NMessageProvider, null, { default: () => h(Calendar) }) }
  return mount(Host, {
    global: {
      plugins: [createPinia(), router],
      ...options,
    },
  })
}

describe('Calendar', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    semesterMocks.listSemesters.mockResolvedValue([])
    calendarMocks.listCalendarExceptions.mockResolvedValue([])
    calendarMocks.getSemesterReadiness.mockResolvedValue(readiness)
  })

  it('读取学期期间显示加载状态，没有学期时显示明确空态', async () => {
    const request = deferred<never[]>()
    semesterMocks.listSemesters.mockReturnValue(request.promise)

    const wrapper = await mountCalendar()
    await nextTick()
    expect(wrapper.get('[data-testid="calendar-loading"]').text()).toContain('正在读取校历设置')

    request.resolve([])
    await flushPromises()
    expect(wrapper.get('[data-testid="calendar-empty"]').text()).toContain('尚未创建任何学期')
  })

  it('当前学期校历读取失败时提供局部重试入口', async () => {
    semesterMocks.listSemesters.mockResolvedValue([semester])
    calendarMocks.listCalendarExceptions.mockRejectedValue({ detail: '校历服务暂时不可用' })

    const wrapper = await mountCalendar()
    await flushPromises()

    expect(wrapper.get('[data-testid="calendar-data-error"]').text()).toContain('校历服务暂时不可用')
    expect(wrapper.find('[data-testid="calendar-data-retry"]').exists()).toBe(true)
  })

  it('删除特殊日期进行中时重复确认只发送一次请求', async () => {
    const deletion = deferred<void>()
    semesterMocks.listSemesters.mockResolvedValue([semester])
    calendarMocks.listCalendarExceptions.mockResolvedValue([exception])
    calendarMocks.deleteCalendarException.mockReturnValue(deletion.promise)

    const wrapper = await mountCalendar({
      stubs: {
        Popconfirm: {
          emits: ['positive-click'],
          template: '<span><slot name="trigger" /><button data-testid="confirm-calendar-delete-9" @click="$emit(\'positive-click\')">确认</button></span>',
        },
      },
    })
    await flushPromises()

    const confirm = wrapper.get('[data-testid="confirm-calendar-delete-9"]')
    await confirm.trigger('click')
    await confirm.trigger('click')

    expect(calendarMocks.deleteCalendarException).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="calendar-delete-9"]').attributes('disabled')).toBeDefined()

    deletion.resolve()
    await flushPromises()
  })
})
