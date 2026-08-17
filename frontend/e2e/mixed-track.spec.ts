import { expect, test } from '@playwright/test'
import {
  createTestPeriodTable,
  createTestSemester,
  deleteSemesterByYearTerm,
  login,
  semesterLabel,
  SENIOR_HIGH_SLOTS,
} from './helpers'

const YEAR = 2032 // 专用测试学年
const SHOTS = 'e2e/screenshots'

// 完全中学场景:同学期两套作息时间表,班级可指定所属作息时间表。
test('混合学制:班级可指定作息时间表(≥2 套时出现下拉)', async ({ page }) => {
  await login(page)
  // 标记向导已完成,避免首登守卫把导航转向 /wizard

  // 前置(API):清掉测试学期后,创建含两套作息时间表的学期
  await deleteSemesterByYearTerm(page, YEAR, 1)
  const sem = await createTestSemester(page, YEAR)
  await createTestPeriodTable(page, sem.id, '高中部作息时间表', SENIOR_HIGH_SLOTS)

  // 进入基础数据 → 选择该学期 → 打开班级页签
  await page.goto('/basedata')
  await page.locator('.n-base-selection').first().click()
  await page.locator('.n-base-select-option', { hasText: semesterLabel(YEAR) }).click()
  await page.locator('.n-tabs-tab', { hasText: '班级' }).click()

  // 新增班级:作息时间表下拉应出现(因有 2 套)
  await page.getByTestId('class-add').click()
  await page.getByTestId('class-name').locator('input').fill('高中501')
  const ptSelect = page.getByTestId('class-period-table')
  await expect(ptSelect).toBeVisible()
  await ptSelect.click()
  await page.locator('.n-base-select-option', { hasText: '高中部作息时间表' }).click()
  await page.screenshot({ path: `${SHOTS}/mixed-1-form.png` })
  await page.getByTestId('class-save').click()

  // 列表应出现该班,且作息时间表栏显示「高中部作息时间表」
  await expect(page.getByRole('cell', { name: '高中501' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '高中部作息时间表' })).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/mixed-2-list.png` })

  // 清理
  await deleteSemesterByYearTerm(page, YEAR, 1)
})
