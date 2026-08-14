import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { OnboardingStatus } from '@/api/onboarding'
import type { WizardState } from '@/api/wizard'
import { useAuthStore } from '@/stores/auth'
import Wizard from './Wizard.vue'

const mocks = vi.hoisted(() => ({
  listTemplates: vi.fn(),
  createSemester: vi.fn(),
  getSemester: vi.fn(),
  getWizardState: vi.fn(),
  updateWizardState: vi.fn(),
  getSemesterSummary: vi.fn(),
  getOnboardingStatus: vi.fn(),
  demoDataStatus: vi.fn(),
  loadDemoData: vi.fn(),
}))

vi.mock('@/api/semesters', () => ({
  listTemplates: mocks.listTemplates,
  createSemester: mocks.createSemester,
  getSemester: mocks.getSemester,
}))
vi.mock('@/api/wizard', () => ({
  getWizardState: mocks.getWizardState,
  updateWizardState: mocks.updateWizardState,
  getSemesterSummary: mocks.getSemesterSummary,
}))
vi.mock('@/api/onboarding', () => ({
  getOnboardingStatus: mocks.getOnboardingStatus,
}))
vi.mock('@/api/assignments', () => ({
  demoDataStatus: mocks.demoDataStatus,
  loadDemoData: mocks.loadDemoData,
}))

const template = {
  key: 'junior_high_draft',
  name: '初中（空白模板）',
  minutes_per_period: 40,
  subject_count: 12,
  editable: true,
}
const baseState = {
  current_step: 0,
  completed: false,
  semester_id: null,
  total_steps: 5,
  has_semesters: false,
}
const semester = {
  id: 8,
  academic_year: 2042,
  term: 1,
  label: '2042-2043学年第一学期',
  status: 'preparing' as const,
  readiness: 'draft' as const,
  start_date: null,
  end_date: null,
  period_tables: [{
    id: 99,
    name: '初中作息时间表',
    num_weekdays: 5,
    is_default: true,
    periods: [],
  }],
}

const onboardingStages = [
  ['semester', '学期'], ['periods', '作息'], ['calendar', '校历'],
  ['basedata', '基础数据'], ['assignments', '教学任务'], ['integrity', '完整性检查'],
  ['draft', '课表草稿'], ['published', '课表发布'],
] as const

function makeOnboardingStatus(nextStage: string, currentSemester: OnboardingStatus['current_semester'] = null): OnboardingStatus {
  const nextIndex = onboardingStages.findIndex(([key]) => key === nextStage)
  const stages = onboardingStages.map(([key, label], index) => {
    const complete = nextIndex >= 0 && index < nextIndex
    const action = {
      stage: key,
      label: `前往${label}`,
      href: key === 'semester' ? '/wizard' : '/settings/semesters',
    }
    return {
      key,
      label,
      complete,
      status: complete ? 'complete' as const : 'blocked' as const,
      blocking_reason: complete ? '' : `请完成${label}`,
      next_action: complete ? null : action,
      details: {},
    }
  })
  const todos = stages.filter((stage) => !stage.complete)
  return {
    first_success: todos.length === 0,
    wizard_completed: false,
    current_semester: currentSemester,
    stages,
    p0_todos: todos,
    next_action: todos[0]?.next_action ?? null,
  }
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/wizard', name: 'wizard', component: Wizard },
      { path: '/basedata', name: 'basedata', component: { template: '<main>基础数据</main>' } },
      { path: '/settings/semesters', name: 'semesters', component: { template: '<main>学期设置</main>' } },
      { path: '/scheduling/assignments', name: 'assignments', component: { template: '<main>教学任务管理</main>' } },
      { path: '/', name: 'dashboard', component: { template: '<main>仪表盘</main>' } },
      { path: '/settings/period-tables/:id', name: 'period-table-editor', component: { template: '<main>编辑器</main>' } },
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
  const Host = {
    render: () => h(NMessageProvider, null, { default: () => h(Wizard) }),
  }
  const wrapper = mount(Host, {
    global: {
      plugins: [pinia, router],
      stubs: {
        ImportTab: {
          emits: ['imported'],
          template: '<div data-testid="import-tab-stub"><button data-testid="import-complete" @click="$emit(\'imported\')">导入控件</button></div>',
        },
      },
    },
  })
  await flushPromises()
  return { router, wrapper }
}

