import { expect, test } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'
import {
  createTestSemester,
  deleteSemesterByYearTerm,
  login,
  semesterLabel,
} from './helpers'

const YEAR = 2037
const SHOTS = 'e2e/screenshots'

// 初中模板可排课节次(period_no):1=早自习、6=午休,其余为一般课
const SLOTS = [2, 3, 4, 5, 7, 8, 9]
const SUBJECTS = ['语文', '数学', '英语', '生物学', '道德与法治', '艺术', '体育与健康']

/** 以 dispatchEvent + 真实 DataTransfer 驱动 HTML5 拖放,才能在「放下前」断言冲突红框。 */
async function newDataTransfer(page: Page) {
  return page.evaluateHandle(() => new DataTransfer())
}
async function dragOver(page: Page, source: Locator, target: Locator) {
  const dt = await newDataTransfer(page)
  await source.dispatchEvent('dragstart', { dataTransfer: dt })
  await target.dispatchEvent('dragenter', { dataTransfer: dt })
  return { dt, end: () => source.dispatchEvent('dragend', { dataTransfer: dt }) }
}
async function dragDrop(page: Page, source: Locator, target: Locator) {
  const dt = await newDataTransfer(page)
  await source.dispatchEvent('dragstart', { dataTransfer: dt })
  await target.dispatchEvent('dragenter', { dataTransfer: dt })
  await target.dispatchEvent('drop', { dataTransfer: dt })
}
const cell = (page: Page, weekday: number, period: number) =>
  page.locator(`[data-weekday="${weekday}"][data-period="${period}"]`)

