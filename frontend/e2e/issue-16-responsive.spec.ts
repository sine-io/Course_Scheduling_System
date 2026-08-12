import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'
import { SEM_END, SEM_START, WED } from './dates'

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
  { width: 375, height: 812 },
] as const

const SEMESTER = {
  id: 16,
  academic_year: Number(SEM_START.slice(0, 4)),
  term: 1,
  label: `${SEM_START.slice(0, 4)}-${SEM_END.slice(0, 4)}学年第一学期`,
  status: 'active',
  readiness: 'ready',
  start_date: SEM_START,
  end_date: SEM_END,
}

const USER = {
  id: 16,
  username: 'issue-16-scheduler',
  display_name: '调课验收用户',
  roles: ['scheduler'],
  must_change_password: false,
}

const AFFECTED_PERIOD = {
  id: 1601,
  date: WED,
  weekday: 3,
  period_no: 1,
  period_name: '第一节',
  start_time: '08:00',
  end_time: '08:40',
  subject_name: '语文',
  class_names: '七年级1班',
  room_name: '七年级1班教室',
  status: 'pending',
  handler_teacher_id: null,
  handler_name: null,
}

const PENDING_LEAVE = {
  id: 160,
  semester_id: SEMESTER.id,
  teacher_id: 161,
  teacher_name: '王老师',
  leave_type: 'sick',
  leave_type_label: '病假',
  start_date: WED,
  start_time: null,
  end_date: WED,
  end_time: null,
  reason: '身体不适',
  status: 'registered',
  created_by_name: '调课验收用户',
  created_at: `${WED}T08:00:00`,
  affected_count: 1,
  pending_count: 1,
  affected_periods: [AFFECTED_PERIOD],
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

interface MockOptions {
  failLeavesOnce?: boolean
  delayLeaves?: number
  pendingLeave?: boolean
  failAssignment?: boolean
  delayAssignment?: number
  delayRecommendations?: number
  failLeaveSave?: boolean
  delayLeaveSave?: number
  noCandidates?: boolean
  noSemesters?: boolean
  roles?: string[]
}

async function mockApplication(page: Page, options: MockOptions = {}) {
  const state = {
    leaveReads: 0,
    leaveWrites: 0,
    assignmentWrites: 0,
    undoWrites: 0,
    teacherReads: 0,
    periodStatus: 'pending' as 'pending' | 'resolved',
    handlerTeacherId: null as number | null,
    handlerName: null as string | null,
    lastAssignmentType: null as string | null,
    requestOrder: [] as string[],
  }
  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    if (!path.startsWith('/api/')) return route.continue()

    if (path === '/api/app-config') return fulfillJson(route, {
      school_name: '调课验收学校',
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
    if (path === '/api/auth/me') return fulfillJson(route, {
      ...USER,
      roles: options.roles ?? USER.roles,
    })
    if (path === '/api/wizard/state') return fulfillJson(route, {
      current_step: 4,
      completed: true,
      semester_id: SEMESTER.id,
      total_steps: 5,
      has_semesters: !options.noSemesters,
    })
    if (path === '/api/notifications/mine' || path === '/api/notifications/mine/unread-count') {
      return fulfillJson(route, path.endsWith('unread-count') ? { unread: 0 } : { items: [], unread: 0 })
    }
    if (path === '/api/semesters' || path === '/api/published/semesters') {
      return fulfillJson(route, options.noSemesters ? [] : [SEMESTER])
    }
    if (path === '/api/leave-types') return fulfillJson(route, { sick: '病假', personal: '事假' })
    if (path === '/api/teachers') {
      state.teacherReads += 1
      return fulfillJson(route, [{ id: 161, name: '王老师' }])
    }
    if (path === '/api/leaves') {
      if (request.method() === 'POST') {
        state.leaveWrites += 1
        if (options.delayLeaveSave) {
          await new Promise((resolve) => setTimeout(resolve, options.delayLeaveSave))
        }
        if (options.failLeaveSave) {
          return fulfillJson(route, { detail: '请假日期范围无效' }, 422)
        }
        return fulfillJson(route, PENDING_LEAVE, 201)
      }
      state.leaveReads += 1
      if (state.leaveReads === 1 && options.delayLeaves) {
        await new Promise((resolve) => setTimeout(resolve, options.delayLeaves))
      }
      if (state.leaveReads === 1 && options.failLeavesOnce) {
        return fulfillJson(route, { detail: '请假记录服务暂时不可用' }, 503)
      }
      return fulfillJson(route, options.pendingLeave ? [{
        ...PENDING_LEAVE,
        pending_count: state.periodStatus === 'pending' ? 1 : 0,
        affected_periods: [{
          ...AFFECTED_PERIOD,
          status: state.periodStatus,
          handler_teacher_id: state.handlerTeacherId,
          handler_name: state.handlerName,
        }],
      }] : [])
    }
    if (path === '/api/substitution-types') return fulfillJson(route, {
      substitute: '代课',
      merge: '合班',
      self_study: '自习',
      cancel: '取消课程',
    })
    if (path === `/api/affected-periods/${AFFECTED_PERIOD.id}/recommendations`) {
      state.requestOrder.push('recommendation:start')
      if (options.delayRecommendations) {
        await new Promise((resolve) => setTimeout(resolve, options.delayRecommendations))
      }
      state.requestOrder.push('recommendation:done')
      return fulfillJson(route, {
        affected_period_id: AFFECTED_PERIOD.id,
        candidates: options.noCandidates ? [] : [{
          teacher_id: 162,
          teacher_name: '陈老师',
          same_subject: true,
          at_school_that_day: true,
          sub_periods_this_month: 1,
          reasons: ['同科目教师', '当天在校'],
        }],
        no_candidate_hint: options.noCandidates ? '暂无可用代课教师，可选择合班或自习。' : '',
      })
    }
    if (
      path === `/api/affected-periods/${AFFECTED_PERIOD.id}/substitution`
      && request.method() === 'PUT'
    ) {
      state.assignmentWrites += 1
      state.requestOrder.push('assignment')
      const body = request.postDataJSON() as {
        type: string
        handler_teacher_id: number | null
        counts_toward_hours: boolean | null
      }
      state.lastAssignmentType = body.type
      if (options.delayAssignment) {
        await new Promise((resolve) => setTimeout(resolve, options.delayAssignment))
      }
      if (options.failAssignment) {
        return fulfillJson(route, { detail: '陈老师该节已有自己的课，无法指派' }, 409)
      }
      state.periodStatus = 'resolved'
      state.handlerTeacherId = body.handler_teacher_id
      state.handlerName = body.handler_teacher_id === 162 ? '陈老师' : null
      const typeLabels: Record<string, string> = {
        substitute: '代课',
        merge: '合班',
        self_study: '自习',
        cancel: '取消课程',
      }
      return fulfillJson(route, {
        id: 1602,
        affected_period_id: AFFECTED_PERIOD.id,
        type: body.type,
        type_label: typeLabels[body.type] ?? body.type,
        handler_teacher_id: body.handler_teacher_id,
        handler_name: state.handlerName,
        counts_toward_hours: body.counts_toward_hours,
        funding_source: '',
        swap_date: null,
        swap_period_name: '',
        swap_class_names: '',
        swap_subject_name: '',
        created_by_name: USER.username,
      })
    }
    if (
      path === `/api/affected-periods/${AFFECTED_PERIOD.id}/substitution`
      && request.method() === 'DELETE'
    ) {
      state.undoWrites += 1
      state.periodStatus = 'pending'
      state.handlerTeacherId = null
      state.handlerName = null
      return fulfillJson(route, {
        affected_period_id: AFFECTED_PERIOD.id,
        status: 'pending',
      })
    }

    return fulfillJson(route, { detail: `未模拟 ${request.method()} ${path}` }, 501)
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

async function expectVisibleKeyboardFocus(page: Page, testId: string) {
  const control = page.getByTestId(testId)
  await control.focus()
  await expect(control).toBeFocused()
  expect(await control.evaluate((element) => {
    const style = getComputedStyle(element)
    return element.matches(':focus-visible')
      && style.outlineStyle !== 'none'
      && Number.parseFloat(style.outlineWidth) > 0
  })).toBe(true)
  return control
}

async function fillDate(page: Page, testId: string, value: string) {
  const input = page.getByTestId(testId).locator('input')
  await input.fill(value)
  await input.press('Enter')
}

for (const viewport of VIEWPORTS) {
  test(`请假与调课工作面 ${viewport.width}x${viewport.height} 保持内容与页面边界`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await mockApplication(page, { pendingLeave: true })

    await page.goto('/leaves')
    await expect(page.getByTestId('leave-form-surface')).toBeVisible()
    await expect(page.getByTestId('lv-card')).toContainText('王老师')
    await expect(page.getByTestId('lv-affected')).toContainText('待处理')
    await expectNoRootOverflow(page)
    await page.screenshot({
      path: testInfo.outputPath(`leaves-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    })

    await page.goto('/substitutions')
    await expect(page.getByTestId('substitution-queue')).toBeVisible()
    await page.getByTestId('sub-handle').click()
    await expect(page.getByTestId('sub-candidate')).toContainText('陈老师')
    await expect(page.getByTestId('sub-alternatives')).toContainText('取消课程')
    await expectNoRootOverflow(page)
    await page.screenshot({
      path: testInfo.outputPath(`substitutions-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    })
  })
}

test('请假页在手机视口保留登记工作面和记录空状态', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await page.setViewportSize({ width: 375, height: 812 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await mockApplication(page)

  await page.goto('/leaves')

  expect(pageErrors).toEqual([])
  await expect(page.getByTestId('leaves-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: '请假登记', level: 1 })).toBeVisible()
  await expect(page.getByLabel('选择工作学期')).toBeVisible()
  await expect(page.getByTestId('leave-form-surface')).toBeVisible()
  await expect(page.getByTestId('leave-records')).toContainText('暂无请假记录')
  await expectNoRootOverflow(page)
})

test('请假页在读取失败后保留明确反馈并可重试', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const state = await mockApplication(page, { failLeavesOnce: true, delayLeaves: 600 })

  await page.goto('/leaves')

  await expect(page.getByTestId('leaves-loading')).toContainText('正在读取请假登记')
  await expect(page.getByTestId('leaves-error')).toContainText('请假记录服务暂时不可用')
  await page.getByTestId('leaves-retry').click()
  await expect(page.getByTestId('leave-records')).toContainText('暂无请假记录')
  expect(state.leaveReads).toBe(2)
  await expectNoRootOverflow(page)
})

test('请假保存中阻止重复提交，失败后保留已填内容', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  const state = await mockApplication(page, { failLeaveSave: true, delayLeaveSave: 700 })

  await page.goto('/leaves')
  await page.getByTestId('lv-teacher').click()
  await page.locator('.n-base-select-option', { hasText: '王老师' }).click()
  await fillDate(page, 'lv-start', WED)
  await fillDate(page, 'lv-end', WED)
  await page.getByTestId('lv-reason').locator('input').fill('需保留的事由')

  const submit = page.getByTestId('lv-submit')
  await submit.click()
  await expect(submit).toBeDisabled()
  await expect(submit).toContainText('登记中')
  await submit.click({ force: true })
  await expect(page.getByText('请假日期范围无效').first()).toBeVisible()
  await expect(page.getByTestId('lv-reason').locator('input')).toHaveValue('需保留的事由')
  expect(state.leaveWrites).toBe(1)
})

test('无可用学期时两个工作面给出明确下一步', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 })
  await mockApplication(page, { noSemesters: true })

  await page.goto('/leaves')
  await expect(page.getByTestId('leaves-no-semester')).toContainText('暂无可登记请假的学期')
  await expect(page.getByTestId('leave-form-surface')).toHaveCount(0)

  await page.goto('/substitutions')
  await expect(page.getByTestId('substitutions-no-semester')).toContainText('请先创建学期')
  await expect(page.getByTestId('substitution-queue')).toHaveCount(0)
  await expectNoRootOverflow(page)
})

test('教师只能登记自己的请假，不读取代登教师选项', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const state = await mockApplication(page, { pendingLeave: true, roles: ['teacher'] })

  await page.goto('/leaves')

  await expect(page.getByRole('heading', { name: '登记我的请假', level: 2 })).toBeVisible()
  await expect(page.getByTestId('lv-teacher')).toHaveCount(0)
  await expect(page.getByTestId('lv-cancel')).toBeVisible()
  expect(state.teacherReads).toBe(0)
  await expectNoRootOverflow(page)
})

test('调课与代课页在手机视口保留逐节处理与候选推荐', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await mockApplication(page, { pendingLeave: true })

  await page.goto('/substitutions')

  await expect(page.getByTestId('substitutions-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: '调课与代课处理', level: 1 })).toBeVisible()
  await expect(page.getByLabel('选择工作学期')).toBeVisible()
  await expect(page.getByTestId('sub-leave')).toContainText('王老师')
  await page.getByTestId('sub-handle').click()
  await expect(page.getByTestId('sub-panel')).toBeVisible()
  await expect(page.getByTestId('sub-candidate')).toContainText('陈老师')
  await expect(page.getByTestId('sub-alternatives')).toContainText('合班')
  await expect(page.getByTestId('sub-alternatives')).toContainText('自习')
  await expect(page.getByTestId('sub-alternatives')).toContainText('取消课程')
  await expectNoRootOverflow(page)
})

test('无代课候选时仍可设为自习、撤回并取消课程', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const state = await mockApplication(page, { pendingLeave: true, noCandidates: true })

  await page.goto('/substitutions')
  await page.getByTestId('sub-handle').click()
  await expect(page.getByTestId('sub-nocandidate')).toContainText('合班或自习')
  await expect(page.getByTestId('sub-candidate')).toHaveCount(0)
  await expect(page.getByTestId('sub-merge')).toBeDisabled()
  await expect(page.getByTestId('sub-merge')).toContainText('暂无接收教师')

  await page.getByTestId('sub-selfstudy').click()
  await expect(page.getByTestId('sub-period')).toContainText('已处理')
  expect(state.lastAssignmentType).toBe('self_study')

  await page.getByTestId('sub-undo').click()
  await expect(page.getByTestId('sub-period')).toContainText('待处理')
  await page.getByTestId('sub-handle').click()
  await page.getByTestId('sub-cancel').click()
  await expect(page.getByTestId('sub-period')).toContainText('已处理')
  expect(state.lastAssignmentType).toBe('cancel')
  expect(state.assignmentWrites).toBe(2)
  expect(state.undoWrites).toBe(1)
})

test('推荐请求完成后才允许提交其他处理方式', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  const state = await mockApplication(page, {
    pendingLeave: true,
    noCandidates: true,
    delayRecommendations: 700,
  })

  await page.goto('/substitutions')
  await page.getByTestId('sub-handle').click()
  await expect(page.getByTestId('sub-rec-loading')).toBeVisible()
  await expect(page.getByTestId('sub-alternatives')).toHaveCount(0)
  await expect(page.getByTestId('sub-nocandidate')).toBeVisible()
  await page.getByTestId('sub-selfstudy').click()

  expect(state.requestOrder).toEqual([
    'recommendation:start',
    'recommendation:done',
    'assignment',
  ])
})

