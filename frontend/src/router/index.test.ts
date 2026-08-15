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

    await router.push('/daily-board')
    expect(router.currentRoute.value.name).toBe('timetable-query')
    await router.push('/notification-board')
    expect(router.currentRoute.value.name).toBe('timetable-query')
    await router.push('/leaves')
    expect(router.currentRoute.value.name).toBe('leaves')
    await router.push('/substitution-stats')
    expect(router.currentRoute.value.name).toBe('substitution-stats')
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
})
