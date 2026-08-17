import { flushPromises, mount } from '@vue/test-utils'
import { NDatePicker, NMessageProvider } from 'naive-ui'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { WizardState } from '@/api/wizard'
import { useAuthStore } from '@/stores/auth'
import Wizard from './Wizard.vue'

const mocks = vi.hoisted(() => ({
  createSemester: vi.fn(),
  getSemester: vi.fn(),
  getSemesterContext: vi.fn(),
  listSemesters: vi.fn(),
  switchSemesterContext: vi.fn(),
  getWizardState: vi.fn(),
  updateWizardState: vi.fn(),
  saveSchoolSettings: vi.fn(),
}))

vi.mock('@/api/semesters', () => ({
  createSemester: mocks.createSemester,
  getSemester: mocks.getSemester,
  getSemesterContext: mocks.getSemesterContext,
  listSemesters: mocks.listSemesters,
  switchSemesterContext: mocks.switchSemesterContext,
}))
vi.mock('@/api/wizard', () => ({
  getWizardState: mocks.getWizardState,
  updateWizardState: mocks.updateWizardState,
}))
vi.mock('@/api/assignments', () => ({
  saveSchoolSettings: mocks.saveSchoolSettings,
}))

const baseState: WizardState = {
  current_step: 0,
  completed: false,
  paused: false,
  semester_id: null,
  total_steps: 4,
  has_semesters: false,
}
const semester = {
  id: 8,
  academic_year: 2042,
  term: 1,
  label: '2042-2043学年第一学期',
  status: 'preparing' as const,
  readiness: 'draft' as const,
  start_date: '2042-09-01',
  end_date: '2043-01-20',
  period_tables: [],
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/wizard', name: 'wizard', component: Wizard },
      { path: '/', name: 'dashboard', component: { template: '<main>仪表盘</main>' } },
      { path: '/scheduling/assignments', name: 'assignments', component: { template: '<main />' } },
      { path: '/settings/period-tables/:id', name: 'period-table-editor', component: { template: '<main />' } },
    ],
  })
}

async function mountWizard(state: WizardState = baseState, roles = ['scheduler']) {
  mocks.getWizardState.mockResolvedValue({ ...state })
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  auth.user = {
    id: 1,
    username: roles.includes('director') ? 'director' : 'scheduler',
    display_name: roles.includes('director') ? '教务主任' : '排课管理员',
    roles,
    must_change_password: false,
  }
  auth.loaded = true
  const router = makeRouter()
  await router.push('/wizard')
  await router.isReady()
  const Host = { render: () => h(NMessageProvider, null, { default: () => h(Wizard) }) }
  const wrapper = mount(Host, {
    global: {
      plugins: [pinia, router],
      stubs: {
        ImportTab: { template: '<div data-testid="import-tab-stub" />' },
        PeriodSetup: { template: '<div data-testid="period-setup-stub" />' },
      },
    },
  })
  await flushPromises()
  return { router, wrapper }
}

async function setDate(wrapper: ReturnType<typeof mount>, testId: string, value: string) {
  const datePicker = wrapper.findComponent(NDatePicker)
  const target = testId === 'wizard-start-date' ? datePicker : wrapper.findAllComponents(NDatePicker)[1]
  await target.vm.$emit('update:formatted-value', value)
  await flushPromises()
}

