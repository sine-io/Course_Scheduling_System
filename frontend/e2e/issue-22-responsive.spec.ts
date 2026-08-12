import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
  { width: 375, height: 812 },
] as const

const SEMESTER = {
  id: 22,
  academic_year: 2061,
  term: 1,
  label: '2061-2062学年第一学期',
  status: 'active',
  readiness: 'ready',
  start_date: '2061-09-01',
  end_date: '2062-01-31',
}

const USER = {
  id: 22,
  username: 'issue-22-scheduler',
  display_name: '报表验收用户',
  roles: ['scheduler'],
  must_change_password: false,
}

const LOG_ENTRY = {
  affected_period_id: 2201,
  date: '2061-09-07',
  weekday: 3,
  period_no: 1,
  period_name: '第一节',
  start_time: '08:00',
  end_time: '08:40',
  class_names: '七年级1班',
  subject_name: '语文',
  room_name: '七年级1班教室',
  absent_teacher_id: 221,
  absent_teacher_name: '王老师',
  leave_type: 'sick',
  leave_type_label: '病假',
  status: 'resolved',
  status_label: '已处理',
  disposed: true,
  sub_type: 'substitute',
  sub_type_label: '代课',
  handler_teacher_id: 222,
  handler_name: '陈老师',
  counts_toward_hours: true,
  swap_date: null,
  swap_period_name: '',
  swap_class_names: '',
  swap_subject_name: '',
  note: '',
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

interface MockOptions {
  failRemind?: boolean
  emptyDaily?: boolean
  emptyNotifications?: boolean
  emptyStats?: boolean
  loadFailure?: 'daily' | 'notifications' | 'log' | 'stats'
  roles?: string[]
}

async function mockApplication(page: Page, options: MockOptions = {}) {
  const state = {
    notificationQueries: [] as string[],
    logQueries: [] as string[],
    statsQueries: [] as string[],
    reminderWrites: 0,
  }
  await page.context().route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    if (!path.startsWith('/api/')) return route.continue()
    if (path === '/api/app-config') return fulfillJson(route, {
      school_name: '报表验收学校',
      timezone: 'Asia/Shanghai',
      role_display_names: {
        admin: '系统管理员',
        director: '教务主任',
        scheduler: '排课管理员',
        teacher: '教师',
      },
      academic_year: {
        storage: 'start_year',
        min: 1900,
        max: 2100,
        label_format: '{year}-{next_year}学年{term_label}',
        term_labels: { '1': '第一学期', '2': '第二学期' },
      },
    })
    if (path === '/api/auth/me') return fulfillJson(route, { ...USER, roles: options.roles ?? USER.roles })
    if (path === '/api/wizard/state') return fulfillJson(route, {
      current_step: 4,
      completed: true,
      semester_id: SEMESTER.id,
      total_steps: 5,
      has_semesters: true,
    })
    if (path === '/api/notifications/mine') return fulfillJson(route, { items: [], unread: 0 })
    if (path === '/api/notifications/mine/unread-count') return fulfillJson(route, { unread: 0 })
    if (path === '/api/semesters') return fulfillJson(route, [SEMESTER])
    if (path === '/api/teachers') return fulfillJson(route, [
      { id: 221, name: '王老师' },
      { id: 222, name: '陈老师' },
    ])
    if (path === '/api/leave-types') return fulfillJson(route, {
      sick: '病假',
      personal: '事假',
    })
    if (path === '/api/published/semesters') {
      return fulfillJson(route, [{ id: SEMESTER.id, label: SEMESTER.label }])
    }
    if (path === '/api/daily-board') {
      if (options.loadFailure === 'daily') {
        return fulfillJson(route, { detail: '当日变动暂时无法读取' }, 503)
      }
      return fulfillJson(route, {
        date: '2061-09-07',
        weekday: 3,
        school_name: '报表验收学校',
        semester_label: SEMESTER.label,
        entries: options.emptyDaily ? [] : [
          LOG_ENTRY,
          {
            ...LOG_ENTRY,
            affected_period_id: 2202,
            period_no: 2,
            period_name: '第二节',
            status: 'pending',
            status_label: '待处理',
            disposed: false,
            sub_type: null,
            sub_type_label: null,
            handler_teacher_id: null,
            handler_name: null,
          },
        ],
      })
    }
    if (path === '/api/notifications') {
      if (options.loadFailure === 'notifications') {
        return fulfillJson(route, { detail: '通知状态暂时无法读取' }, 503)
      }
      state.notificationQueries.push(url.search)
      const pending = {
        id: 2203,
        type: 'substitution_assigned',
        title: '请于第一节代七年级1班语文课',
        teacher_id: 222,
        teacher_name: '陈老师',
        created_at: '2061-09-07T07:30:00',
        read_at: null,
        acknowledged_at: null,
      }
      const acknowledged = {
        ...pending,
        id: 2204,
        teacher_id: 223,
        teacher_name: '李老师',
        title: '请于第二节代七年级2班数学课',
        read_at: '2061-09-07T07:35:00',
        acknowledged_at: '2061-09-07T07:40:00',
      }
      return fulfillJson(route, options.emptyNotifications
        ? []
        : url.searchParams.has('unacknowledged_only')
          ? [pending]
          : [pending, acknowledged])
    }
    if (path === '/api/notifications/2203/remind') {
      state.reminderWrites += 1
      if (options.failRemind) return fulfillJson(route, { detail: '邮件服务暂时不可用' }, 503)
      return fulfillJson(route, {
        id: 2203,
        type: 'substitution_assigned',
        title: '请于第一节代七年级1班语文课',
        body: '',
        link: '',
        created_at: '2061-09-07T07:30:00',
        read_at: null,
        acknowledged_at: null,
      })
    }
    if (path === '/api/substitution-log') {
      if (options.loadFailure === 'log') {
        return fulfillJson(route, { detail: '历史记录暂时无法读取' }, 503)
      }
      state.logQueries.push(url.search)
      if (url.searchParams.get('leave_type') === 'personal') return fulfillJson(route, [])
      if (url.searchParams.has('teacher_id')) return fulfillJson(route, [LOG_ENTRY])
      return fulfillJson(route, [
        LOG_ENTRY,
        {
          ...LOG_ENTRY,
          affected_period_id: 2205,
          date: '2061-09-08',
          weekday: 4,
          period_no: 2,
          period_name: '第二节',
          class_names: '七年级2班',
          subject_name: '数学',
          absent_teacher_id: 223,
          absent_teacher_name: '李老师',
          leave_type: 'personal',
          leave_type_label: '事假',
          handler_teacher_id: 224,
          handler_name: '周老师',
        },
      ])
    }
    if (path === '/api/substitution-stats' || path === '/api/substitution-stats/mine') {
      if (options.loadFailure === 'stats') {
        return fulfillJson(route, { detail: '课时统计暂时无法读取' }, 503)
      }
      const isMine = path.endsWith('/mine')
      const statsQuery = url.search
      state.statsQueries.push(`${path}${statsQuery}`)
      const details = options.emptyStats ? [] : [
        {
          handler_teacher_id: 222,
          handler_name: '陈老师',
          date: '2061-09-07',
          period_name: '第一节',
          class_names: '七年级1班',
          subject_name: '语文',
          absent_teacher_name: '王老师',
          leave_type: 'sick',
          leave_type_label: '病假',
          sub_type: 'substitute',
          sub_type_label: '代课',
          counts_toward_hours: true,
          funding_source: '',
        },
        {
          handler_teacher_id: 222,
          handler_name: '陈老师',
          date: '2061-09-08',
          period_name: '第二节',
          class_names: '七年级2班',
          subject_name: '数学',
          absent_teacher_name: '李老师',
          leave_type: 'personal',
          leave_type_label: '事假',
          sub_type: 'merge',
          sub_type_label: '合班',
          counts_toward_hours: false,
          funding_source: '',
        },
      ]
      const summaries = options.emptyStats
        ? []
        : [{ teacher_id: 222, teacher_name: '陈老师', handled_count: 2, billable_count: 1 }]
      if (isMine || statsQuery.includes('teacher_id=222')) {
        return fulfillJson(route, {
          year: 2061,
          month: 9,
          summaries,
          details,
        })
      }
      return fulfillJson(route, {
        year: 2061,
        month: 9,
        summaries,
        details,
      })
    }
    if (path === '/api/substitution-stats/export') {
      return route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers: { 'content-disposition': 'attachment; filename="substitution-stats-2061-09.xlsx"' },
        body: 'xlsx',
      })
    }
    return fulfillJson(route, { detail: `未模拟 ${route.request().method()} ${path}` }, 501)
  })
  return state
}

