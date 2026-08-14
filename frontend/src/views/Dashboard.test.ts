import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { OnboardingStatus } from '@/api/onboarding'
import Dashboard from './Dashboard.vue'

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function makeRouter() {
  return createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'dashboard', component: Dashboard },
        { path: '/wizard', name: 'wizard', component: { template: '<div />' } },
        { path: '/scheduling/workbench', name: 'workbench', component: { template: '<div />' } },
        { path: '/scheduling/assignments', name: 'assignments', component: { template: '<div />' } },
        { path: '/settings/semesters', name: 'settings-semesters', component: { template: '<div />' } },
        { path: '/settings/calendar', name: 'settings-calendar', component: { template: '<div />' } },
        { path: '/basedata', name: 'basedata', component: { template: '<div />' } },
        { path: '/scheduling/versions', name: 'versions', component: { template: '<div />' } },
        { path: '/daily-board', name: 'daily-board', component: { template: '<div />' } },
      ],
  })
}

describe('Dashboard', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse([]))))
  })

  it('读取学期期间显示可理解的加载状态', async () => {
    const request = deferred<ReturnType<typeof jsonResponse>>()
    vi.stubGlobal('fetch', vi.fn(() => request.promise))

    const wrapper = mount(Dashboard, {
      global: { plugins: [createPinia(), makeRouter()] },
    })
    await nextTick()

    expect(wrapper.text()).toContain('正在读取仪表盘数据')

    request.resolve(jsonResponse([]))
    await flushPromises()
  })

  it('无学期时显示空状态与前往向导', async () => {
    const wrapper = mount(Dashboard, {
      global: { plugins: [createPinia(), makeRouter()] },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('仪表盘')
    expect(wrapper.text()).toContain('尚未创建任何学期数据')
    expect(wrapper.get('a[href="/wizard"]').text()).toContain('前往设置向导')
  })

  it('显示当前学期的真实摘要、今日变动和可用快捷入口', async () => {
    const semesters = [
      {
        id: 9, academic_year: 2042, term: 2, label: '2042-2043学年第二学期',
        status: 'archived', readiness: 'ready', start_date: null, end_date: null,
      },
      {
        id: 8, academic_year: 2042, term: 1, label: '2042-2043学年第一学期',
        status: 'active', readiness: 'ready', start_date: null, end_date: null,
      },
    ]
    const board = {
      date: '2042-09-02', weekday: 2, school_name: '测试学校',
      semester_label: semesters[1].label,
      entries: [
        {
          affected_period_id: 101, date: '2042-09-02', weekday: 2, period_no: 1,
          period_name: '第一节', start_time: '08:00:00', end_time: '08:40:00',
          class_names: '七年级 1 班', subject_name: '数学', room_name: '101',
          absent_teacher_id: 11, absent_teacher_name: '李老师', leave_type: 'sick',
          leave_type_label: '病假', status: 'pending', status_label: '待安排', disposed: false,
          sub_type: null, sub_type_label: null, handler_teacher_id: null, handler_name: null,
          counts_toward_hours: null, swap_date: null, swap_period_name: '',
          swap_class_names: '', swap_subject_name: '', note: '',
        },
        {
          affected_period_id: 102, date: '2042-09-02', weekday: 2, period_no: 2,
          period_name: '第二节', start_time: '08:50:00', end_time: '09:30:00',
          class_names: '七年级 2 班', subject_name: '语文', room_name: '102',
          absent_teacher_id: 12, absent_teacher_name: '王老师', leave_type: 'personal',
          leave_type_label: '事假', status: 'disposed', status_label: '已安排', disposed: true,
          sub_type: 'substitute', sub_type_label: '代课', handler_teacher_id: 13,
          handler_name: '赵老师', counts_toward_hours: true, swap_date: null,
          swap_period_name: '', swap_class_names: '', swap_subject_name: '', note: '',
        },
      ],
    }
    vi.mocked(fetch).mockImplementation((url) => {
      if (String(url).endsWith('/semesters')) return Promise.resolve(jsonResponse(semesters)) as never
      if (String(url).includes('/summary')) {
        return Promise.resolve(jsonResponse({ subjects: 12, teachers: 34, classes: 18, rooms: 7 })) as never
      }
      return Promise.resolve(jsonResponse(board)) as never
    })

    const wrapper = mount(Dashboard, {
      global: { plugins: [createPinia(), makeRouter()] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('2042-2043学年第一学期 · 数据摘要')
    expect(wrapper.text()).toContain('12')
    expect(wrapper.text()).toContain('34')
    expect(wrapper.text()).toContain('18')
    expect(wrapper.text()).toContain('7')
    expect(wrapper.get('[data-testid="dash-entry-101"]').text()).toContain('七年级 1 班')
    expect(wrapper.get('[data-testid="dash-entry-101"]').text()).toContain('数学')
    expect(wrapper.text()).toContain('尚有 1 节待安排')
    expect(wrapper.get('a[href="/scheduling/workbench"]')).toBeTruthy()
    expect(wrapper.get('a[href="/scheduling/assignments"]')).toBeTruthy()
    expect(wrapper.get('a[href="/daily-board"]')).toBeTruthy()
  })

  it('显示首次成功状态、阻塞原因和下一步直达入口', async () => {
    const semesters = [{
      id: 8, academic_year: 2042, term: 1, label: '2042-2043学年第一学期',
      status: 'active', readiness: 'draft', start_date: null, end_date: null,
      is_demo: false, is_current: true,
    }]
    const blockedStage = {
      key: 'periods', label: '作息', complete: false as const, status: 'blocked' as const,
      blocking_reason: '请先创建作息时间表。',
      next_action: {
        stage: 'periods', label: '管理学期与作息时间表', href: '/settings/semesters',
        blocking_reason: '请先创建作息时间表。',
      }, details: {},
    }
    const onboarding: OnboardingStatus = {
      first_success: false,
      wizard_completed: true,
      current_semester: { id: 8, label: semesters[0].label, is_demo: false },
      stages: [
        {
          key: 'semester', label: '学期', complete: true, status: 'complete',
          blocking_reason: '', next_action: null, details: {},
        },
        blockedStage,
      ],
      p0_todos: [blockedStage],
      next_action: {
        stage: 'periods', label: '管理学期与作息时间表', href: '/settings/semesters',
        blocking_reason: '请先创建作息时间表。',
      },
    }
    const board = {
      date: '2042-09-02', weekday: 2, school_name: '测试学校',
      semester_label: semesters[0].label, entries: [],
    }
    vi.mocked(fetch).mockImplementation((url) => {
      const address = String(url)
      if (address.endsWith('/semesters')) return Promise.resolve(jsonResponse(semesters)) as never
      if (address.includes('/onboarding/status')) return Promise.resolve(jsonResponse(onboarding)) as never
      if (address.includes('/summary')) {
        return Promise.resolve(jsonResponse({ subjects: 1, teachers: 2, classes: 3, rooms: 4 })) as never
      }
      return Promise.resolve(jsonResponse(board)) as never
    })

    const wrapper = mount(Dashboard, {
      global: { plugins: [createPinia(), makeRouter()] },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="onboarding-status"]').text()).toContain('首次成功路径')
    expect(wrapper.get('[data-testid="onboarding-stage-periods"]').text()).toContain('请先创建作息时间表')
    expect(wrapper.get('[data-testid="onboarding-next-action"]').attributes('href')).toBe('/settings/semesters')
  })

  it('并发读取学期摘要与今日看板', async () => {
    const summaryRequest = deferred<ReturnType<typeof jsonResponse>>()
    const board = {
      date: '2042-09-02', weekday: 2, school_name: '测试学校',
      semester_label: '2042-2043学年第一学期', entries: [],
    }
    vi.mocked(fetch).mockImplementation((url) => {
      if (String(url).endsWith('/semesters')) {
        return Promise.resolve(jsonResponse([{
          id: 8, academic_year: 2042, term: 1, label: '2042-2043学年第一学期',
          status: 'active', readiness: 'ready', start_date: null, end_date: null,
        }])) as never
      }
      if (String(url).includes('/summary')) return summaryRequest.promise as never
      return Promise.resolve(jsonResponse(board)) as never
    })

    mount(Dashboard, {
      global: { plugins: [createPinia(), makeRouter()] },
    })
    await flushPromises()

    expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('/daily-board'))).toBe(true)
    summaryRequest.resolve(jsonResponse({ subjects: 1, teachers: 2, classes: 3, rooms: 4 }))
    await flushPromises()
  })

  it('摘要请求失败时保留今日看板和快捷入口并显示局部重试', async () => {
    let summaryAttempts = 0
    const board = {
      date: '2042-09-02', weekday: 2, school_name: '测试学校',
      semester_label: '2042-2043学年第一学期', entries: [],
    }
    vi.mocked(fetch).mockImplementation((url) => {
      if (String(url).endsWith('/semesters')) {
        return Promise.resolve(jsonResponse([{
          id: 1, academic_year: 2042, term: 1, label: '2042-2043学年第一学期',
          status: 'active', readiness: 'draft', start_date: null, end_date: null,
        }])) as never
      }
      if (String(url).includes('/summary')) {
        summaryAttempts += 1
        if (summaryAttempts > 1) {
          return Promise.resolve(jsonResponse({ subjects: 12, teachers: 34, classes: 18, rooms: 7 })) as never
        }
        return Promise.resolve(jsonResponse({ detail: '摘要服务暂时不可用' }, 503)) as never
      }
      return Promise.resolve(jsonResponse(board)) as never
    })

    const wrapper = mount(Dashboard, {
      global: { plugins: [createPinia(), makeRouter()] },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="dash-error"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="dash-summary-error"]').text()).toContain('无法读取学期摘要')
    expect(wrapper.get('[data-testid="dash-summary-retry"]').text()).toContain('重新读取摘要')
    expect(wrapper.get('[data-testid="dash-today"]').text()).toContain('今日无调课与代课')
    expect(wrapper.get('[data-testid="dash-shortcut-workbench"]')).toBeTruthy()

    await wrapper.get('[data-testid="dash-summary-retry"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="dash-summary"]').text()).toContain('12')
    expect(wrapper.find('[data-testid="dash-summary-error"]').exists()).toBe(false)
  })

  it('今日看板请求失败时保留摘要并显示局部错误', async () => {
    vi.mocked(fetch).mockImplementation((url) => {
      if (String(url).endsWith('/semesters')) {
        return Promise.resolve(jsonResponse([{
          id: 1, academic_year: 2042, term: 1, label: '2042-2043学年第一学期',
          status: 'active', readiness: 'ready', start_date: null, end_date: null,
        }])) as never
      }
      if (String(url).includes('/summary')) {
        return Promise.resolve(jsonResponse({ subjects: 1, teachers: 2, classes: 3, rooms: 4 })) as never
      }
      return Promise.resolve(jsonResponse({ detail: '看板暂时不可用' }, 503)) as never
    })

    const wrapper = mount(Dashboard, {
      global: { plugins: [createPinia(), makeRouter()] },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="dash-summary"]').text()).toContain('1')
    expect(wrapper.get('[data-testid="dash-board-error"]').text()).toContain('无法读取今日调课与代课')
  })
})
