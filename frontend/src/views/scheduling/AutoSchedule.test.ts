import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AutoSchedule from './AutoSchedule.vue'

const semesterMocks = vi.hoisted(() => ({
  getSemesterContext: vi.fn(),
  listSemesters: vi.fn(),
}))
const solverMocks = vi.hoisted(() => ({
  cancelSolveJob: vi.fn(),
  getConstraintConfig: vi.fn(),
  getSolveJob: vi.fn(),
  listRelaxable: vi.fn(),
  preflight: vi.fn(),
  startAutoSchedule: vi.fn(),
  stopSolveJob: vi.fn(),
}))
const timetableMocks = vi.hoisted(() => ({
  createTimetable: vi.fn(),
  listTimetables: vi.fn(),
}))
const calendarMocks = vi.hoisted(() => ({
  confirmSemesterReadiness: vi.fn(),
}))

vi.mock('@/api/semesters', () => ({ ...semesterMocks }))
vi.mock('@/api/solver', () => ({ ...solverMocks }))
vi.mock('@/api/timetables', () => ({ ...timetableMocks }))
vi.mock('@/api/calendar', () => ({ ...calendarMocks }))

const semester = {
  id: 7,
  academic_year: 2042,
  term: 1,
  label: '2042-2043学年第一学期',
  status: 'preparing',
  readiness: 'draft',
  start_date: '2042-09-01',
  end_date: '2043-01-31',
  is_current: true,
}
const preflightReport = {
  semester_id: semester.id,
  semester_label: semester.label,
  ok: true,
  error_count: 0,
  warning_count: 0,
  issues: [],
  class_count: 1,
  teacher_count: 1,
  assignment_count: 1,
  total_periods: 5,
}
const draft = {
  id: 19,
  semester_id: semester.id,
  name: `${semester.label} · 排课草稿`,
  status: 'draft',
  publication_state: 'draft',
  entry_count: 0,
}

async function mountAutoSchedule() {
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
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/scheduling/auto', name: 'auto-schedule', component: AutoSchedule },
      { path: '/scheduling/workbench', name: 'workbench', component: { template: '<main />' } },
      { path: '/scheduling/versions', name: 'versions', component: { template: '<main />' } },
      { path: '/settings/semesters', name: 'semesters', component: { template: '<main />' } },
    ],
  })
  await router.push('/scheduling/auto')
  await router.isReady()
  const Host = {
    render: () => h(NMessageProvider, null, { default: () => h(AutoSchedule) }),
  }
  const wrapper = mount(Host, {
    attachTo: document.body,
    global: { plugins: [pinia, router] },
  })
  await flushPromises()
  return wrapper
}

describe('AutoSchedule workbench path', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    semesterMocks.getSemesterContext.mockResolvedValue({
      current_semester: semester,
      revision: 1,
      can_switch: false,
    })
    semesterMocks.listSemesters.mockResolvedValue([semester])
    solverMocks.listRelaxable.mockResolvedValue([])
    solverMocks.preflight.mockResolvedValue(preflightReport)
    solverMocks.getConstraintConfig.mockResolvedValue({
      semester_id: semester.id,
      daily_subject_cap: 2,
      teacher_daily_max: 6,
      teacher_consecutive_max: 3,
      weights: {},
      weight_names: {},
    })
    timetableMocks.listTimetables.mockResolvedValue([])
    timetableMocks.createTimetable.mockResolvedValue(draft)
    calendarMocks.confirmSemesterReadiness.mockResolvedValue({
      semester_id: semester.id,
      readiness: 'ready',
      ready: true,
      issues: [],
      checks: [],
      calendar_exception_count: 0,
    })
    solverMocks.startAutoSchedule.mockResolvedValue({ job_id: 'job-1' })
    solverMocks.getSolveJob.mockResolvedValue({
      job_id: 'job-1',
      status: 'finished',
      semester_id: semester.id,
      source_timetable_id: draft.id,
      source_name: draft.name,
      max_seconds: 600,
      elapsed: 2,
      solutions: 1,
      objective: 0,
      result_timetable_id: 20,
      result_name: '自动排课结果',
      error: null,
      report: null,
      phase: 'solving',
      partial: false,
      conflict: null,
      unscheduled: [],
    })
  })

  it('confirms readiness and creates an initial draft when no source draft exists', async () => {
    const wrapper = await mountAutoSchedule()

    await wrapper.get('[data-testid="as-start"]').trigger('click')
    await flushPromises()

    expect(calendarMocks.confirmSemesterReadiness).toHaveBeenCalledWith(semester.id)
    expect(timetableMocks.createTimetable).toHaveBeenCalledWith(
      semester.id,
      `${semester.label} · 排课草稿`,
    )
    expect(solverMocks.startAutoSchedule).toHaveBeenCalledWith(draft.id, 600, {
      allowPartial: false,
      relax: [],
    })

    wrapper.unmount()
  })
})
