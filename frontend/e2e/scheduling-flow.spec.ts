import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

const USER = {
  id: 71,
  username: 'flow-director',
  display_name: '排课工作台验收用户',
  roles: ['director'],
  must_change_password: false,
}

const PERIOD_TABLE = {
  id: 91,
  semester_id: 71,
  name: '默认作息时间表',
  num_weekdays: 5,
  is_default: true,
  periods: [{
    id: 911,
    weekday: 1,
    period_no: 1,
    name: '第一节',
    start_time: '08:00:00',
    end_time: '08:40:00',
    type: 'regular',
  }],
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
  is_current: true,
  period_tables: [PERIOD_TABLE],
}

const CLASS_UNIT = {
  id: 301,
  semester_id: 71,
  grade: 7,
  name: '1班',
  track: 'junior_high',
  department: null,
  student_count: 42,
  homeroom_teacher_id: 401,
  homeroom_teacher: { id: 401, name: '陈老师' },
  period_table_id: 91,
}

const TEACHER = {
  id: 401,
  semester_id: 71,
  name: '陈老师',
  base_periods: 3,
  admin_title: null,
  admin_reduction: 0,
  is_external: false,
  is_active: true,
  subjects: [{ id: 501, name: '语文' }],
  email: null,
  phone: null,
  line_id: null,
  user_id: null,
}

const SUBJECT = {
  id: 501,
  semester_id: 71,
  name: '语文',
  domain: null,
  required_room_type: null,
  default_block_size: 1,
  is_major: true,
}

const ASSIGNMENT = {
  id: 601,
  semester_id: 71,
  scheduling_unit: {
    id: 701,
    semester_id: 71,
    unit_type: 'single',
    name: '七年级1班',
    classes: [{ id: 301, name: '1班', grade: 7 }],
  },
  subject: { id: 501, name: '语文' },
  periods_per_week: 3,
  required_room_type: null,
  room_id: null,
  lock_room: false,
  teachers: [{ teacher_id: 401, is_lead: true, name: '陈老师' }],
  block_rules: [],
}

const PREFLIGHT = {
  semester_id: 71,
  semester_label: SEMESTER.label,
  ok: true,
  error_count: 0,
  warning_count: 0,
  issues: [],
  class_count: 1,
  teacher_count: 1,
  assignment_count: 1,
  total_periods: 3,
}

async function fulfillJson(route: Route, body: unknown) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
}

async function mockFlowApplication(page: Page, options: { emptySemester?: boolean } = {}) {
  let semesterCreated = !options.emptySemester
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname

    // Vite 的源码目录也包含 /api/；只截获实际后端 API，其他请求继续加载。
    if (!path.startsWith('/api/')) return route.continue()

    if (path === '/api/app-config') return fulfillJson(route, {
      school_name: '统一入口验收学校',
      timezone: 'Asia/Shanghai',
      role_display_names: { admin: '系统管理员', director: '教务主任', teacher: '教师' },
      academic_year: {
        storage: 'start_year',
        min: 1900,
        max: 2100,
        label_format: '{year}-{next_year}学年{term_label}',
        term_labels: { '1': '第一学期', '2': '第二学期' },
      },
    })
    if (path === '/api/auth/me') return fulfillJson(route, USER)
    if (path === '/api/semester-context') return fulfillJson(route, {
      current_semester: semesterCreated ? SEMESTER : null,
      revision: 1,
      can_switch: false,
    })
    if (path === '/api/notifications/mine/unread-count') return fulfillJson(route, { unread: 0 })
    if (path === '/api/notifications/mine') return fulfillJson(route, { items: [], unread: 0 })
    if (path === '/api/semesters' && route.request().method() === 'POST') {
      semesterCreated = true
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(SEMESTER),
      })
    }
    if (path === '/api/semesters') return fulfillJson(route, semesterCreated ? [SEMESTER] : [])
    if (path === '/api/semesters/71') return fulfillJson(route, SEMESTER)
    if (path === '/api/semesters/71/period-setup') return fulfillJson(route, {
      fingerprint: 'a'.repeat(64),
      source: 'existing',
      classes: [{
        id: CLASS_UNIT.id,
        name: CLASS_UNIT.name,
        grade: CLASS_UNIT.grade,
        track: CLASS_UNIT.track,
        track_label: '初中',
        period_table_id: PERIOD_TABLE.id,
      }],
      groups: [{
        key: `table:${PERIOD_TABLE.id}`,
        table_id: PERIOD_TABLE.id,
        name: PERIOD_TABLE.name,
        num_weekdays: PERIOD_TABLE.num_weekdays,
        is_default: true,
        class_ids: [CLASS_UNIT.id],
        periods: [{
          period_no: 1,
          weekdays: [1],
          name: '第一节',
          type: 'regular',
          start_time: '08:00:00',
          end_time: '08:40:00',
        }],
      }],
      unresolved_class_ids: [],
      ready: true,
      blockers: [],
      warnings: [],
    })
    if (path === '/api/period-tables/91') return fulfillJson(route, PERIOD_TABLE)
    if (path === '/api/class-units') return fulfillJson(route, [CLASS_UNIT])
    if (path === '/api/teachers') return fulfillJson(route, [TEACHER])
    if (path === '/api/subjects') return fulfillJson(route, [SUBJECT])
    if (path === '/api/rooms') return fulfillJson(route, [])
    if (path === '/api/scheduling-units') return fulfillJson(route, [])
    if (path === '/api/assignments/teacher-load') return fulfillJson(route, [{
      teacher_id: 401,
      name: '陈老师',
      base_periods: 3,
      admin_reduction: 0,
      target: 3,
      assigned: 3,
      delta: 0,
      max_overtime: 2,
      over_limit: false,
    }])
    if (path === '/api/assignments/class-load') return fulfillJson(route, [{
      class_id: 301,
      name: '1班',
      grade: 7,
      assigned: 3,
      capacity: 5,
      over_capacity: false,
    }])
    if (path === '/api/assignments') return fulfillJson(route, [ASSIGNMENT])
    if (path === '/api/solver/preflight') return fulfillJson(route, PREFLIGHT)
    if (path === '/api/solver/relaxable') return fulfillJson(route, [])
    if (path === '/api/solver/config') return fulfillJson(route, {
      semester_id: 71,
      daily_subject_cap: 2,
      teacher_daily_max: 6,
      teacher_consecutive_max: 3,
      weights: {},
      weight_names: {},
    })
    if (path === '/api/timetables') return fulfillJson(route, [])

    return route.fulfill({
      status: 501,
      contentType: 'application/json',
      body: JSON.stringify({ detail: `未模拟 ${route.request().method()} ${path}` }),
    })
  })
}

