import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import BaseData from './BaseData.vue'

const mocks = vi.hoisted(() => ({
  getSemesterContext: vi.fn(),
  listSemesters: vi.fn(),
  switchSemesterContext: vi.fn(),
}))

vi.mock('@/api/semesters', () => ({ ...mocks }))

const semester = {
  id: 8,
  academic_year: 2042,
  term: 1,
  label: '2042-2043学年第一学期',
  status: 'preparing',
  readiness: 'draft',
  start_date: '2042-09-01',
  end_date: '2043-01-20',
  is_current: true,
}

const ManualEntryStub = {
  name: 'ManualEntry',
  props: [
    'semesterId', 'canEdit', 'canDelete', 'canManageAccounts', 'showClasses', 'showReadonlyNotice',
  ],
  template: '<div data-testid="manual-entry-stub">{{ semesterId }}/{{ String(canEdit) }}/{{ String(canDelete) }}/{{ String(canManageAccounts) }}/{{ String(showClasses) }}/{{ String(showReadonlyNotice) }}</div>',
}

const TemplateImportStub = {
  name: 'TemplateImport',
  props: ['semester', 'canEdit'],
  template: '<div data-testid="template-import-stub">{{ semester.id }}/{{ String(canEdit) }}</div>',
}

async function mountBaseData(roles: string[]) {
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  auth.user = {
    id: 1,
    username: 'base-data-user',
    display_name: '基础数据用户',
    roles,
    must_change_password: false,
  }
  auth.loaded = true

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/basedata', name: 'basedata', component: { template: '<main />' } },
      { path: '/settings/semesters', name: 'semesters', component: { template: '<main />' } },
    ],
  })
  await router.push('/basedata')
  await router.isReady()

  const wrapper = mount(BaseData, {
    global: {
      plugins: [pinia, router],
      stubs: { ManualEntry: ManualEntryStub, TemplateImport: TemplateImportStub },
    },
  })
  await flushPromises()
  return wrapper
}

describe('BaseData', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.getSemesterContext.mockResolvedValue({
      current_semester: semester,
      revision: 1,
      can_switch: true,
    })
    mocks.listSemesters.mockResolvedValue([semester])
  })

  it('进入页面后直接展示手工录入，不再渲染外层或批量导入切换', async () => {
    const wrapper = await mountBaseData(['director'])

    expect(wrapper.get('[data-testid="manual-entry-stub"]').text()).toBe('8/true/false/false/false/false')
    expect(wrapper.find('[data-testid="entry-mode"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="combined-import-panel"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('批量导入')
    expect(wrapper.text()).not.toContain('参考文件')
  })

  it('通过基础数据页的正式入口进入模板导入工作区', async () => {
    const wrapper = await mountBaseData(['director'])

    await wrapper.get('[data-testid="basedata-template-import"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="template-import-stub"]').text()).toBe('8/true')
    expect(wrapper.find('[data-testid="manual-entry-stub"]').exists()).toBe(false)
  })

  it('系统管理员在手工录入中保留删除和账号绑定能力', async () => {
    const wrapper = await mountBaseData(['admin'])

    expect(wrapper.get('[data-testid="manual-entry-stub"]').text()).toBe('8/true/true/true/false/false')
  })

  it('只读角色只显示一条页面级权限提示', async () => {
    const wrapper = await mountBaseData(['teacher'])

    expect(wrapper.get('[data-testid="basedata-readonly"]').text()).toContain('仅可查看基础数据')
    expect(wrapper.get('[data-testid="manual-entry-stub"]').text()).toBe('8/false/false/false/false/false')
    expect(wrapper.findAll('[data-testid="basedata-readonly"]')).toHaveLength(1)
  })
})
