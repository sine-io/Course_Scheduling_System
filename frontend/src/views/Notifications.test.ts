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

async function mountNotifications() {
  const fetchMock = vi.fn((input: string | URL | Request) => {
    const url = String(input)
    let body: unknown = {}
    if (url.includes('/semester-context')) {
      body = {
        current_semester_id: 1,
        current_semester: { id: 1, label: '2026-2027学年第一学期', is_demo: false },
        semesters: [{ id: 1, label: '2026-2027学年第一学期', is_demo: false }],
        can_switch: false,
        revision: 1,
      }
    } else if (url.includes('/notifications/mine?')) {
      body = { items: [{ ...notification }], unread: 1 }
    } else if (url.includes('/notifications/9/read')) {
      body = { ...notification, read_at: '2026-08-15T09:00:00Z' }
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
    roles: ['teacher'],
    must_change_password: false,
  }
  auth.loaded = true
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/notifications', name: 'notifications', component: Notifications },
      { path: '/timetable-query', name: 'timetable-query', component: { template: '<main />' } },
    ],
  })
  await router.push('/notifications')
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
})
