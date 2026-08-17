import { expect, test } from '@playwright/test'
import {
  createTestSemester,
  deleteSemesterByYearTerm,
  login,
  semesterLabel,
} from './helpers'

const YEAR = 2035 // 专用测试学年
const SHOTS = 'e2e/screenshots'

// M2-0：教师表单新增联系信息与账号绑定字段。
test('教师联系信息：新增教师并保存电子邮箱', async ({ page }) => {
  await login(page)

  // 前置(API):创建干净的测试学期
  await deleteSemesterByYearTerm(page, YEAR, 1)
  await createTestSemester(page, YEAR)

  // 进入基础数据 → 选择该学期 → 打开教师页签
  await page.goto('/basedata')
  await page.locator('.n-base-selection').first().click()
  await page.locator('.n-base-select-option', { hasText: semesterLabel(YEAR) }).click()
  await page.locator('.n-tabs-tab', { hasText: '教师' }).click()

  // 新增教师,填入姓名与联系信息
  await page.getByTestId('teacher-add').click()
  await page.getByTestId('teacher-name').locator('input').fill('陈老师')
  await page.getByTestId('teacher-email').locator('input').fill('chen@example.edu.cn')
  // 账号绑定属于管理员高风险操作，排课管理员编辑教师时不显示入口。
  await expect(page.getByTestId('teacher-account')).toHaveCount(0)
  await page.screenshot({ path: `${SHOTS}/teacher-1-form.png` })
  await page.getByTestId('teacher-save').click()

  // 列表出现该教师
  await expect(page.getByRole('cell', { name: '陈老师' })).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/teacher-2-list.png` })

  // 验证 Email 已保存(经 API 确认)
  const list = await (await page.request.get('/api/semesters')).json()
  const sem = list.find((s: { academic_year: number; term: number }) =>
    s.academic_year === YEAR && s.term === 1)
  const teachers = await (await page.request.get(`/api/teachers?semester_id=${sem.id}`)).json()
  const chen = teachers.find((t: { name: string }) => t.name === '陈老师')
  expect(chen.email).toBe('chen@example.edu.cn')

  // 清理
  await deleteSemesterByYearTerm(page, YEAR, 1)
})
