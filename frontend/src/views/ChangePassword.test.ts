import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import ChangePassword from './ChangePassword.vue'
import { useAuthStore } from '@/stores/auth'

const user = {
  id: 1,
  username: 'new-user',
  display_name: '新用户',
  roles: ['scheduler'],
  must_change_password: true,
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/change-password', name: 'change-password', component: ChangePassword },
      { path: '/', name: 'dashboard', component: { template: '<main>仪表盘</main>' } },
    ],
  })
}

async function mountChangePassword() {
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  auth.user = user
  auth.loaded = true
  const router = makeRouter()
  await router.push('/change-password')
  await router.isReady()
  const Host = { render: () => h(NMessageProvider, () => h(ChangePassword)) }
  const wrapper = mount(Host, { global: { plugins: [pinia, router] } })
  return { auth, router, wrapper }
}

async function fillPasswordForm(wrapper: ReturnType<typeof mount>, oldPassword: string, newPassword: string, confirmPassword: string) {
  await wrapper.get('[data-testid="cp-old"] input').setValue(oldPassword)
  await wrapper.get('[data-testid="cp-new"] input').setValue(newPassword)
  await wrapper.get('[data-testid="cp-confirm"] input').setValue(confirmPassword)
}

describe('ChangePassword', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('验证原密码、新密码长度和确认密码一致性', async () => {
    const { wrapper } = await mountChangePassword()

    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('[data-testid="cp-feedback"]').text()).toContain('请输入原密码')

    await fillPasswordForm(wrapper, 'old-password', 'short', 'short')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('[data-testid="cp-feedback"]').text()).toContain('新密码至少需要 8 个字符')

    await fillPasswordForm(wrapper, 'old-password', 'long-password', 'different-password')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('[data-testid="cp-feedback"]').text()).toContain('两次输入的新密码不一致')
  })

  it('显示后端失败原因并防止重复请求', async () => {
    const { auth, wrapper } = await mountChangePassword()
    let rejectChange!: (reason: unknown) => void
    const changePassword = vi.spyOn(auth, 'changePassword').mockImplementation(() => new Promise((_, reject) => {
      rejectChange = reject
    }))
    await fillPasswordForm(wrapper, 'old-password', 'long-password', 'long-password')
    await wrapper.get('form').trigger('submit')

    expect(changePassword).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="cp-submit"]').attributes('disabled')).toBeDefined()
    await wrapper.get('form').trigger('submit')
    expect(changePassword).toHaveBeenCalledTimes(1)

    rejectChange({ detail: '原密码错误' })
    await flushPromises()
    expect(wrapper.get('[data-testid="cp-feedback"]').text()).toContain('原密码错误')
  })
})
