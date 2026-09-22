import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import SchedulingFlow from './SchedulingFlow.vue'

const semesterMocks = vi.hoisted(() => ({
  createSemester: vi.fn(),
  getPeriodSetup: vi.fn(),
  getSemester: vi.fn(),
  getSemesterContext: vi.fn(),
  listSemesters: vi.fn(),
}))
const assignmentMocks = vi.hoisted(() => ({
  classLoad: vi.fn(),
  listAssignments: vi.fn(),
}))
const basedataMocks = vi.hoisted(() => ({
  createSubject: vi.fn(),
  listClassUnits: vi.fn(),
  listSubjects: vi.fn(),
  listTeachers: vi.fn(),
}))
const solverMocks = vi.hoisted(() => ({
  preflight: vi.fn(),
}))

vi.mock('@/api/semesters', () => ({ ...semesterMocks }))
vi.mock('@/api/assignments', () => ({ ...assignmentMocks }))
vi.mock('@/api/basedata', () => ({ ...basedataMocks }))
vi.mock('@/api/solver', () => ({ ...solverMocks }))

const semester = {
  id: 7,
  academic_year: 2042,
  term: 1,
  label: '2042-2043学年第一学期',
  status: 'preparing' as const,
  readiness: 'draft' as const,
  start_date: '2042-09-01',
  end_date: '2043-01-31',
  is_current: true,
}
const classUnit = {
  id: 31,
  semester_id: semester.id,
  grade: 7,
  name: '701班',
  track: 'default',
  period_table_id: null,
}
const report = {
  semester_id: semester.id,
  semester_label: semester.label,
  ok: false,
  error_count: 1,
  warning_count: 0,
  issues: [{
    level: 'error' as const,
    code: 'assignment_without_teacher',
    message: '课程“语文”尚未指定授课教师，请先完成“教师任课”后再开始排课',
    subject_type: 'assignment',
    subject_id: 18,
  }],
  class_count: 1,
  teacher_count: 0,
  assignment_count: 1,
  total_periods: 5,
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/scheduling/flow', name: 'scheduling-workbench', component: SchedulingFlow },
      { path: '/basedata', name: 'basedata', component: { template: '<main />' } },
      { path: '/settings/semesters', name: 'semesters', component: { template: '<main />' } },
      { path: '/scheduling/assignments', name: 'assignments', component: { template: '<main />' } },
      { path: '/scheduling/auto', name: 'auto-schedule', component: { template: '<main />' } },
    ],
  })
}

async function mountFlow() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore(pinia)
  auth.user = {
    id: 1,
    username: 'director',
    display_name: '教务主任',
    roles: ['director'],
    must_change_password: false,
  }
  auth.loaded = true
  const router = makeRouter()
  await router.push('/scheduling/flow')
  await router.isReady()
  const Host = {
    render: () => h(NMessageProvider, null, { default: () => h(SchedulingFlow) }),
  }
  const wrapper = mount(Host, {
    attachTo: document.body,
    global: {
      plugins: [pinia, router],
      stubs: {
        Assignments: { template: '<div data-testid="embedded-assignments" />' },
        AutoSchedule: { template: '<div data-testid="embedded-auto-schedule" />' },
        ClassesTab: { template: '<div data-testid="embedded-classes" />' },
        SubjectsTab: { template: '<div data-testid="embedded-subjects" />' },
        TeachersTab: { template: '<div data-testid="embedded-teachers" />' },
        SchedulingSupportWorkspace: {
          props: ['panel', 'semesterId', 'resourceSection'],
          emits: ['back', 'changed', 'semestersChanged', 'editPeriodTable'],
          template: '<section data-testid="flow-support-panel"><span data-testid="flow-support-panel-name">{{ panel }}</span><button data-testid="flow-support-back" @click="$emit(\'back\')">返回</button></section>',
        },
        PeriodTableEditor: {
          emits: ['back'],
          template: '<button data-testid="embedded-period-editor" @click="$emit(\'back\')" />',
        },
        PeriodSetupWorkspace: {
          emits: ['changed', 'edit-period-table'],
          template: '<div><button data-testid="embedded-period-setup" @click="$emit(\'edit-period-table\', 12)" /><button data-testid="embedded-period-setup-changed" @click="$emit(\'changed\')" /></div>',
        },
      },
    },
  })
  await flushPromises()
  return { router, wrapper }
}

