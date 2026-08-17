import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { WED } from './dates'
import {
  createTestSemester,
  deleteSemesterByYearTerm,
  login,
  publishCheckedTimetable,
  semesterLabel,
} from './helpers'

const SHOTS = 'e2e/screenshots'

const post = async (page: Page, url: string, data: object) =>
  (await page.request.post(url, { data })).json()

async function selectSemester(page: Page, year: number) {
  await page.locator('.n-base-selection').first().click()
  await page.locator('.n-base-select-option', { hasText: semesterLabel(year) }).click()
}

/**
 * 王师周三第一节语文请假。陈师同科空堂、周师非本科当天在校、吴师该节有课(被过滤)。
 * 返回 { sid, affectedId }。
 */
async function seed(page: Page, year: number) {
  const sem = await createTestSemester(page, year)
  const sid = sem.id
  const subjects: Record<string, number> = {}
  for (const s of await (await page.request.get(`/api/subjects?semester_id=${sid}`)).json()) {
    subjects[s.name] = s.id
  }
  const subject = async (name: string) => {
    if (!subjects[name]) {
      subjects[name] = (await post(page, `/api/subjects?semester_id=${sid}`, { name })).id
    }
    return subjects[name]
  }
  const teacher = async (name: string, subs: string[]) => (await post(
    page, `/api/teachers?semester_id=${sid}`,
    { name, base_periods: 20, subject_ids: await Promise.all(subs.map(subject)) })).id
  // get-or-create:同学期班名唯一(M6-5),同一个班不能建第二次
  const classes: Record<string, number> = {}
  const klass = async (name: string) => {
    if (!classes[name]) {
      classes[name] = (await post(page, `/api/class-units?semester_id=${sid}`,
        { grade: 7, name, track: 'junior_high' })).id
    }
    return classes[name]
  }

  const T: Record<string, number> = {
    王师: await teacher('王师', ['语文']),
    陈师: await teacher('陈师', ['语文']),
    周师: await teacher('周师', ['数学']),
    吴师: await teacher('吴师', ['数学']),
  }
  const tt = (await post(page, `/api/timetables?semester_id=${sid}`, { name: '草稿A' })).id
  const c0 = await klass('701')
  const wed = (await (await page.request.get(
    `/api/class-units/${c0}/period-table`)).json()).periods
    .filter((p: { weekday: number; type: string }) => p.weekday === 3 && p.type === 'regular')

  const place = async (t: string, subj: string, kls: string, pidx: number) => {
    const a = await post(page, `/api/assignments?semester_id=${sid}`, {
      class_id: await klass(kls), subject_id: await subject(subj), periods_per_week: 1,
      teachers: [{ teacher_id: T[t] }], block_rules: [],
    })
    await page.request.post(`/api/timetables/${tt}/entries`, {
      data: { course_assignment_id: a.id, weekday: 3, period_no: wed[pidx].period_no, span: 1 },
    })
  }
  await place('王师', '语文', '701', 0) // 被请假
  await place('周师', '数学', '703', 2) // 当天在校,第一节空
  await place('吴师', '数学', '704', 0) // 该节有课 → 过滤
  await publishCheckedTimetable(page, tt, true)

  const leave = await post(page, `/api/leaves?semester_id=${sid}`, {
    teacher_id: T['王师'], leave_type: 'sick',
    start_date: WED, end_date: WED,
  })
  return { sid, affectedId: leave.affected_periods[0].id as number }
}

