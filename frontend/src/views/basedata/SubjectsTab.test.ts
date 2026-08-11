import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SubjectsTab from './SubjectsTab.vue'

const mocks = vi.hoisted(() => ({
  listSubjects: vi.fn(),
  createSubject: vi.fn(),
  updateSubject: vi.fn(),
  deleteSubject: vi.fn(),
}))

vi.mock('@/api/basedata', () => ({
  ...mocks,
  ROOM_TYPE_LABELS: {
    normal: '普通教室',
    special: '专用教室',
    workshop: '实训场地',
    outdoor: '户外',
  },
}))

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

const fakeSubjects = [
  {
    id: 1,
    semester_id: 1,
    name: '数学',
    domain: '数学领域',
    required_room_type: null,
    default_block_size: 2,
    is_major: true,
  },
  {
    id: 2,
    semester_id: 1,
    name: '语文',
    domain: null,
    required_room_type: null,
    default_block_size: 1,
    is_major: false,
  },
]

function mountTab(props: { semesterId?: number; canEdit?: boolean } = {}) {
  const Host = {
    render: () => h(
      NMessageProvider,
      null,
      { default: () => h(SubjectsTab, { semesterId: props.semesterId ?? 1, canEdit: props.canEdit ?? true }) },
    ),
  }
  return mount(Host)
}

describe('SubjectsTab', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.listSubjects.mockResolvedValue(fakeSubjects)
  })

  it('读取期间显示加载状态，完成后显示科目列表', async () => {
    const request = deferred<typeof fakeSubjects>()
    mocks.listSubjects.mockReturnValue(request.promise)

    const wrapper = mountTab()
    await nextTick()
    expect(wrapper.get('[data-testid="subjects-loading"]').text()).toContain('正在读取科目')

    request.resolve(fakeSubjects)
    await flushPromises()
    expect(wrapper.text()).toContain('数学')
    expect(wrapper.text()).toContain('2 连堂')
  })

  it('读取失败时提供局部重试入口', async () => {
    let attempts = 0
    mocks.listSubjects.mockImplementation(() => {
      attempts += 1
      return attempts === 1
        ? Promise.reject({ detail: '科目服务暂时不可用' })
        : Promise.resolve(fakeSubjects)
    })

    const wrapper = mountTab()
    await flushPromises()
    expect(wrapper.get('[data-testid="subjects-error"]').text()).toContain('科目服务暂时不可用')

    await wrapper.get('[data-testid="subjects-retry"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="subjects-error"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="subjects-table"]').text()).toContain('语文')
  })

  it('只读角色仍可查看列表但不显示写入操作', async () => {
    const wrapper = mountTab({ canEdit: false })
    await flushPromises()

    expect(wrapper.get('[data-testid="subjects-readonly"]').text()).toContain('仅可查看')
    expect(wrapper.find('[data-testid="subject-add"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="subject-edit-1"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="subject-delete-1"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="subjects-table"]').text()).toContain('数学')
  })
})
