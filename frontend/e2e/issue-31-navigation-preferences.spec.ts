import { expect, test } from '@playwright/test'
import { login } from './helpers'

test.describe('固定导航与仪表盘快捷入口', () => {
  test('侧栏不再提供个人常用配置或偏好请求', async ({ page }) => {
    const preferenceRequests: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('/api/navigation-preference')) preferenceRequests.push(request.url())
    })

    await login(page, 'e2e_scheduler', 'e2etest1234')
    await page.goto('/')

    await expect(page.getByTestId('shell-nav')).toBeVisible()
    await expect(page.getByTestId('nav-manage')).toHaveCount(0)
    await expect(page.getByTestId('nav-preferences')).toHaveCount(0)
    await expect(page.getByTestId('shell-nav')).not.toContainText('常用')
    await expect(page.getByTestId('shell-nav')).not.toContainText('完整功能')
    expect(preferenceRequests).toEqual([])
  })

  test('刷新后仪表盘快捷入口保持角色固定顺序', async ({ page }) => {
    await login(page, 'e2e_scheduler', 'e2etest1234')
    await page.goto('/')

    const shortcuts = page.locator('[data-testid^="dash-shortcut-"]')
    await expect(shortcuts).toHaveCount(3)
    await expect(shortcuts.nth(0)).toHaveAttribute('data-testid', 'dash-shortcut-workbench')
    await expect(shortcuts.nth(1)).toHaveAttribute('data-testid', 'dash-shortcut-assignments')
    await expect(shortcuts.nth(2)).toHaveAttribute('data-testid', 'dash-shortcut-daily-board')

    await page.reload()
    await expect(shortcuts).toHaveCount(3)
    await expect(shortcuts.nth(0)).toHaveAttribute('data-testid', 'dash-shortcut-workbench')
  })
})
