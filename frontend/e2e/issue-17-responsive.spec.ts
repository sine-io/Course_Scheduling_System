import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
  { width: 375, height: 812 },
] as const

const USER = {
  id: 17,
  username: 'issue-17-scheduler',
  display_name: '排课工作面验收用户',
  roles: ['scheduler'],
  must_change_password: false,
}

const PERIODS = Array.from({ length: 7 }, (_, dayIndex) => [
  {
    id: dayIndex * 3 + 1,
    weekday: dayIndex + 1,
    period_no: 1,
    name: '第一节',
    start_time: '08:00',
    end_time: '08:40',
    type: 'regular',
  },
  {
    id: dayIndex * 3 + 2,
    weekday: dayIndex + 1,
    period_no: 2,
    name: '午休',
    start_time: '12:00',
    end_time: '13:10',
    type: 'lunch',
  },
  {
    id: dayIndex * 3 + 3,
    weekday: dayIndex + 1,
    period_no: 3,
    name: '第二节',
    start_time: '13:10',
    end_time: '13:50',
    type: 'regular',
  },
]).flat()

const PERIOD_TABLE = {
  id: 91,
  name: '全周作息时间表',
  semester_id: 71,
  num_weekdays: 7,
  is_default: true,
  periods: PERIODS,
}

const SEMESTER = {
  id: 71,
  academic_year: 2045,
  term: 1,
  label: '2045-2046学年第一学期',
  status: 'preparing',
  readiness: 'ready',
  start_date: '2045-09-01',
  end_date: '2046-01-20',
  period_tables: [PERIOD_TABLE],
}

const CLASS = {
  id: 301,
  semester_id: 71,
  grade: 7,
  name: '1班',
  track: 'junior_high',
  period_table_id: 91,
}
const TEACHER = {
  id: 401,
  semester_id: 71,
  name: '陈老师',
  base_periods: 2,
  admin_reduction: 0,
  email: null,
}
const ROOM = {
  id: 601,
  semester_id: 71,
  name: '七年级1班教室',
  room_type: 'normal',
  capacity: 45,
  bind_subject: null,
}
const ASSIGNMENT = {
  id: 501,
  semester_id: 71,
  scheduling_unit: {
    id: 701,
    semester_id: 71,
    unit_type: 'single',
    name: '七年级1班',
    classes: [{ id: 301, name: '1班', grade: 7 }],
  },
  subject: { id: 501, name: '语文' },
  periods_per_week: 3,
  required_room_type: null,
  room_id: null,
  lock_room: false,
  teachers: [{ teacher_id: 401, is_lead: true, name: '陈老师' }],
  block_rules: [],
}

function entry(id: number, weekday: number, periodNo: number, locked = false) {
  return {
    id,
    course_assignment_id: 501,
    weekday,
    period_no: periodNo,
    span: 1,
    locked,
    subject: '语文',
    teachers: ['陈老师'],
    classes: ['1班'],
    unit_type: 'single',
    unit_name: '七年级1班',
    room: '七年级1班教室',
    teacher_ids: [401],
    class_ids: [301],
    room_id: 601,
  }
}

interface MockState {
  entries: ReturnType<typeof entry>[]
  nextEntryId: number
  writeRequests: string[]
}

