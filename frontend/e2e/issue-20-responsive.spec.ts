import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
  { width: 375, height: 812 },
] as const

const USER = {
  id: 20,
  username: 'issue-20-scheduler',
  display_name: '设置工作面验收用户',
  roles: ['scheduler'],
  must_change_password: false,
}
const SEMESTER = {
  id: 44,
  academic_year: 2042,
  term: 1,
  label: '2042-2043学年第一学期',
  status: 'preparing',
  readiness: 'draft',
  start_date: '2042-09-01',
  end_date: '2043-01-20',
}
const PERIOD_TABLE = {
  id: 77,
  name: '全周作息时间表',
  num_weekdays: 7,
  is_default: true,
  periods: Array.from({ length: 7 }, (_, index) => ({
    id: index + 1,
    weekday: index + 1,
    period_no: 1,
    name: '第一节',
    start_time: '08:00',
    end_time: '08:40',
    type: 'regular',
  })),
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

async function expectNoRootOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth)
}

async function mockSession(page: Page, currentSemester: () => typeof SEMESTER | null) {
  await page.route('**/api/auth/login', (route) => fulfillJson(route, USER))
  await page.route('**/api/auth/me', (route) => fulfillJson(route, USER))
  await page.route('**/api/wizard/state', (route) => fulfillJson(route, {
    current_step: 4,
    completed: true,
    semester_id: 44,
    total_steps: 5,
    has_semesters: true,
  }))
  await page.route('**/api/app-config', (route) => fulfillJson(route, {
    school_name: '设置工作面验收学校',
    timezone: 'Asia/Shanghai',
    role_display_names: { admin: '系统管理员', director: '教务主任', scheduler: '排课管理员', teacher: '教师' },
    academic_year: {
      storage: 'start_year',
      min: 1900,
      max: 2100,
      label_format: '{year}-{next_year}学年{term_label}',
      term_labels: { '1': '第一学期', '2': '第二学期' },
    },
  }))
  await page.route('**/api/notifications/mine**', (route) => fulfillJson(route, { items: [], unread: 0 }))
  await page.route('**/api/notifications/mine/unread-count**', (route) => fulfillJson(route, { unread: 0 }))
  await page.route('**/api/navigation-preference', (route) => fulfillJson(route, {
    fixed: [],
    recent: [],
  }))
  await page.route('**/api/onboarding/status', (route) => fulfillJson(route, {
    first_success: true,
    p0_todos: [],
    stages: [],
    next_action: null,
  }))
  await page.route('**/api/semesters/44/summary', (route) => fulfillJson(route, {
    subjects: 8,
    teachers: 12,
    classes: 6,
    rooms: 7,
  }))
  await page.route('**/api/daily-board**', (route) => fulfillJson(route, {
    date: '2042-09-01',
    weekday: 1,
    school_name: '设置工作面验收学校',
    semester_label: SEMESTER.label,
    entries: [],
  }))
  await page.route('**/api/semester-context', (route) => {
    const semester = currentSemester()
    return fulfillJson(route, {
      current_semester: semester ? { ...semester, is_current: true } : null,
      revision: semester ? 1 : 0,
      can_switch: true,
    })
  })
}

for (const viewport of VIEWPORTS) {
  test(`设置工作面 ${viewport.width}x${viewport.height} 覆盖空态、失败、加载与受限状态`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    let semesterMode: 'empty' | 'calendar' = 'empty'
    await mockSession(page, () => semesterMode === 'empty' ? null : SEMESTER)

    let pendingPeriodRoute: Route | null = null
    const requestedAdminPaths: string[] = []
    page.on('request', (request) => {
      const path = new URL(request.url()).pathname
      if ([
        '/api/settings/smtp',
        '/api/settings/scheduling',
        '/api/settings/school',
        '/api/demo-data',
        '/api/backups',
      ].includes(path)) requestedAdminPaths.push(path)
    })

    await page.route('**/api/school-templates', (route) => fulfillJson(route, []))
    await page.route('**/api/semesters', (route) => fulfillJson(
      route,
      semesterMode === 'empty' ? [] : [SEMESTER],
    ))
    await page.route('**/api/semesters/44/calendar-exceptions**', (route) => fulfillJson(
      route,
      { detail: '校历服务暂时不可用' },
      503,
    ))
    await page.route('**/api/semesters/44/readiness', (route) => fulfillJson(route, {
      semester_id: 44,
      readiness: 'draft',
      ready: false,
      issues: [],
      calendar_exception_count: 0,
    }))
    await page.route('**/api/period-tables/77', async (route) => {
      pendingPeriodRoute = route
    })

    await page.goto('/settings/semesters')
    await expect(page.getByTestId('semesters-empty')).toBeVisible()
    await expectNoRootOverflow(page)

    semesterMode = 'calendar'
    await page.goto('/settings/calendar')
    await expect(page.getByTestId('calendar-data-error')).toContainText('校历服务暂时不可用')
    await expectNoRootOverflow(page)

    await page.goto('/settings/period-tables/77')
    await expect(page.getByTestId('period-table-loading')).toBeVisible()
    await expectNoRootOverflow(page)
    await expect.poll(() => pendingPeriodRoute).not.toBeNull()
    await (pendingPeriodRoute as Route).fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(PERIOD_TABLE),
    })
    await expect(page.getByTestId('period-table-workspace')).toBeVisible()
    await expectNoRootOverflow(page)
    if (viewport.width <= 768) {
      const scrollDimensions = await page.getByTestId('period-grid-scroll').evaluate((element) => ({
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
      }))
      expect(scrollDimensions.scrollWidth).toBeGreaterThan(scrollDimensions.clientWidth)
    }

    await page.goto('/settings/system')
    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByTestId('app-shell')).toBeVisible()
    await expectNoRootOverflow(page)
    expect(requestedAdminPaths).toEqual([])
  })
}
