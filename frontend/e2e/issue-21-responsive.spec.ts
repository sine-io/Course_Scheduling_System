import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
  { width: 375, height: 812 },
] as const

const USER = {
  id: 21,
  username: 'issue-21-scheduler',
  display_name: '自动排课验收用户',
  roles: ['scheduler'],
  must_change_password: false,
}

const SEMESTER = {
  id: 71,
  academic_year: 2045,
  term: 1,
  label: '2045-2046学年第一学期',
  status: 'preparing',
  readiness: 'ready',
  start_date: '2045-09-01',
  end_date: '2046-01-20',
  period_tables: [],
}

const PERIODS = Array.from({ length: 7 }, (_, dayIndex) => [
  {
    id: dayIndex * 3 + 1,
    weekday: dayIndex + 1,
    period_no: 1,
    name: '第一节',
    start_time: '08:00',
    end_time: '08:40',
    type: 'regular',
  },
  {
    id: dayIndex * 3 + 2,
    weekday: dayIndex + 1,
    period_no: 2,
    name: '午休',
    start_time: '12:00',
    end_time: '13:10',
    type: 'lunch',
  },
  {
    id: dayIndex * 3 + 3,
    weekday: dayIndex + 1,
    period_no: 3,
    name: '第二节',
    start_time: '13:10',
    end_time: '13:50',
    type: 'regular',
  },
]).flat()

const PERIOD_TABLE = {
  id: 91,
  name: '全周作息时间表',
  semester_id: SEMESTER.id,
  num_weekdays: 7,
  is_default: true,
  periods: PERIODS,
}

const TIMETABLES = [
  { id: 81, semester_id: SEMESTER.id, name: '草稿A', status: 'draft', entry_count: 1 },
  { id: 82, semester_id: SEMESTER.id, name: '正式课表', status: 'published', entry_count: 1 },
]

const PUBLISHED_TIMETABLE = {
  id: 82,
  semester_id: SEMESTER.id,
  semester_label: SEMESTER.label,
  name: '正式课表',
  status: 'published',
  entries: [{
    id: 801,
    course_assignment_id: 501,
    weekday: 2,
    period_no: 1,
    span: 1,
    locked: false,
    subject: '语文',
    teachers: ['陈老师'],
    classes: ['1班'],
    unit_type: 'single',
    unit_name: '七年级1班',
    room: '七年级1班教室',
    teacher_ids: [401],
    class_ids: [301],
    room_id: 601,
  }],
  classes: [{ id: 301, name: '1班', grade: 7, period_table_id: 91 }],
  teachers: [{ id: 401, name: '陈老师' }],
  rooms: [{ id: 601, name: '七年级1班教室' }],
  period_tables: [PERIOD_TABLE],
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

interface MockOptions {
  failPublishedSemesters?: boolean
  delayPublishedSemesters?: number
  solveLifecycle?: boolean
}

interface MockState {
  jobReads: number
  writeRequests: string[]
}

function solveJob(status: 'running' | 'finished') {
  return {
    job_id: 'job-21',
    status,
    semester_id: SEMESTER.id,
    source_timetable_id: 81,
    source_name: '草稿A',
    max_seconds: 600,
    elapsed: status === 'running' ? 2 : 8,
    solutions: status === 'running' ? 1 : 2,
    objective: 12,
    result_timetable_id: status === 'finished' ? 83 : null,
    result_name: status === 'finished' ? '自动排课结果' : null,
    error: null,
    report: null,
    phase: 'solving',
    partial: false,
    conflict: null,
    unscheduled: null,
  }
}

async function mockApplication(
  page: Page,
  roles = USER.roles,
  options: MockOptions = {},
): Promise<MockState> {
  const state: MockState = { jobReads: 0, writeRequests: [] }
  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    if (!path.startsWith('/api/')) return route.continue()
    if (!['GET', 'HEAD'].includes(request.method())) state.writeRequests.push(`${request.method()} ${path}`)

    if (path === '/api/app-config') {
      return fulfillJson(route, {
        school_name: '自动排课验收学校',
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
    }
    if (path === '/api/auth/me') return fulfillJson(route, { ...USER, roles })
    if (path === '/api/wizard/state') return fulfillJson(route, {
      current_step: 3,
      resume_step: 3,
      completed: true,
      paused: false,
      semester_id: SEMESTER.id,
      total_steps: 4,
      has_semesters: true,
    })
    if (path === '/api/notifications/mine' || path === '/api/notifications/mine/unread-count') {
      return fulfillJson(route, path.endsWith('unread-count') ? { unread: 0 } : { items: [], unread: 0 })
    }
    if (path === '/api/semesters') return fulfillJson(route, [SEMESTER])
    if (path === `/api/semesters/${SEMESTER.id}`) return fulfillJson(route, { ...SEMESTER, period_tables: [PERIOD_TABLE] })
    if (path === '/api/timetables' && request.method() === 'GET') return fulfillJson(route, TIMETABLES)
    if (path === '/api/solver/relaxable') return fulfillJson(route, [])
    if (path === '/api/solver/preflight') return fulfillJson(route, {
      ok: true,
      issues: [],
      semester_id: SEMESTER.id,
      semester_label: SEMESTER.label,
      error_count: 0,
      warning_count: 0,
      assignment_count: 1,
      total_periods: 3,
      teacher_count: 1,
      class_count: 1,
    })
    if (path === '/api/solver/config') return fulfillJson(route, {
      semester_id: SEMESTER.id,
      daily_subject_cap: 2,
      teacher_daily_max: 6,
      teacher_consecutive_max: 3,
      weights: { teacher_overload: 1, class_compactness: 1 },
      weight_names: { teacher_overload: '教师超课时', class_compactness: '班级紧凑度' },
    })
    if (path === '/api/published/semesters' && options.delayPublishedSemesters) {
      await new Promise((resolve) => setTimeout(resolve, options.delayPublishedSemesters))
    }
    if (path === '/api/published/semesters' && options.failPublishedSemesters) {
      return fulfillJson(route, { detail: '已发布课表服务暂时不可用' }, 503)
    }
    if (path === '/api/published/semesters') return fulfillJson(route, [{ id: SEMESTER.id, label: SEMESTER.label }])
    if (path === '/api/published/timetable') return fulfillJson(route, PUBLISHED_TIMETABLE)
    if (path === '/api/published/my-teacher') return fulfillJson(route, null)
    if (path === '/api/timetables/81/auto-schedule' && request.method() === 'POST' && options.solveLifecycle) {
      return fulfillJson(route, { job_id: 'job-21' })
    }
    if (path === '/api/solver/jobs/job-21' && options.solveLifecycle) {
      state.jobReads += 1
      if (state.jobReads === 2) await new Promise((resolve) => setTimeout(resolve, 500))
      return fulfillJson(route, solveJob(state.jobReads === 1 ? 'running' : 'finished'))
    }

    return fulfillJson(route, { detail: `未模拟 ${request.method()} ${path}` }, 501)
  })
  return state
}

async function expectNoRootOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth)
}

