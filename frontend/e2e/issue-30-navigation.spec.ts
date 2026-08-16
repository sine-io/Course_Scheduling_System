import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'
import { browserApiRequest, login } from './helpers'
import { expectCommonNavigation } from './navigation-assertions'
import type { ExpectedNavigationLink } from './navigation-assertions'

type RoleCase = {
  title: string
  username: string
  password: string
  before: ExpectedNavigationLink[]
  after?: ExpectedNavigationLink[]
}

const ROLE_CASES: RoleCase[] = [
  {
    title: '排课管理员',
    username: 'e2e_scheduler',
    password: 'e2etest1234',
    before: [
      { label: '当前待办', href: '/wizard' },
      { label: '教学任务', href: '/scheduling/assignments' },
      { label: '自动排课', href: '/scheduling/auto' },
      { label: '排课工作台', href: '/scheduling/workbench' },
      { label: '版本与发布', href: '/scheduling/versions' },
    ],
    after: [
      { label: '仪表盘', href: '/' },
      { label: '课表查询', href: '/timetable-query' },
      { label: '今日看板', href: '/daily-board' },
      { label: '调课与代课', href: '/substitutions' },
      { label: '版本与发布', href: '/scheduling/versions' },
    ],
  },
  {
    title: '教务主任',
    username: 'e2e_director',
    password: 'e2edirector1234',
    before: [
      { label: '仪表盘', href: '/' },
      { label: '课表查询', href: '/timetable-query' },
      { label: '今日看板', href: '/daily-board' },
      { label: '版本与发布', href: '/scheduling/versions' },
      { label: '代课课时统计', href: '/substitution-stats' },
    ],
  },
  {
    title: '教师',
    username: 'e2e_teacher',
    password: 'e2eteacher1234',
    before: [
      { label: '课表查询', href: '/timetable-query' },
      { label: '请假登记', href: '/leaves' },
      { label: '通知', href: '/notifications' },
      { label: '我的代课课时', href: '/substitution-stats' },
    ],
  },
  {
    title: '系统管理员',
    username: 'e2e_admin',
    password: 'e2eadmin1234',
    before: [
      { label: '仪表盘', href: '/' },
      { label: '系统管理', href: '/settings/system' },
      { label: '备份恢复', href: '/settings/system?section=backup' },
      { label: '账号权限', href: '/settings/system?section=accounts' },
      { label: '上手指南', href: '/wizard' },
    ],
    after: [
      { label: '仪表盘', href: '/' },
      { label: '系统管理', href: '/settings/system' },
      { label: '备份恢复', href: '/settings/system?section=backup' },
      { label: '账号权限', href: '/settings/system?section=accounts' },
      { label: '课表查询', href: '/timetable-query' },
    ],
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

      await expectCommonNavigation(page, roleCase.before)
      if (roleCase.username === 'e2e_director') {
        await expect(page.getByTestId('shell-onboarding')).toHaveCount(0)
        await expect(page.getByTestId('onboarding-status')).toHaveCount(0)
      }

      if (roleCase.after) {
        firstSuccess = true
        await page.reload()
        await expectCommonNavigation(page, roleCase.after)
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

    await expectCommonNavigation(page, ROLE_CASES[0].before)
    const dailyOperations = page.getByRole('region', { name: '日常运行' })
    await expect(dailyOperations.getByRole('link', { name: '通知', exact: true })).toHaveAttribute(
      'href',
      '/notifications',
    )
    await expect(dailyOperations.getByRole('link', { name: '请假登记', exact: true })).toHaveAttribute(
      'href',
      '/leaves',
    )
  })

  test('排课管理员可以固定、排序并恢复常用入口', async ({ page }) => {
    await mockOnboarding(page, () => false)
    await login(page, 'e2e_scheduler', 'e2etest1234')
    await resetNavigationPreference(page)
    await page.goto('/')

    await page.getByRole('button', { name: '管理常用入口' }).click()
    await page.getByRole('checkbox', { name: /^课表查询/ }).check()
    await page.getByRole('checkbox', {
      name: '通知 阅读通知并确认本人收到的消息。',
      exact: true,
    }).check()
    await page.getByRole('button', { name: '将通知上移' }).click()
    await Promise.all([
      page.waitForResponse((response) => (
        response.url().includes('/api/navigation-preference')
        && response.request().method() === 'PUT'
      )),
      page.getByRole('button', { name: '保存', exact: true }).click(),
    ])

    const pinned = [
      { label: '通知', href: '/notifications' },
      { label: '课表查询', href: '/timetable-query' },
    ]
    await expectCommonNavigation(page, pinned, false)
    await page.evaluate(() => window.localStorage.clear())
    await page.reload()
    await expectCommonNavigation(page, pinned, false)

    await page.getByRole('button', { name: '管理常用入口' }).click()
    await Promise.all([
      page.waitForResponse((response) => (
        response.url().includes('/api/navigation-preference')
        && response.request().method() === 'PUT'
      )),
      page.getByRole('button', { name: '恢复默认' }).click(),
    ])
    await page.getByRole('button', { name: '关闭常用入口设置' }).click()
    await page.evaluate(() => window.localStorage.clear())
    await page.reload()
    await expectCommonNavigation(page, ROLE_CASES[0].before)
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