function expectFlowLocation(page: Page, step?: string, table?: string) {
  return expect.poll(() => {
    const url = new URL(page.url())
    return {
      path: url.pathname,
      step: url.searchParams.get('step'),
      table: url.searchParams.get('table'),
    }
  }).toEqual({ path: '/scheduling/flow', step: step ?? null, table: table ?? null })
}

async function openStep(page: Page, step: string, visibleTestId: string) {
  await page.getByTestId(`flow-go-${step}`).click()
  await expectFlowLocation(page, step)
  await expect(page.getByTestId(visibleTestId)).toBeVisible()
  await page.getByTestId('flow-step-back').click()
  await expectFlowLocation(page)
}

async function expectNoRootOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth)
}

async function expectFlowUsesAvailableContentWidth(page: Page) {
  const dimensions = await page.getByTestId('scheduling-flow-page').evaluate((flowPage) => {
    const content = document.getElementById('main-content')
    if (!content) throw new Error('主内容容器不存在')

    const contentStyle = window.getComputedStyle(content)
    return {
      availableWidth: content.clientWidth
        - Number.parseFloat(contentStyle.paddingLeft)
        - Number.parseFloat(contentStyle.paddingRight),
      flowWidth: flowPage.getBoundingClientRect().width,
    }
  })

  expect(dimensions.flowWidth).toBeGreaterThanOrEqual(dimensions.availableWidth - 1)
  expect(dimensions.flowWidth).toBeLessThanOrEqual(dimensions.availableWidth + 1)
}

async function expectEmbeddedStepUsesWorkbenchWidth(page: Page, testId: string) {
  const dimensions = await page.getByTestId(testId).evaluate((stepPage) => {
    const workbench = stepPage.closest<HTMLElement>('[data-testid="flow-embedded-step"]')
    if (!workbench) throw new Error('排课工作台嵌入容器不存在')

    return {
      stepWidth: stepPage.getBoundingClientRect().width,
      workbenchWidth: workbench.getBoundingClientRect().width,
    }
  })

  expect(dimensions.stepWidth).toBeGreaterThanOrEqual(dimensions.workbenchWidth - 1)
  expect(dimensions.stepWidth).toBeLessThanOrEqual(dimensions.workbenchWidth + 1)
}

test('排课工作台在宽屏下占满主内容区', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 })
  await mockFlowApplication(page)
  await page.goto('/scheduling/flow')

  await expect(page.getByTestId('scheduling-flow-steps')).toBeVisible()
  await expectFlowUsesAvailableContentWidth(page)
})

test('排课工作台在当前工作台创建首个学期，不跳转到学期设置页', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await mockFlowApplication(page, { emptySemester: true })
  await page.goto('/scheduling/flow')

  await expect(page.getByTestId('flow-empty')).toBeVisible()
  await expectNoRootOverflow(page)
  await page.getByTestId('flow-semester-start-date').locator('input').fill('2045-09-01')
  await page.getByTestId('flow-semester-end-date').locator('input').fill('2046-01-20')
  await page.getByTestId('flow-semester-create').click()

  await expect.poll(() => new URL(page.url()).pathname).toBe('/scheduling/flow')
  await expect(page.getByTestId('flow-summary')).toBeVisible()
  await expect(page.getByTestId('semesters-page')).not.toBeVisible()
})

