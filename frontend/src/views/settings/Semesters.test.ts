import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import Semesters from './Semesters.vue'

const mocks = vi.hoisted(() => ({
  listTemplates: vi.fn(),
  listSemesters: vi.fn(),
  getSemester: vi.fn(),
  createSemester: vi.fn(),
  deleteSemester: vi.fn(),
  createPeriodTable: vi.fn(),
  deletePeriodTable: vi.fn(),
  copySemester: vi.fn(),
}))

vi.mock('@/api/semesters', () => ({
  ...mocks,
}))

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

const semester = {
  id: 1,
  academic_year: 2042,
  term: 1,
  label: '2042-2043学年第一学期',
  status: 'preparing' as const,
  readiness: 'draft' as const,
  start_date: '2042-09-01',
  end_date: '2043-01-20',
  period_tables: [],
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/settings/semesters', name: 'semesters', component: Semesters },
      { path: '/settings/calendar', name: 'calendar', component: { template: '<main />' } },
      { path: '/settings/period-tables/:id', name: 'period-table-editor', component: { template: '<main />' } },
    ],
  })
}

async function mountSemesters(options: Record<string, unknown> = {}) {
  const router = makeRouter()
  await router.push('/settings/semesters')
  await router.isReady()
  const Host = { render: () => h(NMessageProvider, null, { default: () => h(Semesters) }) }
  return mount(Host, {
    global: {
      plugins: [createPinia(), router],
      ...options,
    },
  })
}

describe('Semesters', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.listTemplates.mockResolvedValue([])
    mocks.listSemesters.mockResolvedValue([])
  })

  it('读取学期与模板期间显示明确的加载状态', async () => {
    const templatesRequest = deferred<never[]>()
    mocks.listTemplates.mockReturnValue(templatesRequest.promise)

    const wrapper = await mountSemesters()
    await nextTick()

    expect(wrapper.get('[data-testid="semesters-loading"]').text()).toContain('正在读取学期与作息时间表')

    templatesRequest.resolve([])
    await flushPromises()
  })

  it('读取失败时保留设置页并提供重试入口', async () => {
    let attempts = 0
    mocks.listTemplates.mockImplementation(() => {
      attempts += 1
      return attempts === 1
        ? Promise.reject({ detail: '模板服务暂时不可用' })
        : Promise.resolve([])
    })

    const wrapper = await mountSemesters()
    await flushPromises()

    expect(wrapper.get('[data-testid="semesters-error"]').text()).toContain('模板服务暂时不可用')
    await wrapper.get('[data-testid="semesters-retry"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="semesters-error"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('尚未创建任何学期')
  })

  it('删除学期进行中时重复确认只发送一次请求', async () => {
    const deletion = deferred<void>()
    mocks.listSemesters.mockResolvedValue([semester])
    mocks.getSemester.mockResolvedValue(semester)
    mocks.deleteSemester.mockReturnValue(deletion.promise)

    const wrapper = await mountSemesters({
      stubs: {
        Popconfirm: {
          emits: ['positive-click'],
          template: '<span><slot name="trigger" /><button data-testid="confirm-semester-delete-1" @click="$emit(\'positive-click\')">确认</button></span>',
        },
      },
    })
    await flushPromises()

    const confirm = wrapper.get('[data-testid="confirm-semester-delete-1"]')
    await confirm.trigger('click')
    await confirm.trigger('click')

    expect(mocks.deleteSemester).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="semester-delete-1"]').attributes('disabled')).toBeDefined()

    deletion.resolve()
    await flushPromises()
  })

  it('复制学期对话框保留排课偏好设置的兼容选择器', async () => {
    mocks.listSemesters.mockResolvedValue([semester])
    mocks.getSemester.mockResolvedValue(semester)

    const wrapper = await mountSemesters({
      stubs: {
        Modal: {
          props: ['show'],
          template: '<div v-if="show"><slot /></div>',
        },
      },
    })
    await flushPromises()

    await wrapper.get('[data-testid="copy-semester"]').trigger('click')
    await flushPromises()

    const preference = wrapper.get('[data-testid="copy-config"]')
    expect(preference.text()).toContain('排课偏好设置')
    expect(preference.attributes('role')).toBe('checkbox')
    expect(preference.attributes('aria-checked')).toBe('true')
  })
})
