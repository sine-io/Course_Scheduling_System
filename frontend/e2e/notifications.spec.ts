import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { WED } from './dates'
import {
  createAdminApiContext,
  createTestSemester,
  deleteSemesterByYearTerm,
  highRiskData,
  login,
  publishCheckedTimetable,
  semesterLabel,
} from './helpers'

const SHOTS = 'e2e/screenshots'
const XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
const TEACHER_USER = 'e2e_teacher'
const TEACHER_PASS = 'e2eteacher1234'

const post = async (page: Page, url: string, data: object) =>
  (await page.request.post(url, { data })).json()
const get = async (page: Page, url: string) => (await page.request.get(url)).json()

async function selectSemester(page: Page, year: number) {
  await page.locator('.n-base-selection').first().click()
  await page.locator('.n-base-select-option', { hasText: semesterLabel(year) }).click()
}

/** 创建/获取绑定 e2e_teacher 账号的教师「陈老师」。返回 teacherId。 */
async function bindTeacher(page: Page, sid: number): Promise<number> {
  const file = fileURLToPath(new URL('./fixtures/teachers_with_account.xlsx', import.meta.url))
  const admin = await createAdminApiContext(page)
  try {
    const confirmation = highRiskData(`semester:${sid}:teacher-accounts`)
    const imp = await (await admin.post(
      `/api/import/teachers?semester_id=${sid}&create_accounts=true`,
      {
        multipart: {
          ...confirmation,
          confirmed: String(confirmation.confirmed),
          file: { name: 't.xlsx', mimeType: XLSX, buffer: readFileSync(file) },
        },
      },
    )).json()
    if (imp.imported === 1) {
      const list = await (await admin.get(`/api/teachers?semester_id=${sid}`)).json()
      return list.find((x: { name: string }) => x.name === '陈老师').id
    }
    const created = await post(page, `/api/teachers?semester_id=${sid}`, { name: '陈老师' })
    const accounts = await (await admin.get(`/api/teachers/bindable-accounts?semester_id=${sid}`)).json()
    const acc = accounts.find((x: { username: string }) => x.username === TEACHER_USER)
    await admin.patch(`/api/teachers/${created.id}`, {
      data: {
        name: '陈老师',
        user_id: acc.id,
        account_confirmation: highRiskData(`teacher:${created.id}:account:${acc.id}`),
      },
    })
    return created.id
  } finally {
    await admin.dispose()
  }
}

async function ensureTeacherPassword(page: Page) {
  await page.request.post('/api/auth/logout')
  const first = await page.request.post('/api/auth/login',
    { data: { username: TEACHER_USER, password: 'changeme' } })
  if (first.ok()) {
    await page.request.post('/api/auth/change-password',
      { data: { old_password: 'changeme', new_password: TEACHER_PASS } })
  }
  await page.request.post('/api/auth/logout')
}

/**
 * 王师(无账号)请假,指派陈老师(有账号)代课 → 陈老师收到通知。
 * 返回 { sid, notificationId }。
 */
async function seedAssignment(page: Page, sid: number, chenId: number) {
  const guo = (await post(page, `/api/subjects?semester_id=${sid}`, { name: '语文' })).id
  const wang = (await post(page, `/api/teachers?semester_id=${sid}`,
    { name: '王师', base_periods: 20 })).id
  const c701 = (await post(page, `/api/class-units?semester_id=${sid}`,
    { grade: 7, name: '701', track: 'junior_high' })).id
  const tt = (await post(page, `/api/timetables?semester_id=${sid}`, { name: '草稿A' })).id
  const wed = (await get(page, `/api/class-units/${c701}/period-table`)).periods
    .filter((p: { weekday: number; type: string }) => p.weekday === 3 && p.type === 'regular')
  const a = await post(page, `/api/assignments?semester_id=${sid}`, {
    class_id: c701, subject_id: guo, periods_per_week: 1,
    teachers: [{ teacher_id: wang }], block_rules: [],
  })
  await page.request.post(`/api/timetables/${tt}/entries`,
    { data: { course_assignment_id: a.id, weekday: 3, period_no: wed[0].period_no, span: 1 } })
  await publishCheckedTimetable(page, tt, true)

  const affected = (await post(page, `/api/leaves?semester_id=${sid}`, {
    teacher_id: wang, leave_type: 'sick', start_date: WED, end_date: WED,
  })).affected_periods[0]
  await page.request.put(`/api/affected-periods/${affected.id}/substitution`,
    { data: { type: 'substitute', handler_teacher_id: chenId } })
}

