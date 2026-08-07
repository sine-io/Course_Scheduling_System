import naive from 'naive-ui'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { setUnauthorizedHandler } from './api/client'
import { router } from './router'
import { useAuthStore } from './stores/auth'
import { useAppConfigStore } from './stores/appConfig'

async function bootstrap() {
  const app = createApp(App)
  const pinia = createPinia()
  app.use(pinia)
  // 原型是完全内存化的静态评审面；没有后端时跳过启动配置请求。
  // 其他路径仍在首次渲染前加载真实的界面配置。
  if (!window.location.pathname.startsWith('/prototype/')) {
    await useAppConfigStore(pinia).load()
  }
  app.use(router)
  app.use(naive)

  // 会话过期或被撤销时，清除登录状态并返回登录页。
  setUnauthorizedHandler(() => {
    useAuthStore().reset()
    if (router.currentRoute.value.name !== 'login') {
      router.push({ name: 'login' })
    }
  })

  app.mount('#app')
}

void bootstrap()
