import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppConfigStore } from '@/stores/appConfig'
import MainLayout from './MainLayout.vue'

const scheduler = {
  id: 1,
  username: 'scheduler',
  display_name: '张教务',
  roles: ['scheduler'],
  must_change_password: false,
}

const admin = {
  id: 3,
  username: 'admin',
  display_name: '系统管理员',
  roles: ['admin'],
  must_change_password: false,
}

const director = {
  id: 4,
  username: 'director',
  display_name: '教务主任',
  roles: ['director'],
  must_change_password: false,
}

const teacher = {
  id: 2,
  username: 'teacher',
  display_name: '陈老师',
  roles: ['teacher'],
  must_change_password: false,
}

const mounted: VueWrapper[] = []

afterEach(() => {
  for (const wrapper of mounted.splice(0)) wrapper.unmount()
})

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/',
        name: 'dashboard',
        component: { template: '<main data-testid="page">仪表盘内容</main>' },
      },
      { path: '/wizard', name: 'wizard', component: { template: '<main />' } },
      { path: '/timetable-query', name: 'timetable-query', component: { template: '<main />' } },
      { path: '/notifications', name: 'notifications', component: { template: '<main />' } },
      { path: '/leaves', name: 'leaves', component: { template: '<main />' } },
      { path: '/substitution-stats', name: 'substitution-stats', component: { template: '<main />' } },
      { path: '/settings/semesters', name: 'semesters', component: { template: '<main />' } },
      { path: '/settings/calendar', name: 'calendar', component: { template: '<main />' } },
      { path: '/basedata', name: 'basedata', component: { template: '<main />' } },
      { path: '/scheduling/assignments', name: 'assignments', component: { template: '<main />' } },
      { path: '/scheduling/workbench', name: 'workbench', component: { template: '<main />' } },
      { path: '/scheduling/auto', name: 'auto-schedule', component: { template: '<main />' } },
      { path: '/scheduling/versions', name: 'versions', component: { template: '<main />' } },
      { path: '/scheduling/timetable-demo', name: 'timetable-demo', component: { template: '<main />' } },
      { path: '/substitutions', name: 'substitutions', component: { template: '<main />' } },
      { path: '/daily-board', name: 'daily-board', component: { template: '<main />' } },
      { path: '/substitution-log', name: 'substitution-log', component: { template: '<main />' } },
      { path: '/notification-board', name: 'notification-board', component: { template: '<main />' } },
      { path: '/settings/system', name: 'system', component: { template: '<main />' } },
    ],
  })
}

async function mountLayout(user: typeof scheduler | typeof teacher) {
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  auth.user = user
  auth.loaded = true
  useAppConfigStore(pinia).config.role_display_names = {
    admin: '系统管理员',
    director: '教务主任',
    scheduler: '排课管理员',
    teacher: '教师',
  }

  const router = makeRouter()
  await router.push('/')
  await router.isReady()
  const wrapper = mount(MainLayout, {
    attachTo: document.body,
    global: {
      plugins: [pinia, router],
      stubs: {
        NotificationBell: {
          template: '<button type="button" aria-label="通知" data-testid="notification-stub">通知</button>',
        },
      },
    },
  })
  mounted.push(wrapper)
  await flushPromises()
  return { wrapper, router }
}

describe('MainLayout', () => {
  it('exposes the real product shell and filters navigation by role', async () => {
    const { wrapper } = await mountLayout(scheduler)

    expect(wrapper.find('[data-testid="app-shell"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="product-identity"]').text()).toContain('教务排课')
    expect(wrapper.get('[data-testid="shell-breadcrumb"]').text()).toContain('仪表盘')
    expect(wrapper.get('[data-testid="shell-nav"]').text()).toContain('排课工作台')
    expect(wrapper.get('[data-testid="shell-nav"]').text()).not.toContain('系统管理')
    expect(wrapper.get('.app-nav-common').text()).not.toContain('当前待办')
    expect(wrapper.get('.app-nav-common').text()).toContain('教学任务')
    expect(wrapper.findAll('.app-nav-common a')).toHaveLength(4)
    expect(wrapper.get('[data-testid="shell-school-context"]').text()).toContain('示范学校')
    expect(wrapper.get('[data-testid="shell-help"]').attributes('href')).toBe('/docs/index.html')
    expect(wrapper.get('[data-testid="shell-logout"]').text()).toContain('退出登录')
    expect(wrapper.find('input[placeholder*="搜索"]').exists()).toBe(false)

    const adminLayout = await mountLayout(admin)
    expect(adminLayout.wrapper.get('[data-testid="shell-nav"]').text()).toContain('系统管理')

    const directorLayout = await mountLayout(director)
    const directorNav = directorLayout.wrapper.get('[data-testid="shell-nav"]').text()
    expect(directorNav).toContain('版本与发布')
    expect(directorNav).not.toContain('系统管理')

    const teacherLayout = await mountLayout(teacher)
    const teacherNav = teacherLayout.wrapper.get('[data-testid="shell-nav"]').text()
    expect(teacherNav).toContain('课表查询')
    expect(teacherNav).toContain('请假登记')
    expect(teacherNav).toContain('我的代课课时')
    expect(teacherNav).not.toContain('排课工作台')
    expect(teacherNav).not.toContain('系统管理')
    expect(teacherLayout.wrapper.get('.app-nav-common').text()).toContain('通知')
    expect(teacherLayout.wrapper.get('.app-nav-common').text()).toContain('我的代课课时')
  })

  it('opens the mobile drawer, moves focus into it, and restores focus on escape', async () => {
    const { wrapper } = await mountLayout(scheduler)
    const menu = wrapper.get('[data-testid="shell-menu"]')

    expect(menu.attributes('aria-expanded')).toBe('false')
    await menu.trigger('click')
    await new Promise((resolve) => window.setTimeout(resolve, 50))
    await flushPromises()

    expect(menu.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('[data-testid="mobile-drawer"]').classes()).toContain('is-open')
    expect(document.activeElement).toBe(wrapper.get('[data-testid="shell-close"]').element)

    await wrapper.get('[data-testid="mobile-drawer"]').trigger('keydown', { key: 'Escape' })
    await flushPromises()
    expect(menu.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(menu.element)

    await menu.trigger('click')
    await wrapper.get('[data-testid="shell-scrim"]').trigger('click')
    expect(menu.attributes('aria-expanded')).toBe('false')
  })
})
