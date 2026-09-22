import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SchedulingSupportWorkspace from './SchedulingSupportWorkspace.vue'

describe('SchedulingSupportWorkspace', () => {
  it('forwards resource changes to the scheduling workbench', async () => {
    const wrapper = mount(SchedulingSupportWorkspace, {
      props: { panel: 'resources', semesterId: 4 },
      global: {
        stubs: {
          BaseData: {
            emits: ['changed'],
            template: '<button data-testid="resource-change" @click="$emit(\'changed\')">change</button>',
          },
        },
      },
    })

    await wrapper.get('[data-testid="resource-change"]').trigger('click')

    expect(wrapper.emitted('changed')).toHaveLength(1)
  })
})
