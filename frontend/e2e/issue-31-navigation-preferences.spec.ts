import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { browserApiRequest, login } from './helpers'

const SCHEDULER_AFTER_FIRST_SUCCESS = [
  'dashboard',
  'timetable-query',
  'daily-board',
  'substitutions',
  'versions',
]

const SCHEDULER_BEFORE_FIRST_SUCCESS = [
  'current-todo',
  'assignments',
  'auto-schedule',
  'workbench',
  'versions',
]

async function mockOnboarding(page: Page, firstSuccess: boolean): Promise<void> {
  await page.route('**/api/onboarding/status', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
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
      }),
    })
  })
}

async function mockOnboardingFailure(page: Page): Promise<void> {
  await page.route('**/api/onboarding/status', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: '暂不可用' }),
    })
  })
}

async function commonKeys(page: Page): Promise<string[]> {
  const items = page.locator('.app-nav-common [data-nav-key]')
  await expect(items.first()).toBeVisible()
  return items.evaluateAll((items) => (
    items.map((item) => item.getAttribute('data-nav-key') ?? '')
  ))
}

async function putPreference(
  page: Page,
  fixed: string[],
  recent: string[] = [],
): Promise<void> {
  expect(await browserApiRequest(
    page,
    'PUT',
    '/api/navigation-preference',
    { fixed, recent },
  )).toBe(200)
}

async function reloadWithoutLocalPreference(page: Page): Promise<void> {
  await page.evaluate(() => window.localStorage.clear())
  await page.reload()
}

test.describe('Issue #31 常用入口个人偏好', () => {
  test('阶段切换后安全忽略已失效的固定入口', async ({ page }) => {
    await mockOnboarding(page, true)
    await login(page, 'e2e_scheduler', 'e2etest1234')
    await putPreference(page, ['current-todo'])

    await reloadWithoutLocalPreference(page)

    await expect(page.locator('.app-nav-common [data-nav-key]')).toHaveCount(5)
    expect(await commonKeys(page)).toEqual(SCHEDULER_AFTER_FIRST_SUCCESS)
    await page.getByTestId('nav-manage').click()
    await expect(page.getByTestId('nav-choice-current-todo')).toHaveCount(0)
    await expect(page.locator('.app-nav-fixed-item')).toHaveCount(0)
  })

  test('阶段未知时忽略阶段专属入口且保留可用入口', async ({ page }) => {
    await mockOnboardingFailure(page)
    await login(page, 'e2e_scheduler', 'e2etest1234')
    await putPreference(page, ['current-todo'])

    await reloadWithoutLocalPreference(page)

    await expect(page.getByTestId('shell-onboarding')).toContainText('首次成功阶段暂时无法读取')
    await expect(page.locator('.app-nav-common [data-nav-key="current-todo"]')).toHaveCount(0)
    await expect(page.locator('.app-nav-common [data-nav-key]')).toHaveCount(4)
    expect(await commonKeys(page)).toEqual([
      'assignments',
      'auto-schedule',
      'workbench',
      'versions',
    ])
  })

  test('固定、取消固定和排序在刷新及重新登录后保持，并可恢复阶段默认', async ({ page }) => {
    await mockOnboarding(page, false)
    await login(page, 'e2e_scheduler', 'e2etest1234')
    await putPreference(page, [])
    await reloadWithoutLocalPreference(page)

    await page.getByTestId('nav-manage').click()
    await page.getByTestId('nav-choice-timetable-query').check()
    await page.getByTestId('nav-choice-notifications').check()
    await page.locator('.app-nav-fixed-item').nth(1).getByRole('button', { name: /上移/ }).click()
    await page.getByTestId('nav-save').click()
    await expect(page.locator('.app-nav-common [data-nav-key]').nth(0)).toHaveAttribute(
      'data-nav-key',
      'notifications',
    )
    expect((await commonKeys(page)).slice(0, 2)).toEqual(['notifications', 'timetable-query'])

    await reloadWithoutLocalPreference(page)
    expect((await commonKeys(page)).slice(0, 2)).toEqual(['notifications', 'timetable-query'])
    await page.getByTestId('shell-logout').click()
    await expect(page).toHaveURL(/\/login$/)
    await login(page, 'e2e_scheduler', 'e2etest1234')
    expect((await commonKeys(page)).slice(0, 2)).toEqual(['notifications', 'timetable-query'])

    await page.getByTestId('nav-manage').click()
    await page.getByTestId('nav-choice-notifications').uncheck()
    await page.getByTestId('nav-save').click()
    await expect(page.locator('.app-nav-common [data-nav-key]').nth(0)).toHaveAttribute(
      'data-nav-key',
      'timetable-query',
    )
    expect(await commonKeys(page)).not.toContain('notifications')

    await page.getByTestId('nav-manage').click()
    await page.getByTestId('nav-reset').click()
    await page.getByTestId('nav-preferences-close').click()
    expect(await commonKeys(page)).toEqual(SCHEDULER_BEFORE_FIRST_SUCCESS)
  })

  test('无权限和已删除入口被忽略，最近访问不覆盖阶段推荐', async ({ page }) => {
    await mockOnboarding(page, false)
    await login(page, 'e2e_scheduler', 'e2etest1234')
    await putPreference(
      page,
      ['removed-entry', 'system', 'notifications'],
      ['account-permissions', 'timetable-query'],
    )

    await reloadWithoutLocalPreference(page)

    expect(await commonKeys(page)).toEqual([
      'notifications',
      'current-todo',
      'assignments',
      'auto-schedule',
      'workbench',
    ])
    await expect(page.locator('.app-nav-common [data-nav-key="removed-entry"]')).toHaveCount(0)
    await expect(page.locator('.app-nav-common [data-nav-key="system"]')).toHaveCount(0)
    await expect(page.locator('.app-nav-common [data-nav-key="account-permissions"]')).toHaveCount(0)
    await expect(page.locator('.app-nav-common a[href=""]')).toHaveCount(0)
  })

  test('多角色账号使用管理视角且保留本人事务入口', async ({ page }) => {
    await mockOnboarding(page, false)
    await login(page, 'e2e_scheduler_teacher', 'e2ecombined1234')
    await putPreference(page, ['notifications', 'leaves'])

    await reloadWithoutLocalPreference(page)

    expect(await commonKeys(page)).toEqual([
      'notifications',
      'leaves',
      'current-todo',
      'assignments',
      'auto-schedule',
    ])
    await expect(page.locator('.app-nav-catalog [data-nav-key="notifications"]')).toBeVisible()
    await expect(page.locator('.app-nav-catalog [data-nav-key="leaves"]')).toBeVisible()
    await expect(page.locator('.app-nav-catalog [data-nav-key="workbench"]')).toBeVisible()
  })
})
