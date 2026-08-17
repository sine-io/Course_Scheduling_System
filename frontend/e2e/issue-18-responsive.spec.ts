import { expect, test } from '@playwright/test'
import type { Locator, Page, Route } from '@playwright/test'

const VIEWPORTS = [
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
  { width: 375, height: 812 },
] as const

const SEMESTER = {
  id: 44,
  academic_year: 2042,
  term: 1,
  label: '2042-2043学年第一学期',
  status: 'preparing',
  readiness: 'draft',
  start_date: '2042-09-01',
  end_date: '2043-01-20',
}
const SUBJECTS = [
  {
    id: 3,
    semester_id: 44,
    name: '数学',
    domain: '数学领域',
    required_room_type: null,
    default_block_size: 2,
    is_major: true,
  },
]
const TEACHERS = [
  {
    id: 7,
    semester_id: 44,
    name: '陈老师',
    base_periods: 12,
    admin_title: '年级负责人',
    admin_reduction: 2,
    is_external: false,
    is_active: true,
    subjects: [{ id: 3, name: '数学' }],
    email: 'chen@example.edu.cn',
    phone: '13800000000',
    line_id: 'chen-teacher',
    user_id: 12,
  },
]
const ROOMS = [
  {
    id: 9,
    semester_id: 44,
    name: '物理实验室',
    room_type: 'special',
    capacity: 48,
    subjects: [{ id: 3, name: '数学' }],
  },
]
const CLASSES = [
  {
    id: 11,
    semester_id: 44,
    grade: 7,
    name: '七年级1班',
    track: 'junior_high',
    department: null,
    student_count: 42,
    homeroom_teacher_id: 7,
    homeroom_teacher: { id: 7, name: '陈老师' },
    period_table_id: 77,
  },
]
const PERIOD_TABLE = {
  id: 77,
  name: '默认作息时间表',
  num_weekdays: 5,
  is_default: true,
  periods: [],
}

interface MockState {
  uploadAttempts: number
  savedRules: unknown
  roomRequests?: Array<{ method: string; body?: unknown }>
  failNextRoomSave?: boolean
  rooms?: Array<(typeof ROOMS)[number]>
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

async function expectNoRootOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth)
}

async function expectInternalOverflow(page: Page, testId: string) {
  const dimensions = await page.getByTestId(testId).evaluate((element) => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }))
  expect(dimensions.scrollWidth).toBeGreaterThan(dimensions.clientWidth)
}

async function expectModalWithinViewport(
  modal: Locator,
  viewport: { width: number; height: number },
) {
  const box = await modal.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width + 1)
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height + 1)
}

function tab(page: Page, label: string) {
  return page.locator('.n-tabs-tab', { hasText: label })
}

