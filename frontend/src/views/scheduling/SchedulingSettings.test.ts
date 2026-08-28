import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { useAuthStore } from '@/stores/auth'
import SchedulingSettings from './SchedulingSettings.vue'

const semesterMocks = vi.hoisted(() => ({
  getSemesterContext: vi.fn(),
  listSemesters: vi.fn(),
  switchSemesterContext: vi.fn(),
}))
const ruleMocks = vi.hoisted(() => ({
  activateSchedulingRules: vi.fn(),
  createSchedulingRule: vi.fn(),
  deleteSchedulingRule: vi.fn(),
  getRuleWorkspace: vi.fn(),
  listRuleTemplates: vi.fn(),
  updateSchedulingRule: vi.fn(),
  validateSchedulingRules: vi.fn(),
}))

vi.mock('@/api/semesters', () => ({ ...semesterMocks }))
vi.mock('@/api/schedulingRules', () => ({ ...ruleMocks }))

const semester = {
  id: 7,
  academic_year: 2042,
  term: 1,
  label: '2042-2043学年第一学期',
  status: 'preparing',
  readiness: 'ready',
  start_date: '2042-09-01',
  end_date: '2043-01-31',
  is_current: true,
}
const template = {
  key: 'global_blackout',
  label: '全校禁排时段',
  description: '指定全校不可排课的时段',
  supported: true,
  target_types: ['school'],
  operators: ['forbid'],
  strengths: ['hard'],
  operator_strengths: { forbid: ['hard'] },
  unavailable_reason: null,
}
const rule = {
  id: 21,
  rule_key: 'rule-school-meeting',
  revision_id: 9,
  name: '行政会保留时段',
  template: template.key,
  template_label: template.label,
  target: { entity_type: 'school', ids: [] },
  timing: { weekdays: [1], period_nos: [2], period_table_ids: [] },
  operator: 'forbid',
  strength: 'hard',
  priority: 'high',
  source_kind: 'custom',
  source_text: '周一第一节行政会',
  enabled: true,
  status: 'draft',
  compiler_version: 'v1',
  compiler_status: '可编译',
  summary: '全校在周一第一节禁排',
}
const draftRevision = {
  id: 9,
  revision_no: 2,
  status: 'draft',
  note: '',
  created_by_name: '教务主任',
  created_at: '2042-08-15T00:00:00Z',
  activated_at: null,
}
const workspace = {
  semester_id: semester.id,
  active_revision: { ...draftRevision, id: 8, revision_no: 1, status: 'active' },
  draft_revision: draftRevision,
  rules: [rule],
  builtin_rules: [{
    rule_key: 'H1',
    name: '班级时间唯一',
    summary: '同一班级在同一课位只能上一门课',
    strength: 'hard',
    source_kind: 'builtin',
    status: 'active',
  }],
  options: {
    subjects: [],
    teachers: [],
    classes: [],
    grades: [],
    assignments: [],
    period_tables: [{
      id: 3,
      name: '初中作息',
      num_weekdays: 5,
      slots: [{ weekday: 1, period_no: 2, name: '第一节', type: 'regular' }],
    }],
  },
}

async function mountEditor() {
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
  const Host = {
    render: () => h(NMessageProvider, null, { default: () => h(SchedulingSettings) }),
  }
  const wrapper = mount(Host, {
    attachTo: document.body,
    global: { plugins: [pinia] },
  })
  await flushPromises()
  return wrapper
}

describe('SchedulingSettings rule editor', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    semesterMocks.getSemesterContext.mockResolvedValue({
      current_semester: semester,
      revision: 3,
      can_switch: true,
    })
    semesterMocks.listSemesters.mockResolvedValue([semester])
    ruleMocks.listRuleTemplates.mockResolvedValue([template])
    ruleMocks.getRuleWorkspace.mockResolvedValue(workspace)
    ruleMocks.updateSchedulingRule.mockResolvedValue(rule)
    ruleMocks.validateSchedulingRules.mockResolvedValue({
      revision_id: draftRevision.id,
      valid: true,
      diagnostics: [],
      matched_assignment_count: 4,
      excluded_candidate_count: 12,
    })
    ruleMocks.activateSchedulingRules.mockResolvedValue({
      ...workspace,
      active_revision: { ...draftRevision, status: 'active' },
      draft_revision: null,
    })
  })

  it('loads the versioned workspace and reports validation impact', async () => {
    const wrapper = await mountEditor()

    expect(ruleMocks.getRuleWorkspace).toHaveBeenCalledWith(semester.id)
    expect(wrapper.text()).toContain('行政会保留时段')
    expect(wrapper.text()).toContain('班级时间唯一')
    expect(wrapper.text()).toContain('v1')
    expect(wrapper.text()).toContain('v2')

    await wrapper.get('[data-testid="rule-validate"]').trigger('click')
    await flushPromises()

    expect(ruleMocks.validateSchedulingRules).toHaveBeenCalledWith(semester.id)
    expect(wrapper.text()).toContain('匹配 4 项教学任务，影响 12 个候选课位')
  })

  it('updates a structured draft and activates its exact revision', async () => {
    const wrapper = await mountEditor()

    await wrapper.get('.rule-list-item').trigger('click')
    await wrapper.get('[data-testid="rule-save"]').trigger('click')
    await flushPromises()

    expect(ruleMocks.updateSchedulingRule).toHaveBeenCalledWith(
      semester.id,
      rule.rule_key,
      expect.objectContaining({
        name: rule.name,
        template: template.key,
        target: rule.target,
        timing: rule.timing,
        operator: 'forbid',
        strength: 'hard',
      }),
    )

    await wrapper.get('[data-testid="rule-activate"]').trigger('click')
    await flushPromises()

    expect(ruleMocks.activateSchedulingRules).toHaveBeenCalledWith(
      semester.id,
      '方案 B 规则编辑器 v2',
    )
  })
})
