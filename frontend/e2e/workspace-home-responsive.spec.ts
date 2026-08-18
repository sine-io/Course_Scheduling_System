import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'
import { login } from './helpers'

const VIEWPORTS = [
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
  { width: 375, height: 812 },
] as const

const USER = {
  id: 31,
  username: 'workspace-user',
  display_name: '张教务',
  roles: ['scheduler'],
  must_change_password: false,
}

const SEMESTER = {
  id: 18,
  academic_year: 2026,
  term: 1,
  label: '2026-2027学年第一学期',
  status: 'preparing',
  readiness: 'ready',
  start_date: '2026-08-01',
  end_date: '2027-01-20',
  is_current: true,
}

const OVERVIEW = {
  semester_id: 18,
  semester_label: SEMESTER.label,
  generated_at: '2026-08-17T06:26:00+00:00',
  metrics: {
    active_teacher_count: 86,
    class_count: 32,
    weekly_affected_periods: 9,
    week_start: '2026-08-17',
    week_end: '2026-08-23',
  },
  timetable: {
    id: 42,
    name: '秋季开学课表草稿',
    status: 'draft',
    updated_at: '2026-08-17T05:50:00+00:00',
    required_periods: 1180,
    placed_periods: 944,
    remaining_periods: 236,
    completion_rate: 80,
  },
  preflight: {
    available: true,
    error_count: 2,
    warning_count: 3,
    unavailable_message: '',
  },
  today_pending_periods: 4,
  unacknowledged_notifications: 7,
  focus_items: [
    {
      code: 'setup_blockers',
      title: '完成学期准备',
      description: '有 2 个班级没有可用的作息分组',
      tone: 'critical',
      target: 'wizard',
      count: 2,
    },
    {
      code: 'preflight_errors',
      title: '处理前置检查问题',
      description: '王老师每周教学任务为 28 节，可排时段只有 25 节',
      tone: 'critical',
      target: 'auto_schedule',
      count: 2,
    },
    {
      code: 'today_pending_periods',
      title: '处理今日调代课',
      description: '今日仍有受影响节次尚未设置处理方式。',
      tone: 'warning',
      target: 'substitutions',
      count: 4,
    },
    {
      code: 'remaining_periods',
      title: '继续完成课表',
      description: '秋季开学课表草稿仍有课时尚未排入。',
      tone: 'warning',
      target: 'workbench',
      count: 236,
    },
  ],
  recommendations: [
    {
      code: 'setup_warning:rooms_missing',
      title: '补充教室与场地',
      description: '尚未录入教室/场地，可稍后补充',
      tone: 'warning',
      target: 'basedata',
      count: null,
    },
    {
      code: 'setup_warning:teacher_accounts_missing',
      title: '绑定教师账号',
      description: '尚未绑定教师账号，可稍后在账号管理中处理',
      tone: 'warning',
      target: 'wizard',
      count: null,
    },
    {
      code: 'setup_warning:special_dates_missing',
      title: '登记特殊日期',
      description: '尚未登记停课或补课等特殊日期',
      tone: 'warning',
      target: 'calendar',
      count: null,
    },
    {
      code: 'preflight_warning:teacher_daily_load',
      title: '检查排课提醒',
      description: '部分教师的周课时分布较集中，请在生成方案后复核',
      tone: 'warning',
      target: 'auto_schedule',
      count: null,
    },
  ],
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

async function mockWorkspace(page: Page) {
  let authenticated = false
  await page.route('**/api/app-config', (route) => fulfillJson(route, {
    school_name: '明德实验学校',
    timezone: 'Asia/Shanghai',
    role_display_names: {
      admin: '系统管理员', director: '教务主任', scheduler: '排课管理员', teacher: '教师',
    },
    academic_year: {
      storage: 'start_year', min: 1900, max: 2100,
      label_format: '{year}-{next_year}学年{term_label}',
      term_labels: { '1': '第一学期', '2': '第二学期' },
    },
  }))
  await page.route('**/api/auth/login', (route) => {
    authenticated = true
    return fulfillJson(route, USER)
  })
  await page.route('**/api/auth/me', (route) => (
    authenticated
      ? fulfillJson(route, USER)
      : fulfillJson(route, { detail: 'Not authenticated' }, 401)
  ))
  await page.route('**/api/wizard/state', (route) => fulfillJson(route, {
    current_step: 3,
    resume_step: 3,
    completed: true,
    paused: false,
    semester_id: SEMESTER.id,
    total_steps: 4,
    has_semesters: true,
  }))
  await page.route('**/api/semester-context', (route) => fulfillJson(route, {
    current_semester: SEMESTER,
    revision: 2,
    can_switch: true,
  }))
  await page.route('**/api/semesters', (route) => fulfillJson(route, [SEMESTER]))
  await page.route('**/api/workspace-overview**', (route) => fulfillJson(route, OVERVIEW))
  await page.route('**/api/notifications/mine**', (route) => fulfillJson(route, {
    items: [], unread: 0,
  }))
  await page.route('**/api/semesters/18/summary', (route) => fulfillJson(route, {
    subjects: 14, teachers: 86, classes: 32, rooms: 20,
  }))
  await page.route('**/api/daily-board**', (route) => fulfillJson(route, {
    date: '2026-08-17',
    weekday: 1,
    school_name: '明德实验学校',
    semester_label: SEMESTER.label,
    entries: [],
  }))
}

async function expectNoSiblingOverlap(page: Page, selector: string) {
  const overlaps = await page.locator(selector).evaluateAll((elements) => {
    const boxes = elements.map((element) => element.getBoundingClientRect())
    const hits: Array<[number, number]> = []
    for (let left = 0; left < boxes.length; left += 1) {
      for (let right = left + 1; right < boxes.length; right += 1) {
        const a = boxes[left]
        const b = boxes[right]
        if (
          a.left < b.right - 1
          && a.right > b.left + 1
          && a.top < b.bottom - 1
          && a.bottom > b.top + 1
        ) hits.push([left, right])
      }
    }
    return hits
  })
  expect(overlaps).toEqual([])
}

for (const viewport of VIEWPORTS) {
  test(`工作空间首页 ${viewport.width}x${viewport.height} 无溢出、重叠且内容完整`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await mockWorkspace(page)
    await login(page, USER.username, 'password123')
    await page.goto('/workspace/home')

    await expect(page).toHaveURL(/\/workspace\/home$/)
    await expect(page.getByRole('heading', { name: '首页总览', level: 1 })).toBeVisible()
    await expect(page.getByTestId('overview-hero')).toBeVisible()
    await expect(page.locator('.workspace-metric')).toHaveCount(6)
    await expect(page.locator('.workspace-feature-link')).toHaveCount(5)
    await expect(page.locator('.workspace-focus-item')).toHaveCount(4)
    await expect(page.locator('.workspace-recommendation')).toHaveCount(4)

    const overflow = await page.evaluate(() => ({
      root: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      content: document.querySelector<HTMLElement>('.app-content')!.scrollWidth
        > document.querySelector<HTMLElement>('.app-content')!.clientWidth,
    }))
    expect(overflow).toEqual({ root: false, content: false })

    await expectNoSiblingOverlap(page, '.workspace-metric')
    await expectNoSiblingOverlap(page, '.workspace-dashboard-grid > .workspace-panel')
    await expectNoSiblingOverlap(page, '.workspace-recommendation')

    for (const target of [
      page.getByTestId('overview-refresh'),
      page.getByRole('link', { name: /查看排课进度/ }),
      page.getByTestId('overview-feature-assignments'),
      page.locator('.workspace-focus-item').first(),
      page.locator('.workspace-recommendation').last(),
    ]) {
      await target.scrollIntoViewIfNeeded()
      await expect(target).toBeVisible()
    }

    await page.locator('.app-content').evaluate((element) => {
      element.scrollTop = 0
    })
    await expect(page.getByRole('heading', { name: '首页总览', level: 1 })).toBeVisible()
    const screenshot = await page.screenshot({
      path: testInfo.outputPath(`workspace-home-${viewport.width}x${viewport.height}.png`),
    })
    expect(screenshot.byteLength).toBeGreaterThan(20_000)
  })
}
