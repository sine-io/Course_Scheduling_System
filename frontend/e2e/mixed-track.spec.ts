import { expect, test } from '@playwright/test'
import {
  createTestPeriodTable,
  createTestSemester,
  deleteSemesterByYearTerm,
  login,
  SENIOR_HIGH_SLOTS,
} from './helpers'

const YEAR = 2032 // 专用测试学年
const SHOTS = 'e2e/screenshots'

// 完全中学场景:同学期两套作息时间表,班级统一在排课工作台中维护。
test('混合学制:班级设置不再管理作息时间表', async ({ page }) => {
  await login(page)

  // 前置(API):清掉测试学期后,创建含两套作息时间表的学期
  await deleteSemesterByYearTerm(page, YEAR, 1)
  const sem = await createTestSemester(page, YEAR)
  await createTestPeriodTable(page, sem.id, '高中部作息时间表', SENIOR_HIGH_SLOTS)

  // 班级统一从“开始排课”工作台进入，保留学期上下文。
  await page.goto(`/scheduling/flow?step=classes&semester=${sem.id}`)
  await expect(page.getByTestId('classes-empty')).toBeVisible()

  // 新增班级:表单只维护班级本身，作息表属于“设置课时”。
  await page.getByTestId('class-add').click()
  await page.getByTestId('class-name').locator('input').fill('高中501')
  await expect(page.getByTestId('class-period-table')).toHaveCount(0)
  await page.screenshot({ path: `${SHOTS}/mixed-1-form.png` })
  await page.getByTestId('class-save').click()

  // 列表应出现该班；作息配置在下一步单独完成。
  await expect(page.getByRole('cell', { name: '高中501' })).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/mixed-2-list.png` })

  // 清理
  await deleteSemesterByYearTerm(page, YEAR, 1)
})