test('处理、合班与撤回均可通过键盘操作且焦点可见', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  const state = await mockApplication(page, { pendingLeave: true })

  await page.goto('/substitutions')
  await expectVisibleKeyboardFocus(page, 'sub-handle')
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('sub-panel')).toBeVisible()
  await expect(page.getByTestId('sub-handle')).toHaveAttribute('aria-expanded', 'true')

  await expectVisibleKeyboardFocus(page, 'sub-merge')
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('sub-period')).toContainText('已处理')
  await expect(page.getByTestId('sub-handler')).toContainText('陈老师')
  expect(state.lastAssignmentType).toBe('merge')

  await expectVisibleKeyboardFocus(page, 'sub-undo')
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('sub-period')).toContainText('待处理')
  expect(state.undoWrites).toBe(1)
})

test('指派冲突时阻止重复提交并保留候选供重新处理', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  const state = await mockApplication(page, {
    pendingLeave: true,
    failAssignment: true,
    delayAssignment: 700,
  })

  await page.goto('/substitutions')
  await page.getByTestId('sub-handle').click()
  const pick = page.getByTestId('sub-pick')
  await pick.click()

  await expect(pick).toBeDisabled()
  await pick.click({ force: true })
  await expect(page.getByTestId('sub-action-error')).toContainText('陈老师该节已有自己的课')
  await expect(page.getByTestId('sub-panel')).toBeVisible()
  await expect(page.getByTestId('sub-candidate')).toContainText('陈老师')
  expect(state.assignmentWrites).toBe(1)
})

test('指派成功后显示处理教师，撤回后退回待处理', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await mockApplication(page, { pendingLeave: true })

  await page.goto('/substitutions')
  await page.getByTestId('sub-handle').click()
  await page.getByTestId('sub-pick').click()

  const period = page.getByTestId('sub-period')
  await expect(period).toContainText('已处理')
  await expect(period.getByTestId('sub-handler')).toContainText('陈老师')
  await period.getByTestId('sub-undo').click()
  await expect(period).toContainText('待处理')
})
