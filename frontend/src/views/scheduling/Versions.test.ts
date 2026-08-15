import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { useAuthStore } from '@/stores/auth'
import Versions from './Versions.vue'

const timetableMocks = vi.hoisted(() => ({
  createTimetable: vi.fn(),
  deleteTimetable: vi.fn(),
  duplicateTimetable: vi.fn(),
  getCompleteness: vi.fn(),
  checkPublication: vi.fn(),
  listTimetables: vi.fn(),
  publishTimetable: vi.fn(),
  renameTimetable: vi.fn(),
}))
const semesterMocks = vi.hoisted(() => ({
  getSemesterContext: vi.fn(),
  listSemesters: vi.fn(),
  switchSemesterContext: vi.fn(),
}))

vi.mock('@/api/timetables', () => ({ ...timetableMocks }))
vi.mock('@/api/semesters', () => ({ ...semesterMocks }))

const semester = {
  id: 7,
  academic_year: 2042,
  term: 1,
  label: '2042-2043学年第一学期',
  status: 'preparing',
  readiness: 'ready',
  start_date: '2042-09-01',
  end_date: '2043-01-31',
  is_demo: false,
  is_current: true,
}
const draft = {
  id: 19,
  semester_id: semester.id,
  name: '秋季正式版',
  status: 'draft',
  publication_state: 'draft',
  entry_count: 42,
}
const checked = { ...draft, publication_state: 'checked' }
const publicationCheck = {
  semester: { id: semester.id, label: semester.label },
  version: { id: draft.id, name: draft.name },
  passed: true,
  requires_force: false,
  completeness: {
    required: 42,
    placed: 42,
    remaining: 0,
    complete: true,
    unplaced: [],
  },
  issues: [],
  fingerprint: 'a'.repeat(64),
  checked_at: '2042-08-15T00:00:00Z',
}

async function mountVersions(role: 'scheduler' | 'director' = 'scheduler') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore(pinia)
  auth.user = {
    id: 1,
    username: 'scheduler',
    display_name: '排课管理员',
    roles: [role],
    must_change_password: false,
  }
  auth.loaded = true
  const Host = {
    render: () => h(NMessageProvider, null, { default: () => h(Versions) }),
  }
  const wrapper = mount(Host, {
    attachTo: document.body,
    global: {
      plugins: [pinia],
      stubs: {
        Modal: {
          props: ['show'],
          template: '<section v-if="show" role="dialog"><slot /></section>',
        },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('Versions publication confirmation', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    semesterMocks.getSemesterContext.mockResolvedValue({
      current_semester: semester,
      revision: 3,
      can_switch: true,
    })
    semesterMocks.listSemesters.mockResolvedValue([semester])
    timetableMocks.listTimetables
      .mockResolvedValueOnce([draft])
      .mockResolvedValue([checked])
    timetableMocks.checkPublication.mockResolvedValue(publicationCheck)
    timetableMocks.getCompleteness.mockResolvedValue(publicationCheck.completeness)
    timetableMocks.publishTimetable.mockResolvedValue({
      ...draft,
      status: 'published',
      entries: [],
    })
  })

  it('shows the checked target and cancellation never submits publication', async () => {
    const wrapper = await mountVersions()

    await wrapper.get('[data-testid="v-publish"]').trigger('click')
    await flushPromises()

    expect(timetableMocks.checkPublication).toHaveBeenCalledWith(draft.id)
    expect(timetableMocks.publishTimetable).not.toHaveBeenCalled()
    const confirmation = wrapper.get('[data-testid="v-publish-confirmation"]')
    expect(confirmation.text()).toContain(semester.label)
    expect(confirmation.text()).toContain(draft.name)
    expect(confirmation.text()).toContain('42 / 42')

    await confirmation.get('[data-testid="v-publish-cancel"]').trigger('click')
    await flushPromises()
    expect(timetableMocks.publishTimetable).not.toHaveBeenCalled()
  })

  it('submits the exact checked fingerprint only after explicit confirmation', async () => {
    const wrapper = await mountVersions()

    await wrapper.get('[data-testid="v-publish"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="v-confirm-publish"]').trigger('click')
    await flushPromises()

    expect(timetableMocks.publishTimetable).toHaveBeenCalledTimes(1)
    expect(timetableMocks.publishTimetable).toHaveBeenCalledWith(draft.id, {
      fingerprint: publicationCheck.fingerprint,
      force: false,
    })
  })

  it('keeps a director completeness check read-only', async () => {
    const wrapper = await mountVersions('director')

    await wrapper.get('[data-testid="v-check"]').trigger('click')
    await flushPromises()

    expect(timetableMocks.getCompleteness).toHaveBeenCalledWith(draft.id)
    expect(timetableMocks.checkPublication).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="versions-check-result"]').text()).toContain('42/42')
  })
})