interface MockOptions {
  emptyDraft?: boolean
  emptyAssignments?: boolean
  failAssignments?: boolean
  failPlace?: boolean
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

async function mockApplication(
  page: Page,
  roles = ['scheduler'],
  options: MockOptions = {},
): Promise<MockState> {
  const state: MockState = {
    entries: [entry(801, 2, 1, true)],
    nextEntryId: 900,
    writeRequests: [],
  }

  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()
    if (!path.startsWith('/api/')) return route.continue()
    if (!['GET', 'HEAD'].includes(method)) state.writeRequests.push(`${method} ${path}`)

    if (path === '/api/app-config') return fulfillJson(route, {
      school_name: '排课工作面验收学校',
      timezone: 'Asia/Shanghai',
      role_display_names: {
        admin: '系统管理员',
        director: '教务主任',
        scheduler: '排课管理员',
        teacher: '教师',
      },
      academic_year: {
        storage: 'start_year',
        min: 1900,
        max: 2100,
        label_format: '{year}-{next_year}学年{term_label}',
        term_labels: { '1': '第一学期', '2': '第二学期' },
      },
    })
    if (path === '/api/auth/me') return fulfillJson(route, { ...USER, roles })
    if (path === '/api/wizard/state') return fulfillJson(route, {
      current_step: 4,
      completed: true,
      semester_id: 71,
      total_steps: 5,
      has_semesters: true,
    })
    if (path === '/api/notifications/mine' || path === '/api/notifications/mine/unread-count') {
      return fulfillJson(route, path.endsWith('unread-count') ? { unread: 0 } : { items: [], unread: 0 })
    }
    if (path === '/api/semesters') return fulfillJson(route, [SEMESTER])
    if (path === '/api/semesters/71') return fulfillJson(route, SEMESTER)
    if (path === '/api/class-units/301/period-table') return fulfillJson(route, PERIOD_TABLE)
    if (path === '/api/class-units') return fulfillJson(route, [CLASS])
    if (path === '/api/subjects') return fulfillJson(route, [{ id: 501, semester_id: 71, name: '语文' }])
    if (path === '/api/teachers') return fulfillJson(route, [TEACHER])
    if (path === '/api/rooms') return fulfillJson(route, [ROOM])
    if (path === '/api/scheduling-units') return fulfillJson(route, [])
    if (path === '/api/assignments/teacher-load') return fulfillJson(route, [{
      teacher_id: 401,
      name: '陈老师',
      base_periods: 2,
      admin_reduction: 0,
      target: 2,
      assigned: 3,
      delta: 1,
      max_overtime: 2,
      over_limit: false,
    }])
    if (path === '/api/assignments/class-load') return fulfillJson(route, [{
      class_id: 301,
      name: '1班',
      grade: 7,
      assigned: 3,
      capacity: 14,
      over_capacity: false,
    }])
    if (path === '/api/assignments' && options.failAssignments) {
      return fulfillJson(route, { detail: '教学任务服务暂时不可用' }, 503)
    }
    if (path === '/api/assignments') {
      return fulfillJson(route, options.emptyAssignments ? [] : [ASSIGNMENT])
    }
    if (path === '/api/timetables' && method === 'GET') return fulfillJson(route, [{
      id: 81,
      semester_id: 71,
      name: '草稿A',
      status: 'draft',
      entry_count: state.entries.length,
    }].filter(() => !options.emptyDraft))
    if (path === '/api/timetables/81' && method === 'GET') return fulfillJson(route, {
      id: 81,
      semester_id: 71,
      name: '草稿A',
      status: 'draft',
      entries: state.entries,
    })
    if (path === '/api/timetables/81/check-conflict') {
      const payload = request.postDataJSON() as { weekday: number; period_no: number }
      if (payload.weekday === 5 && payload.period_no === 3) {
        return fulfillJson(route, {
          ok: false,
          conflicts: [{ code: 'teacher_busy', message: '陈老师此时段已有课' }],
        })
      }
      return fulfillJson(route, { ok: true, conflicts: [] })
    }
    if (path === '/api/timetables/81/entries' && method === 'POST') {
      if (options.failPlace) {
        return fulfillJson(route, { detail: '课表保存失败，请稍后重试' }, 503)
      }
      const payload = request.postDataJSON() as { weekday: number; period_no: number }
      state.entries.push(entry(state.nextEntryId++, payload.weekday, payload.period_no))
      return fulfillJson(route, {
        id: 81,
        semester_id: 71,
        name: '草稿A',
        status: 'draft',
        entries: state.entries,
      }, 201)
    }
    const entryPath = path.match(/^\/api\/timetables\/81\/entries\/(\d+)$/)
    if (entryPath && method === 'PATCH') {
      const payload = request.postDataJSON() as { weekday: number; period_no: number }
      const current = state.entries.find((item) => item.id === Number(entryPath[1]))
      if (current) Object.assign(current, payload)
      return fulfillJson(route, {
        id: 81,
        semester_id: 71,
        name: '草稿A',
        status: 'draft',
        entries: state.entries,
      })
    }
    if (entryPath && method === 'DELETE') {
      state.entries = state.entries.filter((item) => item.id !== Number(entryPath[1]))
      return route.fulfill({ status: 204 })
    }

    return fulfillJson(route, { detail: `未模拟 ${method} ${path}` }, 501)
  })

  return state
}

async function expectNoRootOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth)
}

