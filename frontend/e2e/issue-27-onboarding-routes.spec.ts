import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

const USER = {
  id: 27,
  username: 'issue-27-scheduler',
  display_name: '路线验收用户',
  roles: ['scheduler'],
  must_change_password: false,
}

const DEMO_SEMESTER = {
  id: 270,
  academic_year: 2040,
  term: 1,
  label: '2040-2041学年第一学期',
  status: 'active',
  readiness: 'ready',
  is_demo: true,
  start_date: '2040-09-01',
  end_date: '2041-01-31',
}

const FORMAL_SEMESTER = {
  ...DEMO_SEMESTER,
  id: 271,
  is_demo: false,
}

const TEMPLATE = {
  key: 'junior_high_draft',
  name: '初中（空白模板）',
  minutes_per_period: 40,
  subject_count: 13,
  editable: true,
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

interface MockOptions {
  route: 'fresh' | 'formal' | 'demo'
  currentStep?: number
  completed?: boolean
  semesterId?: number | null
}

interface MockState {
  route: 'demo' | 'formal' | null
  demoCreated: boolean
  generated: boolean
  published: boolean
  routeWrites: string[]
  publishWrites: number
}

async function mockOnboarding(page: Page, options: MockOptions): Promise<MockState> {
  const state: MockState = {
    route: options.route === 'fresh' ? null : options.route,
    demoCreated: options.route === 'demo',
    generated: false,
    published: false,
    routeWrites: [],
    publishWrites: 0,
  }
  const wizard = {
    current_step: options.currentStep ?? (options.route === 'demo' ? 4 : 0),
    completed: options.completed ?? options.route === 'demo',
    semester_id: options.semesterId ?? (options.route === 'demo' ? DEMO_SEMESTER.id : null),
  }

  const currentSemester = () => {
    if (state.route === 'demo' && state.demoCreated) return DEMO_SEMESTER
    if (state.route === 'formal') return FORMAL_SEMESTER
    return null
  }
  const routeSnapshot = () => ({
    route: state.route,
    demo_available: !state.demoCreated && !currentSemester(),
    demo_school_name: '海州市启明实验初级中学',
    has_demo_semester: state.demoCreated,
    has_formal_semester: state.route === 'formal',
    can_reselect: state.route !== 'formal',
    resume_step: wizard.current_step,
    resume_semester_id: wizard.semester_id,
  })
  const onboardingStatus = () => {
    const firstSuccess = state.route === 'formal' && state.published
    const keys = ['semester', 'periods', 'calendar', 'basedata', 'assignments', 'integrity', 'draft', 'published']
    const stages = keys.map((key, index) => ({
      key,
      label: key,
      complete: firstSuccess || index < 7,
      status: firstSuccess || index < 7 ? 'complete' : 'blocked',
      blocking_reason: firstSuccess || index < 7 ? '' : '正式课表尚未发布',
      next_action: null,
      details: {},
    }))
    return {
      first_success: firstSuccess,
      wizard_completed: wizard.completed,
      current_semester: currentSemester(),
      stages,
      p0_todos: stages.filter((stage) => !stage.complete),
      next_action: null,
    }
  }
  const timetable = () => ({
    id: state.generated ? 278 : 277,
    semester_id: currentSemester()?.id ?? DEMO_SEMESTER.id,
    name: state.generated ? '自动排课结果' : '示例课表草稿',
    status: state.published ? 'published' : 'draft',
    publication_state: state.published ? 'published' : 'draft',
    entry_count: state.generated ? 594 : 0,
  })

  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()
    if (!path.startsWith('/api/')) return route.continue()

    if (path === '/api/app-config') return fulfillJson(route, {
      school_name: '路线验收学校',
      timezone: 'Asia/Shanghai',
      role_display_names: {
        admin: '系统管理员', director: '教务主任', scheduler: '排课管理员', teacher: '教师',
      },
      academic_year: {
        storage: 'start_year', min: 1900, max: 2100,
        label_format: '{year}-{next_year}学年{term_label}',
        term_labels: { '1': '第一学期', '2': '第二学期' },
      },
    })
    if (path === '/api/auth/me') return fulfillJson(route, USER)
    if (path === '/api/notifications/mine') return fulfillJson(route, { items: [], unread: 0 })
    if (path === '/api/notifications/mine/unread-count') return fulfillJson(route, { unread: 0 })
    if (path === '/api/school-templates') return fulfillJson(route, [TEMPLATE])

    if (path === '/api/wizard/state') {
      if (method === 'PATCH') {
        const body = request.postDataJSON() as Partial<typeof wizard>
        Object.assign(wizard, body)
      }
      return fulfillJson(route, { ...wizard, total_steps: 5, has_semesters: Boolean(currentSemester()), route: state.route })
    }
    if (path === '/api/onboarding/route') {
      if (method === 'PUT') {
        const body = request.postDataJSON() as { route: 'demo' | 'formal' }
        state.route = body.route
        state.routeWrites.push(body.route)
        if (body.route === 'formal') {
          wizard.current_step = 0
          wizard.completed = false
          wizard.semester_id = null
        } else if (state.demoCreated) {
          wizard.current_step = 4
          wizard.completed = true
          wizard.semester_id = DEMO_SEMESTER.id
        }
      }
      return fulfillJson(route, routeSnapshot())
    }
    if (path === '/api/onboarding/status') return fulfillJson(route, onboardingStatus())
    if (path === '/api/demo-data') {
      if (method === 'POST') {
        state.demoCreated = true
        state.route = 'demo'
        wizard.current_step = 4
        wizard.completed = true
        wizard.semester_id = DEMO_SEMESTER.id
        return fulfillJson(route, {
          semester_id: DEMO_SEMESTER.id, school_name: '海州市启明实验初级中学',
          classes: 18, teachers: 49, subjects: 16, rooms: 26, assignments: 252,
          total_periods: 594, max_overtime_used: 0, under_target: 0,
        }, 201)
      }
      return fulfillJson(route, {
        available: !state.demoCreated && !currentSemester(),
        reason: state.demoCreated ? '已有示例学期' : '',
        school_name: '海州市启明实验初级中学',
      })
    }

    if (path === '/api/semester-context') {
      const semester = currentSemester()
      return fulfillJson(route, {
        current_semester: semester ? { ...semester, is_current: true } : null,
        revision: semester ? 1 : 0,
        can_switch: false,
      })
    }
    if (path === '/api/semesters') {
      const semester = currentSemester()
      return fulfillJson(route, semester ? [{ ...semester, is_current: true }] : [])
    }
    if (/^\/api\/semesters\/\d+$/.test(path)) {
      const semester = currentSemester() ?? FORMAL_SEMESTER
      return fulfillJson(route, {
        ...semester,
        period_tables: [{ id: 279, semester_id: semester.id, name: '示例作息', num_weekdays: 5, is_default: true, periods: [] }],
      })
    }
    if (/^\/api\/semesters\/\d+\/summary$/.test(path)) {
      return fulfillJson(route, { subjects: 16, teachers: 49, classes: 18, rooms: 26 })
    }

    if (path === '/api/timetables' && method === 'GET') {
      return fulfillJson(route, currentSemester() ? [timetable()] : [])
    }
    if (/^\/api\/timetables\/\d+\/auto-schedule$/.test(path) && method === 'POST') {
      state.generated = true
      return fulfillJson(route, { job_id: 'issue-27-job' }, 202)
    }
    if (path === '/api/solver/relaxable') return fulfillJson(route, [])
    if (path === '/api/solver/preflight') return fulfillJson(route, {
      semester_id: currentSemester()?.id ?? DEMO_SEMESTER.id,
      semester_label: currentSemester()?.label ?? DEMO_SEMESTER.label,
      ok: true, error_count: 0, warning_count: 0, issues: [],
      class_count: 18, teacher_count: 49, assignment_count: 252, total_periods: 594,
    })
    if (path === '/api/solver/config') return fulfillJson(route, {
      semester_id: currentSemester()?.id ?? DEMO_SEMESTER.id,
      daily_subject_cap: 2, teacher_daily_max: 8, teacher_consecutive_max: 3,
      weights: {}, weight_names: {},
    })
    if (path === '/api/solver/jobs/issue-27-job') return fulfillJson(route, {
      job_id: 'issue-27-job', status: 'finished', semester_id: DEMO_SEMESTER.id,
      source_timetable_id: 277, source_name: '示例课表草稿', max_seconds: 600,
      elapsed: 2, solutions: 1, objective: 0, result_timetable_id: 278,
      result_name: '自动排课结果', error: null, report: null, phase: 'solving',
      partial: false, conflict: null, unscheduled: null,
    })
    if (/^\/api\/timetables\/\d+\/publication-check$/.test(path) && method === 'POST') {
      const target = timetable()
      return fulfillJson(route, {
        fingerprint: `issue-32-${target.id}`,
        passed: true,
        requires_force: false,
        checked_at: '2026-08-15T12:00:00+08:00',
        semester: {
          id: target.semester_id,
          label: currentSemester()?.label ?? DEMO_SEMESTER.label,
        },
        version: { id: target.id, name: target.name, status: target.status },
        completeness: {
          complete: true, required: target.entry_count, placed: target.entry_count,
          remaining: 0, unplaced: [],
        },
      })
    }
    if (/^\/api\/timetables\/\d+\/publish$/.test(path) && method === 'POST') {
      state.published = true
      state.publishWrites += 1
      return fulfillJson(route, { ...timetable(), status: 'published' })
    }

    // This suite intentionally exercises only the route and scheduling surfaces.
    return fulfillJson(route, {})
  })

  return state
}

