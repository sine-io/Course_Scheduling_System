<script setup lang="ts">
import { NButton, NCard, NForm, NFormItem, NInput, NText, useMessage } from 'naive-ui'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const message = useMessage()

const MIN_LEN = 8
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)

const forced = auth.mustChangePassword

async function onSubmit() {
  // 防止连点两次提交：第二次请求会因密码已经更新而误报原密码错误。
  if (loading.value) return
  if (newPassword.value.length < MIN_LEN) {
    message.warning(`新密码至少需要 ${MIN_LEN} 个字符`)
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    message.warning('两次输入的新密码不一致')
    return
  }
  loading.value = true
  try {
    await auth.changePassword(oldPassword.value, newPassword.value)
    message.success('密码已更新')
    router.push({ name: 'dashboard' })
  } catch (e) {
    message.error((e as ApiError).detail || '修改密码失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 16px">
    <n-card :title="'修改密码'" style="max-width: 420px">
      <n-text
        v-if="forced"
        depth="3"
        style="display: block; margin-bottom: 12px"
        data-testid="cp-forced"
      >
        {{ '这是您首次登录，请设置新密码后继续使用系统。' }}
      </n-text>
      <n-form @submit.prevent="onSubmit">
        <n-form-item :label="'原密码'">
          <n-input
            v-model:value="oldPassword"
            type="password"
            show-password-on="click"
            data-testid="cp-old"
          />
        </n-form-item>
        <n-form-item :label="`新密码（至少 ${MIN_LEN} 个字符）`">
          <n-input
            v-model:value="newPassword"
            type="password"
            show-password-on="click"
            data-testid="cp-new"
          />
        </n-form-item>
        <n-form-item :label="'确认新密码'">
          <n-input
            v-model:value="confirmPassword"
            type="password"
            show-password-on="click"
            data-testid="cp-confirm"
          />
        </n-form-item>
        <n-button
          type="primary"
          block
          :loading="loading"
          attr-type="submit"
          data-testid="cp-submit"
        >
          {{ '更新密码' }}
        </n-button>
      </n-form>
    </n-card>
  </div>
</template>
