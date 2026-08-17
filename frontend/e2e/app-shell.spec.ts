import { expect, test } from '@playwright/test'
import { browserApiRequest, login } from './helpers'

const viewports = [
  { width: 1920, height: 1080, sidebarWidth: 228 },
  { width: 1280, height: 800, sidebarWidth: 228 },
  { width: 768, height: 1024, sidebarWidth: 64 },
] as const

test.describe('生产应用壳层', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
    expect(await browserApiRequest(
      page,
      'PATCH',
      '/api/wizard/state',
      { completed: true },
    )).toBe(200)
  })

  for (const viewport of viewports) {
    test(`${viewport.width}x${viewport.height} 使用稳定侧栏且页面不横向溢出`, async ({ page }) => {
      await page.setViewportSize(viewport)
      await page.goto('/')

      const shell = page.getByTestId('app-shell')
      const sidebar = page.getByTestId('mobile-drawer')
      await expect(shell).toBeVisible()
      await expect(sidebar).toBeVisible()
      await expect(page.getByTestId('product-identity')).toBeVisible()
      await expect(page.getByTestId('shell-breadcrumb')).toContainText(/仪表盘/)
      await expect(page.getByTestId('shell-school-context')).toBeVisible()
      await expect(page.getByTestId('semester-context')).toBeVisible()
      await expect(page.getByTestId('shell-help')).toBeVisible()
      await expect(page.getByTestId('shell-nav').locator('[data-nav-key]')).not.toHaveCount(0)
      await expect(page.locator('.app-topbar').getByRole('button', { name: /发布|删除|备份|恢复|权限/ })).toHaveCount(0)
      const helpResponse = await page.request.get('/docs/index.html')
      expect(helpResponse.ok()).toBe(true)
      await expect(page.getByTestId('shell-menu')).toBeHidden()
      await expect(page.getByTestId('shell-close')).toBeHidden()
      await expect(page.getByPlaceholder(/搜索/)).toHaveCount(0)

      const box = await sidebar.boundingBox()
      expect(box?.width).toBe(viewport.sidebarWidth)
      const hasRootOverflow = await page.evaluate(() => (
        document.documentElement.scrollWidth > document.documentElement.clientWidth
      ))
      expect(hasRootOverflow).toBe(false)
    })
  }

  test('375x812 使用可关闭且保留焦点的手机抽屉', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/')

    const menu = page.getByTestId('shell-menu')
    const drawer = page.getByTestId('mobile-drawer')
    const close = page.getByTestId('shell-close')
    await expect(menu).toBeVisible()
    await expect(drawer).toBeHidden()

    await menu.focus()
    const focusRing = await menu.evaluate((element) => {
      const style = getComputedStyle(element)
      return { style: style.outlineStyle, width: Number.parseFloat(style.outlineWidth) }
    })
    expect(focusRing.style).not.toBe('none')
    expect(focusRing.width).toBeGreaterThanOrEqual(2)

    await menu.click()
    await expect(drawer).toBeVisible()
    await expect(close).toBeFocused()
    await expect(page.locator('.app-main')).toHaveAttribute('inert', '')
    const transitionDuration = await drawer.evaluate((element) => (
      Number.parseFloat(getComputedStyle(element).transitionDuration) || 0
    ))
    expect(transitionDuration).toBeLessThanOrEqual(0.001)

    await page.keyboard.press('Escape')
    await expect(drawer).toBeHidden()
    await expect(menu).toBeFocused()

    await menu.click()
    await expect(drawer).toBeVisible()
    await expect(close).toBeFocused()
    const queryLink = drawer.locator('[data-nav-key="timetable-query"]').first()
    await queryLink.focus()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/timetable-query$/)
    await expect(menu).toBeFocused()

    await menu.click()
    await expect(close).toBeFocused()
    await page.getByTestId('shell-scrim').click({ position: { x: 370, y: 400 } })
    await expect(drawer).toBeHidden()

    const hasRootOverflow = await page.evaluate(() => (
      document.documentElement.scrollWidth > document.documentElement.clientWidth
    ))
    expect(hasRootOverflow).toBe(false)
  })
})
