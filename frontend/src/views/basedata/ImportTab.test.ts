import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ImportTab from './ImportTab.vue'

const ManualEntryStub = {
  name: 'ManualEntry',
  props: ['semesterId', 'canEdit', 'canDelete', 'canManageAccounts', 'initialSection'],
  emits: ['changed'],
  template: '<button data-testid="manual-entry-stub" @click="$emit(\'changed\')">{{ initialSection }}</button>',
}

function mountTab(props: Record<string, unknown> = {}) {
  return mount(ImportTab, {
    props: { semesterId: 8, ...props },
    global: { stubs: { ManualEntry: ManualEntryStub } },
  })
}

describe('ImportTab manual-entry compatibility', () => {
  it('直接展示手工录入，不再渲染批量或模式切换入口', () => {
    const wrapper = mountTab()

    expect(wrapper.get('[data-testid="manual-entry-stub"]').text()).toBe('subjects')
    expect(wrapper.find('[data-testid="entry-mode"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="combined-import-panel"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('批量导入')
  })

  it('透传维护权限和目标分类，并将变更事件转换为 imported', async () => {
    const wrapper = mountTab({
      canEdit: false,
      canDelete: true,
      canManageAccounts: true,
      initialManualSection: 'rooms',
    })
    const manualEntry = wrapper.findComponent(ManualEntryStub)

    expect(manualEntry.props()).toMatchObject({
      semesterId: 8,
      canEdit: false,
      canDelete: true,
      canManageAccounts: true,
      initialSection: 'rooms',
    })

    await wrapper.get('[data-testid="manual-entry-stub"]').trigger('click')
    expect(wrapper.emitted('imported')).toHaveLength(1)
  })
})
