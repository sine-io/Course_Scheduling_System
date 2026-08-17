import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import { useWizardStore } from '@/stores/wizard'
import { router } from './index'

describe('router role boundaries', () => {
  it('allows a director to inspect the wizard but redirects them away from system settings', async () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 1,
      username: 'director',
      display_name: '教务主任',
      roles: ['director'],
      must_change_password: false,
    }
    auth.loaded = true
    useWizardStore().loaded = true

    await router.push('/wizard')
    expect(router.currentRoute.value.name).toBe('wizard')

    await router.push('/settings/system')
    expect(router.currentRoute.value.name).toBe('dashboard')

    await router.push('/scheduling/auto')
    expect(router.currentRoute.value.name).toBe('auto-schedule')
  })

  it('keeps pure teachers on personal daily pages and blocks management links', async () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 2,
      username: 'teacher',
      display_name: '教师',
      roles: ['teacher'],
      must_change_password: false,
    }
    auth.loaded = true
    useWizardStore().loaded = true

    await router.push('/')
    expect(router.currentRoute.value.name).toBe('dashboard')
    await router.push('/daily-board')
    expect(router.currentRoute.value.name).toBe('timetable-query')
    await router.push('/notification-board')
    expect(router.currentRoute.value.name).toBe('notifications')
    expect(router.currentRoute.value.query.view).toBe('board')
    await router.push('/leaves')
    expect(router.currentRoute.value.name).toBe('leaves')
    await router.push('/notifications')
    expect(router.currentRoute.value.name).toBe('notifications')
    await router.push('/substitution-stats')
    expect(router.currentRoute.value.name).toBe('substitution-stats')
    await router.push('/scheduling/workbench')
    expect(router.currentRoute.value.name).toBe('timetable-query')
  })

  it('keeps a scheduler-teacher union in the daily management view', async () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 3,
      username: 'scheduler-teacher',
      display_name: '兼任教师',
      roles: ['scheduler', 'teacher'],
      must_change_password: false,
    }
    auth.loaded = true
    useWizardStore().loaded = true

    await router.push('/substitutions')
    expect(router.currentRoute.value.name).toBe('substitutions')
    await router.push('/leaves')
    expect(router.currentRoute.value.name).toBe('leaves')
  })

  it('respects an explicit save-and-exit pause without marking setup complete', async () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 5,
      username: 'scheduler',
      display_name: '排课管理员',
      roles: ['scheduler'],
      must_change_password: false,
    }
    auth.loaded = true
    const wizard = useWizardStore()
    wizard.loaded = true
    wizard.state = {
      current_step: 1,
      completed: false,
      paused: true,
      semester_id: 8,
      total_steps: 4,
      has_semesters: true,
    }

    await router.push('/')

    expect(router.currentRoute.value.name).toBe('dashboard')
  })

  it('redirects legacy notification, demo, and system section links to their replacements', async () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 4,
      username: 'admin',
      display_name: '系统管理员',
      roles: ['admin'],
      must_change_password: false,
    }
    auth.loaded = true
    useWizardStore().loaded = true

    await router.push('/notification-board')
    expect(router.currentRoute.value.name).toBe('notifications')
    expect(router.currentRoute.value.query.view).toBe('board')

    await router.push('/scheduling/timetable-demo')
    expect(router.currentRoute.value.name).toBe('workbench')

    await router.push('/settings/system?section=backup')
    expect(router.currentRoute.value.name).toBe('backup')
    await router.push('/settings/system?section=accounts')
    expect(router.currentRoute.value.name).toBe('account-permissions')
  })
})
