import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import ManualEntry from './ManualEntry.vue'

const mocks = vi.hoisted(() => ({
  createSubject: vi.fn(),
  listClassUnits: vi.fn(),
  listRooms: vi.fn(),
  listSubjects: vi.fn(),
  listTeachers: vi.fn(),
}))

vi.mock('@/api/basedata', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/api/basedata')>(),
  ...mocks,
}))

const subject = {
  id: 1,
  semester_id: 8,
  name: '语文',
  domain: '语言与文学',
  required_room_type: null,
  default_block_size: 1,
  is_major: true,
}

async function mountEntry(canEdit = true) {
  const Host = {
    render: () => h(NMessageProvider, null, {
      default: () => h(ManualEntry, { semesterId: 8, canEdit }),
    }),
  }
  const wrapper = mount(Host, {
    global: {
      stubs: {
        SubjectsTab: {
          props: ['canEdit'],
          template: '<div data-testid="subjects-child">{{ String(canEdit) }}</div>',
        },
        TeachersTab: {
          props: ['canEdit', 'canManageAccounts'],
          template: '<div data-testid="teachers-child">{{ String(canEdit) }} / {{ String(canManageAccounts) }}</div>',
        },
        ClassesTab: { template: '<div data-testid="classes-child" />' },
        RoomsTab: { template: '<div data-testid="rooms-child" />' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('ManualEntry', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.createSubject.mockImplementation((_semesterId, body) => Promise.resolve({
      ...subject,
      id: body.name === '语文' ? 1 : 2,
      name: body.name,
    }))
    mocks.listSubjects.mockResolvedValue([])
    mocks.listTeachers.mockResolvedValue([])
    mocks.listClassUnits.mockResolvedValue([])
    mocks.listRooms.mockResolvedValue([])
  })

  it('按引用顺序显示真实完成状态，教室为可选项', async () => {
    const wrapper = await mountEntry()

    expect(wrapper.get('[data-testid="manual-section-subjects"]').text()).toContain('0 条 · 待补充')
    expect(wrapper.get('[data-testid="manual-section-teachers"]').text()).toContain('0 条 · 待补充')
    expect(wrapper.get('[data-testid="manual-section-classes"]').text()).toContain('0 条 · 待补充')
    expect(wrapper.get('[data-testid="manual-section-rooms"]').text()).toContain('0 条 · 已完成')
    expect(wrapper.find('[data-testid="manual-common-preview"]').exists()).toBe(false)
    expect(mocks.createSubject).not.toHaveBeenCalled()
  })

  it('逐项展示常用科目，确认前不写入，确认后只新增所选项', async () => {
    const wrapper = await mountEntry()

    await wrapper.get('[data-testid="manual-common-语文"]').trigger('click')
    await wrapper.get('[data-testid="manual-common-数学"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="manual-common-preview"]').text()).toContain('语文、数学')
    expect(mocks.createSubject).not.toHaveBeenCalled()

    await wrapper.get('[data-testid="manual-common-confirm"]').trigger('click')
    await flushPromises()

    expect(mocks.createSubject).toHaveBeenCalledTimes(2)
    expect(mocks.createSubject).toHaveBeenCalledWith(8, expect.objectContaining({ name: '语文' }))
    expect(mocks.createSubject).toHaveBeenCalledWith(8, expect.objectContaining({ name: '数学' }))
  })

  it('缺少引用数据时提供直接处理入口，教师模式不开放账号管理', async () => {
    const wrapper = await mountEntry()

    await wrapper.get('[data-testid="manual-section-teachers"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="manual-teachers-dependency"]').text()).toContain('先添加至少一个科目')
    expect(wrapper.get('[data-testid="teachers-child"]').text()).toContain('true / false')

    await wrapper.get('[data-testid="manual-go-subjects"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="manual-common-subjects"]')).toBeTruthy()
  })

  it('已有数据会立即显示为完成，并标记已有常用科目', async () => {
    mocks.listSubjects.mockResolvedValue([subject])
    mocks.listTeachers.mockResolvedValue([{ id: 2, name: '王老师' }])
    mocks.listClassUnits.mockResolvedValue([{ id: 3, name: '七年级1班' }])
    const wrapper = await mountEntry()

    expect(wrapper.get('[data-testid="manual-section-subjects"]').text()).toContain('1 条 · 已完成')
    expect(wrapper.get('[data-testid="manual-section-teachers"]').text()).toContain('1 条 · 已完成')
    expect(wrapper.get('[data-testid="manual-section-classes"]').text()).toContain('1 条 · 已完成')
    expect(wrapper.get('[data-testid="manual-common-语文"]').text()).toContain('已存在')
    expect(wrapper.get('[data-testid="manual-common-语文"]').classes()).toContain('n-checkbox--disabled')
  })

  it('只读角色可以查看状态，但不能确认写入', async () => {
    const wrapper = await mountEntry(false)

    expect(wrapper.get('[data-testid="manual-readonly"]').text()).toContain('只能查看')
    expect(wrapper.get('[data-testid="subjects-child"]').text()).toBe('false')
    expect(wrapper.get('[data-testid="manual-common-confirm"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="manual-common-语文"]').trigger('click')
    expect(mocks.createSubject).not.toHaveBeenCalled()
  })
})
