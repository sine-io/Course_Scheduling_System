import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

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
    admin_title: '年级组长',
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

function tab(page: Page, label: string) {
  return page.locator('.n-tabs-tab', { hasText: label })
}

async function mockSession(page: Page, roles: string[], state: MockState) {
  const user = {
    id: 18,
    username: 'issue-18-user',
    display_name: '基础数据验收用户',
    roles,
    must_change_password: false,
  }
  await page.route('**/api/auth/me', (route) => fulfillJson(route, user))
  await page.route('**/api/wizard/state', (route) => fulfillJson(route, {
    current_step: 4,
    completed: true,
    semester_id: 44,
    total_steps: 5,
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

  await page.route('**/api/semesters', (route) => fulfillJson(route, [SEMESTER]))
  await page.route('**/api/semesters/44', (route) => fulfillJson(route, {
    ...SEMESTER,
    period_tables: [PERIOD_TABLE],
  }))
  await page.route('**/api/subjects?**', (route) => fulfillJson(route, SUBJECTS))
  await page.route('**/api/teachers?**', (route) => fulfillJson(route, TEACHERS))
  await page.route('**/api/teachers/bindable-accounts**', (route) => fulfillJson(route, [
    { id: 12, username: 'chen', display_name: '陈老师' },
  ]))
  await page.route('**/api/class-units?**', (route) => fulfillJson(route, CLASSES))
  await page.route('**/api/rooms?**', (route) => fulfillJson(route, ROOMS))
  await page.route('**/api/period-tables/77/available-slots', (route) => fulfillJson(route, [
    {
      weekday: 1,
      period_no: 1,
      name: '第一节',
      start_time: '08:00',
      end_time: '08:40',
    },
    {
      weekday: 2,
      period_no: 1,
      name: '第一节',
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

for (const viewport of VIEWPORTS) {
  test(`基础数据工作面 ${viewport.width}x${viewport.height} 保持功能与内部滚动`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const state: MockState = { uploadAttempts: 0, savedRules: null }
    await mockSession(page, ['scheduler'], state)

    await page.goto('/basedata')
    await expect(page.getByTestId('basedata-workspace')).toBeVisible()
    await expect(page.getByTestId('teachers-table')).toContainText('陈老师')
    await expectNoRootOverflow(page)

    if (viewport.width <= 768) {
      const dimensions = await page.getByTestId('teachers-table-scroll').evaluate((element) => ({
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
      }))
      expect(dimensions.scrollWidth).toBeGreaterThan(dimensions.clientWidth)
    }

    await page.getByTestId('teacher-add').click()
    const teacherModal = page.locator('.n-modal').filter({ hasText: '新增教师' })
    await expect(teacherModal.getByTestId('teacher-email')).toBeVisible()
    await expect(teacherModal.getByTestId('teacher-account')).toBeVisible()
    if (viewport.width === 375) {
      const box = await teacherModal.boundingBox()
      expect(box).not.toBeNull()
      expect(box!.x).toBeGreaterThanOrEqual(0)
      expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width + 1)
    }
    await teacherModal.getByRole('button', { name: '取消' }).click()

    if (viewport.width === 1280) {
      await page.getByTestId('teacher-rules-7').click()
      const ruleButton = page.getByRole('button', { name: /周一，第 1 节/ })
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
    await expectNoRootOverflow(page)

    await tab(page, '科目').click()
    await expect(page.getByTestId('subjects-table')).toContainText('数学')
    await page.getByTestId('subject-add').click()
    const subjectModal = page.locator('.n-modal').filter({ hasText: '新增科目' })
    await expect(subjectModal.getByTestId('sub-name')).toBeVisible()
    if (viewport.width === 375) {
      const box = await subjectModal.boundingBox()
      expect(box).not.toBeNull()
      expect(box!.x).toBeGreaterThanOrEqual(0)
      expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width + 1)
    }
    await subjectModal.getByRole('button', { name: '取消' }).click()
    await expectNoRootOverflow(page)

    await tab(page, '教室/场地').click()
    await expect(page.getByTestId('rooms-table')).toContainText('物理实验室')
    await expectNoRootOverflow(page)

    await tab(page, '批量导入').click()
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
  await expect(page.getByTestId('teacher-rules-7')).toHaveCount(0)

  await tab(page, '班级').click()
  await expect(page.getByTestId('class-add')).toHaveCount(0)
  await tab(page, '科目').click()
  await expect(page.getByTestId('subject-add')).toHaveCount(0)
  await tab(page, '教室/场地').click()
  await expect(page.getByTestId('room-add')).toHaveCount(0)
  await expect(tab(page, '批量导入')).toHaveCount(0)
  await expectNoRootOverflow(page)

  expect(writeRequests).toEqual([])
  expect(state.uploadAttempts).toBe(0)
  expect(state.savedRules).toBeNull()
})
