import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { useAuthStore } from '@/stores/auth'
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

    await router.push('/wizard')
    expect(router.currentRoute.value.name).toBe('wizard')

    await router.push('/settings/system')
    expect(router.currentRoute.value.name).toBe('dashboard')
  })
})