async function expectNoRootOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    contentScrollWidth: document.querySelector<HTMLElement>('.app-content')?.scrollWidth ?? 0,
    contentClientWidth: document.querySelector<HTMLElement>('.app-content')?.clientWidth ?? 0,
  }))
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth)
  expect(dimensions.contentScrollWidth).toBeLessThanOrEqual(dimensions.contentClientWidth)
}

async function expectInternalOverflow(page: Page, testId: string) {
  const dimensions = await page.getByTestId(testId).evaluate((element) => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }))
  expect(dimensions.scrollWidth).toBeGreaterThan(dimensions.clientWidth)
}

async function expectVisibleKeyboardFocus(page: Page, testId: string) {
  const control = page.getByTestId(testId).first()
  await control.focus()
  await expect(control).toBeFocused()
  expect(await control.evaluate((element) => {
    const style = getComputedStyle(element)
    return element.matches(':focus-visible')
      && style.outlineStyle !== 'none'
      && Number.parseFloat(style.outlineWidth) > 0
  })).toBe(true)
}

test('日看板在手机视口保留日期、处理语义与打印入口', async ({ page }) => {
  const pageErrors: string[] = []
  const failedRequests: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('requestfailed', (request) => failedRequests.push(
    `${request.url()}: ${request.failure()?.errorText ?? '请求失败'}`,
  ))
  await page.setViewportSize({ width: 375, height: 812 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await mockApplication(page)

  await page.goto(`/daily-board?semester_id=${SEMESTER.id}&date=2061-09-07`)

  await expect.poll(() => pageErrors).toEqual([])
  await expect.poll(() => failedRequests).toEqual([])
  await expect(page.getByTestId('daily-board-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: '今日调课与代课', level: 1 })).toBeVisible()
  await expect(page.getByLabel('选择工作学期')).toBeVisible()
  await expect(page.getByTestId('board-datelabel')).toContainText('2061-09-07（星期三）')
  await expect(page.getByTestId('board-row')).toHaveCount(2)
  await expect(page.getByTestId('board-row').nth(0)).toContainText('已处理')
  await expect(page.getByTestId('board-row').nth(0)).toContainText('陈老师')
  await expect(page.getByTestId('board-row').nth(1)).toContainText('待安排')
  await expect(page.getByTestId('board-print')).toBeVisible()
  await expect(page.getByTestId('board-table-scroll')).toBeVisible()
  const [popup] = await Promise.all([
    page.waitForEvent('popup'),
    page.getByTestId('board-print').click(),
  ])
  await popup.waitForLoadState()
  await expect(popup.getByTestId('print-table')).toBeVisible()
  await expect(popup.getByText('调课与代课通知单')).toBeVisible()
  await popup.close()
  await expectNoRootOverflow(page)
  await expectInternalOverflow(page, 'board-table-scroll')
})

test('通知看板筛选确认状态并再次提醒', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const state = await mockApplication(page)

  await page.goto('/notification-board')

  await expect(page.getByTestId('notification-board-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: '通知确认看板', level: 1 })).toBeVisible()
  await expect(page.getByLabel('选择工作学期')).toBeVisible()
  await expect(page.getByTestId('board-row')).toHaveCount(1)
  await expect(page.getByTestId('board-row')).toContainText('陈老师')
  await expect(page.getByTestId('board-row')).toContainText('未读')
  await expect(page.getByTestId('notification-table-scroll')).toBeVisible()

  await page.getByTestId('board-unackonly').click()
  await expect(page.getByTestId('board-row')).toHaveCount(2)
  await expect(page.getByTestId('board-row').nth(1)).toContainText('李老师')
  await expect(page.getByTestId('board-row').nth(1)).toContainText('已确认')

  await page.getByTestId('board-row').nth(0).getByTestId('board-remind').click()
  await expect(page.getByText('已再次提醒 陈老师').first()).toBeVisible()
  expect(state.reminderWrites).toBe(1)
  expect(state.notificationQueries.some((query) => query.includes('unacknowledged_only=true'))).toBe(true)
  expect(state.notificationQueries.some((query) => !query.includes('unacknowledged_only'))).toBe(true)
  await expectNoRootOverflow(page)
  await expectInternalOverflow(page, 'notification-table-scroll')
})

test('通知再次提醒失败时给出可操作反馈', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await mockApplication(page, { failRemind: true })

  await page.goto('/notification-board')
  const remind = page.getByTestId('board-remind').first()
  await remind.click()
  await expect(page.getByText('邮件服务暂时不可用').first()).toBeVisible()
  await expect(remind).toBeEnabled()
})

test('调课与代课记录组合筛选、清除并呈现空结果', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const state = await mockApplication(page)

  await page.goto('/substitution-log')

  await expect(page.getByTestId('substitution-log-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: '调课与代课记录', level: 1 })).toBeVisible()
  await expect(page.getByLabel('选择工作学期')).toBeVisible()
  await expect(page.getByTestId('log-row')).toHaveCount(2)
  await expect(page.getByTestId('log-count')).toContainText('共 2 条')
  await expect(page.getByTestId('log-table-scroll')).toBeVisible()

  await page.getByTestId('log-teacher').click()
  await page.locator('.n-base-select-option', { hasText: '陈老师' }).click()
  await expect(page.getByTestId('log-row')).toHaveCount(1)
  await expect.poll(() => state.logQueries.some((query) => query.includes('teacher_id=222'))).toBe(true)

  const dateInputs = page.getByTestId('log-range').locator('input')
  await dateInputs.nth(0).fill('2061-09-01')
  await dateInputs.nth(1).fill('2061-09-30')
  await dateInputs.nth(1).press('Enter')
  await expect.poll(() => state.logQueries.some((query) =>
    query.includes('date_from=2061-09-01') && query.includes('date_to=2061-09-30'))).toBe(true)

  await page.getByTestId('log-leavetype').click()
  await page.locator('.n-base-select-option', { hasText: '事假' }).click()
  await expect(page.getByTestId('log-empty')).toContainText('没有符合条件的记录')
  await expect(page.getByTestId('log-count')).toContainText('共 0 条')

  await page.getByTestId('log-reset').click()
  await expect(page.getByTestId('log-row')).toHaveCount(2)
  await expect(page.getByTestId('log-count')).toContainText('共 2 条')
  const lastQuery = state.logQueries.at(-1) ?? ''
  expect(lastQuery).toContain('semester_id=22')
  expect(lastQuery).not.toContain('teacher_id')
  expect(lastQuery).not.toContain('date_from')
  expect(lastQuery).not.toContain('leave_type')
  await expectNoRootOverflow(page)
  await expectInternalOverflow(page, 'log-table-scroll')
})

test('管理员查看代课统计汇总、明细并按教师导出', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const state = await mockApplication(page)

  await page.goto(`/substitution-stats?semester_id=${SEMESTER.id}&year=2061&month=9`)

  await expect(page.getByTestId('substitution-stats-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: '代课课时统计', level: 1 })).toBeVisible()
  await expect(page.getByLabel('选择工作学期')).toBeVisible()
  await expect(page.getByTestId('stats-summary-row')).toHaveCount(1)
  await expect(page.getByTestId('stats-summary-row')).toContainText('陈老师')
  await expect(page.getByTestId('stats-total')).toContainText(/计费合计\s*1\s*节/)
  await expect(page.getByTestId('stats-detail-row')).toHaveCount(2)
  await expect(page.getByTestId('stats-summary-scroll')).toBeVisible()
  await expect(page.getByTestId('stats-detail-scroll')).toBeVisible()

  await page.getByTestId('stats-teacher').click()
  await page.locator('.n-base-select-option', { hasText: '陈老师' }).click()
  await expect.poll(() => state.statsQueries.some((query) =>
    query.includes('/api/substitution-stats?') && query.includes('teacher_id=222'))).toBe(true)

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByTestId('stats-export').click(),
  ])
  expect(download.suggestedFilename()).toContain('substitution-stats-2061-09.xlsx')
  await expectNoRootOverflow(page)
})

test('教师只查看自己的代课统计且没有管理操作', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const state = await mockApplication(page, { roles: ['teacher'] })

  await page.goto(`/substitution-stats?semester_id=${SEMESTER.id}&year=2061&month=9`)

  await expect(page.getByTestId('substitution-stats-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: '我的代课课时', level: 1 })).toBeVisible()
  await expect(page.getByTestId('stats-detail-row')).toHaveCount(2)
  await expect(page.getByTestId('stats-summary')).toHaveCount(0)
  await expect(page.getByTestId('stats-teacher')).toHaveCount(0)
  await expect(page.getByTestId('stats-export')).toHaveCount(0)
  await expect.poll(() => state.statsQueries.some((query) =>
    query.startsWith('/api/substitution-stats/mine?'))).toBe(true)
  expect(state.statsQueries.some((query) =>
    query.startsWith('/api/substitution-stats?'))).toBe(false)
  await expectNoRootOverflow(page)
})

test('空的日看板与统计报告隐藏无效操作', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await mockApplication(page, { emptyDaily: true, emptyStats: true })

  await page.goto(`/daily-board?semester_id=${SEMESTER.id}&date=2061-09-07`)
  await expect(page.getByTestId('board-empty')).toBeVisible()
  await expect(page.getByTestId('board-print')).toHaveCount(0)
  await expectNoRootOverflow(page)

  await page.goto(`/substitution-stats?semester_id=${SEMESTER.id}&year=2061&month=9`)
  await expect(page.getByTestId('stats-empty')).toBeVisible()
  await expect(page.getByTestId('stats-export')).toHaveCount(0)
  await expectNoRootOverflow(page)
})

test('通知空状态隐藏无效操作', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await mockApplication(page, { emptyNotifications: true })

  await page.goto('/notification-board')

  await expect(page.getByTestId('notification-empty')).toContainText('没有符合条件的通知')
  await expect(page.getByTestId('board-remind')).toHaveCount(0)
  await expectNoRootOverflow(page)
})

const LOAD_FAILURES = [
  {
    name: '日看板',
    kind: 'daily',
    path: `/daily-board?semester_id=${SEMESTER.id}&date=2061-09-07`,
    errorTestId: 'daily-board-error',
    retryTestId: 'daily-board-retry',
    message: '当日变动暂时无法读取',
  },
  {
    name: '通知看板',
    kind: 'notifications',
    path: '/notification-board',
    errorTestId: 'notification-board-error',
    retryTestId: 'notification-board-retry',
    message: '通知状态暂时无法读取',
  },
  {
    name: '调课与代课记录',
    kind: 'log',
    path: '/substitution-log',
    errorTestId: 'log-error',
    retryTestId: 'log-retry',
    message: '历史记录暂时无法读取',
  },
  {
    name: '代课课时统计',
    kind: 'stats',
    path: `/substitution-stats?semester_id=${SEMESTER.id}&year=2061&month=9`,
    errorTestId: 'stats-error',
    retryTestId: 'stats-retry',
    message: '课时统计暂时无法读取',
  },
] as const

for (const scenario of LOAD_FAILURES) {
  test(`${scenario.name}读取失败时显示明确反馈与重试入口`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await mockApplication(page, { loadFailure: scenario.kind })

    await page.goto(scenario.path)

    await expect(page.getByTestId(scenario.errorTestId)).toContainText(scenario.message)
    await expect(page.getByTestId(scenario.retryTestId)).toBeVisible()
    await expectNoRootOverflow(page)
  })
}

test('四个报表工作面在四种视口保留关键字段与内部滚动', async ({ page }, testInfo) => {
  await mockApplication(page)
  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })

    await page.goto(`/daily-board?semester_id=${SEMESTER.id}&date=2061-09-07`)
    await expect(page.getByTestId('daily-board-page')).toBeVisible()
    await expect(page.getByTestId('board-datelabel')).toContainText('2061-09-07')
    await expectNoRootOverflow(page)
    if (viewport.width <= 768) await expectInternalOverflow(page, 'board-table-scroll')
    if (viewport.width === 1920 || viewport.width === 375) {
      await page.screenshot({
        path: testInfo.outputPath(`daily-board-${viewport.width}x${viewport.height}.png`),
        fullPage: true,
      })
    }

    await page.goto('/notification-board')
    await expect(page.getByTestId('notification-board-page')).toBeVisible()
    await expect(page.getByTestId('board-row').first()).toContainText('陈老师')
    await expectNoRootOverflow(page)
    if (viewport.width <= 768) await expectInternalOverflow(page, 'notification-table-scroll')
    if (viewport.width === 1920 || viewport.width === 375) {
      await page.screenshot({
        path: testInfo.outputPath(`notification-board-${viewport.width}x${viewport.height}.png`),
        fullPage: true,
      })
    }

    await page.goto('/substitution-log')
    await expect(page.getByTestId('substitution-log-page')).toBeVisible()
    await expect(page.getByTestId('log-count')).toContainText('共 2 条')
    await expectNoRootOverflow(page)
    if (viewport.width <= 768) await expectInternalOverflow(page, 'log-table-scroll')
    if (viewport.width === 1920 || viewport.width === 375) {
      await page.screenshot({
        path: testInfo.outputPath(`substitution-log-${viewport.width}x${viewport.height}.png`),
        fullPage: true,
      })
    }

    await page.goto(`/substitution-stats?semester_id=${SEMESTER.id}&year=2061&month=9`)
    await expect(page.getByTestId('substitution-stats-page')).toBeVisible()
    await expect(page.getByTestId('stats-detail-row').first()).toBeVisible()
    await expectNoRootOverflow(page)
    if (viewport.width <= 768) await expectInternalOverflow(page, 'stats-detail-scroll')
    if (viewport.width === 1920 || viewport.width === 375) {
      await page.screenshot({
        path: testInfo.outputPath(`substitution-stats-${viewport.width}x${viewport.height}.png`),
        fullPage: true,
      })
    }
  }
})

test('四个报表工作面提供可见的键盘焦点', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await mockApplication(page)

  await page.goto(`/daily-board?semester_id=${SEMESTER.id}&date=2061-09-07`)
  await expectVisibleKeyboardFocus(page, 'board-table-scroll')

  await page.goto('/notification-board')
  await expectVisibleKeyboardFocus(page, 'notification-table-scroll')
  await expectVisibleKeyboardFocus(page, 'board-remind')

  await page.goto('/substitution-log')
  await expectVisibleKeyboardFocus(page, 'log-table-scroll')
  await expectVisibleKeyboardFocus(page, 'log-reset')

  await page.goto(`/substitution-stats?semester_id=${SEMESTER.id}&year=2061&month=9`)
  await expectVisibleKeyboardFocus(page, 'stats-detail-scroll')
  await expectVisibleKeyboardFocus(page, 'stats-export')
})