describe('Wizard', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.getWizardState.mockResolvedValue({ ...baseState })
    mocks.updateWizardState.mockImplementation((body: Record<string, unknown>) => Promise.resolve({
      ...baseState,
      ...body,
      semester_id: body.semester_id ?? baseState.semester_id,
    }))
    mocks.getSemester.mockResolvedValue(semester)
    mocks.createSemester.mockResolvedValue(semester)
    mocks.getSemesterContext.mockResolvedValue({ current_semester: null, revision: 0, can_switch: true })
    mocks.listSemesters.mockResolvedValue([])
    mocks.switchSemesterContext.mockResolvedValue({
      current_semester: { ...semester, is_current: true }, revision: 1, can_switch: true,
    })
    mocks.saveSchoolSettings.mockResolvedValue({ school_name: '示范学校' })
  })

  it('全新进入时显示四步中的学校与学期，且没有模板概念', async () => {
    const { wrapper } = await mountWizard()

    expect(wrapper.get('[data-testid="wizard-step-title"]').text()).toContain('学校与学期')
    expect(wrapper.text()).not.toContain('学制模板')
    expect(wrapper.text()).not.toContain('学校模板')
    expect((wrapper.get('[data-testid="wizard-school-name"] input').element as HTMLInputElement).value).toBe('示范学校')
    expect(wrapper.text()).toContain('开始日期')
    expect(wrapper.text()).toContain('结束日期')
    expect(wrapper.text()).toContain('第 1 步 / 4')
  })

  it('排课管理员可以看到校名但不能编辑', async () => {
    const { wrapper } = await mountWizard()
    const input = wrapper.get('[data-testid="wizard-school-name"] input')
    expect(input.attributes('disabled')).toBeDefined()
  })

  it('日期缺失或顺序错误时不创建学期', async () => {
    const { wrapper } = await mountWizard()

    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="wizard-error"]').text()).toContain('开始日期')
    expect(mocks.createSemester).not.toHaveBeenCalled()

    await setDate(wrapper, 'wizard-start-date', '2042-09-01')
    await setDate(wrapper, 'wizard-end-date', '2042-08-31')
    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="wizard-error"]').text()).toContain('结束日期')
    expect(mocks.createSemester).not.toHaveBeenCalled()
  })

  it('第一步提交用户输入并只创建中性学期，然后进入基础数据', async () => {
    const { wrapper } = await mountWizard()
    await setDate(wrapper, 'wizard-start-date', '2042-09-01')
    await setDate(wrapper, 'wizard-end-date', '2043-01-20')

    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()

    expect(mocks.createSemester).toHaveBeenCalledWith({
      academic_year: expect.any(Number),
      term: 1,
      start_date: '2042-09-01',
      end_date: '2043-01-20',
    })
    expect(wrapper.get('[data-testid="wizard-step-title"]').text()).toContain('基础数据')
    expect(mocks.updateWizardState).toHaveBeenCalledWith({ semester_id: semester.id })
  })

  it('创建失败时停留在第一步并可重试', async () => {
    mocks.createSemester.mockRejectedValue({ detail: '该学年学期已存在' })
    const { wrapper } = await mountWizard()
    await setDate(wrapper, 'wizard-start-date', '2042-09-01')
    await setDate(wrapper, 'wizard-end-date', '2043-01-20')

    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="wizard-error"]').text()).toContain('该学年学期已存在')
    expect(wrapper.get('[data-testid="wizard-step-title"]').text()).toContain('学校与学期')
  })

  it('教务主任只读查看向导', async () => {
    const { wrapper } = await mountWizard(baseState, ['director'])
    expect(wrapper.get('[data-testid="wizard-readonly"]').text()).toContain('只能查看')
    expect(wrapper.get('[data-testid="wizard-next"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="wizard-school-name"] input').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    expect(mocks.updateWizardState).not.toHaveBeenCalled()
  })

  it('保存并退出后回到工作台，重新打开恢复最近步骤', async () => {
    const { router, wrapper } = await mountWizard({ ...baseState, current_step: 1, semester_id: semester.id })
    await wrapper.get('[data-testid="wizard-save-exit"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('dashboard')
    expect(mocks.updateWizardState).toHaveBeenCalledWith({
      current_step: 1,
      semester_id: semester.id,
      paused: true,
    })
  })

  it('第三步直接显示可调整的作息配置，而不是跳转旧编辑器', async () => {
    const { wrapper } = await mountWizard({ ...baseState, current_step: 2, semester_id: semester.id })

    expect(wrapper.get('[data-testid="wizard-step-title"]').text()).toContain('作息安排')
    expect(wrapper.get('[data-testid="period-setup-stub"]')).toBeTruthy()
    expect(wrapper.text()).toContain('根据班级生成可调整的作息建议')
    expect(wrapper.find('[data-testid="wizard-period-edit"]').exists()).toBe(false)
  })
})
