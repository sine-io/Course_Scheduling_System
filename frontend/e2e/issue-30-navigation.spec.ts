import { expect, test } from '@playwright/test'
import { login } from './helpers'

type RoleCase = {
  title: string
  username: string
  password: string
  links: Array<{ label: string; href: string }>
  forbidden: string[]
}

const ROLE_CASES: RoleCase[] = [
  {
    title: '排课管理员',
    username: 'e2e_scheduler',
    password: 'e2etest1234',
    links: [
      { label: '仪表盘', href: '/' },
      { label: '教学任务', href: '/scheduling/assignments' },
      { label: '自动排课', href: '/scheduling/auto' },
      { label: '排课工作台', href: '/scheduling/workbench' },
      { label: '版本与发布', href: '/scheduling/versions' },
      { label: '通知', href: '/notifications' },
    ],
    forbidden: ['系统管理'],
  },
  {
    title: '教务主任',
    username: 'e2e_director',
    password: 'e2edirector1234',
    links: [
      { label: '仪表盘', href: '/' },
      { label: '课表查询', href: '/timetable-query' },
      { label: '今日看板', href: '/daily-board' },
      { label: '版本与发布', href: '/scheduling/versions' },
      { label: '代课课时统计', href: '/substitution-stats' },
    ],
    forbidden: ['系统管理'],
  },
  {
    title: '教师',
    username: 'e2e_teacher',
    password: 'e2eteacher1234',
    links: [
      { label: '仪表盘', href: '/' },
      { label: '课表查询', href: '/timetable-query' },
      { label: '请假登记', href: '/leaves' },
      { label: '通知', href: '/notifications' },
      { label: '我的代课课时', href: '/substitution-stats' },
    ],
    forbidden: ['排课工作台', '系统管理'],
  },
  {
    title: '系统管理员',
    username: 'e2e_admin',
    password: 'e2eadmin1234',
    links: [
      { label: '仪表盘', href: '/' },
      { label: '系统管理', href: '/settings/system' },
      { label: '备份恢复', href: '/settings/backup' },
      { label: '账号权限', href: '/settings/accounts' },
    ],
    forbidden: [],
  },
]

async function expectNavigationLink(page: Parameters<typeof login>[0], label: string, href: string) {
  const link = page.getByTestId('shell-nav').getByRole('link', { name: label, exact: true })
  await expect(link).toBeVisible()
  if (href) await expect(link).toHaveAttribute('href', href)
}

test.describe('角色导航与页面兼容', () => {
  for (const roleCase of ROLE_CASES) {
    test(`${roleCase.title}看到直接分组导航`, async ({ page }) => {
      await login(page, roleCase.username, roleCase.password)
      await page.goto('/')

      const nav = page.getByTestId('shell-nav')
      await expect(nav).toContainText('学期准备')
      await expect(nav).toContainText('日常运行')
      await expect(nav).not.toContainText('常用')
      await expect(nav).not.toContainText('完整功能')
      await expect(nav).not.toContainText('课表组件（演示）')
      await expect(page.getByTestId('nav-manage')).toHaveCount(0)
      for (const forbidden of roleCase.forbidden) {
        await expect(nav).not.toContainText(forbidden)
      }
      for (const link of roleCase.links) {
        await expectNavigationLink(page, link.label, link.href)
      }
    })
  }

  test('仪表盘快捷入口固定且随角色变化', async ({ page }) => {
    await login(page, 'e2e_teacher', 'e2eteacher1234')
    await page.goto('/')
    await expect(page.locator('[data-testid^="dash-shortcut-"]')).toHaveCount(3)
    await expect(page.getByTestId('dash-shortcut-timetable-query')).toBeVisible()
    await expect(page.getByTestId('dash-shortcut-leaves')).toBeVisible()
    await expect(page.getByTestId('dash-shortcut-notifications')).toBeVisible()
    await expect(page.getByRole('button', { name: /管理常用/ })).toHaveCount(0)
  })

  test('旧通知、演示和系统分区链接重定向到新页面', async ({ page }) => {
    await login(page, 'e2e_scheduler', 'e2etest1234')

    await page.goto('/notification-board')
    await expect(page).toHaveURL(/\/notifications\?view=board$/)

    await page.goto('/scheduling/timetable-demo')
    await expect(page).toHaveURL(/\/scheduling\/workbench$/)

    await page.request.post('/api/auth/logout')
    await login(page, 'e2e_admin', 'e2eadmin1234')
    await page.goto('/settings/system?section=backup')
    await expect(page).toHaveURL(/\/settings\/backup$/)
    await expect(page.getByRole('heading', { name: '备份恢复', level: 1 })).toBeVisible()
    await expect(page.getByTestId('backup-card')).toBeVisible()
    await expect(page.getByTestId('smtp-card')).toHaveCount(0)
    await page.goto('/settings/system?section=accounts')
    await expect(page).toHaveURL(/\/settings\/accounts$/)
    await expect(page.getByRole('heading', { name: '账号权限', level: 1 })).toBeVisible()
    await expect(page.getByTestId('accounts-card')).toBeVisible()
    await expect(page.getByTestId('backup-card')).toHaveCount(0)
  })
})