async function mockSession(
  page: Page,
  roles: string[],
  state: MockState,
  currentSemester: typeof SEMESTER | null = SEMESTER,
) {
  const user = {
    id: 18,
    username: 'issue-18-user',
    display_name: '基础数据验收用户',
    roles,
    must_change_password: false,
  }
  await page.route('**/api/auth/me', (route) => fulfillJson(route, user))
  await page.route('**/api/wizard/state', (route) => fulfillJson(route, {
    current_step: 3,
    resume_step: 3,
    completed: true,
    paused: false,
    semester_id: 44,
    total_steps: 4,
    has_semesters: true,
  }))
  await page.route('**/api/app-config', (route) => fulfillJson(route, {
    school_name: '基础数据验收学校',
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
  }))
  await page.route('**/api/notifications/mine**', (route) => fulfillJson(route, { items: [], unread: 0 }))
  await page.route('**/api/notifications/mine/unread-count**', (route) => fulfillJson(route, { unread: 0 }))
  await page.route('**/api/semester-context', (route) => fulfillJson(route, {
    current_semester: currentSemester ? { ...currentSemester, is_current: true } : null,
    revision: 1,
    can_switch: roles.some((role) => role === 'admin' || role === 'scheduler'),
  }))

  await page.route('**/api/semesters', (route) => fulfillJson(route, [SEMESTER]))
  await page.route('**/api/semesters/44', (route) => fulfillJson(route, {
    ...SEMESTER,
    period_tables: [
      PERIOD_TABLE,
      { ...PERIOD_TABLE, id: 78, name: '走班作息时间表', is_default: false },
    ],
  }))
  await page.route('**/api/subjects?**', (route) => fulfillJson(route, SUBJECTS))
  await page.route('**/api/teachers?**', (route) => fulfillJson(route, TEACHERS))
  await page.route('**/api/teachers/bindable-accounts**', (route) => fulfillJson(route, [
    { id: 12, username: 'chen', display_name: '陈老师' },
  ]))
  await page.route('**/api/class-units?**', (route) => fulfillJson(route, CLASSES))
  state.rooms ??= ROOMS.map((room) => ({ ...room, subjects: [...room.subjects] }))
  await page.route('**/api/rooms**', async (route) => {
    const request = route.request()
    const method = request.method()
    const path = new URL(request.url()).pathname
    if (method === 'GET') return fulfillJson(route, state.rooms)

    const body = request.postDataJSON() as {
      name: string
      room_type: string
      capacity: number | null
      subject_ids: number[]
    } | null
    state.roomRequests?.push({ method, body })

    if (method === 'POST') {
      if (state.failNextRoomSave) {
        state.failNextRoomSave = false
        return fulfillJson(route, { detail: '模拟保存失败，请重试' }, 503)
      }
      const room = {
        id: Math.max(0, ...state.rooms.map((item) => item.id)) + 1,
        semester_id: 44,
        name: body!.name,
        room_type: body!.room_type,
        capacity: body!.capacity,
        subjects: SUBJECTS.filter((subject) => body!.subject_ids.includes(subject.id))
          .map((subject) => ({ id: subject.id, name: subject.name })),
      }
      state.rooms.push(room)
      return fulfillJson(route, room, 201)
    }

    const roomId = Number(path.split('/').at(-1))
    if (method === 'PATCH') {
      const room = state.rooms.find((item) => item.id === roomId)!
      Object.assign(room, {
        name: body!.name,
        room_type: body!.room_type,
        capacity: body!.capacity,
        subjects: SUBJECTS.filter((subject) => body!.subject_ids.includes(subject.id))
          .map((subject) => ({ id: subject.id, name: subject.name })),
      })
      return fulfillJson(route, room)
    }
    if (method === 'DELETE') {
      state.rooms = state.rooms.filter((item) => item.id !== roomId)
      return route.fulfill({ status: 204 })
    }
    return fulfillJson(route, { detail: `未模拟 ${method} ${path}` }, 501)
  })
  await page.route('**/api/period-tables/77/available-slots', (route) => fulfillJson(route, [
    {
      weekday: 1,
      period_no: 1,
      name: '早自习',
      start_time: '08:00',
      end_time: '08:40',
    },
    {
      weekday: 2,
      period_no: 1,
      name: '早自习',
      start_time: '08:00',
      end_time: '08:40',
    },
  ]))
  await page.route('**/api/teachers/7/time-rules', async (route) => {
    if (route.request().method() === 'PUT') {
      state.savedRules = route.request().postDataJSON()
      await fulfillJson(route, state.savedRules)
      return
    }
    await fulfillJson(route, [])
  })
  await page.route('**/api/import/templates/*', (route) => route.fulfill({
    status: 200,
    contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    body: 'mock template',
  }))
  await page.route('**/api/import/subjects?**', async (route) => {
    state.uploadAttempts += 1
    await fulfillJson(route, state.uploadAttempts === 1
      ? { imported: 0, errors: ['第 4 行：科目名称不能为空'] }
      : { imported: 1, errors: [] })
  })
}

