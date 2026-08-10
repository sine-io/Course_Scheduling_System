import { expect, test } from '@playwright/test'
import { deleteSemesterByYearTerm, login, semesterLabel } from './helpers'

const YEAR = 2031 // 使用不与现有数据冲突的学年
const SHOTS = 'e2e/screenshots'

test('设置向导:使用初中空白模板创建学期并在仪表盘显示摘要', async ({ page }) => {
  await login(page)

  // 前置:重设向导状态、清掉测试学期,确保从头运行且不受干扰
  await page.request.post('/api/wizard/reset')
  await deleteSemesterByYearTerm(page, YEAR, 1)

  await page.goto('/wizard')
  await expect(page.getByRole('heading', { name: '设置向导' })).toBeVisible()

  // 步骤 0：选择初中模板。
  await page.getByTestId('tpl-junior_high_draft').click()
  await expect(page.getByText('初中（空白模板）')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/wizard-1-template.png` })
  await page.getByTestId('wizard-next').click()

  // 步骤 1：设置公历学年并创建学期。
  const yearInput = page.getByTestId('wizard-year').locator('input')
  await yearInput.fill(String(YEAR))
  await yearInput.press('Enter')
  await page.screenshot({ path: `${SHOTS}/wizard-2-year.png` })
  await page.getByTestId('wizard-next').click()

  // 步骤 2：创建学期后进入作息时间表设置。
  await expect(page.getByText('模板不会默认铃声和上课时段，请按学校实际作息填写。')).toBeVisible()
  await expect(page.getByText('（共 0 格，每周 5 天）')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/wizard-3-periods.png` })
  await page.getByTestId('wizard-next').click()

  // 步骤 3：跳过导入并进入下一步。
  await page.screenshot({ path: `${SHOTS}/wizard-4-import.png` })
  await page.getByTestId('wizard-next').click()

  // 步骤 4：完成页应显示数据摘要。
  await expect(page.getByText('初始设置即将完成')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/wizard-5-done.png` })
  await page.getByTestId('wizard-finish').click()

  // 完成后导向教学任务管理页
  await expect(page).toHaveURL(/\/scheduling\/assignments$/)
  await expect(page.getByRole('heading', { name: '教学任务管理' })).toBeVisible()

  // 仪表盘显示该学期摘要(验收①)
  await page.goto('/')
  await expect(page.getByText(`${semesterLabel(YEAR)} · 数据摘要`)).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/wizard-6-dashboard.png` })

  // 清理:移除测试学期
  await deleteSemesterByYearTerm(page, YEAR, 1)
})