describe('SchedulingFlow', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    basedataMocks.createSubject.mockResolvedValue({
      id: 3,
      semester_id: semester.id,
      name: '数学',
      domain: '数学',
      required_room_type: null,
      default_block_size: 1,
      is_major: true,
    })
    semesterMocks.getSemesterContext.mockResolvedValue({
      current_semester: semester,
      revision: 1,
      can_switch: false,
    })
    semesterMocks.listSemesters.mockResolvedValue([semester])
    semesterMocks.getSemester.mockResolvedValue({
      ...semester,
      period_tables: [{
        id: 4,
        semester_id: semester.id,
        name: '默认作息',
        num_weekdays: 5,
        is_default: true,
        periods: [{
          id: 1,
          weekday: 1,
          period_no: 1,
          name: '第一节',
          start_time: '08:00:00',
          end_time: '08:40:00',
          type: 'regular',
        }],
      }],
    })
    basedataMocks.listClassUnits.mockResolvedValue([classUnit])
    basedataMocks.listSubjects.mockResolvedValue([{ id: 2, semester_id: semester.id, name: '语文' }])
    basedataMocks.listTeachers.mockResolvedValue([])
    assignmentMocks.listAssignments.mockResolvedValue([{
      id: 18,
      semester_id: semester.id,
      scheduling_unit: {
        id: 8,
        semester_id: semester.id,
        unit_type: 'single',
        name: '701班',
        classes: [{ id: classUnit.id, name: classUnit.name, grade: classUnit.grade }],
      },
      subject: { id: 2, name: '语文' },
      periods_per_week: 5,
      required_room_type: null,
      room_id: null,
      lock_room: false,
      teachers: [],
      block_rules: [],
    }])
    assignmentMocks.classLoad.mockResolvedValue([{
      class_id: classUnit.id,
      name: classUnit.name,
      grade: classUnit.grade,
      assigned: 5,
      capacity: 5,
      over_capacity: false,
    }])
    solverMocks.preflight.mockResolvedValue(report)
    semesterMocks.getPeriodSetup.mockResolvedValue({
      fingerprint: 'a'.repeat(64),
      source: 'existing',
      classes: [],
      groups: [{
        key: 'table:4',
        table_id: 4,
        name: '默认作息',
        num_weekdays: 5,
        is_default: true,
        class_ids: [classUnit.id],
        periods: [],
      }],
      unresolved_class_ids: [],
      ready: true,
      blockers: [],
      warnings: [],
    })
  })

  it('separates subject periods from teacher assignment and opens the teacher step inside the workbench', async () => {
    const { router, wrapper } = await mountFlow()

    expect(wrapper.get('[data-testid="scheduling-flow-steps"]').text()).toContain('设置班级')
    expect(wrapper.get('[data-testid="scheduling-flow-steps"]').text()).toContain('设置课时')
    expect(wrapper.get('[data-testid="scheduling-flow-steps"]').text()).toContain('科目节数')
    expect(wrapper.get('[data-testid="scheduling-flow-steps"]').text()).toContain('教师任课')
    expect(wrapper.get('[data-testid="scheduling-flow-steps"]').text()).toContain('开始排课')
    expect(wrapper.get('[data-testid="flow-step-subjects"]').classes()).toContain('is-done')
    expect(wrapper.get('[data-testid="flow-step-teachers"]').classes()).toContain('is-active')
    expect(wrapper.get('[data-testid="flow-start"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="flow-go-teachers"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toMatchObject({ step: 'teachers', semester: '7' })
    expect(wrapper.get('[data-testid="flow-embedded-step"]').text()).toContain('教师任课')
    expect(wrapper.find('[data-testid="scheduling-flow-steps"]').exists()).toBe(false)

    await wrapper.get('[data-testid="flow-teachers-archive"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toMatchObject({ step: 'teachers', semester: '7', view: 'archive' })
    expect(wrapper.find('[data-testid="embedded-teachers"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="embedded-assignments"]').exists()).toBe(false)

    await wrapper.get('[data-testid="flow-teachers-work"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.view).toBeUndefined()
    expect(wrapper.find('[data-testid="embedded-assignments"]').exists()).toBe(true)

    await wrapper.get('[data-testid="flow-step-back"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query.step).toBeUndefined()
    expect(wrapper.find('[data-testid="scheduling-flow-steps"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it.each([
    ['no_period_table', 'periods'],
    ['period_table_missing', 'periods'],
    ['regular_period_missing', 'periods'],
    ['period_time_invalid', 'periods'],
    ['class_period_table_missing', 'periods'],
    ['class_period_capacity_exceeded', 'periods'],
    ['assignment_without_teacher', 'teachers'],
    ['assignment_teacher_missing', 'teachers'],
    ['teacher_overload', 'teachers'],
    ['assignment_without_class', 'subjects'],
    ['class_assignment_periods_mismatch', 'subjects'],
    ['group_shape_mismatch', 'subjects'],
    ['class_overload', 'subjects'],
    ['block_infeasible', 'subjects'],
    ['block_exceeds_periods', 'subjects'],
  ])('routes the %s preflight blocker to the %s step', async (code, step) => {
    solverMocks.preflight.mockResolvedValue({
      ...report,
      issues: [{
        ...report.issues[0],
        code,
        subject_type: code === 'teacher_overload' ? 'teacher' : 'assignment',
      }],
    })

    const { router, wrapper } = await mountFlow()

    await wrapper.get('[data-testid="flow-go-issue"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toMatchObject({ step, semester: '7' })

    wrapper.unmount()
  })

  it.each(['semester_dates_missing', 'semester_dates_invalid'])(
    'routes the %s readiness blocker to semester maintenance',
    async (code) => {
      solverMocks.preflight.mockResolvedValue({
        ...report,
        issues: [{
          ...report.issues[0],
          code,
          subject_type: 'semester',
        }],
      })

      const { router, wrapper } = await mountFlow()

      expect(wrapper.get('[data-testid="flow-go-issue"]').text()).toContain('维护学期日期')
      await wrapper.get('[data-testid="flow-go-issue"]').trigger('click')
      await flushPromises()
      expect(router.currentRoute.value.name).toBe('scheduling-workbench')
      expect(router.currentRoute.value.query).toEqual({ panel: 'semester', semester: '7' })

      wrapper.unmount()
    },
  )

  it('routes room preflight blockers to room maintenance', async () => {
    solverMocks.preflight.mockResolvedValue({
      ...report,
      issues: [{
        ...report.issues[0],
        code: 'room_no_candidate',
        message: '没有可用的实验室',
        subject_type: 'room',
      }],
    })

    const { router, wrapper } = await mountFlow()

    expect(wrapper.get('[data-testid="flow-go-issue"]').text()).toContain('管理教室/场地')
    await wrapper.get('[data-testid="flow-go-issue"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toMatchObject({ panel: 'resources', resource: 'rooms', semester: '7' })

    wrapper.unmount()
  })

  it('opens semester, calendar, and resource support surfaces from the workbench overview', async () => {
    const { router, wrapper } = await mountFlow()

    expect(wrapper.get('[data-testid="flow-support-surfaces"]').text()).toContain('学期管理')
    expect(wrapper.find('[data-testid="flow-open-semester-support"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="flow-open-calendar-support"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="flow-open-resources-support"]').exists()).toBe(true)

    await wrapper.get('[data-testid="flow-open-calendar-support"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ panel: 'calendar', semester: '7' })
    expect(wrapper.get('[data-testid="flow-support-panel-name"]').text()).toBe('calendar')

    await wrapper.get('[data-testid="flow-support-back"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ semester: '7' })
    expect(wrapper.find('[data-testid="flow-support-panel"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('reloads all semester-scoped readiness data after a URL semester switch', async () => {
    const otherSemester = {
      ...semester,
      id: 8,
      label: '2042-2043学年第二学期',
      term: 2,
      is_current: false,
    }
    semesterMocks.listSemesters.mockResolvedValue([semester, otherSemester])
    semesterMocks.getSemester.mockImplementation(async (id: number) => ({
      ...(id === otherSemester.id ? otherSemester : semester),
      period_tables: [],
    }))
    basedataMocks.listClassUnits.mockImplementation(async (id: number) => ([{
      ...classUnit,
      semester_id: id,
      id: id === otherSemester.id ? 81 : classUnit.id,
    }]))
    basedataMocks.listSubjects.mockImplementation(async (id: number) => ([{
      id: id === otherSemester.id ? 82 : 2,
      semester_id: id,
      name: id === otherSemester.id ? '英语' : '语文',
    }]))
    basedataMocks.listTeachers.mockImplementation(async () => [])
    assignmentMocks.listAssignments.mockImplementation(async (id: number) => {
      const other = id === otherSemester.id
      const classId = other ? 81 : classUnit.id
      const className = other ? '702班' : classUnit.name
      return [{
        id: other ? 88 : 18,
        semester_id: id,
        scheduling_unit: {
          id: other ? 89 : 8,
          semester_id: id,
          unit_type: 'single',
          name: className,
          classes: [{ id: classId, name: className, grade: 7 }],
        },
        subject: { id: other ? 82 : 2, name: other ? '英语' : '语文' },
        periods_per_week: 5,
        required_room_type: null,
        room_id: null,
        lock_room: false,
        teachers: [],
        block_rules: [],
      }]
    })
    solverMocks.preflight.mockImplementation(async (id: number) => ({
      ...report,
      semester_id: id,
      semester_label: id === otherSemester.id ? otherSemester.label : semester.label,
    }))
    semesterMocks.getPeriodSetup.mockImplementation(async (id: number) => ({
      fingerprint: String(id),
      source: 'existing',
      classes: [],
      groups: [],
      unresolved_class_ids: [],
      ready: true,
      blockers: [],
      warnings: [],
    }))

    const { router, wrapper } = await mountFlow()
    await router.push({ name: 'scheduling-workbench', query: { semester: String(otherSemester.id) } })
    await flushPromises()

    expect(semesterMocks.getSemester).toHaveBeenLastCalledWith(otherSemester.id)
    expect(basedataMocks.listClassUnits).toHaveBeenLastCalledWith(otherSemester.id)
    expect(basedataMocks.listSubjects).toHaveBeenLastCalledWith(otherSemester.id)
    expect(basedataMocks.listTeachers).toHaveBeenLastCalledWith(otherSemester.id)
    expect(assignmentMocks.listAssignments).toHaveBeenLastCalledWith(otherSemester.id)
    expect(solverMocks.preflight).toHaveBeenLastCalledWith(otherSemester.id)
    expect(semesterMocks.getPeriodSetup).toHaveBeenLastCalledWith(otherSemester.id)
    expect(wrapper.get('[data-testid="flow-summary"]').text()).toContain(otherSemester.label)

    wrapper.unmount()
  })

  it('keeps the subject archive in the subject-periods step and allows teacher archive before assignments exist', async () => {
    assignmentMocks.listAssignments.mockResolvedValue([])

    const { router, wrapper } = await mountFlow()

    expect(wrapper.get('[data-testid="flow-step-teachers"]').classes()).toContain('is-blocked')
    expect(wrapper.get('[data-testid="flow-go-teachers"]').attributes('disabled')).toBeUndefined()

    await wrapper.get('[data-testid="flow-go-subjects"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="flow-subjects-archive"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toMatchObject({ step: 'subjects', semester: '7', view: 'archive' })
    expect(wrapper.find('[data-testid="flow-subject-archive"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="manual-common-subjects"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="embedded-subjects"]').exists()).toBe(true)

    await wrapper.get('[data-testid="manual-common-数学"]').trigger('click')
    await wrapper.get('[data-testid="manual-common-confirm"]').trigger('click')
    await flushPromises()
    expect(basedataMocks.createSubject).toHaveBeenCalledWith(7, expect.objectContaining({ name: '数学' }))

    await wrapper.get('[data-testid="flow-step-back"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="flow-go-teachers"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toMatchObject({ step: 'teachers', semester: '7', view: 'archive' })
    expect(wrapper.find('[data-testid="embedded-teachers"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('keeps class, period, and subject setup on the scheduling-workbench route', async () => {
    const { router, wrapper } = await mountFlow()
    const steps = [
      ['classes', 'embedded-classes'],
      ['periods', 'embedded-period-setup'],
      ['subjects', 'embedded-assignments'],
    ] as const

    for (const [step, embeddedTestId] of steps) {
      await wrapper.get(`[data-testid="flow-go-${step}"]`).trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.name).toBe('scheduling-workbench')
      expect(router.currentRoute.value.query).toMatchObject({ step, semester: '7' })
      expect(wrapper.find(`[data-testid="${embeddedTestId}"]`).exists()).toBe(true)

      await wrapper.get('[data-testid="flow-step-back"]').trigger('click')
      await flushPromises()
      expect(router.currentRoute.value.query.step).toBeUndefined()
    }

    wrapper.unmount()
  })

  it('opens the period table editor inside the workbench and returns to its overview', async () => {
    const { router, wrapper } = await mountFlow()

    await wrapper.get('[data-testid="flow-go-periods"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="embedded-period-setup"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toMatchObject({ step: 'periods', table: '12', semester: '7' })
    expect(wrapper.find('[data-testid="embedded-period-editor"]').exists()).toBe(true)

    await wrapper.get('[data-testid="embedded-period-editor"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.step).toBeUndefined()
    expect(router.currentRoute.value.query.table).toBeUndefined()
    expect(wrapper.find('[data-testid="scheduling-flow-steps"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('reloads readiness after the period setup workspace changes data', async () => {
    const { wrapper } = await mountFlow()
    await wrapper.get('[data-testid="flow-go-periods"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="embedded-period-setup-changed"]').trigger('click')
    await flushPromises()

    expect(semesterMocks.getSemester).toHaveBeenLastCalledWith(semester.id)
    expect(assignmentMocks.classLoad).toHaveBeenLastCalledWith(semester.id)
    expect(wrapper.find('[data-testid="embedded-period-setup"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('does not treat an unsaved suggested period setup as complete', async () => {
    semesterMocks.getSemester.mockResolvedValue({ ...semester, period_tables: [] })
    semesterMocks.getPeriodSetup.mockResolvedValue({
      fingerprint: 'b'.repeat(64),
      source: 'suggested',
      classes: [],
      groups: [{
        key: 'suggested',
        table_id: null,
        name: '建议作息',
        num_weekdays: 5,
        is_default: true,
        class_ids: [classUnit.id],
        periods: [],
      }],
      unresolved_class_ids: [],
      ready: true,
      blockers: [],
      warnings: [],
    })

    const { wrapper } = await mountFlow()

    expect(wrapper.get('[data-testid="flow-step-periods"]').classes()).toContain('is-active')
    expect(wrapper.get('[data-testid="flow-step-subjects"]').classes()).toContain('is-blocked')

    wrapper.unmount()
  })

  it('blocks the next scheduling step when class course load exceeds regular capacity', async () => {
    assignmentMocks.classLoad.mockResolvedValue([{
      class_id: classUnit.id,
      name: classUnit.name,
      grade: classUnit.grade,
      assigned: 6,
      capacity: 5,
      over_capacity: true,
    }])

    const { wrapper } = await mountFlow()

    expect(wrapper.get('[data-testid="flow-step-periods"]').classes()).toContain('is-active')
    expect(wrapper.get('[data-testid="flow-step-subjects"]').classes()).toContain('is-blocked')
    expect(wrapper.get('[data-testid="flow-step-teachers"]').classes()).toContain('is-blocked')
    expect(wrapper.get('[data-testid="flow-step-periods"]').text()).toContain('常规容量仅 5 节')
    expect(wrapper.get('[data-testid="flow-start"]').attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('creates the first semester inside the workbench without navigating to settings', async () => {
    const created = { ...semester }
    semesterMocks.getSemesterContext
      .mockResolvedValueOnce({ current_semester: null, revision: 0, can_switch: false })
      .mockResolvedValue({ current_semester: created, revision: 1, can_switch: false })
    semesterMocks.listSemesters
      .mockResolvedValueOnce([])
      .mockResolvedValue([created])
    semesterMocks.createSemester.mockResolvedValue(created)

    const { router, wrapper } = await mountFlow()

    expect(wrapper.get('[data-testid="flow-empty"]').text()).toContain('创建学期')
    const datePickers = wrapper.findAll('.n-date-picker')
    expect(datePickers.length).toBe(2)
    await datePickers[0].find('input').setValue('2042-09-01')
    await datePickers[1].find('input').setValue('2043-01-31')
    await flushPromises()
    await wrapper.get('[data-testid="flow-semester-create"]').trigger('click')
    await flushPromises()

    expect(semesterMocks.createSemester).toHaveBeenCalledWith({
      academic_year: expect.any(Number),
      term: 1,
      start_date: '2042-09-01',
      end_date: '2043-01-31',
    })
    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
    expect(router.currentRoute.value.query).toMatchObject({ semester: '7' })
    expect(wrapper.find('[data-testid="flow-empty"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="flow-summary"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('keeps the in-place form available when semester creation fails', async () => {
    semesterMocks.getSemesterContext.mockResolvedValueOnce({
      current_semester: null,
      revision: 0,
      can_switch: false,
    })
    semesterMocks.listSemesters.mockResolvedValue([])
    semesterMocks.createSemester.mockRejectedValue({ detail: '该学年学期已存在' })

    const { wrapper } = await mountFlow()
    const datePickers = wrapper.findAll('.n-date-picker')
    await datePickers[0].find('input').setValue('2042-09-01')
    await datePickers[1].find('input').setValue('2043-01-31')
    await flushPromises()
    await wrapper.get('[data-testid="flow-semester-create"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="flow-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="flow-semester-create-form"]').exists()).toBe(true)

    wrapper.unmount()
  })
})