test('教室/场地保留原有校验、失败重试和完整 CRUD 语义', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  const state: MockState = {
    uploadAttempts: 0,
    savedRules: null,
    roomRequests: [],
    failNextRoomSave: true,
  }
  await mockSession(page, ['admin'], state)

  await page.goto('/basedata')
  await tab(page, '教室/场地').click()
  await page.getByTestId('room-add').click()
  const modal = page.locator('.n-modal').filter({ hasText: '新增教室/场地' })

  await modal.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText('请输入教室/场地名称')).toBeVisible()
  expect(state.roomRequests).toEqual([])

  await modal.getByLabel('名称').fill('   ')
  await modal.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText('模拟保存失败，请重试')).toBeVisible()
  await expect.poll(() => state.roomRequests?.length).toBe(1)
  expect(state.roomRequests?.[0]).toEqual({
    method: 'POST',
    body: { name: '   ', room_type: 'normal', capacity: null, subject_ids: [] },
  })

  await modal.getByLabel('名称').fill('  备用教室  ')
  await modal.getByRole('button', { name: '保存' }).click()
  await expect(modal).toBeHidden()
  await expect(page.getByTestId('rooms-table')).toContainText('备用教室')

  await page.getByTestId('room-edit-10').click()
  const editModal = page.locator('.n-modal').filter({ hasText: '编辑教室/场地' })
  await editModal.getByLabel('名称').fill('  更新后的教室  ')
  await editModal.getByLabel('容量').fill('55')
  await editModal.getByRole('button', { name: '保存' }).click()
  await expect(page.getByTestId('rooms-table')).toContainText('更新后的教室')
  expect(state.roomRequests?.at(-1)).toMatchObject({
    method: 'PATCH',
    body: { name: '  更新后的教室  ', capacity: 55 },
  })

  await page.getByTestId('room-delete-10').click()
  const confirmation = page.locator('.n-popover').filter({ hasText: '将永久删除教室/场地' })
  await confirmation.getByRole('button', { name: '确认' }).click()
  await expect(page.getByTestId('rooms-table')).not.toContainText('更新后的教室')
  expect(state.roomRequests?.at(-1)).toMatchObject({
    method: 'DELETE',
    body: { confirmed: true, target: 'room:10' },
  })
})

test('基础数据在学期请求期间显示加载状态', async ({ page }) => {
  const state: MockState = { uploadAttempts: 0, savedRules: null }
  await mockSession(page, ['scheduler'], state)
  let release!: () => void
  const pending = new Promise<void>((resolve) => { release = resolve })
  await page.route('**/api/semesters', async (route) => {
    await pending
    await fulfillJson(route, [SEMESTER])
  })

  const navigation = page.goto('/basedata')
  await expect(page.getByTestId('basedata-loading')).toBeVisible()
  release()
  await navigation
  await expect(page.getByTestId('basedata-workspace')).toBeVisible()
})

test('基础数据在没有学期时显示明确空状态', async ({ page }) => {
  const state: MockState = { uploadAttempts: 0, savedRules: null }
  await mockSession(page, ['scheduler'], state, null)
  await page.route('**/api/semesters', (route) => fulfillJson(route, []))

  await page.goto('/basedata')
  await expect(page.getByTestId('basedata-empty')).toContainText('尚未创建任何学期')
  await expect(page.getByRole('button', { name: '前往学期配置' })).toBeVisible()
})

test('基础数据学期请求失败后可以重试', async ({ page }) => {
  const state: MockState = { uploadAttempts: 0, savedRules: null }
  await mockSession(page, ['scheduler'], state)
  let attempts = 0
  let failing = true
  await page.route('**/api/semesters', (route) => {
    attempts += 1
    return failing
      ? fulfillJson(route, { detail: '学期服务暂时不可用' }, 503)
      : fulfillJson(route, [SEMESTER])
  })

  await page.goto('/basedata')
  await expect(page.getByTestId('basedata-error')).toContainText('学期服务暂时不可用')
  failing = false
  await page.getByTestId('basedata-retry').click()
  await expect(page.getByTestId('basedata-workspace')).toBeVisible()
  expect(attempts).toBeGreaterThanOrEqual(2)
})