describe('Wizard', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.listTemplates.mockResolvedValue([template])
    mocks.getWizardState.mockResolvedValue({ ...baseState })
    mocks.updateWizardState.mockImplementation((body: Record<string, unknown>) => Promise.resolve({
      ...baseState,
      ...body,
      semester_id: body.semester_id ?? baseState.semester_id,
    }))
    mocks.getSemester.mockResolvedValue(semester)
    mocks.createSemester.mockResolvedValue(semester)
    mocks.getSemesterSummary.mockResolvedValue({ subjects: 12, teachers: 8, classes: 4, rooms: 3 })
    mocks.getOnboardingStatus.mockResolvedValue(makeOnboardingStatus('semester'))
    mocks.demoDataStatus.mockRejectedValue(new Error('not available'))
  })

  it('读取中显示明确状态', async () => {
    let resolveTemplates!: (value: typeof template[]) => void
    mocks.listTemplates.mockReturnValue(new Promise((resolve) => { resolveTemplates = resolve }))
    const pinia = createPinia()
    const router = makeRouter()
    await router.push('/wizard')
    const Host = { render: () => h(NMessageProvider, null, { default: () => h(Wizard) }) }
    const wrapper = mount(Host, { global: { plugins: [pinia, router] } })
    expect(wrapper.get('[data-testid="wizard-loading"]').text()).toContain('正在读取设置向导')
    resolveTemplates([template])
    await flushPromises()
  })

  it('没有模板时显示空状态并禁用下一步', async () => {
    mocks.listTemplates.mockResolvedValue([])
    const { wrapper } = await mountWizard()

    expect(wrapper.get('[data-testid="wizard-empty"]').text()).toContain('暂无可用的学制模板')
    expect(wrapper.get('[data-testid="wizard-next"]').attributes('disabled')).toBeDefined()
  })

  it('教务主任进入向导时只读，不能保存或跳过设置', async () => {
    const { wrapper } = await mountWizard(baseState, ['director'])

    expect(wrapper.get('[data-testid="wizard-readonly"]').text()).toContain('只能查看')
    expect(wrapper.find('[data-testid="wizard-skip"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="wizard-next"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('input[type="radio"][name="wizard-template"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    expect(mocks.updateWizardState).not.toHaveBeenCalled()
  })

  it('模板使用原生单选组以支持标准键盘操作', async () => {
    mocks.listTemplates.mockResolvedValue([
      template,
      { ...template, key: 'senior_high_draft', name: '高中（空白模板）' },
    ])
    const { wrapper } = await mountWizard()

    const radios = wrapper.findAll('input[type="radio"][name="wizard-template"]')
    expect(radios).toHaveLength(2)
    expect((radios[0].element as HTMLInputElement).checked).toBe(true)
    await radios[1].setValue(true)
    expect((radios[1].element as HTMLInputElement).checked).toBe(true)
  })

  it('创建学期失败时保留当前步骤并给出重试提示', async () => {
    const { wrapper } = await mountWizard()
    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="wizard-step-title"]').text()).toContain('学年学期')

    mocks.createSemester.mockRejectedValue({ detail: '该学年学期已存在' })
    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="wizard-error"]').text()).toContain('该学年学期已存在')
    expect(wrapper.get('[data-testid="wizard-step-title"]').text()).toContain('学年学期')
  })

  it('创建正式学期后刷新首次成功状态', async () => {
    mocks.getOnboardingStatus
      .mockResolvedValueOnce(makeOnboardingStatus('semester'))
      .mockResolvedValueOnce(makeOnboardingStatus('periods', {
        id: semester.id,
        label: semester.label,
        is_demo: false,
      }))
    const { wrapper } = await mountWizard()

    expect(wrapper.get('[data-testid="onboarding-next-action"]').attributes('href')).toBe('/wizard')
    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()

    expect(mocks.getOnboardingStatus).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="onboarding-stage-periods"]').text()).toContain('请完成作息')
    expect(wrapper.get('[data-testid="onboarding-next-action"]').attributes('href')).toBe('/settings/semesters')
  })

  it('导入基础数据后刷新首次成功状态', async () => {
    mocks.getOnboardingStatus
      .mockResolvedValueOnce(makeOnboardingStatus('basedata', {
        id: semester.id,
        label: semester.label,
        is_demo: false,
      }))
      .mockResolvedValueOnce(makeOnboardingStatus('assignments', {
        id: semester.id,
        label: semester.label,
        is_demo: false,
      }))
    const { wrapper } = await mountWizard({
      ...baseState,
      current_step: 3,
      semester_id: semester.id,
    })

    await wrapper.get('[data-testid="import-complete"]').trigger('click')
    await flushPromises()

    expect(mocks.getOnboardingStatus).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="onboarding-stage-assignments"]').text()).toContain('请完成教学任务')
  })

  it('学期创建成功但进度保存失败时可从断点重试', async () => {
    let semesterPatchAttempts = 0
    mocks.updateWizardState.mockImplementation((body: Record<string, unknown>) => {
      if ('semester_id' in body) {
        semesterPatchAttempts += 1
        if (semesterPatchAttempts === 1) return Promise.reject({ detail: '进度保存失败' })
      }
      return Promise.resolve({
        ...baseState,
        ...body,
        semester_id: body.semester_id ?? baseState.semester_id,
      })
    })
    const { wrapper } = await mountWizard()

    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="wizard-error"]').text()).toContain('进度保存失败')
    expect(wrapper.get('[data-testid="wizard-step-title"]').text()).toContain('学年学期')

    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()

    expect(mocks.createSemester).toHaveBeenCalledTimes(1)
    expect(semesterPatchAttempts).toBe(2)
    expect(mocks.getSemester).toHaveBeenCalledWith(semester.id)
    expect(wrapper.get('[data-testid="wizard-step-title"]').text()).toContain('作息时间表')
  })

  it('没有默认作息表时显示并打开第一张表', async () => {
    mocks.getSemester.mockResolvedValue({
      ...semester,
      period_tables: [{ ...semester.period_tables[0], is_default: false }],
    })
    const { router, wrapper } = await mountWizard({
      ...baseState,
      current_step: 2,
      semester_id: semester.id,
    })

    expect(wrapper.text()).toContain('初中作息时间表')
    await wrapper.get('[data-testid="wizard-period-edit"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('period-table-editor')
    expect(router.currentRoute.value.params.id).toBe(String(semester.period_tables[0].id))
  })

  it('完成摘要读取失败时进入完成页并提供专用重试状态', async () => {
    mocks.getSemesterSummary.mockRejectedValue({ detail: '摘要服务暂时不可用' })
    const { wrapper } = await mountWizard({
      ...baseState,
      current_step: 3,
      semester_id: semester.id,
    })

    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="wizard-step-title"]').text()).toContain('完成')
    expect(wrapper.get('[data-testid="wizard-summary-error"]').text()).toContain('摘要服务暂时不可用')
  })

  it('完成五步后跳转教学任务管理并显示真实摘要', async () => {
    const { router, wrapper } = await mountWizard()

    await wrapper.get('[data-testid="tpl-junior_high_draft"]').trigger('keydown.space')
    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="wizard-next"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="wizard-step-title"]').text()).toContain('完成')
    expect(wrapper.text()).toContain('12')
    expect(wrapper.text()).toContain('8')
    await wrapper.get('[data-testid="wizard-finish"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('assignments')
  })
})
