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
  // Naive UI locale and date parsing must be selected before the first render.
  await useAppConfigStore(pinia).load()
  app.use(router)
  app.use(naive)

  // session 過期/被撤銷時,清除登入狀態並導回登入頁
  setUnauthorizedHandler(() => {
    useAuthStore().reset()
    if (router.currentRoute.value.name !== 'login') {
      router.push({ name: 'login' })
    }
  })

  app.mount('#app')
}

void bootstrap()
