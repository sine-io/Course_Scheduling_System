import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'
import { browserApiRequest, login } from './helpers'

type RoleCase = {
  title: string
  username: string
  password: string
  before: string[]
  after?: string[]
}

const ROLE_CASES: RoleCase[] = [
  {
    title: '排课管理员',
    username: 'e2e_scheduler',
    password: 'e2etest1234',
    before: ['current-todo', 'assignments', 'auto-schedule', 'workbench', 'versions'],
    after: ['dashboard', 'timetable-query', 'daily-board', 'substitutions', 'versions'],
  },
  {
    title: '教务主任',
    username: 'e2e_director',
    password: 'e2edirector1234',
    before: ['dashboard', 'timetable-query', 'daily-board', 'versions', 'substitution-stats'],
  },
  {
    title: '教师',
    username: 'e2e_teacher',
    password: 'e2eteacher1234',
    before: ['timetable-query', 'leaves', 'notifications', 'substitution-stats-mine'],
  },
  {
    title: '系统管理员',
    username: 'e2e_admin',
    password: 'e2eadmin1234',
    before: ['dashboard', 'system', 'backup', 'account-permissions', 'help-guide'],
    after: ['dashboard', 'system', 'backup', 'account-permissions', 'timetable-query'],
  },
]

function onboardingStatus(firstSuccess: boolean) {
  return {
    first_success: firstSuccess,
    wizard_completed: true,
    current_semester: null,
    stages: [],
    p0_todos: firstSuccess ? [] : [{
      key: 'semester',
      label: '学期',
      complete: false,
      status: 'blocked',
      blocking_reason: '尚未创建正式当前学期。',
      next_action: {
        stage: 'semester',
        label: '创建正式学期',
        href: '/wizard',
        blocking_reason: '尚未创建正式当前学期。',
      },
      details: {},
    }],
    next_action: firstSuccess ? null : {
      stage: 'semester',
      label: '创建正式学期',
      href: '/wizard',
      blocking_reason: '尚未创建正式当前学期。',
    },
  }
}

async function mockOnboarding(page: Page, firstSuccess: () => boolean): Promise<void> {
  await page.route('**/api/onboarding/status', async (route: Route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(onboardingStatus(firstSuccess())),
    })
  })
}

async function commonKeys(page: Page): Promise<string[]> {
  return page.locator('.app-nav-common [data-nav-key]').evaluateAll((items) => (
    items.map((item) => item.getAttribute('data-nav-key') ?? '')
  ))
}

async function resetNavigationPreference(page: Page): Promise<void> {
  expect(await browserApiRequest(
    page,
    'PUT',
    '/api/navigation-preference',
    { fixed: [], recent: [] },
  )).toBe(200)
}