const cell = (page: Page, weekday: number, period: number) => (
  page.locator(`[data-weekday="${weekday}"][data-period="${period}"]`)
)

for (const viewport of VIEWPORTS) {
  test(`排课工作面 ${viewport.width}x${viewport.height} 保持高密度内容与页面边界`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await mockApplication(page)

    await page.goto('/scheduling/assignments')
    await expect(page.getByTestId('assignments-page')).toBeVisible()
    await expect(page.getByLabel('选择工作学期')).toBeVisible()
    await expect(page.getByTestId('assignment-table')).toContainText('语文')
    await expect(page.getByTestId('teacher-load')).toContainText('+1 超课时')
    await expectNoRootOverflow(page)
    await page.screenshot({
      path: testInfo.outputPath(`assignments-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    })

    if (viewport.width <= 768) {
      const tableDimensions = await page.getByTestId('assignment-table-scroll').evaluate((element) => ({
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
      }))
      expect(tableDimensions.scrollWidth).toBeGreaterThan(tableDimensions.clientWidth)
    }

    if (viewport.width === 375) {
      await page.getByTestId('assignment-add').click()
      const modal = page.locator('.n-modal').filter({ hasText: '新增教学任务' })
      await expect(modal.getByRole('radiogroup', { name: '排课对象' })).toBeVisible()
      await expect(modal.getByLabel('选择排课班级')).toBeVisible()
      await expect(modal.getByLabel('选择科目')).toBeVisible()
      await expect(modal.getByLabel('选择授课教师')).toBeVisible()
      await expect(modal.getByLabel('每周课时')).toBeVisible()
      await expect(modal.getByLabel('选择教室/场地类型')).toBeVisible()
      await expect(modal.getByLabel('指定教室/场地')).toBeVisible()
      await expect(modal.getByRole('checkbox', { name: '锁定教室/场地（排课时不得变更）' })).toBeVisible()
      const box = await modal.boundingBox()
      expect(box).not.toBeNull()
      expect(box!.x).toBeGreaterThanOrEqual(0)
      expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width + 1)
      expect(box!.y).toBeGreaterThanOrEqual(0)
      expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height + 1)
      await page.keyboard.press('Escape')
    }

    await page.goto('/scheduling/workbench')
    await expect(page.getByTestId('workbench-page')).toBeVisible()
    await expect(page.getByLabel('选择工作学期')).toBeVisible()
    await expect(page.getByLabel('选择课表草稿')).toBeVisible()
    await expect(page.getByRole('radiogroup', { name: '课表视角' })).toBeVisible()
    await expect(page.getByLabel('选择班级')).toBeVisible()
    await expect(page.getByTestId('wb-remaining')).toHaveText('剩余 2 节')
    await expect(page.getByTestId('timetable-scroll')).toBeVisible()
    await expectNoRootOverflow(page)
    await page.screenshot({
      path: testInfo.outputPath(`workbench-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    })

    const gridDimensions = await page.getByTestId('timetable-scroll').evaluate((element) => ({
      scrollWidth: element.scrollWidth,
      clientWidth: element.clientWidth,
    }))
    if (viewport.width <= 768) {
      expect(gridDimensions.scrollWidth).toBeGreaterThan(gridDimensions.clientWidth)
    }

    await page.getByTestId('wb-view-teacher').click()
    await expect(page.getByLabel('选择教师')).toBeVisible()
    await expect(page.getByTestId('workbench-readonly')).toContainText('只读')
    await expectNoRootOverflow(page)

    if (viewport.width === 1280) {
      await page.getByTestId('wb-view-class').click()
      const trayItem = page.getByTestId('wb-tray-语文')
      await trayItem.focus()
      await expect(trayItem).toBeFocused()
      await page.keyboard.press('Enter')
      await expect(trayItem).toHaveAttribute('aria-pressed', 'true')

      const conflictAction = page.getByRole('button', { name: '将语文排入星期五第二节' })
      await conflictAction.focus()
      await expect(conflictAction).toBeFocused()
      await page.keyboard.press('Enter')
      await expect(cell(page, 5, 3)).toHaveClass(/is-conflict/)
      await expect(cell(page, 5, 3)).toContainText('陈老师此时段已有课')

      const placeAction = page.getByRole('button', { name: '将语文排入星期一第二节' })
      await placeAction.focus()
      await page.keyboard.press('Enter')
      await expect(page.getByTestId('wb-remaining')).toHaveText('剩余 1 节')
      await expect(page.getByTestId('workbench-save-status')).toContainText('已保存')

      await page.getByTestId('wb-undo').click()
      await expect(cell(page, 1, 3)).not.toContainText('语文')
      await expect(page.getByTestId('wb-remaining')).toHaveText('剩余 2 节')
      await expect(page.getByTestId('wb-redo')).toBeEnabled()
      await page.getByTestId('wb-redo').click()
      await expect(cell(page, 1, 3)).toContainText('语文')
      await expect(page.getByTestId('wb-remaining')).toHaveText('剩余 1 节')

      const moveAction = cell(page, 1, 3).getByRole('button', { name: '移动语文' })
      await moveAction.focus()
      await page.keyboard.press('Enter')
      const moveTarget = page.getByRole('button', { name: '将语文移到星期二第二节' })
      await moveTarget.focus()
      await page.keyboard.press('Enter')
      await expect(cell(page, 1, 3)).not.toContainText('语文')
      await expect(cell(page, 2, 3)).toContainText('语文')

      const removeAction = cell(page, 2, 3).getByRole('button', { name: '移除语文' })
      await removeAction.focus()
      await page.keyboard.press('Enter')
      await expect(cell(page, 2, 3)).not.toContainText('语文')
      await expect(page.getByTestId('wb-remaining')).toHaveText('剩余 2 节')
    }
  })
}

