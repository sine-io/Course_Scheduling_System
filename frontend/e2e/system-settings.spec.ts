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
 * 因此本测试的第一个断言(卡片看得到)就是核心:页面只要 setup 抛出异常就是全白,必红。
 */
test('系统管理:三张卡片渲染、可立即备份并删除备份', async ({ page }) => {
  test.setTimeout(120_000)
  await login(page, 'e2e_admin', 'e2eadmin1234')

  await page.goto('/settings/system')
  await expect(page.getByRole('heading', { name: '系统管理' })).toBeVisible()

  // setup 若抛出异常(缺 dialog provider),以下三张卡片一张都不会出现
  await expect(page.getByTestId('smtp-status')).toBeVisible()
  await expect(page.getByTestId('backup-card')).toBeVisible()
  await expect(page.getByText('重新启动设置向导')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/system-1-page.png` })

  // 立即备份 → 列表多一列(这条路径会打到 worker-ops 的 pg_dump)
  const rows = page.getByTestId('backup-row')
  const before = await rows.count()
  await page.getByTestId('backup-now').click()
  await expect(page.getByText('备份已创建')).toBeVisible({ timeout: 60_000 })
  await expect(rows).toHaveCount(before + 1)
  await page.screenshot({ path: `${SHOTS}/system-2-backup.png` })

  // 删除刚才那份,不留垃圾(最新的在最上面)
  await rows.first().getByRole('button', { name: '删除' }).click()
  await page.getByRole('button', { name: '确认' }).click()
  await expect(page.getByText('备份已删除')).toBeVisible()
  await expect(rows).toHaveCount(before)
})
