import { expect, test } from '@playwright/test'
import { login } from './helpers'

test('已移除的课表演示页兼容重定向到排课工作台', async ({ page }) => {
  await login(page)
  await page.goto('/scheduling/timetable-demo')
  await expect(page).toHaveURL(/\/scheduling\/workbench$/)
  await expect(page.getByTestId('timetable-demo-page')).toHaveCount(0)
})
