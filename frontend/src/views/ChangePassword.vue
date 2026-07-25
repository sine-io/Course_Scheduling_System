<script setup lang="ts">
import { NButton, NCard, NForm, NFormItem, NInput, NText, useMessage } from 'naive-ui'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import { useProfileText } from '@/composables/useProfileText'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const message = useMessage()
const { tr } = useProfileText()

const MIN_LEN = 8
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)

const forced = auth.mustChangePassword

async function onSubmit() {
  if (newPassword.value.length < MIN_LEN) {
    message.warning(tr(`新密碼至少需 ${MIN_LEN} 個字元`, `新密码至少需要 ${MIN_LEN} 个字符`))
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    message.warning(tr('兩次輸入的新密碼不一致', '两次输入的新密码不一致'))
    return
  }
  loading.value = true
  try {
    await auth.changePassword(oldPassword.value, newPassword.value)
    message.success(tr('密碼已更新', '密码已更新'))
    router.push({ name: 'dashboard' })
  } catch (e) {
    message.error((e as ApiError).detail || tr('變更密碼失敗', '修改密码失败'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 16px">
    <n-card :title="tr('變更密碼', '修改密码')" style="max-width: 420px">
      <n-text v-if="forced" depth="3" style="display: block; margin-bottom: 12px">
        {{ tr('這是您的首次登入,請設定新密碼後繼續使用系統。', '这是您首次登录，请设置新密码后继续使用系统。') }}
      </n-text>
      <n-form @submit.prevent="onSubmit">
        <n-form-item :label="tr('原密碼', '原密码')">
          <n-input v-model:value="oldPassword" type="password" show-password-on="click" />
        </n-form-item>
        <n-form-item :label="tr(`新密碼(至少 ${MIN_LEN} 字元)`, `新密码（至少 ${MIN_LEN} 个字符）`)">
          <n-input v-model:value="newPassword" type="password" show-password-on="click" />
        </n-form-item>
        <n-form-item :label="tr('確認新密碼', '确认新密码')">
          <n-input
            v-model:value="confirmPassword"
            type="password"
            show-password-on="click"
            @keyup.enter="onSubmit"
          />
        </n-form-item>
        <n-button type="primary" block :loading="loading" attr-type="submit" @click="onSubmit">
          {{ tr('更新密碼', '更新密码') }}
        </n-button>
      </n-form>
    </n-card>
  </div>
</template>
