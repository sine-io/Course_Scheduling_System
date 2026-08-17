import { expect, test } from '@playwright/test'
import type { APIResponse } from '@playwright/test'
import {
  createSchedulerApiContext,
  deleteSemesterByYearTerm,
  E2E_DIRECTOR_PASS,
  E2E_DIRECTOR_USER,
  login,
} from './helpers'

const YEAR = 2031
const SHOTS = 'e2e/screenshots'

test.use({ viewport: { width: 1440, height: 900 } })

async function requireOk(response: APIResponse, action: string): Promise<void> {
  if (!response.ok()) throw new Error(`${action}失败：${await response.text()}`)
}

test('设置向导完整旅程：中性学期、手工录入、作息确认、续作与当前学期补全', async ({ page }) => {
  test.setTimeout(120_000)
  await login(page)
  const api = await createSchedulerApiContext(page)

  const originalContextResponse = await api.get('/api/semester-context')
  await requireOk(originalContextResponse, '读取原当前学期')
  const originalContext = await originalContextResponse.json() as {
    current_semester: { id: number } | null
  }
  const originalSemesterId = originalContext.current_semester?.id ?? null
  let semesterId: number | null = null
  let canRestoreCompletion = false

  try {
    await deleteSemesterByYearTerm(page, YEAR, 1)
    const initialState = await api.patch('/api/wizard/state', {
      data: { current_step: 0, semester_id: null, paused: false },
    })
    await requireOk(initialState, '准备向导状态')

    await page.goto('/wizard')
    await expect(page.getByRole('heading', { name: '设置向导' })).toBeVisible()
    await expect(page.getByTestId('wizard-step-title')).toHaveText('学校与学期')
    await expect(page.getByText('不会自动生成科目、教师、班级或作息')).toBeVisible()

    const yearInput = page.getByTestId('wizard-year').locator('input')
    await yearInput.fill(String(YEAR))
    await yearInput.press('Enter')
    const startInput = page.getByTestId('wizard-start-date').locator('input')
    await startInput.fill(`${YEAR}-09-01`)
    await startInput.press('Enter')
    const endInput = page.getByTestId('wizard-end-date').locator('input')
    await endInput.fill(`${YEAR + 1}-01-31`)
    await endInput.press('Enter')
    await page.getByTestId('wizard-step-title').click()
    await page.screenshot({ path: `${SHOTS}/wizard-1-school-semester.png` })
    await page.getByTestId('wizard-next').click()

    await expect(page.getByTestId('wizard-step-title')).toHaveText('基础数据')
    const stateResponse = await api.get('/api/wizard/state')
    await requireOk(stateResponse, '读取向导学期')
    const state = await stateResponse.json() as { semester_id: number | null }
    expect(state.semester_id).not.toBeNull()
    semesterId = state.semester_id

    await page.getByTestId('entry-mode').getByText('手工录入', { exact: true }).click()
    await expect(page.getByTestId('manual-entry')).toBeVisible()

    await page.getByTestId('manual-common-数学').click()
    await expect(page.getByTestId('manual-common-preview')).toContainText('数学')
    await page.getByTestId('manual-common-confirm').click()
    await expect(page.getByTestId('manual-section-subjects')).toContainText('1 条')

    await page.getByTestId('manual-section-teachers').click()
    await page.getByTestId('teacher-add').click()
    await page.getByTestId('teacher-name').locator('input').fill('向导测试教师')
    await page.getByTestId('teacher-save').click()
    await expect(page.getByTestId('teachers-table')).toContainText('向导测试教师')
    await expect(page.getByTestId('manual-section-teachers')).toContainText('1 条')

    await page.getByTestId('manual-section-classes').click()
    await page.getByTestId('class-add').click()
    await page.getByTestId('class-name').locator('input').fill('向导测试一班')
    await page.getByTestId('class-save').click()
    await expect(page.getByTestId('classes-table')).toContainText('向导测试一班')
    await expect(page.getByTestId('manual-section-classes')).toContainText('1 条')
    await page.screenshot({ path: `${SHOTS}/wizard-2-manual-base-data.png` })

    await page.getByTestId('wizard-next').click()
    await expect(page.getByTestId('wizard-step-title')).toHaveText('作息安排')
    await expect(page.getByTestId('period-setup-source')).toContainText('可编辑建议')
    const suggestedGroup = page.getByTestId('period-group-track-elementary')
    await expect(suggestedGroup).toContainText('向导测试一班 · 小学')
    await expect(suggestedGroup.getByText('周视图预览')).toBeVisible()
    await expect(suggestedGroup.locator('[data-testid^="period-preview-"]').first()).toContainText('第一节')
    await page.getByTestId('period-setup-apply').click()
    await expect(page.getByTestId('period-setup-source')).toContainText('已经应用')
    await page.screenshot({ path: `${SHOTS}/wizard-3-period-arrangement.png` })

    await page.getByTestId('wizard-next').click()
    await expect(page.getByTestId('wizard-step-title')).toHaveText('完成检查')
    await expect(page.getByTestId('wizard-blockers')).toHaveCount(0)
    await expect(page.getByTestId('wizard-warnings')).toBeVisible()
    canRestoreCompletion = true

    const reopenedForResume = await api.post('/api/wizard/reopen')
    await requireOk(reopenedForResume, '重新打开当前学期')
    await page.reload()
    await expect(page.getByTestId('wizard-step-title')).toHaveText('完成检查')
    await page.getByTestId('wizard-save-exit').click()
    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByTestId('dash-setup-resume')).toContainText('下一步：完成检查')
    await page.getByTestId('dash-setup-resume').getByText('继续设置').click()
    await expect(page.getByTestId('wizard-step-title')).toHaveText('完成检查')

    await expect(page.getByTestId('wizard-finish')).toBeDisabled()
    await page.getByTestId('wizard-warning-ack').click()
    await expect(page.getByTestId('wizard-finish')).toBeEnabled()
    await page.screenshot({ path: `${SHOTS}/wizard-4-completion-check.png` })
    await page.getByTestId('wizard-finish').click()
    await expect(page).toHaveURL(/\/scheduling\/assignments$/)
    await expect(page.getByRole('heading', { name: '教学任务管理' })).toBeVisible()

    const semestersBeforeResponse = await api.get('/api/semesters')
    await requireOk(semestersBeforeResponse, '读取补全前学期')
    const semestersBefore = await semestersBeforeResponse.json() as Array<{ id: number }>
    const reopened = await api.post('/api/wizard/reopen')
    await requireOk(reopened, '检查并补全当前学期')
    const reopenedState = await reopened.json() as { semester_id: number | null }
    expect(reopenedState.semester_id).toBe(semesterId)
    const semestersAfterResponse = await api.get('/api/semesters')
    await requireOk(semestersAfterResponse, '读取补全后学期')
    const semestersAfter = await semestersAfterResponse.json() as Array<{ id: number }>
    expect(semestersAfter).toHaveLength(semestersBefore.length)

    await page.goto('/wizard')
    await expect(page.getByTestId('wizard-step-title')).toHaveText('完成检查')
    await page.getByTestId('wizard-warning-ack').click()
    await page.getByTestId('wizard-finish').click()
    await expect(page).toHaveURL(/\/scheduling\/assignments$/)
  } finally {
    if (canRestoreCompletion && semesterId !== null) {
      await api.post('/api/wizard/complete', {
        data: { semester_id: semesterId, acknowledge_warnings: true },
      })
    }
    if (semesterId !== null) await deleteSemesterByYearTerm(page, YEAR, 1)
    if (originalSemesterId !== null) {
      const contextResponse = await api.get('/api/semester-context')
      await requireOk(contextResponse, '读取恢复前学期上下文')
      const context = await contextResponse.json() as { revision: number }
      const switchResponse = await api.put('/api/semester-context', {
        data: { semester_id: originalSemesterId, expected_revision: context.revision },
      })
      await requireOk(switchResponse, '恢复原当前学期')
    }
    await api.patch('/api/wizard/state', {
      data: {
        current_step: 3,
        semester_id: originalSemesterId,
        paused: false,
      },
    })
    await api.dispose()
  }
})

test('教务主任只能查看设置向导', async ({ page }) => {
  await login(page, E2E_DIRECTOR_USER, E2E_DIRECTOR_PASS)
  const api = await createSchedulerApiContext(page)
  const stateResponse = await api.get('/api/wizard/state')
  await requireOk(stateResponse, '读取只读用例前向导状态')
  const originalState = await stateResponse.json() as {
    current_step: number
    semester_id: number | null
    paused: boolean
  }

  try {
    const prepared = await api.patch('/api/wizard/state', {
      data: { current_step: 0, semester_id: originalState.semester_id, paused: false },
    })
    await requireOk(prepared, '准备只读向导状态')
    await page.goto('/wizard')

    await expect(page.getByTestId('wizard-readonly')).toContainText('只能查看')
    await expect(page.getByTestId('wizard-save-exit')).toHaveCount(0)
    await expect(page.getByTestId('wizard-school-name')).toBeDisabled()
  } finally {
    await api.patch('/api/wizard/state', {
      data: {
        current_step: originalState.current_step,
        semester_id: originalState.semester_id,
        paused: originalState.paused,
      },
    })
    await api.dispose()
  }
})