test('只读班级工作台保留真实未排课程信息但禁用写入操作', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  const state = await mockApplication(page, ['director'])

  await page.goto('/scheduling/workbench')
  await expect(page.getByTestId('workbench-readonly')).toContainText('仅可查看')
  await expect(page.getByTestId('workbench-save-status')).toContainText('只读')
  await expect(page.getByTestId('wb-remaining')).toHaveText('剩余 2 节')
  await expect(page.getByTestId('wb-tray-语文')).toBeDisabled()
  expect(state.writeRequests.filter((request) => request.includes('/entries'))).toEqual([])
})

test('班级未配置教学任务时与全部排完状态明确区分', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await mockApplication(page, ['scheduler'], { emptyAssignments: true })

  await page.goto('/scheduling/assignments')
  await expect(page.getByTestId('assignment-list-empty')).toContainText('暂无教学任务')

  await page.goto('/scheduling/workbench')
  await expect(page.getByTestId('wb-tray-unconfigured')).toContainText('尚未配置教学任务')
  await expect(page.getByTestId('wb-tray-empty')).toHaveCount(0)
})

test('课表保存失败时显示持久的错误状态', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await mockApplication(page, ['scheduler'], { failPlace: true })

  await page.goto('/scheduling/workbench')
  const trayItem = page.getByTestId('wb-tray-语文')
  await trayItem.focus()
  await page.keyboard.press('Enter')
  const target = page.getByRole('button', { name: '将语文排入星期一第二节' })
  await target.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('workbench-save-status')).toContainText('保存失败')
  await expectNoRootOverflow(page)
})

test('教务主任看到只读工作台时不创建草稿或显示写入控件', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  const state = await mockApplication(page, ['director'], { emptyDraft: true })

  await page.goto('/scheduling/workbench')
  await expect(page.getByTestId('workbench-page')).toBeVisible()
  await expect(page.getByTestId('workbench-readonly')).toContainText('仅可查看')
  await expect(page.getByTestId('workbench-no-draft')).toContainText('还没有课表草稿')
  expect(state.writeRequests.filter((request) => request === 'POST /api/timetables')).toEqual([])

  await page.goto('/scheduling/assignments')
  await expect(page.getByTestId('assignments-page')).toBeVisible()
  await expect(page.getByTestId('assignments-readonly')).toBeVisible()
  await expect(page.getByTestId('assignment-add')).toHaveCount(0)
})

test('教学任务读取失败时显示可重试状态', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await mockApplication(page, ['scheduler'], { failAssignments: true })

  await page.goto('/scheduling/assignments')
  await expect(page.getByTestId('assignments-error')).toContainText('教学任务服务暂时不可用')
  await expect(page.getByTestId('assignments-retry')).toBeVisible()

  await page.goto('/scheduling/workbench')
  await expect(page.getByTestId('workbench-error')).toContainText('教学任务服务暂时不可用')
  await expect(page.getByTestId('workbench-retry')).toBeVisible()
})
