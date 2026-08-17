import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Notifications from './Notifications.vue'

const notification = {
  id: 9,
  type: 'timetable_published',
  title: '新课表已发布',
  body: '请查看本周课表。',
  link: '/timetable-query',
  created_at: '2026-08-15T08:00:00Z',
  read_at: null,
  acknowledged_at: null,
}
const boardEntry = {
  id: 11,
  type: 'substitution_assigned',
  title: '王老师请假，由陈老师代课',
  teacher_id: 7,
  teacher_name: '陈老师',
  created_at: '2026-08-15T08:00:00Z',
  read_at: null,
  acknowledged_at: null,
}

async function mountNotifications(role = 'teacher', path = '/notifications') {
  const fetchMock = vi.fn((input: string | URL | Request) => {
    const url = String(input)
    let body: unknown = {}
    if (url.includes('/semester-context')) {
      body = {
        current_semester_id: 1,
        current_semester: { id: 1, label: '2026-2027学年第一学期' },
        semesters: [{ id: 1, label: '2026-2027学年第一学期' }],
        can_switch: false,
        revision: 1,
      }
    } else if (url.includes('/notifications/mine?')) {
      body = { items: [{ ...notification }], unread: 1 }
    } else if (url.includes('/notifications/9/read')) {
      body = { ...notification, read_at: '2026-08-15T09:00:00Z' }
    } else if (url.includes('/notifications?semester_id=')) {
      body = [boardEntry]
    } else if (url.includes('/notifications/11/remind')) {
      body = { ...boardEntry }
    } else if (url.includes('/semesters')) {
      body = [{ id: 1, label: '2026-2027学年第一学期' }]
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) })
  })
  vi.stubGlobal('fetch', fetchMock)

  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  auth.user = {
    id: 2,
    username: 'teacher',
    display_name: '陈老师',
    roles: [role],
    must_change_password: false,
  }
  auth.loaded = true
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'dashboard', component: { template: '<main />' } },
      { path: '/notifications', name: 'notifications', component: Notifications },
      { path: '/timetable-query', name: 'timetable-query', component: { template: '<main />' } },
    ],
  })
  await router.push(path)
  await router.isReady()
  const Host = { render: () => h(NMessageProvider, () => h(Notifications)) }
  const wrapper = mount(Host, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { fetchMock, wrapper }
}

describe('Notifications', () => {
  it('marks an unread notification only through a reachable command', async () => {
    const { fetchMock, wrapper } = await mountNotifications()
    const card = wrapper.get('[data-testid="notification-9"]')

    await card.trigger('mouseenter')
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining('/notifications/9/read'),
      expect.anything(),
    )

    await wrapper.get('[data-testid="notification-read-9"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/notifications/9/read'),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(wrapper.find('[data-testid="notification-read-9"]').exists()).toBe(false)
  })

  it('shows the confirmation board as an operator-only view on the same page', async () => {
    const { fetchMock, wrapper } = await mountNotifications('scheduler', '/notifications?view=board')

    expect(wrapper.find('[data-testid="notifications-tab-board"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="notification-board-page"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="board-row"]').text()).toContain('陈老师')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/notifications?semester_id=1&unacknowledged_only=true'),
      expect.anything(),
    )

    await wrapper.get('[data-testid="board-remind"]').trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/notifications/11/remind'),
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('keeps a board query on the personal notification view for teachers', async () => {
    const { fetchMock, wrapper } = await mountNotifications('teacher', '/notifications?view=board')

    expect(wrapper.find('[data-testid="notifications-tab-board"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="notification-9"]').exists()).toBe(true)
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/notifications?semester_id='))).toBe(false)
  })
})
