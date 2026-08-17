import { expect, test } from '@playwright/test'
import type { Locator, Page, Route } from '@playwright/test'
import { login } from './helpers'

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
  { width: 375, height: 812 },
] as const

const FORCED_PASSWORD_USER = {
  id: 7,
  username: 'responsive-user',
  display_name: '响应式验收用户',
  roles: ['scheduler'],
  must_change_password: true,
}
const DASHBOARD_USER = {
  ...FORCED_PASSWORD_USER,
  must_change_password: false,
}
const DASHBOARD_SEMESTER = {
  id: 12,
  academic_year: 2042,
  term: 1,
  label: '2042-2043学年第一学期',
  status: 'active',
  readiness: 'ready',
  start_date: null,
  end_date: null,
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

async function mockSurfaceData(
  page: Page,
  surface: 'change-password' | 'wizard' | 'dashboard',
) {
  if (surface === 'change-password') {
    await page.route('**/api/auth/login', (route) => fulfillJson(route, FORCED_PASSWORD_USER))
    return
  }

  if (surface === 'wizard') {
    await page.route('**/api/wizard/state', (route) => fulfillJson(route, {
      current_step: 0, resume_step: 0, completed: false, paused: false,
      semester_id: null, total_steps: 4, has_semesters: false,
    }))
    return
  }

  if (surface === 'dashboard') {
    let authenticated = false
    await page.route('**/api/auth/login', (route) => {
      authenticated = true
      return fulfillJson(route, DASHBOARD_USER)
    })
    await page.route('**/api/auth/me', (route) => (
      authenticated
        ? fulfillJson(route, DASHBOARD_USER)
        : fulfillJson(route, { detail: 'Not authenticated' }, 401)
    ))
    await page.route('**/api/app-config', (route) => fulfillJson(route, {
      school_name: '响应式验收学校',
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
    await page.route('**/api/wizard/state', (route) => fulfillJson(route, {
      current_step: 3, resume_step: 3, completed: true, paused: false,
      semester_id: 12, total_steps: 4, has_semesters: true,
    }))
    await page.route('**/api/semester-context', (route) => fulfillJson(route, {
      current_semester: { ...DASHBOARD_SEMESTER, is_current: true },
      revision: 1,
      can_switch: true,
    }))
    await page.route('**/api/semesters', (route) => fulfillJson(route, [DASHBOARD_SEMESTER]))
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

async function expectVisibleFlow(page: Page, items: Array<{ name: string, locator: Locator }>) {
  const viewport = page.viewportSize()!
  const boxes = await Promise.all(items.map(({ locator }) => locator.boundingBox()))
  for (const [index, box] of boxes.entries()) {
    expect(box, `${items[index].name} should have a layout box`).not.toBeNull()
    if (!box) continue
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.x + box.width).toBeLessThanOrEqual(viewport.width + 1)
    if (index > 0 && boxes[index - 1]) {
      const previous = boxes[index - 1]!
      expect(box.y).toBeGreaterThanOrEqual(previous.y + previous.height - 1)
    }
  }

  for (const { name, locator } of items) {
    await locator.scrollIntoViewIfNeeded()
    const visibleBox = await locator.boundingBox()
    expect(visibleBox, `${name} should remain visible after scrolling`).not.toBeNull()
    if (!visibleBox) continue
    expect(visibleBox.y, `${name} should not be clipped above the viewport`).toBeGreaterThanOrEqual(-1)
    expect(
      visibleBox.y + visibleBox.height,
      `${name} should not be clipped below the viewport`,
    ).toBeLessThanOrEqual(viewport.height + 1)
  }
}

for (const viewport of VIEWPORTS) {
  test(`登录页 ${viewport.width}x${viewport.height} 保持可见且无溢出`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/login')

    await expect(page.getByTestId('login-submit')).toBeVisible()
    await expect(page.getByPlaceholder('请输入账号')).toBeVisible()
    await expect(page.getByPlaceholder('请输入密码')).toBeVisible()
    await expectNoRootOverflow(page)
    await expectVisibleFlow(page, [
      { name: '登录标题', locator: page.getByRole('heading', { name: '登录教务排课' }) },
      { name: '账号输入框', locator: page.getByPlaceholder('请输入账号') },
      { name: '密码输入框', locator: page.getByPlaceholder('请输入密码') },
      { name: '登录按钮', locator: page.getByTestId('login-submit') },
      { name: '安全提示', locator: page.getByText('请勿在公共设备上保存密码。') },
    ])
  })

  test(`改密页 ${viewport.width}x${viewport.height} 保持可见且无溢出`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await mockSurfaceData(page, 'change-password')
    await login(page)

    await expect(page).toHaveURL(/\/change-password$/)
    await expect(page.getByTestId('cp-forced')).toBeVisible()
    await expect(page.getByTestId('cp-submit')).toBeVisible()
    await expectNoRootOverflow(page)
    await expectVisibleFlow(page, [
      { name: '改密标题', locator: page.getByRole('heading', { name: '修改密码' }) },
      { name: '强制改密提示', locator: page.getByTestId('cp-forced') },
      { name: '原密码输入框', locator: page.getByPlaceholder('请输入原密码') },
      { name: '新密码输入框', locator: page.getByPlaceholder('请输入新密码') },
      { name: '确认密码输入框', locator: page.getByPlaceholder('请再次输入新密码') },
      { name: '确认修改按钮', locator: page.getByTestId('cp-submit') },
    ])
  })

  test(`设置向导 ${viewport.width}x${viewport.height} 保持四步控件可见`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await mockSurfaceData(page, 'wizard')
    await login(page)

    await expect(page).toHaveURL(/\/wizard$/)
    await expect(page.getByRole('heading', { name: '设置向导' })).toBeVisible()
    await expect(page.getByTestId('wizard-step-title')).toHaveText('学校与学期')
    await expect(page.getByTestId('wizard-next')).toBeVisible()
    await expectNoRootOverflow(page)
    await expectVisibleFlow(page, [
      { name: '向导标题', locator: page.getByRole('heading', { name: '设置向导' }) },
      { name: '设置步骤', locator: page.getByRole('navigation', { name: '设置步骤' }) },
      { name: '当前步骤标题', locator: page.getByTestId('wizard-step-title') },
      { name: '下一步按钮', locator: page.getByTestId('wizard-next') },
    ])
  })

  test(`仪表盘 ${viewport.width}x${viewport.height} 保持摘要与快捷入口可见`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await mockSurfaceData(page, 'dashboard')
    await login(page)

    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByTestId('dash-summary')).toBeVisible()
    await expect(page.getByTestId('dash-today')).toBeVisible()
    await expect(page.getByTestId('dash-shortcut-workbench')).toBeVisible()
    await expectNoRootOverflow(page)
    await expectVisibleFlow(page, [
      { name: '仪表盘标题', locator: page.getByRole('heading', { name: '仪表盘' }) },
      { name: '学期摘要', locator: page.getByTestId('dash-summary') },
      { name: '今日运行', locator: page.getByTestId('dash-today') },
      { name: '排课工作台快捷入口', locator: page.getByTestId('dash-shortcut-workbench') },
    ])
  })
}
