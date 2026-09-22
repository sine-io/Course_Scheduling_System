import { flushPromises, mount } from '@vue/test-utils'
import { NDialogProvider, NMessageProvider, NSelect } from 'naive-ui'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import TeacherAccountBindings from './TeacherAccountBindings.vue'

const mocks = vi.hoisted(() => ({
  listBindableAccounts: vi.fn(),
  listTeachers: vi.fn(),
  updateTeacher: vi.fn(),
}))
const dialogMocks = vi.hoisted(() => ({ warning: vi.fn() }))

vi.mock('@/api/basedata', () => ({ ...mocks }))
vi.mock('naive-ui', async () => {
  const actual = await vi.importActual<typeof import('naive-ui')>('naive-ui')
  return {
    ...actual,
    useDialog: () => ({
      warning: (options: { onPositiveClick?: () => unknown }) => {
        dialogMocks.warning(options)
        return options.onPositiveClick?.()
      },
    }),
  }
})

const teacher = {
  id: 17,
  semester_id: 8,
  name: '林老师',
  id_last4: '1234',
  base_periods: 14,
  admin_title: '年级负责人',
  admin_reduction: 2,
  is_external: false,
  is_active: true,
  subjects: [{ id: 3, name: '数学' }],
  email: 'lin@example.test',
  phone: '13800000000',
  line_id: 'lin-teacher',
  user_id: null,
}

function mountBindings(canEdit = true) {
  const Host = {
    render: () => h(NMessageProvider, null, {
      default: () => h(NDialogProvider, null, {
        default: () => h(TeacherAccountBindings, { semesterId: 8, canEdit }),
      }),
    }),
  }
  return mount(Host, {
    global: {
      stubs: {
        Modal: {
          props: ['show'],
          template: '<div v-if="show"><slot /></div>',
        },
      },
    },
  })
}

describe('TeacherAccountBindings', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.listTeachers.mockResolvedValue([teacher])
    mocks.listBindableAccounts.mockResolvedValue([
      { id: 29, username: 'lin', display_name: '林老师账号' },
    ])
    mocks.updateTeacher.mockResolvedValue({ ...teacher, user_id: 29 })
    dialogMocks.warning.mockClear()
  })

  it('只提供账号绑定操作，不提供教师新增、编辑或删除', async () => {
    const wrapper = mountBindings()
    await flushPromises()

    expect(wrapper.get('[data-testid="teacher-accounts-table"]').text()).toContain('林老师')
    expect(wrapper.find('[data-testid="teacher-add"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="teacher-edit-17"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="teacher-delete-17"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="teacher-account-bind-17"]').text()).toContain('绑定账号')
  })

  it('保存绑定时保留教师字段并附带精确的高风险确认目标', async () => {
    const wrapper = mountBindings()
    await flushPromises()
    await wrapper.get('[data-testid="teacher-account-bind-17"]').trigger('click')
    await flushPromises()

    const select = wrapper.getComponent(NSelect)
    select.vm.$emit('update:value', 29)
    await flushPromises()
    await wrapper.get('[data-testid="teacher-account-save"]').trigger('click')
    await flushPromises()

    expect(dialogMocks.warning).toHaveBeenCalledOnce()
    expect(mocks.updateTeacher).toHaveBeenCalledWith(17, expect.objectContaining({
      name: '林老师',
      id_last4: '1234',
      base_periods: 14,
      admin_title: '年级负责人',
      admin_reduction: 2,
      subject_ids: [3],
      email: 'lin@example.test',
      phone: '13800000000',
      line_id: 'lin-teacher',
      user_id: 29,
      account_confirmation: expect.objectContaining({
        confirmed: true,
        target: 'teacher:17:account:29',
      }),
    }))
  })

  it('只读状态不显示绑定按钮', async () => {
    const wrapper = mountBindings(false)
    await flushPromises()
    expect(wrapper.find('[data-testid="teacher-account-bind-17"]').exists()).toBe(false)
  })
})
