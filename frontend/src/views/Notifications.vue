<script setup lang="ts">
import {
  Bell,
  Check,
  CheckCheck,
  RefreshCw,
} from '@lucide/vue'
import { NAlert, NButton, NEmpty, NSpin, NTag, useMessage } from 'naive-ui'
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import {
  acknowledge,
  markRead,
  myNotifications,
} from '@/api/notifications'
import type { Notification } from '@/api/notifications'
import { publishedSemesters } from '@/api/timetables'
import { canViewCore } from '@/permissions'
import { useAuthStore } from '@/stores/auth'
import { useSemesterContextStore } from '@/stores/semesterContext'

const message = useMessage()
const auth = useAuthStore()
const semesterContext = useSemesterContextStore()

const items = ref<Notification[]>([])
const semesterLabel = ref('')
const loading = ref(true)
const refreshing = ref(false)
const error = ref<string | null>(null)
const busyId = ref<number | null>(null)
const unread = computed(() => items.value.filter((item) => !item.read_at).length)
const homeRoute = computed(() => (
  canViewCore(auth.user?.roles) ? { name: 'dashboard' } : { name: 'timetable-query' }
))
const homeLabel = computed(() => canViewCore(auth.user?.roles) ? '返回仪表盘' : '返回课表查询')

const typeLabels: Record<string, string> = {
  substitution_assigned: '代课通知',
  substitution_cancelled: '代课取消',
  leave_registered: '请假登记',
  leave_cancelled: '销假',
  timetable_published: '课表发布',
}

async function resolveSemester(): Promise<number | null> {
  await semesterContext.load()
  if (semesterContext.currentSemester) {
    semesterLabel.value = semesterContext.currentSemester.label
    return semesterContext.currentSemester.id
  }
  // A teacher may only see published semesters; this fallback also keeps the
  // page usable during a rolling upgrade where the context endpoint is absent.
  const published = await publishedSemesters()
  semesterLabel.value = published[0]?.label ?? ''
  return published[0]?.id ?? null
}

