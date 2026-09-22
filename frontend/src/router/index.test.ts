import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import { router } from './index'

describe('router role boundaries', () => {
  it('does not register the removed workspace home route', () => {
    expect(router.resolve('/workspace/home').matched).toHaveLength(0)
  })

  it('allows a pure teacher who must change their password to reach the change-password page', async () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 6,
      username: 'new-teacher',
      display_name: '新教师',
      roles: ['teacher'],
      must_change_password: true,
    }
    auth.loaded = true

    await router.push('/change-password')

    expect(router.currentRoute.value.name).toBe('change-password')
  })

  it('allows a director to use core pages but redirects them away from system settings', async () => {
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
    await router.push('/settings/system')
    expect(router.currentRoute.value.name).toBe('dashboard')

    await router.push('/scheduling/auto')
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toEqual({ step: 'start' })
  }, 10_000)

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

  it('keeps a director-teacher union in the daily management view', async () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 3,
      username: 'director-teacher',
      display_name: '兼任教师',
      roles: ['director', 'teacher'],
      must_change_password: false,
    }
    auth.loaded = true

    await router.push('/substitutions')
    expect(router.currentRoute.value.name).toBe('substitutions')
    await router.push('/leaves')
    expect(router.currentRoute.value.name).toBe('leaves')
  })

  it('does not force a director away from the dashboard when setup is incomplete', async () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 5,
      username: 'director',
      display_name: '教务主任',
      roles: ['director'],
      must_change_password: false,
    }
    auth.loaded = true
    await router.push('/')

    expect(router.currentRoute.value.name).toBe('dashboard')
  })

  it('redirects legacy and duplicated links to their replacements without losing context', async () => {
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

    await router.push('/notification-board')
    expect(router.currentRoute.value.name).toBe('notifications')
    expect(router.currentRoute.value.query.view).toBe('board')

    await router.push('/scheduling/timetable-demo')
    expect(router.currentRoute.value.name).toBe('workbench')

    await router.push('/settings/system?section=backup')
    expect(router.currentRoute.value.name).toBe('backup')
    await router.push('/settings/system?section=accounts')
    expect(router.currentRoute.value.name).toBe('account-permissions')

    await router.push('/basedata?tab=classes&semester=8')
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toEqual({ step: 'classes', semester: '8' })

    await router.push('/basedata?tab=classes&semester=invalid')
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toEqual({ step: 'classes' })

    await router.push('/basedata?tab=subjects&semester=8')
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toEqual({ step: 'subjects', view: 'archive', semester: '8' })

    await router.push('/basedata?tab=teachers&semester=8')
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toEqual({ step: 'teachers', view: 'archive', semester: '8' })

    await router.push('/basedata?tab=rooms&semester=8')
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toEqual({ panel: 'resources', resource: 'rooms', semester: '8' })

    await router.push('/basedata?tab=template&semester=8')
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toEqual({ panel: 'resources', resource: 'template', semester: '8' })

    await router.push('/settings/semesters?semester=8')
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toEqual({ panel: 'semester', semester: '8' })

    await router.push('/settings/calendar?semester=8')
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toEqual({ panel: 'calendar', semester: '8' })

    await router.push('/scheduling/assignments?mode=teachers&semester_id=9')
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toEqual({ step: 'teachers', semester: '9' })

    await router.push('/scheduling/assignments?mode=periods&semester=8')
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toEqual({ step: 'subjects', semester: '8' })

    await router.push('/scheduling/auto?semester_id=9')
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toEqual({ step: 'start', semester: '9' })

    await router.push('/settings/period-tables/12?semester=8')
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toEqual({ step: 'periods', table: '12', semester: '8' })
  })

  it('keeps the scheduling workbench deep-link path and query context', async () => {
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

    await router.push('/scheduling/flow?step=periods&table=12&semester=8')

    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.path).toBe('/scheduling/flow')
    expect(router.currentRoute.value.query).toEqual({ step: 'periods', table: '12', semester: '8' })
  })

  it('keeps the scheduling flow prototype public and normalizes variant aliases', async () => {
    await router.push('/prototype/paike-flow/b')
    expect(router.currentRoute.value.name).toBe('paike-flow-prototype')
    expect(router.currentRoute.value.query.variant).toBe('B')

    await router.push('/prototype/paike-flow?variant=C')
    expect(router.currentRoute.value.name).toBe('paike-flow-prototype')
    expect(router.currentRoute.value.query.variant).toBe('C')
  })
})
