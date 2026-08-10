import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
  { width: 375, height: 812 },
] as const

const USER = {
  id: 7,
  username: 'responsive-user',
  display_name: '响应式验收用户',
  roles: ['scheduler'],
  must_change_password: false,
}

const APP_CONFIG = {
  school_name: '响应式验收学校',
  timezone: 'Asia/Shanghai',
  role_display_names: { scheduler: '排课管理员' },
  academic_year: {
    storage: 'start_year', min: 1900, max: 2100,
    label_format: '{year}-{next_year}学年{term_label}',
    term_labels: { '1': '第一学期', '2': '第二学期' },
  },
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

async function mockSurface(page: Page, surface: 'login' | 'change-password' | 'wizard' | 'dashboard') {
  await page.route('**/api/app-config', (route) => fulfillJson(route, APP_CONFIG))

  if (surface === 'login') {
    await page.route('**/api/auth/me', (route) => fulfillJson(route, { detail: '未登录' }, 401))
    return
  }

  const user = surface === 'change-password'
    ? { ...USER, must_change_password: true }
    : USER
  await page.route('**/api/auth/me', (route) => fulfillJson(route, user))

  if (surface === 'wizard') {
    await page.route('**/api/school-templates', (route) => fulfillJson(route, [{
      key: 'junior_high_draft', name: '初中（空白模板）', minutes_per_period: 40,
      subject_count: 13, editable: true,
    }]))
    await page.route('**/api/wizard/state', (route) => fulfillJson(route, {
      current_step: 0, completed: false, semester_id: null, total_steps: 5, has_semesters: false,
    }))
    await page.route('**/api/demo-data', (route) => fulfillJson(route, {
      available: false, reason: 'visual test', school_name: '',
    }))
    return
  }

  if (surface === 'dashboard') {
    await page.route('**/api/wizard/state', (route) => fulfillJson(route, {
      current_step: 4, completed: true, semester_id: 12, total_steps: 5, has_semesters: true,
    }))
    await page.route('**/api/semesters', (route) => fulfillJson(route, [{
      id: 12, academic_year: 2042, term: 1, label: '2042-2043学年第一学期',
      status: 'active', readiness: 'ready', start_date: null, end_date: null,
    }]))
    await page.route('**/api/semesters/12/summary', (route) => fulfillJson(route, {
      subjects: 13, teachers: 42, classes: 18, rooms: 9,
    }))
    await page.route('**/api/daily-board**', (route) => fulfillJson(route, {
      date: '2042-09-02', weekday: 2, school_name: '响应式验收学校',
      semester_label: '2042-2043学年第一学期', entries: [],
    }))
    await page.route('**/api/notifications/mine**', (route) => fulfillJson(route, {
      items: [], unread: 0,
    }))
  }
}

async function expectNoRootOverflow(page: Page) {
  const overflow = await page.evaluate(() => (
    document.documentElement.scrollWidth > document.documentElement.clientWidth
  ))
  expect(overflow).toBe(false)
}

async function expectVisibleFlow(page: Page, selectors: string[]) {
  const boxes = await Promise.all(selectors.map((selector) => page.locator(selector).boundingBox()))
  for (const [index, box] of boxes.entries()) {
    expect(box, `${selectors[index]} should have a layout box`).not.toBeNull()
    if (!box) continue
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.x + box.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1)
    if (index > 0 && boxes[index - 1]) {
      const previous = boxes[index - 1]!
      expect(box.y).toBeGreaterThanOrEqual(previous.y + previous.height - 1)
    }
  }
}

for (const viewport of VIEWPORTS) {
  test(`登录页 ${viewport.width}x${viewport.height} 保持可见且无溢出`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await mockSurface(page, 'login')
    await page.goto('/login')

    await expect(page.getByTestId('login-submit')).toBeVisible()
    await expect(page.getByPlaceholder('请输入账号')).toBeVisible()
    await expect(page.getByPlaceholder('请输入密码')).toBeVisible()
    await expectNoRootOverflow(page)
    await expectVisibleFlow(page, ['.auth-panel-header', '.auth-form', '.auth-note'])
  })

  test(`改密页 ${viewport.width}x${viewport.height} 保持可见且无溢出`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await mockSurface(page, 'change-password')
    await page.goto('/change-password')

    await expect(page.getByTestId('cp-forced')).toBeVisible()
    await expect(page.getByTestId('cp-submit')).toBeVisible()
    await expectNoRootOverflow(page)
    await expectVisibleFlow(page, ['.auth-panel-header', '.auth-callout', '.auth-form', '.auth-note'])
  })

  test(`设置向导 ${viewport.width}x${viewport.height} 保持五步控件可见`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await mockSurface(page, 'wizard')
    await page.goto('/wizard')

    await expect(page.getByRole('heading', { name: '设置向导' })).toBeVisible()
    await expect(page.getByTestId('wizard-step-title')).toHaveText('学制模板')
    await expect(page.getByTestId('wizard-next')).toBeVisible()
    await expectNoRootOverflow(page)
    await expectVisibleFlow(page, ['.wizard-header', '.wizard-progress', '.wizard-panel', '.wizard-actions'])
    const progressOverflow = await page.locator('.wizard-progress').evaluate((element) => (
      element.scrollWidth >= element.clientWidth
    ))
    expect(progressOverflow).toBe(true)
  })

  test(`仪表盘 ${viewport.width}x${viewport.height} 保持摘要与快捷入口可见`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await mockSurface(page, 'dashboard')
    await page.goto('/')

    await expect(page.getByTestId('dash-summary')).toBeVisible()
    await expect(page.getByTestId('dash-today')).toBeVisible()
    await expect(page.getByTestId('dash-shortcut-workbench')).toBeVisible()
    await expectNoRootOverflow(page)
    await expectVisibleFlow(page, ['.dashboard-header', '.dashboard-summary-panel', '.dashboard-today-panel', '.dashboard-shortcuts'])
  })
}