test('新用户选择路线后刷新仍停留在已选正式路线', async ({ page }) => {
  const state = await mockOnboarding(page, { route: 'fresh' })
  await page.goto('/wizard')

  await expect(page.getByTestId('route-choice')).toBeVisible()
  await page.getByTestId('route-formal').click()
  await page.getByTestId('route-confirm').click()
  await expect(page.getByTestId('wizard-step-title')).toHaveText('学制模板')
  expect(state.routeWrites).toEqual(['formal'])

  await page.reload()
  await expect(page.getByTestId('route-choice')).toHaveCount(0)
  await expect(page.getByTestId('wizard-step-title')).toHaveText('学制模板')
})

test('正式向导在刷新后恢复中断步骤', async ({ page }) => {
  await mockOnboarding(page, {
    route: 'formal', currentStep: 2, completed: false, semesterId: FORMAL_SEMESTER.id,
  })
  await page.goto('/wizard')

  await expect(page.getByTestId('wizard-step-title')).toHaveText('作息时间表')
  await expect(page.getByTestId('route-choice')).toHaveCount(0)
})

test('示例路线可运行自动排课并在版本页发布结果', async ({ page }) => {
  const state = await mockOnboarding(page, { route: 'fresh' })
  await page.goto('/wizard')
  await page.getByTestId('route-demo').click()
  await page.getByTestId('route-confirm').click()
  await expect(page).toHaveURL(/\/scheduling\/auto$/)
  await expect(page.getByTestId('as-preflight')).toBeVisible()

  await page.getByTestId('as-start').click()
  await expect(page.getByTestId('as-job')).toContainText('已完成')
  await page.goto('/scheduling/versions')
  await expect(page.getByTestId('v-publish')).toBeVisible()
  await page.getByTestId('v-publish').click()
  await page.getByTestId('v-confirm-publish').click()
  await expect(page.getByTestId('v-status-自动排课结果')).toHaveText('已发布')
  const formalStatus = await page.evaluate(async () => (
    await (await fetch('/api/onboarding/status')).json()
  )) as { first_success: boolean }
  expect(formalStatus.first_success).toBe(false)
  expect(state.routeWrites).toEqual(['demo'])
  expect(state.publishWrites).toBe(1)
})

test('正式课表发布前后版本状态可在浏览器中核对', async ({ page }) => {
  const state = await mockOnboarding(page, {
    route: 'formal', currentStep: 4, completed: true, semesterId: FORMAL_SEMESTER.id,
  })
  await page.goto('/scheduling/versions')

  await expect(page.getByTestId('v-status-示例课表草稿')).toHaveText('草稿')
  await page.getByTestId('v-publish').click()
  await page.getByTestId('v-confirm-publish').click()
  await expect(page.getByTestId('v-status-示例课表草稿')).toHaveText('已发布')
  expect(state.publishWrites).toBe(1)
})