for (const viewport of VIEWPORTS) {
  test(`基础数据工作面 ${viewport.width}x${viewport.height} 保持功能与内部滚动`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const state: MockState = { uploadAttempts: 0, savedRules: null }
    await mockSession(page, ['scheduler'], state)

    await page.goto('/basedata')
    await expect(page.getByTestId('basedata-workspace')).toBeVisible()
    await expect(page.getByLabel('选择工作学期')).toBeVisible()
    await expect(page.getByTestId('teachers-table')).toContainText('陈老师')
    await expectNoRootOverflow(page)

    if (viewport.width <= 768) await expectInternalOverflow(page, 'teachers-table-scroll')
    await page.screenshot({
      path: testInfo.outputPath(`basedata-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    })

    await page.getByTestId('teacher-add').click()
    const teacherModal = page.locator('.n-modal').filter({ hasText: '新增教师' })
    await expect(teacherModal.getByLabel('姓名')).toBeVisible()
    await expect(teacherModal.getByLabel('任教科目')).toBeVisible()
    await expect(teacherModal.getByLabel('基本课时')).toBeVisible()
    await expect(teacherModal.getByLabel('行政减课')).toBeVisible()
    await expect(teacherModal.getByLabel('行政职务')).toBeVisible()
    await expect(teacherModal.getByRole('switch', { name: '外聘教师' })).toBeVisible()
    await expect(teacherModal.getByRole('switch', { name: '在职' })).toBeVisible()
    await expect(teacherModal.getByLabel('电子邮箱')).toBeVisible()
    await expect(teacherModal.getByLabel('手机')).toBeVisible()
    await expect(teacherModal.getByLabel('即时通讯账号')).toBeVisible()
    await expect(teacherModal.getByLabel('绑定登录账号')).toHaveCount(0)
    if (viewport.width === 375) {
      await expectModalWithinViewport(teacherModal, viewport)
    }
    await teacherModal.getByRole('button', { name: '取消' }).click()

    if (viewport.width === 1280) {
      await page.getByTestId('teacher-rules-7').click()
      const ruleButton = page.getByRole('button', { name: /周一，早自习/ })
      await expect(ruleButton).toBeVisible()
      await ruleButton.focus()
      await ruleButton.press('Enter')
      await expect(ruleButton).toHaveText('不可排')
      await page.getByTestId('time-rules-save').click()
      await expect.poll(() => state.savedRules).toEqual([
        { weekday: 1, period_no: 1, rule_type: 'unavailable' },
      ])
    }

    await tab(page, '班级').click()
    await expect(page.getByTestId('classes-table')).toContainText('七年级1班')
    if (viewport.width <= 768) await expectInternalOverflow(page, 'classes-table-scroll')
    await page.getByTestId('class-add').click()
    const classModal = page.locator('.n-modal').filter({ hasText: '新增班级' })
    await expect(classModal.getByLabel('年级')).toBeVisible()
    await expect(classModal.getByLabel('班级名称')).toBeVisible()
    await expect(classModal.getByLabel('学段')).toBeVisible()
    await expect(classModal.getByLabel('班主任')).toBeVisible()
    await expect(classModal.getByLabel('作息时间表')).toBeVisible()
    await expect(classModal.getByLabel('人数')).toBeVisible()
    if (viewport.width === 375) await expectModalWithinViewport(classModal, viewport)
    await classModal.getByRole('button', { name: '取消' }).click()
    await expectNoRootOverflow(page)

    await tab(page, '科目').click()
    await expect(page.getByTestId('subjects-table')).toContainText('数学')
    if (viewport.width <= 768) await expectInternalOverflow(page, 'subjects-table-scroll')
    await page.getByTestId('subject-add').click()
    const subjectModal = page.locator('.n-modal').filter({ hasText: '新增科目' })
    await expect(subjectModal.getByLabel('名称')).toBeVisible()
    await expect(subjectModal.getByLabel('领域/类别')).toBeVisible()
    await expect(subjectModal.getByLabel('所需教室/场地类型')).toBeVisible()
    await expect(subjectModal.getByLabel('默认连堂长度')).toBeVisible()
    await expect(subjectModal.getByRole('checkbox', { name: /主科/ })).toBeVisible()
    if (viewport.width === 375) {
      await expectModalWithinViewport(subjectModal, viewport)
    }
    await subjectModal.getByRole('button', { name: '取消' }).click()
    await expectNoRootOverflow(page)

    await tab(page, '教室/场地').click()
    await expect(page.getByTestId('rooms-table')).toContainText('物理实验室')
    if (viewport.width <= 768) await expectInternalOverflow(page, 'rooms-table-scroll')
    await page.getByTestId('room-add').click()
    const roomModal = page.locator('.n-modal').filter({ hasText: '新增教室/场地' })
    await expect(roomModal.getByLabel('名称')).toBeVisible()
    await expect(roomModal.getByLabel('教室/场地类型')).toBeVisible()
    await expect(roomModal.getByLabel('容量')).toBeVisible()
    await expect(roomModal.getByLabel('适用科目')).toBeVisible()
    if (viewport.width === 375) await expectModalWithinViewport(roomModal, viewport)
    await roomModal.getByRole('button', { name: '取消' }).click()
    await expectNoRootOverflow(page)

    await tab(page, '批量导入').click()
    await expect(page.getByTestId('combined-import-panel')).toBeVisible()
    await expect(page.getByTestId('combined-download')).toBeVisible()
    await expect(page.getByTestId('combined-preview')).toBeDisabled()
    await page.locator('.n-radio-button', { hasText: '按表导入' }).click()
    await expect(page.getByRole('radiogroup', { name: '选择导入数据类型' })).toBeVisible()
    await expect(page.getByTestId('import-download')).toBeVisible()
    await expect(page.getByTestId('import-upload')).toBeDisabled()
    await expectNoRootOverflow(page)

    if (viewport.width === 1280) {
      const [download] = await Promise.all([
        page.waitForEvent('download'),
        page.getByTestId('import-download').click(),
      ])
      expect(download.suggestedFilename()).toBe('subjects_template.xlsx')

      await page.locator('input[type="file"]').setInputFiles({
        name: 'subjects.xlsx',
        mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        buffer: Buffer.from('mock workbook'),
      })
      await page.getByTestId('import-upload').click()
      await expect(page.getByTestId('import-result-errors')).toContainText('第 4 行：科目名称不能为空')
      await expect(page.getByTestId('import-upload')).toContainText('修正文件后重试')

      const importWorkspace = page.getByTestId('import-workspace')
      const importEntity = (label: string) => importWorkspace.locator('.n-radio-button', { hasText: label })
      await importEntity('教师').click()
      const createAccounts = page.getByRole('checkbox', { name: /同时创建教师登录账号/ })
      await expect(createAccounts).toHaveCount(0)
      await importEntity('科目').click()
      await expect(page.getByTestId('import-result-errors')).toBeVisible()
      await importEntity('教师').click()
      await expect(createAccounts).toHaveCount(0)
      await expect(page.getByText('subjects.xlsx')).toBeVisible()
      await importEntity('科目').click()

      await page.getByTestId('import-upload').click()
      await expect(page.getByTestId('import-success')).toContainText('成功导入 1 条数据')
      expect(state.uploadAttempts).toBe(2)
    }
  })
}

test('教务主任仅能查看基础数据且不会触发写请求', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  const state: MockState = { uploadAttempts: 0, savedRules: null }
  await mockSession(page, ['director'], state)
  const writeRequests: string[] = []
  page.on('request', (request) => {
    if (!['GET', 'HEAD'].includes(request.method())) {
      writeRequests.push(`${request.method()} ${new URL(request.url()).pathname}`)
    }
  })

  await page.goto('/basedata')
  await expect(page.getByTestId('basedata-readonly')).toContainText('仅可查看基础数据')
  await expect(page.getByTestId('teachers-table')).toContainText('陈老师')
  await expect(page.getByTestId('teacher-add')).toHaveCount(0)
  await expect(page.getByTestId('teacher-edit-7')).toHaveCount(0)
  await page.getByTestId('teacher-rules-7').click()
  const readOnlyRule = page.getByRole('button', { name: /周一，早自习/ })
  await expect(readOnlyRule).toBeDisabled()
  await expect(page.getByTestId('time-rules-save')).toHaveCount(0)
  await page.keyboard.press('Escape')

  await tab(page, '班级').click()
  await expect(page.getByTestId('class-add')).toHaveCount(0)
  await tab(page, '科目').click()
  await expect(page.getByTestId('subject-add')).toHaveCount(0)
  await tab(page, '教室/场地').click()
  await expect(page.getByTestId('room-add')).toHaveCount(0)
  await tab(page, '批量导入').click()
  await expect(page.getByTestId('import-readonly')).toContainText('没有基础数据写入权限')
  await expect(page.getByTestId('combined-import-panel')).toBeVisible()
  await expect(page.getByTestId('combined-download')).toBeVisible()
  await expect(page.getByTestId('combined-file')).toHaveCount(0)
  await expect(page.getByTestId('combined-preview')).toHaveCount(0)
  await page.locator('.n-radio-button', { hasText: '按表导入' }).click()
  await expect(page.getByRole('radiogroup', { name: '选择导入数据类型' })).toBeVisible()
  await expect(page.getByTestId('import-download')).toBeVisible()
  await expect(page.getByTestId('import-file')).toHaveCount(0)
  await expect(page.getByTestId('import-upload')).toHaveCount(0)
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByTestId('import-download').click(),
  ])
  expect(download.suggestedFilename()).toBe('subjects_template.xlsx')
  await expectNoRootOverflow(page)

  expect(writeRequests).toEqual([])
  expect(state.uploadAttempts).toBe(0)
  expect(state.savedRules).toBeNull()
})