test.describe('Issue #30 阶段化角色导航', () => {
  for (const roleCase of ROLE_CASES) {
    test(`${roleCase.title}看到稳定的常用入口`, async ({ page }) => {
      let firstSuccess = false
      await mockOnboarding(page, () => firstSuccess)
      await login(page, roleCase.username, roleCase.password)
      await resetNavigationPreference(page)
      if (roleCase.username === 'e2e_scheduler' || roleCase.username === 'e2e_admin') {
        expect(await browserApiRequest(
          page,
          'PATCH',
          '/api/wizard/state',
          { completed: true },
        )).toBe(200)
      }
      await page.goto('/')

      await expect(page.locator('.app-nav-common [data-nav-key]')).toHaveCount(roleCase.before.length)
      expect(await commonKeys(page)).toEqual(roleCase.before)

      if (roleCase.after) {
        firstSuccess = true
        await page.reload()
        await expect(page.locator('.app-nav-common [data-nav-key]')).toHaveCount(roleCase.after.length)
        expect(await commonKeys(page)).toEqual(roleCase.after)
      }
    })
  }

  test('兼任排课管理员默认管理视角，同时保留本人事务入口', async ({ page }) => {
    await mockOnboarding(page, () => false)
    await login(page, 'e2e_scheduler_teacher', 'e2ecombined1234')
    await resetNavigationPreference(page)
    expect(await browserApiRequest(
      page,
      'PATCH',
      '/api/wizard/state',
      { completed: true },
    )).toBe(200)
    await page.goto('/')

    await expect(page.locator('.app-nav-common [data-nav-key]')).toHaveCount(5)
    expect((await commonKeys(page))[0]).toBe('current-todo')
    await expect(page.locator('.app-nav-catalog [data-nav-key="notifications"]')).toBeVisible()
    await expect(page.locator('.app-nav-catalog [data-nav-key="leaves"]')).toBeVisible()
  })

  test('排课管理员可以固定、排序并恢复常用入口', async ({ page }) => {
    await mockOnboarding(page, () => false)
    await login(page, 'e2e_scheduler', 'e2etest1234')
    await resetNavigationPreference(page)
    await page.goto('/')

    await page.getByTestId('nav-manage').click()
    await page.getByTestId('nav-choice-timetable-query').check()
    await page.getByTestId('nav-choice-notifications').check()
    await page.locator('.app-nav-fixed-item').nth(1).getByRole('button', { name: /上移/ }).click()
    await Promise.all([
      page.waitForResponse((response) => (
        response.url().includes('/api/navigation-preference')
        && response.request().method() === 'PUT'
      )),
      page.getByTestId('nav-save').click(),
    ])

    expect((await commonKeys(page)).slice(0, 2)).toEqual(['notifications', 'timetable-query'])
    await page.evaluate(() => window.localStorage.clear())
    await page.reload()
    await expect(page.locator('.app-nav-common [data-nav-key]').nth(0)).toHaveAttribute(
      'data-nav-key',
      'notifications',
    )
    await expect(page.locator('.app-nav-common [data-nav-key]').nth(1)).toHaveAttribute(
      'data-nav-key',
      'timetable-query',
    )
    expect((await commonKeys(page)).slice(0, 2)).toEqual(['notifications', 'timetable-query'])

    await page.getByTestId('nav-manage').click()
    await Promise.all([
      page.waitForResponse((response) => (
        response.url().includes('/api/navigation-preference')
        && response.request().method() === 'PUT'
      )),
      page.getByTestId('nav-reset').click(),
    ])
    await page.getByTestId('nav-preferences-close').click()
    await page.evaluate(() => window.localStorage.clear())
    await page.reload()
    await expect(page.locator('.app-nav-common [data-nav-key]')).toHaveCount(5)
    await expect(page.locator('.app-nav-common [data-nav-key]').nth(0)).toHaveAttribute(
      'data-nav-key',
      'current-todo',
    )
    expect(await commonKeys(page)).toEqual([
      'current-todo', 'assignments', 'auto-schedule', 'workbench', 'versions',
    ])
  })

  test('教师不能通过直达地址进入排课或系统页面，且当前学期明确只读', async ({ page }) => {
    await login(page, 'e2e_teacher', 'e2eteacher1234')
    await resetNavigationPreference(page)
    await page.goto('/scheduling/workbench')
    await expect(page).toHaveURL(/\/timetable-query$/)

    await page.goto('/settings/system')
    await expect(page).toHaveURL(/\/timetable-query$/)

    await page.goto('/notifications')
    await expect(page.getByRole('heading', { name: '通知', level: 1 })).toBeVisible()
    await expect(page.getByTestId('semester-access-mode')).toHaveText('只读')
  })

  test('阶段接口失败时仍显示可重试的待办状态', async ({ page }) => {
    await page.route('**/api/onboarding/status', async (route) => {
      await route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"暂不可用"}' })
    })
    await login(page, 'e2e_scheduler', 'e2etest1234')
    await resetNavigationPreference(page)
    await page.goto('/')

    await expect(page.getByTestId('shell-onboarding')).toContainText('首次成功阶段暂时无法读取')
    await expect(page.getByTestId('shell-onboarding-retry')).toBeVisible()
  })
})
