import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import SchedulingFlow from './SchedulingFlow.vue'

const semesterMocks = vi.hoisted(() => ({
  getPeriodSetup: vi.fn(),
  getSemester: vi.fn(),
  getSemesterContext: vi.fn(),
  listSemesters: vi.fn(),
}))
const assignmentMocks = vi.hoisted(() => ({
  listAssignments: vi.fn(),
}))
const basedataMocks = vi.hoisted(() => ({
  listClassUnits: vi.fn(),
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
      { path: '/scheduling/flow', name: 'scheduling-flow', component: SchedulingFlow },
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
        PeriodTableEditor: {
          emits: ['back'],
          template: '<button data-testid="embedded-period-editor" @click="$emit(\'back\')" />',
        },
        Semesters: {
          emits: ['edit-period-table'],
          template: '<button data-testid="embedded-semesters" @click="$emit(\'edit-period-table\', 12)" />',
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
    expect(router.currentRoute.value.name).toBe('scheduling-flow')
    expect(router.currentRoute.value.query).toMatchObject({ step: 'teachers', semester: '7' })
    expect(wrapper.get('[data-testid="flow-embedded-step"]').text()).toContain('教师任课')
    expect(wrapper.find('[data-testid="scheduling-flow-steps"]').exists()).toBe(false)

    await wrapper.get('[data-testid="flow-step-back"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('scheduling-flow')
    expect(router.currentRoute.value.query.step).toBeUndefined()
    expect(wrapper.find('[data-testid="scheduling-flow-steps"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('keeps class, period, and subject setup on the scheduling-flow route', async () => {
    const { router, wrapper } = await mountFlow()
    const steps = [
      ['classes', 'embedded-classes'],
      ['periods', 'embedded-semesters'],
      ['subjects', 'embedded-assignments'],
    ] as const

    for (const [step, embeddedTestId] of steps) {
      await wrapper.get(`[data-testid="flow-go-${step}"]`).trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.name).toBe('scheduling-flow')
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
    await wrapper.get('[data-testid="embedded-semesters"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('scheduling-flow')
    expect(router.currentRoute.value.query).toMatchObject({ step: 'periods', table: '12', semester: '7' })
    expect(wrapper.find('[data-testid="embedded-period-editor"]').exists()).toBe(true)

    await wrapper.get('[data-testid="embedded-period-editor"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.step).toBeUndefined()
    expect(router.currentRoute.value.query.table).toBeUndefined()
    expect(wrapper.find('[data-testid="scheduling-flow-steps"]').exists()).toBe(true)

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
    expect(wrapper.get('[data-testid="flow-step-subjects"]').classes()).toContain('is-done')

    wrapper.unmount()
  })
})
