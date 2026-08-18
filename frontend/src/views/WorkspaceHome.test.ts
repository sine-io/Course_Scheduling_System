import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { WorkspaceOverview } from '@/api/workspaceOverview'
import { useAuthStore } from '@/stores/auth'
import WorkspaceHome from './WorkspaceHome.vue'

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  }
}

const semester = {
  id: 8,
  academic_year: 2026,
  term: 1,
  label: '2026-2027学年第一学期',
  status: 'preparing',
  readiness: 'ready',
  start_date: '2026-08-01',
  end_date: '2027-01-20',
  is_current: true,
}

const overview: WorkspaceOverview = {
  semester_id: 8,
  semester_label: semester.label,
  generated_at: '2026-08-17T06:30:00+00:00',
  metrics: {
    active_teacher_count: 56,
    class_count: 18,
    weekly_affected_periods: 7,
    week_start: '2026-08-17',
    week_end: '2026-08-23',
  },
  timetable: {
    id: 21,
    name: '开学课表草稿',
    status: 'draft',
    updated_at: '2026-08-17T05:00:00+00:00',
    required_periods: 600,
    placed_periods: 450,
    remaining_periods: 150,
    completion_rate: 75,
  },
  preflight: {
    available: true,
    error_count: 2,
    warning_count: 3,
    unavailable_message: '',
  },
  today_pending_periods: 2,
  unacknowledged_notifications: 4,
  focus_items: [
    {
      code: 'today_pending_periods',
      title: '处理今日调代课',
      description: '今日仍有受影响节次尚未设置处理方式。',
      tone: 'warning',
      target: 'substitutions',
      count: 2,
    },
    {
      code: 'remaining_periods',
      title: '继续完成课表',
      description: '课表仍有课时尚未排入。',
      tone: 'warning',
      target: 'workbench',
      count: 150,
    },
  ],
  recommendations: [
    {
      code: 'setup_warning:rooms_missing',
      title: '补充教室与场地',
      description: '尚未录入教室/场地，可稍后补充。',
      tone: 'warning',
      target: 'basedata',
      count: null,
    },
  ],
}

function makeRouter() {
  const page = { template: '<main />' }
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'dashboard', component: page },
      { path: '/wizard', name: 'wizard', component: page },
      { path: '/basedata', name: 'basedata', component: page },
      { path: '/settings/calendar', name: 'calendar', component: page },
      { path: '/settings/semesters', name: 'semesters', component: page },
      { path: '/scheduling/assignments', name: 'assignments', component: page },
      { path: '/scheduling/auto', name: 'auto-schedule', component: page },
      { path: '/scheduling/workbench', name: 'workbench', component: page },
      { path: '/scheduling/versions', name: 'versions', component: page },
      { path: '/timetable-query', name: 'timetable-query', component: page },
      { path: '/substitutions', name: 'substitutions', component: page },
      { path: '/daily-board', name: 'daily-board', component: page },
      { path: '/substitution-stats', name: 'substitution-stats', component: page },
      { path: '/notifications', name: 'notifications', component: page },
    ],
  })
}

function makePinia(roles: string[]) {
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  auth.user = {
    id: 1,
    username: 'test-user',
    display_name: roles.includes('director') ? '林主任' : '张老师',
    roles,
    must_change_password: false,
  }
  auth.loaded = true
  return pinia
}

