import { expect, test } from '@playwright/test'
import {
  E2E_DIRECTOR_PASS,
  E2E_DIRECTOR_USER,
  E2E_TEACHER_PASS,
  E2E_TEACHER_USER,
  createTestSemester,
  deleteSemesterByYearTerm,
  login,
  switchCurrentSemester,
} from './helpers'
import { SEM_END, SEM_START } from './dates'

test.describe('Issue 25: current semester context', () => {
  test('persists the shared switch and rejects an old-link write', async ({ page }) => {
    await login(page)
    const firstYear = 2080 + (Date.now() % 10)
    const secondYear = firstYear + 1
    const copyYear = firstYear + 2
    await deleteSemesterByYearTerm(page, firstYear, 1)
    await deleteSemesterByYearTerm(page, secondYear, 1)
    await deleteSemesterByYearTerm(page, copyYear, 1)

    const first = await createTestSemester(page, firstYear, { subjects: [] })
    const second = await createTestSemester(page, secondYear, { subjects: [] })
    const firstDetail = await (await page.request.get(`/api/semesters/${first.id}`)).json() as {
      period_tables: Array<{ id: number }>
    }

    await page.goto('/scheduling/flow?step=subjects')
    const selector = page.getByTestId('current-semester-select')
    await expect(selector).toHaveValue(String(second.id))
    const confirmation = new Promise<string>((resolve) => {
      page.once('dialog', async (dialog) => {
        const message = dialog.message()
        await dialog.accept()
        resolve(message)
      })
    })
    await selector.selectOption(String(first.id))
    await expect(confirmation).resolves.toContain('会改变全校用户的当前工作学期')
    await expect(selector).toHaveValue(String(first.id))

    await page.reload()
    await expect(page.getByTestId('current-semester-select')).toHaveValue(String(first.id))

    await switchCurrentSemester(page, second.id)
    const oldLinkWrite = await page.request.post(`/api/subjects?semester_id=${first.id}`, {
      data: { name: '旧链接不可写' },
    })
    expect(oldLinkWrite.status()).toBe(409)
    expect((await oldLinkWrite.json()).detail.code).toBe('semester_not_current')

    await page.goto(`/scheduling/flow?step=periods&table=${firstDetail.period_tables[0].id}&semester=${first.id}`)
    await expect(page.getByTestId('period-table-readonly')).toContainText('历史学期')
    await expect(page.getByTestId('period-table-save')).toBeDisabled()

    const copied = await page.request.post(`/api/semesters/${first.id}/copy`, {
      data: {
        academic_year: copyYear,
        term: 1,
        start_date: SEM_START,
        end_date: SEM_END,
      },
    })
    expect(copied.status()).toBe(201)
    expect((await (await page.request.get('/api/semester-context')).json()).current_semester.id)
      .toBe(second.id)

    const revision = (await (await page.request.get('/api/semester-context')).json()).revision as number
    const [left, right] = await Promise.all([
      page.request.put('/api/semester-context', {
        data: { semester_id: first.id, expected_revision: revision },
      }),
      page.request.put('/api/semester-context', {
        data: { semester_id: first.id, expected_revision: revision },
      }),
    ])
    expect([left.status(), right.status()].sort()).toEqual([200, 409])

    await deleteSemesterByYearTerm(page, firstYear, 1)
    await deleteSemesterByYearTerm(page, secondYear, 1)
    await deleteSemesterByYearTerm(page, copyYear, 1)
  })

  test('director can switch the current context while teacher cannot', async ({ page }) => {
    const year = 2080 + (Date.now() % 10)
    await login(page)
    await deleteSemesterByYearTerm(page, year, 2)
    const semester = await createTestSemester(page, year, { term: 2, subjects: [] })

    try {
      await page.request.post('/api/auth/logout')
      await login(page, E2E_DIRECTOR_USER, E2E_DIRECTOR_PASS)
      await expect(page.getByTestId('current-semester-select')).toHaveValue(String(semester.id))
      const directorContext = await (await page.request.get('/api/semester-context')).json() as {
        revision: number
        can_switch: boolean
      }
      expect(directorContext.can_switch).toBe(true)
      const switched = await page.request.put('/api/semester-context', {
        data: { semester_id: semester.id, expected_revision: directorContext.revision },
      })
      expect(switched.status()).toBe(200)

      await page.request.post('/api/auth/logout')
      await login(page, E2E_TEACHER_USER, E2E_TEACHER_PASS)
      await expect(page.getByTestId('current-semester-label')).toHaveText(
        `${year}-${year + 1}学年第二学期`,
      )
      await expect(page.getByTestId('current-semester-select')).toHaveCount(0)
      const teacherContext = await (await page.request.get('/api/semester-context')).json() as {
        revision: number
        can_switch: boolean
      }
      expect(teacherContext.can_switch).toBe(false)
      const denied = await page.request.put('/api/semester-context', {
        data: { semester_id: semester.id, expected_revision: teacherContext.revision },
      })
      expect(denied.status()).toBe(403)
    } finally {
      await page.request.post('/api/auth/logout')
      await login(page)
      await deleteSemesterByYearTerm(page, year, 2)
    }
  })
})
