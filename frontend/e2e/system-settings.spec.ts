import { expect, test } from '@playwright/test'
import { login } from './helpers'

const SHOTS = 'e2e/screenshots'

/**
 * 系统管理页的回归测试。
 *
 * 这一页先前**完全没有 e2e 覆盖**,于是一个致命 bug 一路上了 v1.0.0 与 v1.1.0:
 * `System.vue` 调用 `useDialog()`,但 `App.vue` 没有挂 `<n-dialog-provider>`——
 * Naive 会在 setup 直接抛出异常,整页渲染不出来(侧边菜单还在,内容区一片空白)。
 * 也就是说备份、恢复、SMTP、重设向导这四件事,用户根本点不进去。
 *
 * 因此本测试的第一个断言(卡片看得到)就是核心:页面只要 setup 抛出异常(或错误路由加载),必红。
 */
test('系统管理与备份恢复页面可独立打开并完成备份操作', async ({ page }) => {
  test.setTimeout(120_000)
  await login(page, 'e2e_admin', 'e2eadmin1234')

  await page.goto('/settings/system')
  await expect(page.getByRole('heading', { name: '系统管理' })).toBeVisible()

  // 系统配置页只显示系统配置职责
  await expect(page.getByTestId('smtp-status')).toBeVisible()
  await expect(page.getByTestId('backup-card')).toHaveCount(0)
  await expect(page.getByText('重新启动设置向导')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/system-1-page.png` })

  await page.getByRole('link', { name: '备份恢复' }).click()
  await expect(page.getByRole('heading', { name: '备份恢复' })).toBeVisible()
  await expect(page).toHaveURL(/\/settings\/backup$/)
  await expect(page.getByTestId('backup-card')).toBeVisible()

  // 立即备份 → 列表多一列(这条路径会打到 worker-ops 的 pg_dump)
  const rows = page.getByTestId('backup-row')
  const before = await rows.count()
  await page.getByTestId('backup-now').click()
  await page.getByRole('button', { name: '确认' }).click()
  await expect(page.getByText('备份已创建')).toBeVisible({ timeout: 60_000 })
  await expect(rows).toHaveCount(before + 1)
  await page.screenshot({ path: `${SHOTS}/system-2-backup.png` })

  // 删除刚才那份,不留垃圾(最新的在最上面)
  await rows.first().getByRole('button', { name: '删除' }).click()
  await page.getByRole('button', { name: '确认' }).click()
  await expect(page.getByText('备份已删除')).toBeVisible()
  await expect(rows).toHaveCount(before)

  await page.getByRole('link', { name: '账号权限' }).click()
  await expect(page).toHaveURL(/\/settings\/accounts$/)
  await expect(page.getByRole('heading', { name: '账号权限' })).toBeVisible()
  await expect(page.getByTestId('accounts-card')).toBeVisible()
})

test('操作审计支持服务器分页、URL 深链与窄屏操作', async ({ page }) => {
  await login(page, 'e2e_admin', 'e2eadmin1234')

  const auditLogs = Array.from({ length: 45 }, (_, index) => {
    const id = 45 - index
    return {
      id,
      operation_id: null,
      username: `audit-user-${id}`,
      actor_roles: ['admin'],
      action: id % 2 ? 'publish_timetable' : 'create_backup',
      target_type: id % 2 ? 'timetable' : 'backup',
      target_id: id,
      semester_id: null,
      target_version: '',
      result: 'success',
      reason: '',
      detail: `审计分页记录 ${id}`,
      created_at: new Date(Date.UTC(2026, 7, 17, 8, id % 60)).toISOString(),
    }
  })

  await page.route('**/api/audit-logs?*', async (route) => {
    const url = new URL(route.request().url())
    const requestedPage = Number(url.searchParams.get('page') ?? '1')
    const pageSize = Number(url.searchParams.get('page_size') ?? '20')
    const query = (url.searchParams.get('q') ?? '').trim().toLowerCase()
    const filtered = query
      ? auditLogs.filter((log) => [log.username, log.action, log.detail]
          .some((value) => value.toLowerCase().includes(query)))
      : auditLogs
    const start = (requestedPage - 1) * pageSize
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: filtered.slice(start, start + pageSize),
        total: filtered.length,
        page: requestedPage,
        page_size: pageSize,
      }),
    })
  })

  await page.goto('/settings/system?audit_page=2&audit_page_size=20')
  const auditCard = page.getByTestId('audit-card')
  const controls = page.getByTestId('audit-pagination-controls')
  await expect(page.getByTestId('audit-pagination-total')).toHaveText('共 45 条')
  await expect(page.getByTestId('audit-row')).toHaveCount(20)
  await expect(page.getByTestId('audit-row').first()).toContainText('audit-user-25')
  await expect(auditCard).toBeInViewport()
  await auditCard.screenshot({ path: `${SHOTS}/audit-pagination-desktop.png` })

  await controls.locator('.n-pagination-item--clickable').filter({ hasText: /^3$/ }).click()
  await expect(page).toHaveURL(/audit_page=3/)
  await expect(page.getByTestId('audit-row')).toHaveCount(5)

  const quickJumper = controls.locator('.n-pagination-quick-jumper input')
  await quickJumper.fill('1')
  await quickJumper.press('Enter')
  await expect(page).toHaveURL(/audit_page=1/)
  await expect(page.getByTestId('audit-row').first()).toContainText('audit-user-45')

  await controls.locator('.n-base-selection').click()
  await page.getByText('50 / 页', { exact: true }).click()
  await expect(page).toHaveURL(/audit_page_size=50/)
  await expect(page.getByTestId('audit-row')).toHaveCount(45)

  const searchRequest = page.waitForRequest((request) => {
    const url = new URL(request.url())
    return url.pathname === '/api/audit-logs' && url.searchParams.get('q') === 'audit-user-7'
  })
  await page.getByTestId('audit-search').locator('input').fill('audit-user-7')
  await searchRequest
  await expect(page).toHaveURL(/audit_q=audit-user-7/)
  await expect(page).toHaveURL(/audit_page=1/)
  await expect(page.getByTestId('audit-row')).toHaveCount(1)
  await expect(page.getByTestId('audit-row')).toContainText('audit-user-7')

  await page.setViewportSize({ width: 390, height: 844 })
  await auditCard.scrollIntoViewIfNeeded()
  await expect(controls).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await auditCard.screenshot({ path: `${SHOTS}/audit-pagination-mobile.png` })

  await page.setViewportSize({ width: 320, height: 844 })
  await auditCard.scrollIntoViewIfNeeded()
  await expect(controls).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})
