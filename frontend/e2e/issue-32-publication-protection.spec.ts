import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import {
  browserApiRequest,
  createTestSemester,
  deleteSemesterByYearTerm,
  E2E_DIRECTOR_PASS,
  E2E_DIRECTOR_USER,
  login,
  semesterLabel,
} from './helpers'

const YEAR = 2074
const ADMIN_USER = 'e2e_admin'
const ADMIN_PASS = 'e2eadmin1234'

async function post(page: Page, path: string, data: object) {
  const response = await page.request.post(path, { data })
  expect(response.ok(), await response.text()).toBe(true)
  return response.json()
}

test('发布入口统一经过检查确认，取消不发布且尝试均可审计', async ({ page }) => {
  await login(page)
  await page.request.patch('/api/wizard/state', { data: { completed: true } })
  await deleteSemesterByYearTerm(page, YEAR, 1)

  const semester = await createTestSemester(page, YEAR, { subjects: [] })
  const classUnit = await post(page, `/api/class-units?semester_id=${semester.id}`, {
    grade: 7, name: '701', track: 'junior_high',
  })
  const subject = await post(page, `/api/subjects?semester_id=${semester.id}`, {
    name: '语文',
  })
  const teacher = await post(page, `/api/teachers?semester_id=${semester.id}`, {
    name: '王老师', base_periods: 10,
  })
  const assignment = await post(page, `/api/assignments?semester_id=${semester.id}`, {
    class_id: classUnit.id,
    subject_id: subject.id,
    periods_per_week: 1,
    teachers: [{ teacher_id: teacher.id }],
    block_rules: [],
  })
  const timetable = await post(page, `/api/timetables?semester_id=${semester.id}`, {
    name: '可核验发布',
  })
  await post(page, `/api/timetables/${timetable.id}/entries`, {
    course_assignment_id: assignment.id, weekday: 1, period_no: 2, span: 1,
  })

  expect(await browserApiRequest(page, 'PUT', '/api/navigation-preference', {
    fixed: ['versions'], recent: [],
  })).toBe(200)
  await page.evaluate(() => window.localStorage.clear())
  await page.reload()

  const commonEntry = page.locator('.app-nav-common [data-nav-key="versions"]')
  await expect(commonEntry).toBeVisible()
  await commonEntry.click()
  await expect(page).toHaveURL(/\/scheduling\/versions$/)

  const row = page.locator('[data-testid="v-row-可核验发布"]')
  await row.getByTestId('v-publish').click()
  const confirmation = page.getByTestId('v-publish-confirmation')
  await expect(confirmation).toContainText(semesterLabel(YEAR))
  await expect(confirmation).toContainText(`可核验发布（#${timetable.id}）`)
  await expect(confirmation).toContainText('1 / 1 节已排')
  await expect(page.getByTestId('v-status-可核验发布')).toHaveText('检查通过')

  await page.getByTestId('v-publish-cancel').click()
  await expect(confirmation).toBeHidden()
  let versions = await (await page.request.get(
    `/api/timetables?semester_id=${semester.id}`,
  )).json()
  expect(versions[0]).toMatchObject({ status: 'draft', publication_state: 'checked' })

  await page.goto('/scheduling/workbench')
  await expect(page.getByTestId('wb-publish')).toBeVisible()
  await page.getByTestId('wb-publish').click()
  await expect(page).toHaveURL(/\/scheduling\/versions$/)

  const unconfirmed = await page.request.post(`/api/timetables/${timetable.id}/publish`, {
    data: {},
  })
  expect(unconfirmed.status()).toBe(409)
  expect((await unconfirmed.json()).detail.code).toBe('publication_confirmation_required')

  await page.locator('[data-testid="v-row-可核验发布"]').getByTestId('v-publish').click()
  await page.getByTestId('v-confirm-publish').click()
  await expect(page.getByTestId('v-status-可核验发布')).toHaveText('已发布')
  versions = await (await page.request.get(
    `/api/timetables?semester_id=${semester.id}`,
  )).json()
  expect(versions[0].status).toBe('published')

  await page.request.post('/api/auth/logout')
  await login(page, E2E_DIRECTOR_USER, E2E_DIRECTOR_PASS)
  const forbidden = await page.request.post(`/api/timetables/${timetable.id}/publish`, {
    data: { fingerprint: 'invalid' },
  })
  expect(forbidden.status()).toBe(403)
  expect((await forbidden.json()).detail.code).toBe('publication_permission_denied')

  await page.request.post('/api/auth/logout')
  await login(page, ADMIN_USER, ADMIN_PASS)
  const logs = await (await page.request.get(
    '/api/audit-logs?action=publish_timetable&limit=100',
  )).json() as Array<Record<string, unknown>>
  const attempts = logs.filter((log) => log.target_id === timetable.id)
  expect(attempts).toHaveLength(3)
  expect(attempts.map((log) => [log.username, log.result, log.reason])).toEqual([
    [E2E_DIRECTOR_USER, 'rejected', 'publication_permission_denied'],
    ['e2e_scheduler', 'success', ''],
    ['e2e_scheduler', 'rejected', 'publication_confirmation_required'],
  ])
  for (const attempt of attempts) {
    expect(attempt.semester_id).toBe(semester.id)
    expect(attempt.target_version).toBe(`可核验发布 (#${timetable.id})`)
    expect(attempt.created_at).toBeTruthy()
  }

  await page.request.post('/api/auth/logout')
  await login(page)
  await deleteSemesterByYearTerm(page, YEAR, 1)
})

test('两个草稿并发确认后仍只有一个已发布版本', async ({ page }) => {
  const year = YEAR + 1
  await login(page)
  await deleteSemesterByYearTerm(page, year, 1)
  const semester = await createTestSemester(page, year, { subjects: [] })
  const first = await post(page, `/api/timetables?semester_id=${semester.id}`, {
    name: '并发版本A',
  })
  const second = await post(page, `/api/timetables?semester_id=${semester.id}`, {
    name: '并发版本B',
  })
  const [firstCheck, secondCheck] = await Promise.all([
    page.request.post(`/api/timetables/${first.id}/publication-check`),
    page.request.post(`/api/timetables/${second.id}/publication-check`),
  ])
  expect(firstCheck.ok()).toBe(true)
  expect(secondCheck.ok()).toBe(true)
  const [firstResult, secondResult] = await Promise.all([
    page.request.post(`/api/timetables/${first.id}/publish`, {
      data: { fingerprint: (await firstCheck.json()).fingerprint },
    }),
    page.request.post(`/api/timetables/${second.id}/publish`, {
      data: { fingerprint: (await secondCheck.json()).fingerprint },
    }),
  ])

  expect(firstResult.status()).toBe(200)
  expect(secondResult.status()).toBe(200)
  const versions = await (await page.request.get(
    `/api/timetables?semester_id=${semester.id}`,
  )).json() as Array<{ status: string }>
  expect(versions.filter((version) => version.status === 'published')).toHaveLength(1)
  expect(versions.filter((version) => version.status === 'archived')).toHaveLength(1)

  await deleteSemesterByYearTerm(page, year, 1)
})
