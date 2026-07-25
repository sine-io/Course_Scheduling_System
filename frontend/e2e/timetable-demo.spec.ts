import { expect, test } from '@playwright/test'
import { login } from './helpers'

const SHOTS = 'e2e/screenshots'

// M2-2:TimetableGrid 拖拽课表组件示范页(纯前端,不依赖后端数据)。
test('课表组件:拖拽未排教学任务置入格子,并切换小学/中职两套作息时间表', async ({ page }) => {
  await login(page)
  await page.request.patch('/api/wizard/state', { data: { completed: true } })

  await page.goto('/scheduling/timetable-demo')
  await expect(page.getByRole('heading', { name: '课表组件演示（TimetableGrid）' })).toBeVisible()

  // 小学 40 分作息时间表(默认)截图
  await page.screenshot({ path: `${SHOTS}/timetable-1-elementary.png` })

  // 拖拽「英语」到周四第1节(周四=4, 第1节=1 为一般课空格)
  const tray = page.getByTestId('tray-英语')
  const target = page.locator('[data-weekday="4"][data-period="1"]')
  await tray.dragTo(target)

  // 该格出现英语卡片
  await expect(target.getByText('英语')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/timetable-2-placed.png` })

  // 切到中职 50 分作息时间表:应见连堂(综合实践活动,占 2 节)
  await page.getByTestId('demo-vocational').click()
  await expect(page.getByText('综合实践活动')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/timetable-3-vocational.png` })
})
