import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import {
  createTestSemester,
  deleteSemesterByYearTerm,
  login,
  semesterLabel,
} from './helpers'

const SHOTS = 'e2e/screenshots'

/** Naive 下拉框采用虚拟滚动,选项可能不在 DOM;可筛选下拉框统一先输入再点击。 */
async function pickFiltered(page: Page, testId: string, text: string) {
  await page.getByTestId(testId).click()
  await page.keyboard.type(text)
  await page.locator('.n-base-select-option', { hasText: text }).first().click()
}
async function selectSemester(page: Page, year: number) {
  await page.locator('.n-base-selection').first().click()
  await page.locator('.n-base-select-option', { hasText: semesterLabel(year) }).click()
}
async function api(page: Page, url: string, data: object) {
  return (await page.request.post(url, { data })).json()
}

test('教学任务管理:走班群组创建、协同教师+连堂、班级超节数警告', async ({ page }) => {
  const YEAR = 2038
  await login(page)
  await page.request.patch('/api/wizard/state', { data: { completed: true } })

  await deleteSemesterByYearTerm(page, YEAR, 1)
  const sem = await createTestSemester(page, YEAR)
  const sid = sem.id
  for (const [grade, name] of [[2, '201'], [2, '202'], [1, '机械一']] as [number, string][]) {
    await api(page, `/api/class-units?semester_id=${sid}`, { grade, name, track: 'junior_high' })
  }
  for (const n of ['陈师', '林师', '超量师']) {
    await api(page, `/api/teachers?semester_id=${sid}`, { name: n })
  }
  for (const n of ['机械实习', '超量科']) {
    await api(page, `/api/subjects?semester_id=${sid}`, { name: n })
  }

  await page.goto('/scheduling/assignments')
  await selectSemester(page, YEAR)

  // ── ① 走班群组创建(UI)──
  await page.getByTestId('group-add').click()
  await page.getByTestId('group-name').click()
  await page.locator('.n-base-select-option', { hasText: '八年级选修走班' }).click()
  await pickFiltered(page, 'group-classes', '2年201')
  await pickFiltered(page, 'group-classes', '2年202')
  await page.keyboard.press('Escape')
  await page.getByTestId('group-save').click()
  const groupCard = page.locator('.assignment-group-panel').filter({ hasText: '八年级选修走班' })
  await expect(groupCard).toContainText('八年级选修走班')
  await expect(groupCard).toContainText('2年201')
  await expect(groupCard).toContainText('2年202')
  await page.screenshot({ path: `${SHOTS}/adv-1-group.png` })

  // ── ② 协同教师 + 连堂(机械实习:2 位教师、6 节含 3 连堂×2)──
  await page.getByTestId('assignment-add').click()
  await pickFiltered(page, 'a-class', '1年机械一')
  await pickFiltered(page, 'a-subject', '机械实习')
  await page.getByTestId('a-teachers').click()
  await page.keyboard.type('陈师')
  await page.locator('.n-base-select-option', { hasText: '陈师' }).first().click()
  await page.keyboard.type('林师')
  await page.locator('.n-base-select-option', { hasText: '林师' }).first().click()
  await page.keyboard.press('Escape')
  const periods = page.getByTestId('a-periods').locator('input')
  await periods.fill('6')
  await periods.press('Enter')
  await page.getByTestId('a-add-block').click()
  const bs = page.getByTestId('a-block-size-0').locator('input')
  await bs.fill('3')
  await bs.press('Enter')
  const bc = page.getByTestId('a-block-count-0').locator('input')
  await bc.fill('2')
  await bc.press('Enter')
  await page.screenshot({ path: `${SHOTS}/adv-2-coteach-block.png` })
  await page.getByTestId('a-save').click()

  const row = page.locator('tr', { hasText: '机械实习' })
  await expect(row).toContainText('陈师（主讲）')
  await expect(row).toContainText('林师')
  await expect(row).toContainText('3连堂×2')

  // ── ③ 班级超节数警告(机械一 可排 35 节,再配 40 节 → 共 46 > 35)──
  await page.getByTestId('assignment-add').click()
  await pickFiltered(page, 'a-class', '1年机械一')
  await pickFiltered(page, 'a-subject', '超量科')
  await page.getByTestId('a-teachers').click()
  await page.keyboard.type('超量师')
  await page.locator('.n-base-select-option', { hasText: '超量师' }).first().click()
  await page.keyboard.press('Escape')
  const p2 = page.getByTestId('a-periods').locator('input')
  await p2.fill('40')
  await p2.press('Enter')
  await page.getByTestId('a-save').click()

  const warn = page.getByTestId('class-warning')
  await expect(warn).toBeVisible()
  await expect(warn).toContainText('教学任务 46 节')
  await expect(warn).toContainText('可排 35 节')
  await page.screenshot({ path: `${SHOTS}/adv-3-capacity-warning.png` })

  await deleteSemesterByYearTerm(page, YEAR, 1)
})

test('批量导入:教学任务 Excel 导入(单班×协同教师×连堂)', async ({ page }) => {
  const YEAR = 2039
  await login(page)
  await page.request.patch('/api/wizard/state', { data: { completed: true } })

  await deleteSemesterByYearTerm(page, YEAR, 1)
  const sem = await createTestSemester(page, YEAR)
  const sid = sem.id
  // 导入文件(fixtures/assignments_import.xlsx)引用的名称须先存在
  await api(page, `/api/class-units?semester_id=${sid}`, { grade: 7, name: '701', track: 'junior_high' })
  await api(page, `/api/subjects?semester_id=${sid}`, { name: '机械实习' })
  for (const n of ['陈师', '林师']) {
    await api(page, `/api/teachers?semester_id=${sid}`, { name: n })
  }

  await page.goto('/basedata')
  await selectSemester(page, YEAR)
  await page.locator('.n-tabs-tab', { hasText: '批量导入' }).click()
  await page.locator('.n-radio-button', { hasText: '教学任务' }).click()

  const file = fileURLToPath(new URL('./fixtures/assignments_import.xlsx', import.meta.url))
  await page.locator('input[type="file"]').setInputFiles(file)
  await page.getByRole('button', { name: '开始导入' }).click()

  await expect(page.getByText('成功导入 1 条数据。')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/adv-4-import.png` })

  // 经 API 验证:2 位教师(陈师为主讲教师)+ 3 连堂×2
  const list = await (await page.request.get(`/api/assignments?semester_id=${sid}`)).json()
  expect(list).toHaveLength(1)
  const a = list[0]
  expect(a.subject.name).toBe('机械实习')
  expect(a.periods_per_week).toBe(6)
  expect(a.teachers.map((t: { name: string }) => t.name).sort()).toEqual(['林师', '陈师'])
  expect(a.teachers.find((t: { is_lead: boolean }) => t.is_lead).name).toBe('陈师')
  expect(a.block_rules[0]).toMatchObject({ block_size: 3, count_per_week: 2 })

  await deleteSemesterByYearTerm(page, YEAR, 1)
})
