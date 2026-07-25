<script setup lang="ts">
import { NButton, NCard, NForm, NFormItem, NInput, useMessage } from 'naive-ui'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useAppConfigStore } from '@/stores/appConfig'

const auth = useAuthStore()
const appConfig = useAppConfigStore()
const router = useRouter()
const message = useMessage()

const username = ref('')
const password = ref('')
const loading = ref(false)
const tr = (tw: string, mainland: string) => appConfig.isMainland ? mainland : tw

async function onSubmit() {
  if (!username.value || !password.value) {
    message.warning(tr('請輸入帳號與密碼', '请输入账号和密码'))
    return
  }
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    // 首次登入需改密碼者導向改密碼頁,否則進儀表板
    router.push(auth.mustChangePassword ? { name: 'change-password' } : { name: 'dashboard' })
  } catch (e) {
    message.error((e as ApiError).detail || tr('登入失敗', '登录失败'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 16px">
    <n-card :title="appConfig.isMainland ? '排课与调代课系统' : '排課與調代課系統'" style="max-width: 400px">
      <n-form @submit.prevent="onSubmit">
        <n-form-item :label="tr('帳號', '账号')">
          <n-input v-model:value="username" :placeholder="tr('請輸入帳號', '请输入账号')" @keyup.enter="onSubmit" />
        </n-form-item>
        <n-form-item :label="tr('密碼', '密码')">
          <n-input
            v-model:value="password"
            type="password"
            show-password-on="click"
            :placeholder="tr('請輸入密碼', '请输入密码')"
            @keyup.enter="onSubmit"
          />
        </n-form-item>
        <n-button type="primary" block :loading="loading" attr-type="submit" @click="onSubmit">
          {{ tr('登入', '登录') }}
        </n-button>
      </n-form>
    </n-card>
  </div>
</template>
