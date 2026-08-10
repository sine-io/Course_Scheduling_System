<script setup lang="ts">
import { NButton, NForm, NFormItem, NInput } from 'naive-ui'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import AuthPageFrame from '@/components/AuthPageFrame.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const loading = ref(false)
const feedback = ref<string | null>(null)

function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as Partial<ApiError> | null)?.detail
  return detail || fallback
}

async function onSubmit() {
  if (loading.value) return

  const account = username.value.trim()
  if (!account && !password.value) {
    feedback.value = '请输入账号和密码'
    return
  }
  if (!account) {
    feedback.value = '请输入账号'
    return
  }
  if (!password.value) {
    feedback.value = '请输入密码'
    return
  }

  feedback.value = null
  loading.value = true
  try {
    await auth.login(account, password.value)
    // 首次登录需要修改密码时进入修改密码页，否则进入仪表盘。
    await router.push(auth.mustChangePassword ? { name: 'change-password' } : { name: 'dashboard' })
  } catch (error) {
    feedback.value = apiErrorMessage(error, '登录失败，请检查账号和密码后重试。')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthPageFrame
    eyebrow="账户登录"
    title="登录教务排课"
    description="使用学校分配的账号进入教务工作台。"
    context-title="学校排课、调课与代课管理系统"
    context-description="使用学校账号进入排课、调课与代课工作台。"
  >
    <n-form class="auth-form" autocomplete="on" @submit.prevent="onSubmit">
      <n-form-item :label="'账号'">
        <n-input
          v-model:value="username"
          placeholder="请输入账号"
          name="username"
          autocomplete="username"
          autofocus
        />
      </n-form-item>
      <n-form-item :label="'密码'">
        <n-input
          v-model:value="password"
          type="password"
          show-password-on="click"
          placeholder="请输入密码"
          name="password"
          autocomplete="current-password"
        />
      </n-form-item>

      <div
        v-if="feedback"
        class="auth-feedback"
        data-testid="login-feedback"
        role="alert"
        aria-live="assertive"
      >
        {{ feedback }}
      </div>

      <n-button
        type="primary"
        block
        :loading="loading"
        :disabled="loading"
        attr-type="submit"
        data-testid="login-submit"
      >
        {{ loading ? '登录中' : '登录' }}
      </n-button>
    </n-form>
    <p class="auth-note">{{ '请勿在公共设备上保存密码。' }}</p>
  </AuthPageFrame>
</template>