// ── 验收①:推荐排序(同科第一)+ 硬性过滤 + 指派 ──
test('调课与代课处理：优先推荐同科教师、过滤已有课教师，指派后标记为已处理', async ({ page }) => {
  test.setTimeout(120_000)
  const YEAR = 2051
  await login(page)
  await deleteSemesterByYearTerm(page, YEAR, 1)
  await seed(page, YEAR)

  await page.goto('/substitutions')
  await selectSemester(page, YEAR)

  // 展开待处理节次 → 看推荐
  await page.getByTestId('sub-handle').first().click()
  const panel = page.getByTestId('sub-panel')
  await expect(panel).toBeVisible()

  const candidates = panel.getByTestId('sub-candidate')
  await expect(candidates).toHaveCount(2) // 陈师(同科)、周师(当天在校);吴师有课被过滤
  await expect(candidates.first()).toContainText('陈师')
  await expect(candidates.first()).toContainText('同科目教师')
  await expect(panel).not.toContainText('吴师')
  await page.screenshot({ path: `${SHOTS}/sub-1-recommend.png` })

  // 指派第一名(陈师)
  await candidates.first().getByTestId('sub-pick').click()
  await expect(page.getByText('已指派 陈师 代课')).toBeVisible()
  const period = page.getByTestId('sub-period').first()
  await expect(period).toContainText('已处理')
  await expect(period.getByTestId('sub-handler')).toContainText('陈师')
  await page.screenshot({ path: `${SHOTS}/sub-2-assigned.png` })

  // 撤回 → 退回待处理
  await period.getByTestId('sub-undo').click()
  await expect(page.getByText('已撤回处理方式')).toBeVisible()
  await expect(page.getByTestId('sub-period').first()).toContainText('待处理')

  await deleteSemesterByYearTerm(page, YEAR, 1)
})

// ── 验收③:全校无人可代 → 提示合班/自习,可直接改用 ──
test('调课与代课处理:无人可代时提示合班/自习并可直接设置', async ({ page }) => {
  test.setTimeout(120_000)
  const YEAR = 2052
  await login(page)
  await deleteSemesterByYearTerm(page, YEAR, 1)

  // 只有王师与陈师,且陈师该节也有课 → 无人可代
  const sem = await createTestSemester(page, YEAR)
  const sid = sem.id
  const guo = (await (await page.request.get(
    `/api/subjects?semester_id=${sid}`)).json()).find(
    (s: { name: string }) => s.name === '语文').id
  const wang = (await post(page, `/api/teachers?semester_id=${sid}`,
    { name: '王师', base_periods: 20, subject_ids: [guo] })).id
  const chen = (await post(page, `/api/teachers?semester_id=${sid}`,
    { name: '陈师', base_periods: 20, subject_ids: [guo] })).id
  const c1 = (await post(page, `/api/class-units?semester_id=${sid}`,
    { grade: 7, name: '701', track: 'junior_high' })).id
  const c2 = (await post(page, `/api/class-units?semester_id=${sid}`,
    { grade: 7, name: '702', track: 'junior_high' })).id
  const tt = (await post(page, `/api/timetables?semester_id=${sid}`, { name: '草稿A' })).id
  const wed = (await (await page.request.get(
    `/api/class-units/${c1}/period-table`)).json()).periods
    .filter((p: { weekday: number; type: string }) => p.weekday === 3 && p.type === 'regular')
  for (const [tid, cid] of [[wang, c1], [chen, c2]] as const) {
    const a = await post(page, `/api/assignments?semester_id=${sid}`, {
      class_id: cid, subject_id: guo, periods_per_week: 1,
      teachers: [{ teacher_id: tid }], block_rules: [],
    })
    await page.request.post(`/api/timetables/${tt}/entries`, {
      data: { course_assignment_id: a.id, weekday: 3, period_no: wed[0].period_no, span: 1 },
    })
  }
  await publishCheckedTimetable(page, tt, true)
  await post(page, `/api/leaves?semester_id=${sid}`, {
    teacher_id: wang, leave_type: 'sick', start_date: WED, end_date: WED,
  })

  await page.goto('/substitutions')
  await selectSemester(page, YEAR)
  await page.getByTestId('sub-handle').first().click()

  await expect(page.getByTestId('sub-nocandidate')).toContainText('合班')
  await expect(page.getByTestId('sub-nocandidate')).toContainText('自习')
  await page.screenshot({ path: `${SHOTS}/sub-3-nocandidate.png` })

  // 直接改用自习
  await page.getByTestId('sub-selfstudy').click()
  await expect(page.getByText('已设为自习')).toBeVisible()
  await expect(page.getByTestId('sub-period').first()).toContainText('已处理')

  await deleteSemesterByYearTerm(page, YEAR, 1)
})