test('排课工作台的自动排课步骤在宽屏下占满工作台', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 })
  await mockFlowApplication(page)
  await page.goto('/scheduling/flow')

  await page.getByTestId('flow-go-start').click()
  await expect(page.getByTestId('auto-schedule-page')).toBeVisible()
  await expectNoRootOverflow(page)
  await expectEmbeddedStepUsesWorkbenchWidth(page, 'auto-schedule-page')
})

const responsiveViewports = [
  { label: '桌面', width: 1440, height: 900 },
  { label: '横向平板', width: 1024, height: 768 },
  { label: '纵向平板', width: 768, height: 1024 },
  { label: '手机', width: 375, height: 812 },
] as const

for (const viewport of responsiveViewports) {
  test(`排课工作台在${viewport.label}宽度下完整响应`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await mockFlowApplication(page)
    await page.goto('/scheduling/flow')

    await expect(page.getByTestId('scheduling-flow-steps')).toBeVisible()
    await expectNoRootOverflow(page)
    await expectFlowUsesAvailableContentWidth(page)

    await page.getByTestId('flow-go-start').click()
    await expect(page.getByTestId('auto-schedule-page')).toBeVisible()
    await expectNoRootOverflow(page)
    await expectEmbeddedStepUsesWorkbenchWidth(page, 'auto-schedule-page')
    await page.screenshot({ path: testInfo.outputPath(`scheduling-flow-${viewport.width}.png`), fullPage: true })
  })
}

test('排课工作台在同一路由内完成五步设置并可返回总览', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await mockFlowApplication(page)
  await page.goto('/scheduling/flow')

  await expect(page.getByTestId('scheduling-flow-steps')).toBeVisible()
  const navigation = page.getByTestId('shell-nav')
  await expect(navigation.locator('.app-nav-group').first()).toContainText('工作空间')
  await expect(navigation.locator('.app-nav-group').first()).toContainText('仪表盘')
  await expect(navigation.getByRole('link', { name: '排课工作台', exact: true })).toHaveAttribute('href', '/scheduling/flow')
  await expect(navigation.getByRole('link', { name: '基础数据', exact: true })).toBeVisible()
  await expect(page.getByTestId('flow-go-rooms')).toHaveCount(0)

  await openStep(page, 'classes', 'classes-table')

  await page.getByTestId('flow-go-periods').click()
  await expectFlowLocation(page, 'periods')
  await expect(page.getByTestId('period-setup-workspace')).toBeVisible()
  await page.getByTestId('period-group-open-detail').click()
  await expectFlowLocation(page, 'periods', '91')
  await expect(page.getByTestId('period-table-back')).toContainText('返回排课工作台')
  await page.getByTestId('period-table-back').click()
  await expectFlowLocation(page)

  await page.getByTestId('flow-go-subjects').click()
  await expectFlowLocation(page, 'subjects')
  await expect(page.getByTestId('assignment-table')).toBeVisible()
  await page.getByTestId('flow-subjects-archive').click()
  await expect(page.getByTestId('manual-common-subjects')).toBeVisible()
  await expect(page.getByTestId('subjects-table')).toBeVisible()
  await page.getByTestId('flow-subjects-work').click()
  await expect(page.getByTestId('assignment-table')).toBeVisible()
  await page.getByTestId('flow-step-back').click()
  await expectFlowLocation(page)

  await page.getByTestId('flow-go-teachers').click()
  await expectFlowLocation(page, 'teachers')
  await expect(page.getByTestId('assignment-table')).toBeVisible()
  await page.getByTestId('flow-teachers-archive').click()
  await expect(page.getByTestId('teachers-table')).toBeVisible()
  await page.getByTestId('flow-teachers-work').click()
  await expect(page.getByTestId('assignment-table')).toBeVisible()
  await page.getByTestId('flow-step-back').click()
  await expectFlowLocation(page)

  await openStep(page, 'start', 'auto-schedule-page')

  await expectNoRootOverflow(page)
  await page.screenshot({ path: testInfo.outputPath('scheduling-flow-desktop.png'), fullPage: true })
})

test('排课工作台在窄屏下不溢出且移动导航保留统一入口', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await mockFlowApplication(page)
  await page.goto('/scheduling/flow')

  await expect(page.getByTestId('scheduling-flow-steps')).toBeVisible()
  await expectNoRootOverflow(page)
  await page.getByTestId('shell-menu').click()
  await expect(page.getByTestId('mobile-drawer')).toBeVisible()
  await expect(page.getByTestId('shell-nav')).toContainText('工作空间')
  await expect(page.getByTestId('shell-nav').getByRole('link', { name: '排课工作台', exact: true })).toBeVisible()
  await page.getByTestId('shell-close').click()

  await page.getByTestId('flow-go-classes').click()
  await expectFlowLocation(page, 'classes')
  await expect(page.getByTestId('classes-table-scroll')).toBeVisible()
  await expectNoRootOverflow(page)
  await page.screenshot({ path: testInfo.outputPath('scheduling-flow-mobile.png'), fullPage: true })
})
