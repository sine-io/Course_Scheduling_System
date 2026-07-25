<script setup lang="ts">
import { NButton, NCard, NForm, NFormItem, NInput, useMessage } from 'naive-ui'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const message = useMessage()

const username = ref('')
const password = ref('')
const loading = ref(false)

async function onSubmit() {
  if (!username.value || !password.value) {
    message.warning('请输入账号和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    // 首次登录需要修改密码时进入修改密码页，否则进入仪表盘。
    router.push(auth.mustChangePassword ? { name: 'change-password' } : { name: 'dashboard' })
  } catch (e) {
    message.error((e as ApiError).detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 16px">
    <n-card title="学校排课、调课与代课管理系统" style="max-width: 400px">
      <n-form @submit.prevent="onSubmit">
        <n-form-item :label="'账号'">
          <n-input v-model:value="username" :placeholder="'请输入账号'" @keyup.enter="onSubmit" />
        </n-form-item>
        <n-form-item :label="'密码'">
          <n-input
            v-model:value="password"
            type="password"
            show-password-on="click"
            :placeholder="'请输入密码'"
            @keyup.enter="onSubmit"
          />
        </n-form-item>
        <n-button type="primary" block :loading="loading" attr-type="submit" @click="onSubmit">
          {{ '登录' }}
        </n-button>
      </n-form>
    </n-card>
  </div>
</template>
