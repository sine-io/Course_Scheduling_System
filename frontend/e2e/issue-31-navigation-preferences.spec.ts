import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { browserApiRequest, login } from './helpers'
import { expectCommonNavigation } from './navigation-assertions'

const SCHEDULER_AFTER_FIRST_SUCCESS = [
  { label: '仪表盘', href: '/' },
  { label: '课表查询', href: '/timetable-query' },
  { label: '今日看板', href: '/daily-board' },
  { label: '调课与代课', href: '/substitutions' },
  { label: '版本与发布', href: '/scheduling/versions' },
]

const SCHEDULER_BEFORE_FIRST_SUCCESS = [
  { label: '当前待办', href: '/wizard' },
  { label: '教学任务', href: '/scheduling/assignments' },
  { label: '自动排课', href: '/scheduling/auto' },
  { label: '排课工作台', href: '/scheduling/workbench' },
  { label: '版本与发布', href: '/scheduling/versions' },
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

    await expectCommonNavigation(page, SCHEDULER_AFTER_FIRST_SUCCESS)
    await page.getByRole('button', { name: '管理常用入口' }).click()
    await expect(page.getByRole('checkbox', { name: /^当前待办/ })).toHaveCount(0)
    await expect(page.getByText('尚未固定，当前使用角色默认入口。')).toBeVisible()
  })

  test('阶段未知时忽略阶段专属入口且保留可用入口', async ({ page }) => {
    await mockOnboardingFailure(page)
    await login(page, 'e2e_scheduler', 'e2etest1234')
    await putPreference(page, ['current-todo'])

    await reloadWithoutLocalPreference(page)

    await expect(page.getByTestId('shell-onboarding')).toContainText('首次成功阶段暂时无法读取')
    await expectCommonNavigation(page, [
      { label: '教学任务', href: '/scheduling/assignments' },
      { label: '自动排课', href: '/scheduling/auto' },
      { label: '排课工作台', href: '/scheduling/workbench' },
      { label: '版本与发布', href: '/scheduling/versions' },
    ])
  })

  test('固定、取消固定和排序在刷新及重新登录后保持，并可恢复阶段默认', async ({ page }) => {
    await mockOnboarding(page, false)
    await login(page, 'e2e_scheduler', 'e2etest1234')
    await putPreference(page, [])
    await reloadWithoutLocalPreference(page)

    await page.getByRole('button', { name: '管理常用入口' }).click()
    await page.getByRole('checkbox', { name: /^课表查询/ }).check()
    await page.getByRole('checkbox', {
      name: '通知 阅读通知并确认本人收到的消息。',
      exact: true,
    }).check()
    await page.getByRole('button', { name: '将通知上移' }).click()
    await page.getByRole('button', { name: '保存', exact: true }).click()
    const pinned = [
      { label: '通知', href: '/notifications' },
      { label: '课表查询', href: '/timetable-query' },
    ]
    await expectCommonNavigation(page, pinned, false)

    await reloadWithoutLocalPreference(page)
    await expectCommonNavigation(page, pinned, false)
    await page.getByTestId('shell-logout').click()
    await expect(page).toHaveURL(/\/login$/)
    await login(page, 'e2e_scheduler', 'e2etest1234')
    await expectCommonNavigation(page, pinned, false)

    await page.getByRole('button', { name: '管理常用入口' }).click()
    await page.getByRole('checkbox', {
      name: '通知 阅读通知并确认本人收到的消息。',
      exact: true,
    }).uncheck()
    await page.getByRole('button', { name: '保存', exact: true }).click()
    await expectCommonNavigation(page, [{ label: '课表查询', href: '/timetable-query' }], false)
    const common = page.getByRole('region', { name: '常用' })
    await expect(common.getByRole('link', { name: '通知', exact: true })).toHaveCount(0)

    await page.getByRole('button', { name: '管理常用入口' }).click()
    await page.getByRole('button', { name: '恢复默认' }).click()
    await page.getByRole('button', { name: '关闭常用入口设置' }).click()
    await expectCommonNavigation(page, SCHEDULER_BEFORE_FIRST_SUCCESS)
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

    await expectCommonNavigation(page, [
      { label: '通知', href: '/notifications' },
      { label: '当前待办', href: '/wizard' },
      { label: '教学任务', href: '/scheduling/assignments' },
      { label: '自动排课', href: '/scheduling/auto' },
      { label: '排课工作台', href: '/scheduling/workbench' },
    ])
    const common = page.getByRole('region', { name: '常用' })
    await expect(common.getByRole('link', { name: '系统管理', exact: true })).toHaveCount(0)
    await expect(common.getByRole('link', { name: '账号权限', exact: true })).toHaveCount(0)
  })

  test('多角色账号使用管理视角且保留本人事务入口', async ({ page }) => {
    await mockOnboarding(page, false)
    await login(page, 'e2e_scheduler_teacher', 'e2ecombined1234')
    await putPreference(page, ['notifications', 'leaves'])

    await reloadWithoutLocalPreference(page)

    await expectCommonNavigation(page, [
      { label: '通知', href: '/notifications' },
      { label: '请假登记', href: '/leaves' },
      { label: '当前待办', href: '/wizard' },
      { label: '教学任务', href: '/scheduling/assignments' },
      { label: '自动排课', href: '/scheduling/auto' },
    ])
    const dailyOperations = page.getByRole('region', { name: '日常运行' })
    await expect(dailyOperations.getByRole('link', { name: '通知', exact: true })).toHaveAttribute(
      'href',
      '/notifications',
    )
    await expect(dailyOperations.getByRole('link', { name: '请假登记', exact: true })).toHaveAttribute(
      'href',
      '/leaves',
    )
    await expect(
      page.getByRole('region', { name: '排课主流程' })
        .getByRole('link', { name: '排课工作台', exact: true }),
    ).toHaveAttribute('href', '/scheduling/workbench')
  })
})