test('排课工作台:冲突红框、拖放排课、锁定、拖回移除、Ctrl+Z、三视角一致、排满归零', async ({ page }) => {
  await login(page)
  await page.request.patch('/api/wizard/state', { data: { completed: true } })

  // ── 前置(API):学期 + 2 班 + 8 位教师 + 8 科 + 教学任务 ──
  await deleteSemesterByYearTerm(page, YEAR, 1)
  const sem = await createTestSemester(page, YEAR, { subjects: [] })
  const sid = sem.id
  const post = async (url: string, data: object) =>
    (await page.request.post(url, { data })).json()

  const c301 = await post(`/api/class-units?semester_id=${sid}`, { grade: 3, name: '301', track: 'junior_high' })
  const c302 = await post(`/api/class-units?semester_id=${sid}`, { grade: 3, name: '302', track: 'junior_high' })

  // 王师教 301 语文,同时教 302 数学二(用来制造教师冲突)
  const wang = await post(`/api/teachers?semester_id=${sid}`, { name: '王师' })
  const others = []
  for (let i = 1; i < SUBJECTS.length; i++) {
    others.push(await post(`/api/teachers?semester_id=${sid}`, { name: `师${i}` }))
  }
  const teacherOf = (i: number) => (i === 0 ? wang : others[i - 1])

  const aIds: number[] = []
  for (let i = 0; i < SUBJECTS.length; i++) {
    const s = await post(`/api/subjects?semester_id=${sid}`, { name: SUBJECTS[i] })
    const a = await post(`/api/assignments?semester_id=${sid}`, {
      class_id: c301.id, subject_id: s.id, periods_per_week: 5,
      teachers: [{ teacher_id: teacherOf(i).id, is_lead: true }], block_rules: [],
    })
    aIds.push(a.id)
  }
  const s302 = await post(`/api/subjects?semester_id=${sid}`, { name: '数学二' })
  const a302 = await post(`/api/assignments?semester_id=${sid}`, {
    class_id: c302.id, subject_id: s302.id, periods_per_week: 5,
    teachers: [{ teacher_id: wang.id, is_lead: true }], block_rules: [],
  })

  // ── 进入工作台(首次加载自动创建草稿)──
  await page.goto('/scheduling/workbench')
  await page.locator('.n-base-selection').first().click()
  await page.locator('.n-base-select-option', { hasText: semesterLabel(YEAR) }).click()
  await expect(page.getByTestId('wb-remaining')).toHaveText('剩余 35 节')

  // 获取草稿 id,并让王师在 302 班的周五第七节(period_no 9)先有课
  const tts = await (await page.request.get(`/api/timetables?semester_id=${sid}`)).json()
  const ttId = tts[0].id
  await page.request.post(`/api/timetables/${ttId}/entries`, {
    data: { course_assignment_id: a302.id, weekday: 5, period_no: 9, span: 1 },
  })
  await page.reload()
  await page.locator('.n-base-selection').first().click()
  await page.locator('.n-base-select-option', { hasText: semesterLabel(YEAR) }).click()

  // ── ① 冲突红框:拖 301 语文(王师)到周五第七节 ──
  const tray语文 = page.getByTestId('wb-tray-语文')
  const conflictCell = cell(page, 5, 9)
  const drag = await dragOver(page, tray语文, conflictCell)
  await expect(conflictCell).toHaveClass(/is-conflict/)
  await expect(conflictCell).toContainText('教师王师')
  // 该格在宽表右侧,整页截图看不到 → 直接截该格元素以便人工查看红框与原因
  await conflictCell.screenshot({ path: `${SHOTS}/wb-1-conflict-cell.png` })
  await page.screenshot({ path: `${SHOTS}/wb-1-conflict.png` })
  await drag.end()

  // ── ② 可放绿框 + 放入:周一第一节(period_no 2)──
  const okCell = cell(page, 1, 2)
  const d2 = await dragOver(page, tray语文, okCell)
  await expect(okCell).toHaveClass(/is-droppable/)
  await okCell.dispatchEvent('drop', { dataTransfer: d2.dt })
  await expect(okCell).toContainText('语文')
  await expect(page.getByTestId('wb-remaining')).toHaveText('剩余 34 节')
  await page.screenshot({ path: `${SHOTS}/wb-2-placed.png` })

  // ── ③ Ctrl+Z 撤销 ──
  await page.keyboard.press('Control+z')
  await expect(okCell).not.toContainText('语文')
  await expect(page.getByTestId('wb-remaining')).toHaveText('剩余 35 节')

  // 重新放入供后续步骤使用
  await dragDrop(page, page.getByTestId('wb-tray-语文'), okCell)
  await expect(okCell).toContainText('语文')

  // ── ④ 点卡片锁定 → 不可拖拽;再点解锁 ──
  const card = okCell.locator('.tg-card')
  await card.click()
  await expect(okCell.locator('.tg-lock')).toBeVisible()
  await expect(card).toHaveAttribute('draggable', 'false')
  await card.click()
  await expect(okCell.locator('.tg-lock')).toHaveCount(0)
  await expect(card).toHaveAttribute('draggable', 'true')

  // ── ⑤ 拖回未排列表 → 移除 ──
  await dragDrop(page, card, page.getByTestId('wb-tray'))
  await expect(okCell).not.toContainText('语文')
  await expect(page.getByTestId('wb-remaining')).toHaveText('剩余 35 节')

  // ── ⑥ 排完整班:其余经 API 依计画排入(每科一天一节,不触发 H2/H10)──
  for (let i = 0; i < SUBJECTS.length; i++) {
    for (let d = 1; d <= 5; d++) {
      const r = await page.request.post(`/api/timetables/${ttId}/entries`, {
        data: { course_assignment_id: aIds[i], weekday: d, period_no: SLOTS[i], span: 1 },
      })
      expect(r.status(), `${SUBJECTS[i]} 周${d} 节次${SLOTS[i]}`).toBe(201)
    }
  }
  await page.reload()
  await page.locator('.n-base-selection').first().click()
  await page.locator('.n-base-select-option', { hasText: semesterLabel(YEAR) }).click()

  // 未排列表归零(验收①)
  await expect(page.getByTestId('wb-remaining')).toHaveText('剩余 0 节')
  await expect(page.getByTestId('wb-tray-empty')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/wb-3-full.png` })

  // ── ⑦ 三视角一致(验收②):班级视角排的课,教师视角立即可见 ──
  await page.getByTestId('wb-view-teacher').click()
  await page.getByTestId('wb-teacher').click()
  await page.locator('.n-base-select-option', { hasText: '王师' }).first().click()
  // 王师:301 语文(周一~周五第一节)+ 302 数学二(周五第七节)
  await expect(cell(page, 1, 2)).toContainText('语文')
  await expect(cell(page, 5, 9)).toContainText('数学二')
  await page.screenshot({ path: `${SHOTS}/wb-4-teacher-view.png` })

  await deleteSemesterByYearTerm(page, YEAR, 1)
})