async function mountPage(roles: string[] = ['scheduler']) {
  const router = makeRouter()
  await router.push('/')
  await router.isReady()
  const wrapper = mount(WorkspaceHome, {
    global: { plugins: [makePinia(roles), router] },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn((url) => {
    const path = String(url)
    if (path.includes('/semester-context')) {
      return Promise.resolve(jsonResponse({
        current_semester: semester,
        revision: 3,
        can_switch: false,
      }))
    }
    if (path.includes('/workspace-overview')) {
      return Promise.resolve(jsonResponse(overview))
    }
    return Promise.resolve(jsonResponse([]))
  }))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('WorkspaceHome', () => {
  it('renders real metrics, scheduler features, and actionable overview links', async () => {
    const wrapper = await mountPage()

    expect(wrapper.get('h1').text()).toBe('首页总览')
    expect(wrapper.get('[data-testid="overview-hero"]').text()).toContain('下午好，张老师')
    expect(wrapper.findAll('.workspace-metric')).toHaveLength(6)
    expect(wrapper.get('[data-testid="overview-metric-completion"]').text()).toContain('75%')
    expect(wrapper.get('[data-testid="overview-metric-preflight"]').text()).toContain('5')
    expect(wrapper.findAll('.workspace-metric a')).toHaveLength(0)
    expect(wrapper.findAll('.workspace-metric button')).toHaveLength(0)

    expect(wrapper.findAll('.workspace-feature-link')).toHaveLength(5)
    expect(wrapper.get('[data-testid="overview-feature-assignments"]').attributes('href'))
      .toBe('/scheduling/assignments')
    expect(wrapper.get('[data-testid="overview-feature-auto-schedule"]').attributes('href'))
      .toBe('/scheduling/auto')
    expect(wrapper.find('[data-testid="overview-feature-timetable-query"]').exists()).toBe(false)
    expect(wrapper.get('.workspace-focus-item').attributes('href')).toBe('/substitutions')
    expect(wrapper.get('.workspace-recommendation').attributes('href')).toBe('/basedata')
    expect(wrapper.text()).not.toContain('AI 今日摘要')
    expect(wrapper.text()).not.toContain('让 AI 帮我处理')
  })

  it('shows the director feature set without edit-first scheduling entries', async () => {
    const wrapper = await mountPage(['director'])

    expect(wrapper.get('[data-testid="overview-feature-timetable-query"]').attributes('href'))
      .toBe('/timetable-query')
    expect(wrapper.get('[data-testid="overview-feature-substitution-stats"]').attributes('href'))
      .toBe('/substitution-stats')
    expect(wrapper.get('[data-testid="overview-feature-notifications"]').attributes('href'))
      .toContain('/notifications?view=board')
    expect(wrapper.find('[data-testid="overview-feature-assignments"]').exists()).toBe(false)
    expect(wrapper.findAll('.workspace-feature-link')).toHaveLength(5)
  })

  it('scrolls to focus items and refreshes the aggregate on demand', async () => {
    const wrapper = await mountPage()
    const scrollIntoView = vi.fn()
    wrapper.get('[data-testid="overview-focus"]').element.scrollIntoView = scrollIntoView

    await wrapper.get('[data-testid="overview-focus-button"]').trigger('click')
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })

    await wrapper.get('[data-testid="overview-refresh"]').trigger('click')
    await flushPromises()
    const overviewRequests = vi.mocked(fetch).mock.calls
      .filter(([url]) => String(url).includes('/workspace-overview'))
    expect(overviewRequests).toHaveLength(2)
  })

  it('renders positive states instead of filler when there is no work', async () => {
    const emptyOverview: WorkspaceOverview = {
      ...overview,
      timetable: {
        ...overview.timetable,
        required_periods: 0,
        placed_periods: 0,
        remaining_periods: 0,
        completion_rate: null,
      },
      preflight: {
        available: false,
        error_count: 0,
        warning_count: 0,
        unavailable_message: '排课前置检查暂时无法读取',
      },
      focus_items: [],
      recommendations: [],
    }
    vi.mocked(fetch).mockImplementation((url) => {
      if (String(url).includes('/semester-context')) {
        return Promise.resolve(jsonResponse({
          current_semester: semester,
          revision: 3,
          can_switch: false,
        })) as never
      }
      return Promise.resolve(jsonResponse(emptyOverview)) as never
    })

    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('当前没有重点事项')
    expect(wrapper.text()).toContain('当前没有运行建议')
    expect(wrapper.get('[data-testid="overview-metric-completion"]').text()).toContain('--')
    expect(wrapper.get('[data-testid="overview-metric-preflight"]').text()).toContain('暂时无法读取')
    expect(wrapper.find('[data-testid="overview-focus-button"]').exists()).toBe(false)
  })

  it('links administrators to setup when no current semester exists', async () => {
    vi.mocked(fetch).mockImplementation((url) => {
      if (String(url).includes('/semester-context')) {
        return Promise.resolve(jsonResponse({
          current_semester: null,
          revision: 0,
          can_switch: true,
        })) as never
      }
      return Promise.resolve(jsonResponse([])) as never
    })

    const wrapper = await mountPage(['admin'])

    expect(wrapper.get('[data-testid="overview-no-semester"]').text()).toContain('尚未建立当前工作学期')
    expect(wrapper.get('a[href="/wizard"]').text()).toContain('前往设置向导')
    expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('/workspace-overview')))
      .toBe(false)
  })

  it('gives directors an explanation without a setup action when no semester exists', async () => {
    vi.mocked(fetch).mockImplementation((url) => {
      if (String(url).includes('/semester-context')) {
        return Promise.resolve(jsonResponse({
          current_semester: null,
          revision: 0,
          can_switch: false,
        })) as never
      }
      return Promise.resolve(jsonResponse([])) as never
    })

    const wrapper = await mountPage(['director'])

    expect(wrapper.get('[data-testid="overview-no-semester"]').text()).toContain('联系排课管理员')
    expect(wrapper.find('a[href="/wizard"]').exists()).toBe(false)
  })
})