async function loadNotifications(initial = false) {
  if (initial) loading.value = true
  else refreshing.value = true
  error.value = null
  try {
    const semesterId = await resolveSemester()
    if (!semesterId) {
      items.value = []
      return
    }
    const result = await myNotifications(semesterId)
    items.value = result.items
  } catch (cause) {
    error.value = apiErrorMessage(cause, '暂时无法读取通知，请稍后重试。')
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function onRead(item: Notification) {
  if (item.read_at || busyId.value !== null) return
  busyId.value = item.id
  try {
    const updated = await markRead(item.id)
    item.read_at = updated.read_at
  } catch (cause) {
    message.error(apiErrorMessage(cause, '通知标记已读失败。'))
  } finally {
    busyId.value = null
  }
}

async function onAcknowledge(item: Notification) {
  if (item.acknowledged_at || busyId.value !== null) return
  busyId.value = item.id
  try {
    const updated = await acknowledge(item.id)
    item.read_at = updated.read_at
    item.acknowledged_at = updated.acknowledged_at
    message.success('已确认收到通知')
  } catch (cause) {
    message.error(apiErrorMessage(cause, '通知确认失败，请稍后重试。'))
  } finally {
    busyId.value = null
  }
}

function formatTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' })
}

onMounted(() => { void loadNotifications(true) })
watch(() => semesterContext.revision, () => {
  if (semesterContext.loaded && !loading.value) void loadNotifications()
})
</script>

<template>
  <div class="notifications-page" data-testid="notifications-page">
    <header class="notifications-header">
      <div>
        <p class="notifications-eyebrow">日常运行</p>
        <h1>通知</h1>
        <p v-if="semesterLabel">{{ semesterLabel }} · {{ unread ? `${unread} 条未读` : '全部已读' }}</p>
        <p v-else>查看课表发布、请假和调课与代课通知。</p>
      </div>
      <div class="notifications-header-actions">
        <n-button
          quaternary
          circle
          :loading="refreshing"
          :disabled="loading || refreshing"
          aria-label="刷新通知"
          title="刷新通知"
          data-testid="notifications-refresh"
          @click="loadNotifications()"
        >
          <template #icon><RefreshCw :size="17" aria-hidden="true" /></template>
        </n-button>
        <RouterLink class="notifications-back" :to="homeRoute">{{ homeLabel }}</RouterLink>
      </div>
    </header>

    <section v-if="loading" class="notifications-state" data-testid="notifications-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>正在读取通知</strong>
    </section>
    <section v-else-if="error" class="notifications-state notifications-error" data-testid="notifications-error" role="alert">
      <Bell :size="22" aria-hidden="true" />
      <strong>{{ error }}</strong>
      <n-button type="primary" data-testid="notifications-retry" @click="loadNotifications(true)">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        重新读取
      </n-button>
    </section>
    <section v-else class="notifications-panel">
      <n-alert v-if="unread" type="info" :show-icon="false" class="notifications-hint">
        未读通知可单独标记为已读；需要留痕的消息请使用“确认收到”。
      </n-alert>
      <n-empty v-if="!items.length" description="没有通知" data-testid="notifications-empty" />
      <ul v-else class="notifications-list" aria-label="通知列表">
        <li
          v-for="item in items"
          :key="item.id"
          class="notification-card"
          :class="{ 'is-unread': !item.read_at }"
          :data-testid="`notification-${item.id}`"
        >
          <div class="notification-card-heading">
            <div class="notification-card-title">
              <span class="notification-type-icon" aria-hidden="true"><Bell :size="16" /></span>
              <strong>{{ item.title }}</strong>
            </div>
            <n-tag size="small" :type="item.acknowledged_at ? 'success' : 'warning'">
              {{ typeLabels[item.type] ?? '通知' }}
            </n-tag>
          </div>
          <p class="notification-card-body">{{ item.body }}</p>
          <div class="notification-card-footer">
            <time :datetime="item.created_at">{{ formatTime(item.created_at) }}</time>
            <div class="notification-card-actions">
              <n-button
                v-if="!item.read_at"
                size="small"
                secondary
                :loading="busyId === item.id"
                :disabled="busyId !== null"
                :data-testid="`notification-read-${item.id}`"
                @click="onRead(item)"
              >
                <template #icon><Check :size="14" aria-hidden="true" /></template>
                标记已读
              </n-button>
              <n-tag v-if="item.acknowledged_at" size="small" type="success">
                <template #icon><CheckCheck :size="13" /></template>
                已确认收到
              </n-tag>
              <n-button
                v-else
                size="small"
                type="primary"
                :loading="busyId === item.id"
                :disabled="busyId !== null"
                :data-testid="`notification-ack-${item.id}`"
                @click="onAcknowledge(item)"
              >
                <template #icon><Check :size="14" aria-hidden="true" /></template>
                确认收到
              </n-button>
            </div>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.notifications-page { display: grid; min-width: 0; gap: 20px; }
.notifications-header { display: flex; min-width: 0; align-items: flex-end; justify-content: space-between; gap: 16px; }
.notifications-eyebrow { margin: 0 0 7px; color: var(--app-primary-strong); font-size: 11px; font-weight: 700; }
.notifications-header h1 { margin: 0; font-size: 28px; line-height: 1.2; }
.notifications-header p:last-child { margin: 8px 0 0; color: var(--app-text-muted); font-size: 13px; }
.notifications-header-actions { display: flex; align-items: center; gap: 8px; }
.notifications-back { color: var(--app-primary-strong); font-size: 13px; font-weight: 650; text-decoration: none; }
.notifications-back:hover { text-decoration: underline; }
.notifications-state { display: grid; min-height: 230px; place-items: center; align-content: center; gap: 10px; padding: 28px; border: 1px dashed var(--app-border-strong); border-radius: var(--app-radius-md); background: var(--app-surface); color: var(--app-text-muted); text-align: center; }
.notifications-state strong { color: var(--app-text); }
.notifications-error { border-style: solid; }
.notifications-error > svg { color: var(--app-danger); }
.notifications-panel { display: grid; min-width: 0; gap: 14px; padding: 20px; border: 1px solid var(--app-border); border-radius: var(--app-radius-md); background: var(--app-surface); box-shadow: var(--app-shadow-sm); }
.notifications-hint { font-size: 12px; }
.notifications-list { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }
.notification-card { display: grid; min-width: 0; gap: 11px; padding: 15px; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); background: var(--app-surface-muted); }
.notification-card.is-unread { border-color: var(--app-primary-border); background: var(--app-primary-soft); }
.notification-card-heading,
.notification-card-footer { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 12px; }
.notification-card-title { display: flex; min-width: 0; align-items: center; gap: 8px; }
.notification-card-title strong { min-width: 0; overflow-wrap: anywhere; font-size: 14px; }
.notification-type-icon { display: grid; width: 28px; height: 28px; flex: 0 0 auto; place-items: center; border-radius: var(--app-radius-sm); background: var(--app-surface); color: var(--app-primary-strong); }
.notification-card-body { margin: 0; color: var(--app-text-muted); font-size: 13px; line-height: 1.6; white-space: pre-wrap; }
.notification-card-footer time { color: var(--app-text-faint); font-size: 12px; }
.notification-card-actions { display: flex; align-items: center; gap: 8px; }
@media (max-width: 560px) {
  .notifications-header { align-items: flex-start; flex-direction: column; }
  .notifications-header-actions { width: 100%; justify-content: space-between; }
  .notifications-header h1 { font-size: 25px; }
  .notifications-panel { padding: 16px; }
  .notification-card-heading { align-items: flex-start; }
  .notification-card-footer { align-items: flex-start; flex-direction: column; }
  .notification-card-actions { width: 100%; justify-content: flex-end; }
}
</style>
