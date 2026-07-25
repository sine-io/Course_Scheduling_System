import { expect, test } from '@playwright/test'
import {
  createTestSemester,
  deleteSemesterByYearTerm,
  login,
  semesterLabel,
} from './helpers'

const YEAR = 2036 // 专用测试学年
const SHOTS = 'e2e/screenshots'

// M2-1:单班教学任务 + 教师课时实时统计(超课时红字)。
test('教学任务管理:创建单班教学任务并显示教师超课时', async ({ page }) => {
  await login(page)
  await page.request.patch('/api/wizard/state', { data: { completed: true } })

  // 前置(API):建学期(初中模板含作息时间表)+ 班级、科目、教师(基本课时 2)
  await deleteSemesterByYearTerm(page, YEAR, 1)
  const sem = await createTestSemester(page, YEAR)
  const sid = sem.id
  await page.request.post(`/api/class-units?semester_id=${sid}`, {
    data: { grade: 3, name: '301', track: 'junior_high' },
  })
  await page.request.post(`/api/subjects?semester_id=${sid}`, { data: { name: '教学任务测试科' } })
  await page.request.post(`/api/teachers?semester_id=${sid}`, {
    data: { name: '王师', base_periods: 2 },
  })

  // 进入教学任务管理 → 选学期
  await page.goto('/scheduling/assignments')
  await page.locator('.n-base-selection').first().click()
  await page.locator('.n-base-select-option', { hasText: semesterLabel(YEAR) }).click()

  // 新增教学任务:301 班 × 语文 × 王师 × 每周 5 节(> 基本课时 2 → 超课时)
  await page.getByTestId('assignment-add').click()
  await page.getByTestId('a-class').click()
  await page.locator('.n-base-select-option', { hasText: '3年301' }).click()
  await page.getByTestId('a-subject').click()
  await page.keyboard.type('教学任务测试科') // 筛选(科目列表经虚拟卷动,直接输入定位)
  await page.locator('.n-base-select-option', { hasText: '教学任务测试科' }).click()
  await page.getByTestId('a-teachers').click()
  await page.locator('.n-base-select-option', { hasText: '王师' }).click()
  await page.keyboard.press('Escape')
  await page.getByTestId('a-periods').locator('input').fill('5')
  await page.getByTestId('a-periods').locator('input').press('Enter')
  await page.screenshot({ path: `${SHOTS}/assignment-1-form.png` })
  await page.getByTestId('a-save').click()

  // 教学任务列表出现该项任务
  await expect(page.getByRole('cell', { name: '教学任务测试科' })).toBeVisible()
  // 侧栏教师课时显示超课时(已配 5 > 应授 2 → +3)
  const loadPanel = page.getByTestId('teacher-load')
  await expect(loadPanel.getByText('王师')).toBeVisible()
  await expect(loadPanel.getByText('+3 超课时')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/assignment-2-load.png` })

  // 清理
  await deleteSemesterByYearTerm(page, YEAR, 1)
})
