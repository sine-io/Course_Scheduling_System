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

const RoomsTabStub = {
  name: 'RoomsTab',
  props: ['semesterId', 'canEdit', 'canDelete'],
  template: '<div data-testid="rooms-tab-stub">{{ semesterId }}/{{ String(canEdit) }}/{{ String(canDelete) }}</div>',
}

const TemplateImportStub = {
  name: 'TemplateImport',
  props: ['semester', 'canEdit'],
  template: '<div data-testid="template-import-stub">{{ semester.id }}/{{ String(canEdit) }}</div>',
}

const ReferenceImportStub = {
  name: 'ReferenceImport',
  props: ['semesterId', 'canEdit'],
  template: '<div data-testid="reference-import-stub">{{ semesterId }}/{{ String(canEdit) }}</div>',
}

const TeacherAccountBindingsStub = {
  name: 'TeacherAccountBindings',
  props: ['semesterId', 'canEdit'],
  template: '<div data-testid="teacher-account-bindings-stub">{{ semesterId }}/{{ String(canEdit) }}</div>',
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
      { path: '/scheduling/flow', name: 'scheduling-workbench', component: { template: '<main />' } },
    ],
  })
  await router.push('/basedata')
  await router.isReady()

  const wrapper = mount(BaseData, {
    global: {
      plugins: [pinia, router],
      stubs: {
        RoomsTab: RoomsTabStub,
        TemplateImport: TemplateImportStub,
        ReferenceImport: ReferenceImportStub,
        TeacherAccountBindings: TeacherAccountBindingsStub,
      },
    },
  })
  await flushPromises()
  return { wrapper, router }
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

  it('进入页面后默认只展示基础数据独有的教室/场地维护', async () => {
    const { wrapper } = await mountBaseData(['director'])

    expect(wrapper.get('[data-testid="rooms-tab-stub"]').text()).toBe('8/true/false')
    expect(wrapper.find('[data-testid="manual-entry-stub"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="basedata-section-teacher-accounts"]').exists()).toBe(false)
  })

  it('可在保留的模板与参考文件导入功能间切换', async () => {
    const { wrapper, router } = await mountBaseData(['director'])

    await router.replace('/basedata?tab=template')
    await flushPromises()

    expect(wrapper.get('[data-testid="template-import-stub"]').text()).toBe('8/true')
    expect(wrapper.find('[data-testid="rooms-tab-stub"]').exists()).toBe(false)

    await router.replace('/basedata?tab=reference')
    await flushPromises()
    expect(wrapper.get('[data-testid="reference-import-stub"]').text()).toBe('8/true')
  })

  it('系统管理员通过专用页面管理账号绑定，不再进入完整教师维护页', async () => {
    const { wrapper, router } = await mountBaseData(['admin'])

    expect(wrapper.get('[data-testid="rooms-tab-stub"]').text()).toBe('8/true/true')
    await router.replace('/basedata?tab=teacher-accounts')
    await flushPromises()
    expect(wrapper.get('[data-testid="teacher-account-bindings-stub"]').text()).toBe('8/true')
    expect(wrapper.find('[data-testid="manual-entry-stub"]').exists()).toBe(false)
  })

  it('只读角色只显示一条页面级权限提示', async () => {
    const { wrapper } = await mountBaseData(['teacher'])

    expect(wrapper.get('[data-testid="basedata-readonly"]').text()).toContain('当前学期仅可查看')
    expect(wrapper.get('[data-testid="rooms-tab-stub"]').text()).toBe('8/false/false')
    expect(wrapper.findAll('[data-testid="basedata-readonly"]')).toHaveLength(1)
  })

  it('没有学期时从空状态回到排课工作台入口', async () => {
    mocks.getSemesterContext.mockResolvedValue({
      current_semester: null,
      revision: 0,
      can_switch: true,
    })
    mocks.listSemesters.mockResolvedValue([])

    const { wrapper, router } = await mountBaseData(['director'])

    expect(wrapper.get('[data-testid="basedata-empty"]').text()).toContain('排课工作台')
    await wrapper.get('[data-testid="basedata-start-scheduling"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('scheduling-workbench')
  })
})
