<script setup lang="ts">
import { KeyRound } from '@lucide/vue'
import { NButton, NForm, NFormItem, NInput, useMessage } from 'naive-ui'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import AuthPageFrame from '@/components/AuthPageFrame.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const message = useMessage()

const MIN_LEN = 8
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const feedback = ref<{ text: string; kind: 'error' | 'warning' | 'success' } | null>(null)

const forced = auth.mustChangePassword

function apiErrorMessage(error: unknown): string {
  const detail = (error as Partial<ApiError> | null)?.detail
  return detail || '修改密码失败，请稍后重试。'
}

async function onSubmit() {
  if (loading.value) return

  if (!oldPassword.value) {
    feedback.value = { text: '请输入原密码', kind: 'warning' }
    return
  }
  if (newPassword.value.length < MIN_LEN) {
    feedback.value = { text: `新密码至少需要 ${MIN_LEN} 个字符`, kind: 'warning' }
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    feedback.value = { text: '两次输入的新密码不一致', kind: 'warning' }
    return
  }

  feedback.value = null
  loading.value = true
  try {
    await auth.changePassword(oldPassword.value, newPassword.value)
    feedback.value = { text: '密码已更新', kind: 'success' }
    message.success('密码已更新')
    await router.push({ name: 'dashboard' })
  } catch (error) {
    feedback.value = { text: apiErrorMessage(error), kind: 'error' }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthPageFrame
    eyebrow="首次登录设置"
    title="修改密码"
    description="设置一个只有您知道的新密码，完成后即可进入教务工作台。"
    context-title="学校排课、调课与代课管理系统"
    context-description="完成密码更新后，系统会重新确认您的权限并返回工作台。"
  >
    <div v-if="forced" class="auth-callout" data-testid="cp-forced" role="note">
      <KeyRound :size="18" :stroke-width="1.9" aria-hidden="true" />
      <span>{{ '这是您首次登录，请设置新密码后继续使用系统。' }}</span>
    </div>

    <n-form class="auth-form" autocomplete="on" @submit.prevent="onSubmit">
      <n-form-item :label="'原密码'">
        <n-input
          v-model:value="oldPassword"
          type="password"
          show-password-on="click"
          placeholder="请输入原密码"
          name="current-password"
          autocomplete="current-password"
          data-testid="cp-old"
        />
      </n-form-item>
      <n-form-item :label="`新密码（至少 ${MIN_LEN} 个字符）`">
        <n-input
          v-model:value="newPassword"
          type="password"
          show-password-on="click"
          placeholder="请输入新密码"
          name="new-password"
          autocomplete="new-password"
          data-testid="cp-new"
        />
      </n-form-item>
      <n-form-item :label="'确认新密码'">
        <n-input
          v-model:value="confirmPassword"
          type="password"
          show-password-on="click"
          placeholder="请再次输入新密码"
          name="new-password-confirm"
          autocomplete="new-password"
          data-testid="cp-confirm"
        />
      </n-form-item>

      <div
        v-if="feedback"
        class="auth-feedback"
        :class="`is-${feedback.kind}`"
        data-testid="cp-feedback"
        :role="feedback.kind === 'success' ? 'status' : 'alert'"
        aria-live="assertive"
      >
        {{ feedback.text }}
      </div>

      <n-button
        type="primary"
        block
        :loading="loading"
        :disabled="loading"
        attr-type="submit"
        data-testid="cp-submit"
      >
        {{ loading ? '更新中' : '更新密码' }}
      </n-button>
    </n-form>
    <p class="auth-note">{{ `建议使用至少 ${MIN_LEN} 个字符，并避免与其他服务共用密码。` }}</p>
  </AuthPageFrame>
</template>

<style scoped>
.auth-callout {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin-bottom: 18px;
  padding: 11px 12px;
  border: 1px solid var(--app-primary-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-primary-soft);
  color: var(--app-primary-strong);
  font-size: 13px;
  line-height: 1.55;
}

.auth-callout svg { flex: 0 0 auto; margin-top: 1px; }
</style>
