<script setup lang="ts">
import { AlertTriangle, RefreshCw, Save, SlidersHorizontal } from '@lucide/vue'
import { NAlert, NButton, NInputNumber, NSpin, useMessage } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { getSchedulingSettings, saveSchedulingSettings } from '@/api/assignments'
import { apiErrorMessage } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import './scheduling-workspace.css'

const auth = useAuthStore()
const message = useMessage()
const canEdit = computed(() => auth.hasRole('admin') || auth.hasRole('director'))
const loading = ref(true)
const saving = ref(false)
const loadError = ref<string | null>(null)
const maxOvertime = ref(8)

async function loadSettings() {
  loading.value = true
  loadError.value = null
  try {
    const settings = await getSchedulingSettings()
    maxOvertime.value = settings.max_overtime
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取排课规则，请重试。')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!canEdit.value || saving.value || maxOvertime.value === null) return
  saving.value = true
  try {
    const settings = await saveSchedulingSettings({ max_overtime: maxOvertime.value })
    maxOvertime.value = settings.max_overtime
    message.success('排课规则已保存')
  } catch (error) {
    message.error(apiErrorMessage(error, '排课规则保存失败，请重试。'))
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <div class="scheduling-page scheduling-settings-page" data-testid="scheduling-settings-page">
    <header class="scheduling-page-header">
      <div>
        <p class="scheduling-eyebrow">排课配置</p>
        <h1>排课规则</h1>
        <p>维护教师课时负载使用的学校级排课参数。</p>
      </div>
      <SlidersHorizontal :size="22" aria-hidden="true" />
    </header>

    <section v-if="loading" class="scheduling-state" data-testid="scheduling-settings-loading" role="status" aria-live="polite">
      <NSpin size="small" />
      <strong>正在读取排课规则</strong>
      <span>参数加载完成后可继续调整。</span>
    </section>

    <section v-else-if="loadError" class="scheduling-state scheduling-state-error" data-testid="scheduling-settings-error" role="alert">
      <AlertTriangle :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <NButton type="primary" data-testid="scheduling-settings-retry" @click="loadSettings">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        重新读取
      </NButton>
    </section>

    <section v-else class="scheduling-panel scheduling-settings-panel">
      <NAlert type="info" :show-icon="true">
        超课时上限用于检查教学任务负载；设置为 0 表示不限制。
      </NAlert>
      <div class="scheduling-settings-field">
        <label for="scheduling-max-overtime">超课时上限（课时）</label>
        <NInputNumber
          id="scheduling-max-overtime"
          v-model:value="maxOvertime"
          :min="0"
          :max="20"
          :disabled="!canEdit || saving"
          data-testid="scheduling-max-overtime"
        />
      </div>
      <div class="scheduling-settings-actions">
        <NButton type="primary" :loading="saving" :disabled="!canEdit || saving" data-testid="scheduling-settings-save" @click="save">
          <template #icon><Save :size="15" aria-hidden="true" /></template>
          保存排课规则
        </NButton>
      </div>
    </section>
  </div>
</template>

<style scoped>
.scheduling-settings-page { max-width: 1080px; }
.scheduling-settings-panel { display: grid; gap: 22px; }
.scheduling-settings-field { display: grid; gap: 8px; max-width: 360px; }
.scheduling-settings-field label { font-weight: 600; }
.scheduling-settings-actions { display: flex; justify-content: flex-end; }
</style>
