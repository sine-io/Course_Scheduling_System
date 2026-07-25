import { expect, test } from '@playwright/test'
import {
  createTestSemester,
  deleteSemesterByYearTerm,
  login,
  semesterLabel,
} from './helpers'

const SHOTS = 'e2e/screenshots'

// ── M3-3:科目可标记为「主科」(排课引擎 S5 会尽量排上午)──
test('科目管理:勾选主科后列表显示标签,重新加载仍保留', async ({ page }) => {
  const YEAR = 2044
  await login(page)
  await page.request.patch('/api/wizard/state', { data: { completed: true } })

  await deleteSemesterByYearTerm(page, YEAR, 1)
  const sem = await createTestSemester(page, YEAR, { subjects: [] })

  await page.goto('/basedata')
  await page.locator('.n-base-selection').first().click()
  await page.locator('.n-base-select-option', { hasText: semesterLabel(YEAR) }).click()
  await page.locator('.n-tabs-tab', { hasText: '科目' }).click()

  // 新增一般科目(不勾主科)
  await page.getByRole('button', { name: '新增科目' }).click()
  await page.getByTestId('sub-name').locator('input').fill('美术')
  await page.getByTestId('sub-save').click()
  await expect(page.getByText('已保存')).toBeVisible()

  // 新增主科
  await page.getByRole('button', { name: '新增科目' }).click()
  await page.getByTestId('sub-name').locator('input').fill('语文')
  await page.getByTestId('sub-is-major').click()
  await page.getByTestId('sub-save').click()

  await expect(page.getByTestId('sub-major-语文')).toHaveText('主科')
  await expect(page.getByTestId('sub-major-美术')).toHaveCount(0)
  await page.waitForTimeout(350) // 等 modal 淡出完成,截图才清楚
  await page.screenshot({ path: `${SHOTS}/major-1-list.png` })

  // 重新加载后仍保留(确认真的写进 DB,不是前端状态)
  await page.reload()
  await page.locator('.n-base-selection').first().click()
  await page.locator('.n-base-select-option', { hasText: semesterLabel(YEAR) }).click()
  await page.locator('.n-tabs-tab', { hasText: '科目' }).click()
  await expect(page.getByTestId('sub-major-语文')).toBeVisible()

  const subjects = await (await page.request.get(`/api/subjects?semester_id=${sem.id}`)).json()
  expect(subjects.find((s: { name: string }) => s.name === '语文').is_major).toBe(true)
  expect(subjects.find((s: { name: string }) => s.name === '美术').is_major).toBe(false)

  // 软约束设置端点:默认值 + 关闭 S2
  const cfg = await (await page.request.get(`/api/solver/config?semester_id=${sem.id}`)).json()
  expect(cfg.weights.S2).toBe(8)
  expect(cfg.weight_names.S5).toBe('主科优先排上午')

  const saved = await (await page.request.put(`/api/solver/config?semester_id=${sem.id}`, {
    data: { daily_subject_cap: 2, teacher_daily_max: 6, teacher_consecutive_max: 3,
      weights: { S2: 0 } },
  })).json()
  expect(saved.weights.S2).toBe(0)
  expect(saved.weights.S5).toBe(4)

  await deleteSemesterByYearTerm(page, YEAR, 1)
})