for (const viewport of VIEWPORTS) {
  test(`自动排课工作面 ${viewport.width}x${viewport.height} 保持页面边界`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await mockApplication(page)

    await page.goto('/scheduling/auto')
    await expect(page.getByTestId('auto-schedule-page')).toBeVisible()
    await expect(page.getByLabel('选择工作学期')).toBeVisible()
    await expect(page.getByTestId('as-constraints')).toBeVisible()
    await expect(page.getByTestId('as-start')).toBeVisible()
    await expectNoRootOverflow(page)
    await page.screenshot({
      path: testInfo.outputPath(`auto-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    })

    await page.goto('/scheduling/versions')
    await expect(page.getByTestId('versions-page')).toBeVisible()
    await expect(page.getByLabel('选择工作学期')).toBeVisible()
    await expect(page.getByTestId('versions-table-scroll')).toBeVisible()
    await expect(page.getByTestId('v-status-正式课表')).toHaveText('已发布')
    await expectNoRootOverflow(page)
    await page.screenshot({
      path: testInfo.outputPath(`versions-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    })

    await page.goto('/timetable-query')
    await expect(page.getByTestId('timetable-query-page')).toBeVisible()
    await expect(page.getByLabel('选择已发布学期')).toBeVisible()
    await expect(page.getByRole('radiogroup', { name: '课表视角' })).toBeVisible()
    await expect(page.getByTestId('tq-grid')).toContainText('语文')
    await expect(page.getByTestId('timetable-scroll')).toBeVisible()
    await expectNoRootOverflow(page)
    await page.screenshot({
      path: testInfo.outputPath(`query-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    })

    if (viewport.width <= 768) {
      const gridDimensions = await page.getByTestId('timetable-scroll').evaluate((element) => ({
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
      }))
      expect(gridDimensions.scrollWidth).toBeGreaterThan(gridDimensions.clientWidth)
    }

    await page.goto('/scheduling/timetable-demo')
    await expect(page).toHaveURL(/\/scheduling\/workbench$/)
    await expect(page.getByTestId('timetable-demo-page')).toHaveCount(0)
  })
}

test('教务主任能读取准备度和版本，但不会看到写入入口', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  const state = await mockApplication(page, ['director'])

  await page.goto('/scheduling/auto')
  await expect(page.getByTestId('as-restricted')).toContainText('仅可查看')
  await expect(page.getByTestId('as-start')).toBeDisabled()

  await page.goto('/scheduling/versions')
  await expect(page.getByTestId('versions-restricted')).toContainText('可查看版本')
  await expect(page.getByTestId('v-new')).toHaveCount(0)
  await expect(page.getByTestId('v-publish')).toHaveCount(0)
  await expect(page.getByTestId('v-duplicate')).toHaveCount(0)
  expect(state.writeRequests).toEqual([])
})

test('课表查询在加载中和读取失败时提供明确反馈', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await mockApplication(page, USER.roles, { delayPublishedSemesters: 800 })

  await page.goto('/timetable-query')
  await expect(page.getByTestId('tq-loading')).toContainText('正在读取已发布课表')
  await expect(page.getByTestId('tq-grid')).toBeVisible()

  const failedPage = await page.context().newPage()
  await mockApplication(failedPage, USER.roles, { failPublishedSemesters: true })
  await failedPage.goto('/timetable-query')
  await expect(failedPage.getByTestId('tq-error')).toContainText('已发布课表服务暂时不可用')
  await expect(failedPage.getByTestId('tq-retry')).toBeVisible()
  await expectNoRootOverflow(failedPage)
})

test('自动排课离页时忽略迟到轮询，返回后恢复真实终态', async ({ page }) => {
  test.setTimeout(20_000)
  await page.setViewportSize({ width: 1280, height: 800 })
  const state = await mockApplication(page, USER.roles, { solveLifecycle: true })

  await page.goto('/scheduling/auto')
  await page.getByTestId('as-start').click()
  await expect(page.getByTestId('as-status')).toHaveText('排课中')
  await expect.poll(() => state.jobReads).toBeGreaterThanOrEqual(2)

  await page.goto('/timetable-query')
  await page.waitForTimeout(650)
  await expect(page.getByText('已生成“自动排课结果”')).toHaveCount(0)

  await page.goto('/scheduling/auto')
  await expect(page.getByTestId('as-status')).toHaveText('已完成')
  await expect(page.getByTestId('as-done')).toContainText('自动排课结果')
})
