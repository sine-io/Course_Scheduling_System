import { expect, test } from '@playwright/test'
import {
  createTestSemester,
  deleteSemesterByYearTerm,
  E2E_ADMIN_PASS,
  E2E_ADMIN_USER,
  highRiskData,
  login,
} from './helpers'

const YEAR = 2066

test.describe('Issue #33 管理员高风险操作保护与审计', () => {
  test.afterEach(async ({ page }) => {
    await deleteSemesterByYearTerm(page, YEAR, 1)
  })

  test('非管理员无删除入口，伪造请求被拒绝且管理员可追溯', async ({ page }) => {
    await login(page)
    await deleteSemesterByYearTerm(page, YEAR, 1)
    const semester = await createTestSemester(page, YEAR, { subjects: [] })
    const subjectResponse = await page.request.post(
      `/api/subjects?semester_id=${semester.id}`,
      { data: { name: '高风险边界测试科目' } },
    )
    expect(subjectResponse.ok()).toBeTruthy()
    const subject = await subjectResponse.json() as { id: number }

    await page.goto('/basedata')
    await page.locator('.n-tabs-tab', { hasText: '科目' }).click()
    await expect(page.getByRole('cell', { name: '高风险边界测试科目' })).toBeVisible()
    await expect(page.getByTestId(`subject-delete-${subject.id}`)).toHaveCount(0)

    const confirmation = highRiskData(`subject:${subject.id}`)
    const denied = await page.request.delete(`/api/subjects/${subject.id}`, {
      data: confirmation,
    })
    expect(denied.status()).toBe(403)
    expect((await denied.json()).detail.code).toBe('high_risk_permission_denied')
    const subjects = await (await page.request.get(
      `/api/subjects?semester_id=${semester.id}`,
    )).json() as Array<{ id: number }>
    expect(subjects.some((item) => item.id === subject.id)).toBeTruthy()

    await page.request.post('/api/auth/logout')
    await login(page, E2E_ADMIN_USER, E2E_ADMIN_PASS)
    const logs = await (await page.request.get('/api/audit-logs?action=delete_subject')).json() as Array<{
      operation_id: string | null
      username: string
      actor_roles: string[]
      target_id: number | null
      result: string
    }>
    const rejected = logs.find((log) => log.operation_id === confirmation.operation_id)
    expect(rejected).toMatchObject({
      username: 'e2e_scheduler',
      actor_roles: ['scheduler'],
      target_id: subject.id,
      result: 'rejected',
    })
  })

  test('管理员账号变更取消不提交，恢复失败不显示成功', async ({ page }) => {
    await login(page, E2E_ADMIN_USER, E2E_ADMIN_PASS)
    let accountCreates = 0
    let restoreCalls = 0
    page.on('request', (request) => {
      if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/accounts') {
        accountCreates += 1
      }
    })
    await page.route('**/api/backups', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.continue()
        return
      }
      await route.fulfill({
        json: [{
          name: 'backup_issue33_manual.dump',
          size_bytes: 1024,
          created_at: '2066-01-01T00:00:00Z',
          reason: 'manual',
          reason_label: '手动备份',
        }],
      })
    })
    await page.route('**/api/backups/backup_issue33_manual.dump/restore', async (route) => {
      restoreCalls += 1
      await route.fulfill({
        status: 502,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '模拟恢复失败' }),
      })
    })

    await page.goto('/settings/system')
    await expect(page.getByTestId('accounts-card')).toBeVisible()
    await expect(page.getByTestId('audit-card')).toBeVisible()

    await page.getByTestId('account-add').click()
    await page.getByTestId('account-username').locator('input').fill('issue33-cancelled')
    await page.getByTestId('account-display-name').locator('input').fill('取消创建测试')
    await page.getByTestId('account-password').locator('input').fill('temporary123')
    await page.getByTestId('account-save').click()
    const accountDialog = page.getByRole('dialog').filter({ hasText: '确认账号与角色变更' })
    await expect(accountDialog).toContainText('目标：新账号 issue33-cancelled')
    await expect(accountDialog).toContainText('影响：将创建账号并授予：教师')
    await accountDialog.getByRole('button', { name: '取消' }).click()
    await expect.poll(() => accountCreates).toBe(0)
    await page.locator('.n-modal').filter({ hasText: '新增账号' })
      .getByRole('button', { name: '取消' }).click()

    const restore = page.getByTestId('backup-restore')
    await restore.click()
    const restorePopover = page.locator('.n-popover')
      .filter({ hasText: 'backup_issue33_manual.dump' }).last()
    await expect(restorePopover).toContainText('覆盖当前所有数据')
    await expect(restorePopover).toContainText('所有用户需要重新登录')
    await restorePopover.getByRole('button', { name: '取消' }).click()
    expect(restoreCalls).toBe(0)

    await restore.click()
    await restorePopover.getByRole('button', { name: '确认' }).click()
    await expect(page.getByText('模拟恢复失败')).toBeVisible()
    await expect(page.locator('.n-message--success').filter({ hasText: '恢复完成' })).toHaveCount(0)
    await expect(restore).toBeEnabled()
    expect(restoreCalls).toBe(1)
  })
})
