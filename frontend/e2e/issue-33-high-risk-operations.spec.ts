import { expect, test, type Page } from '@playwright/test'
import {
  createTestSemester,
  deleteSemesterByYearTerm,
  E2E_ADMIN_PASS,
  E2E_ADMIN_USER,
  highRiskData,
  login,
} from './helpers'

const YEAR = 2066
const ARCHIVED_YEAR = YEAR + 2
const ARCHIVED_SUBJECT = '归档学期保留科目'

async function ensureArchivedSubject(page: Page): Promise<{ semesterId: number; subjectId: number }> {
  const semesters = await (await page.request.get('/api/semesters')).json() as Array<{
    id: number
    academic_year: number
    term: number
    status: string
  }>
  const existing = semesters.find((item) => (
    item.academic_year === ARCHIVED_YEAR && item.term === 1 && item.status === 'archived'
  ))
  if (existing) {
    const subjects = await (await page.request.get(
      `/api/subjects?semester_id=${existing.id}`,
    )).json() as Array<{ id: number; name: string }>
    const subject = subjects.find((item) => item.name === ARCHIVED_SUBJECT)
    expect(subject, '归档学期夹具应保留标记科目').toBeDefined()
    return { semesterId: existing.id, subjectId: subject!.id }
  }

  const semester = await createTestSemester(page, ARCHIVED_YEAR, { subjects: [] })
  const created = await page.request.post(`/api/subjects?semester_id=${semester.id}`, {
    data: { name: ARCHIVED_SUBJECT },
  })
  expect(created.ok()).toBeTruthy()
  const subject = await created.json() as { id: number }
  const archived = await page.request.patch(`/api/semesters/${semester.id}`, {
    data: { status: 'archived' },
  })
  expect(archived.ok()).toBeTruthy()
  return { semesterId: semester.id, subjectId: subject.id }
}

test.describe('Issue #33 管理员高风险操作保护与审计', () => {
  test.afterEach(async ({ page }) => {
    await deleteSemesterByYearTerm(page, YEAR + 1, 1)
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
    const auditPage = await (await page.request.get('/api/audit-logs?action=delete_subject')).json() as {
      items: Array<{
        operation_id: string | null
        username: string
        actor_roles: string[]
        target_id: number | null
        result: string
      }>
    }
    const logs = auditPage.items
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

    await page.goto('/settings/accounts')
    await expect(page.getByTestId('accounts-card')).toBeVisible()

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

    await page.goto('/settings/backup')
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

  test('管理员确认后可删除，历史/归档学期入口隐藏且接口拒绝', async ({ page }) => {
    await login(page, E2E_ADMIN_USER, E2E_ADMIN_PASS)
    await deleteSemesterByYearTerm(page, YEAR + 1, 1)
    await deleteSemesterByYearTerm(page, YEAR, 1)
    const semester = await createTestSemester(page, YEAR, { subjects: [] })
    const firstResponse = await page.request.post(
      `/api/subjects?semester_id=${semester.id}`,
      { data: { name: '管理员确认删除科目' } },
    )
    expect(firstResponse.ok()).toBeTruthy()
    const first = await firstResponse.json() as { id: number }

    await page.goto('/basedata')
    await page.locator('.n-tabs-tab', { hasText: '科目' }).click()
    const deleteButton = page.getByTestId(`subject-delete-${first.id}`)
    await deleteButton.click()
    const deletePopover = page.locator('.n-popover')
      .filter({ hasText: '管理员确认删除科目' }).last()
    await expect(deletePopover).toContainText('永久删除')
    await expect(deletePopover).toContainText('相关排课数据')
    await deletePopover.getByRole('button', { name: '取消' }).click()
    await expect(page.getByRole('cell', { name: '管理员确认删除科目' })).toBeVisible()

    await deleteButton.click()
    await deletePopover.getByRole('button', { name: '确认' }).click()
    await expect(page.getByRole('cell', { name: '管理员确认删除科目' })).toHaveCount(0)
    const successPage = await (await page.request.get(
      '/api/audit-logs?action=delete_subject',
    )).json() as { items: Array<{ target_id: number | null; result: string }> }
    const successLogs = successPage.items
    expect(successLogs).toContainEqual(expect.objectContaining({
      target_id: first.id,
      result: 'success',
    }))

    const historicalResponse = await page.request.post(
      `/api/subjects?semester_id=${semester.id}`,
      { data: { name: '历史学期保留科目' } },
    )
    expect(historicalResponse.ok()).toBeTruthy()
    const historicalSubject = await historicalResponse.json() as { id: number }
    await createTestSemester(page, YEAR + 1, { subjects: [] })

    await page.goto('/settings/semesters')
    const historicalRow = page.getByTestId(`semester-${semester.id}`)
    await expect(historicalRow).toBeVisible()
    await expect(historicalRow.getByTestId(`semester-delete-${semester.id}`)).toHaveCount(0)

    const rejected = await page.request.delete(`/api/subjects/${historicalSubject.id}`, {
      data: highRiskData(`subject:${historicalSubject.id}`),
    })
    expect(rejected.status()).toBe(409)
    expect((await rejected.json()).detail.code).toBe('semester_not_current')
    const historicalSubjects = await (await page.request.get(
      `/api/subjects?semester_id=${semester.id}`,
    )).json() as Array<{ id: number }>
    expect(historicalSubjects.some((item) => item.id === historicalSubject.id)).toBeTruthy()

    const archivedFixture = await ensureArchivedSubject(page)
    await page.goto('/settings/semesters')
    const archivedRow = page.getByTestId(`semester-${archivedFixture.semesterId}`)
    await expect(archivedRow).toContainText('已归档')
    await expect(
      archivedRow.getByTestId(`semester-delete-${archivedFixture.semesterId}`),
    ).toHaveCount(0)

    const archivedRejected = await page.request.delete(
      `/api/subjects/${archivedFixture.subjectId}`,
      { data: highRiskData(`subject:${archivedFixture.subjectId}`) },
    )
    expect(archivedRejected.status()).toBe(409)
    expect((await archivedRejected.json()).detail.code).toBe('semester_read_only')
    const archivedSubjects = await (await page.request.get(
      `/api/subjects?semester_id=${archivedFixture.semesterId}`,
    )).json() as Array<{ id: number }>
    expect(archivedSubjects.some((item) => item.id === archivedFixture.subjectId)).toBeTruthy()
  })
})
