import naive from 'naive-ui'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import './styles/tokens.css'
import { setUnauthorizedHandler } from './api/client'
import { router } from './router'
import { useAuthStore } from './stores/auth'
import { useAppConfigStore } from './stores/appConfig'

async function bootstrap() {
  const app = createApp(App)
  const pinia = createPinia()
  app.use(pinia)
  await useAppConfigStore(pinia).load()
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
