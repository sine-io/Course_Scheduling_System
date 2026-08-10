import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import Login from './Login.vue'
import { useAuthStore } from '@/stores/auth'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: Login },
      { path: '/', name: 'dashboard', component: { template: '<main>仪表盘</main>' } },
      { path: '/change-password', name: 'change-password', component: { template: '<main>修改密码</main>' } },
    ],
  })
}

async function mountLogin() {
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  const router = makeRouter()
  await router.push('/login')
  await router.isReady()
  const Host = { render: () => h(NMessageProvider, () => h(Login)) }
  const wrapper = mount(Host, { global: { plugins: [pinia, router] } })
  return { auth, router, wrapper }
}

describe('Login', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('提交空表单时逐项提示账号和密码', async () => {
    const { wrapper } = await mountLogin()

    await wrapper.get('form').trigger('submit')

    expect(wrapper.get('[data-testid="login-feedback"]').text()).toContain('请输入账号和密码')
  })

  it('支持表单提交、显示加载状态并且只发送一次请求', async () => {
    const { auth, wrapper } = await mountLogin()
    let resolveLogin!: () => void
    const login = vi.spyOn(auth, 'login').mockImplementation(() => new Promise<void>((resolve) => {
      resolveLogin = resolve
    }))
    auth.user = {
      id: 1,
      username: 'scheduler',
      display_name: '排课管理员',
      roles: ['scheduler'],
      must_change_password: false,
    }

    await wrapper.get('input[placeholder="请输入账号"]').setValue('scheduler')
    await wrapper.get('input[placeholder="请输入密码"]').setValue('secret123')
    await wrapper.get('form').trigger('submit')

    expect(login).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="login-submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="login-submit"]').text()).toContain('登录中')

    resolveLogin()
    await flushPromises()
    expect(wrapper.get('[data-testid="login-submit"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.vm).toBeTruthy()
  })

  it('把登录失败原因显示在页面上', async () => {
    const { auth, wrapper } = await mountLogin()
    vi.spyOn(auth, 'login').mockRejectedValue({ detail: '账号或密码错误' })

    await wrapper.get('input[placeholder="请输入账号"]').setValue('scheduler')
    await wrapper.get('input[placeholder="请输入密码"]').setValue('wrong')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-testid="login-feedback"]').text()).toContain('账号或密码错误')
  })
})