// ── 验收①②:教师端铃铛确认(手机) + 排课管理员看板再次提醒 ──
// 这些测试共用 e2e_teacher 账号并发布课表;留下的学期会盖掉别的测试的「最近学期」
// 默认,故统一以 afterEach 兜底清理(即使测试中途失败也删掉)。
const YEARS = [2053, 2054]

test.describe('通知系统', () => {
  test.afterEach(async ({ page }) => {
    await page.request.post('/api/auth/logout')
    await login(page)
    for (const y of YEARS) await deleteSemesterByYearTerm(page, y, 1)
  })

  test('排课管理员指派代课后,教师手机收到通知并确认;排课管理员看板可再次提醒', async ({ page }) => {
    test.setTimeout(180_000)
    const YEAR = 2053
    await login(page)
    await page.request.patch('/api/wizard/state', { data: { completed: true } })
    await deleteSemesterByYearTerm(page, YEAR, 1)

    const sem = await createTestSemester(page, YEAR, { subjects: [] })
    const chenId = await bindTeacher(page, sem.id)
    await seedAssignment(page, sem.id, chenId)
    await ensureTeacherPassword(page)

    // ── 排课管理员看板:陈老师的代课通知未确认,可再次提醒 ──
    await login(page)
    await page.goto('/notification-board')
    await selectSemester(page, YEAR)
    const row = page.getByTestId('board-row').filter({ hasText: '陈老师' }).first()
    await expect(row).toContainText('代课通知')
    await expect(row).toContainText('未读')
    await row.getByTestId('board-remind').click()
    await expect(page.getByText('已再次提醒 陈老师')).toBeVisible()
    await page.screenshot({ path: `${SHOTS}/notif-1-board.png` })
    await deleteSemesterByYearTerm(page, YEAR, 1)
    await page.request.post('/api/auth/logout')
  })

  test.describe('教师手机端', () => {
    test.use({ viewport: { width: 390, height: 844 } })

    test('教师登录手机看到铃铛未读数,点开确认收到', async ({ page }) => {
      test.setTimeout(180_000)
      const YEAR = 2054
      await login(page)
      await page.request.patch('/api/wizard/state', { data: { completed: true } })
      await deleteSemesterByYearTerm(page, YEAR, 1)
      const sem = await createTestSemester(page, YEAR, { subjects: [] })
      const chenId = await bindTeacher(page, sem.id)
      await seedAssignment(page, sem.id, chenId)
      await ensureTeacherPassword(page)

      // 陈老师手机登录 → 铃铛有未读
      await login(page, TEACHER_USER, TEACHER_PASS)
      const badge = page.getByTestId('notif-badge')
      await expect(badge).toContainText('1')

      await page.getByTestId('notif-bell').click()
      const item = page.getByTestId('notif-item').first()
      await expect(item).toContainText('代课通知')
      await expect(item).toContainText('王师')
      await page.screenshot({ path: `${SHOTS}/notif-2-teacher-mobile.png` })

      // 一键确认收到
      await item.getByTestId('notif-ack').click()
      await expect(page.getByText('已提交确认回复')).toBeVisible()
      await expect(item).toContainText('已确认收到')

      // 未读数归零(重开铃铛 badge 消失)
      await page.keyboard.press('Escape')
      await expect(page.getByTestId('notif-badge')).not.toContainText('1')

      // 清理:留下的已发布学期会盖掉其他测试的「最近学期」默认,务必删除
      await page.request.post('/api/auth/logout')
      await login(page)
      await deleteSemesterByYearTerm(page, YEAR, 1)
    })
  })
})
