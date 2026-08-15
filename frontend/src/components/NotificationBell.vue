<script setup lang="ts">
import { Bell } from '@lucide/vue'
import { NBadge, NButton, NEmpty, NPopover, NSpace, NTag, NText, useMessage } from 'naive-ui'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { acknowledge, markRead, myNotifications } from '@/api/notifications'
import type { Notification } from '@/api/notifications'
import { publishedSemesters } from '@/api/timetables'
import { listSemesters } from '@/api/semesters'
import { canOperateDaily } from '@/permissions'
import { useAuthStore } from '@/stores/auth'
import { useSemesterContextStore } from '@/stores/semesterContext'

const auth = useAuthStore()
const semesterContext = useSemesterContextStore()
const message = useMessage()

const POLL_MS = 20000 // 站内通知轮询;铃铛不需要实时更新,20 秒足够

const sid = ref<number | null>(null)
const items = ref<Notification[]>([])
const unread = ref(0)
const compactViewport = ref(false)
let timer: ReturnType<typeof setInterval> | null = null
let viewportMedia: MediaQueryList | null = null

const bellLabel = computed(() => unread.value > 0 ? `通知，${unread.value} 条未读` : '通知')
const popoverPlacement = computed(() => compactViewport.value ? 'bottom' : 'bottom-end')

const canManage = computed(() => canOperateDaily(auth.user?.roles))
const canWrite = computed(() =>
  !semesterContext.authoritative || semesterContext.isCurrent(sid.value))

async function resolveSemester() {
  await semesterContext.load()
  // 所有角色都以服务端当前上下文为通知写入边界；没有当前学期时才兼容旧部署。
  const list = canManage.value ? await listSemesters() : await publishedSemesters()
  sid.value = semesterContext.currentSemesterId ?? list[0]?.id ?? null
}

async function refresh() {
  if (sid.value === null) return
  try {
    const data = await myNotifications(sid.value)
    items.value = data.items
    unread.value = data.unread
  } catch {
    // 静默:铃铛不该打断用户
  }
}

onMounted(async () => {
  if (typeof window.matchMedia === 'function') {
    viewportMedia = window.matchMedia('(max-width: 767px)')
    compactViewport.value = viewportMedia.matches
    viewportMedia.addEventListener('change', onViewportChange)
  } else {
    compactViewport.value = window.innerWidth < 768
  }
  await resolveSemester()
  await refresh()
  timer = setInterval(refresh, POLL_MS)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
  viewportMedia?.removeEventListener('change', onViewportChange)
})

function onViewportChange(event: MediaQueryListEvent) {
  compactViewport.value = event.matches
}

async function onOpen(show: boolean) {
  if (show) await refresh()
}

async function onAcknowledge(n: Notification) {
  if (!canWrite.value) return
  await acknowledge(n.id)
  message.success('已提交确认回复')
  await refresh()
}

async function onRead(n: Notification) {
  if (n.read_at || !canWrite.value) return
  await markRead(n.id)
  await refresh()
}

watch(() => semesterContext.revision, async () => {
  if (!semesterContext.loaded) return
  await resolveSemester()
  await refresh()
})

const typeTag = computed<Record<string, string>>(() => ({
  substitution_assigned: '代课通知',
  substitution_cancelled: '代课取消',
  leave_registered: '请假登记',
  leave_cancelled: '销假',
  timetable_published: '课表发布',
}))
</script>

<template>
  <n-popover
    trigger="click" :placement="popoverPlacement" :flip="!compactViewport"
    @update:show="onOpen"
  >
    <template #trigger>
      <n-badge :value="unread" :max="99" data-testid="notif-badge">
        <n-button
          quaternary circle class="notification-button" data-testid="notif-bell"
          :aria-label="bellLabel" :title="bellLabel"
        >
          <Bell :size="18" :stroke-width="1.9" aria-hidden="true" />
        </n-button>
      </n-badge>
    </template>

    <div class="notification-panel">
      <n-empty v-if="!items.length" :description="'没有通知'" class="notification-empty" />
      <div v-else class="notification-scroll">
        <n-space vertical size="small" class="notification-list">
          <div
            v-for="n in items" :key="n.id" data-testid="notif-item"
            class="notification-item"
            @mouseenter="onRead(n)"
          >
            <n-space align="center" size="small">
              <n-tag size="tiny" :type="n.acknowledged_at ? 'success' : 'warning'">
                {{ typeTag[n.type] ?? '通知' }}
              </n-tag>
              <n-text v-if="!n.read_at" type="error" class="notification-unread">● {{ '未读' }}</n-text>
            </n-space>
            <div class="notification-title">{{ n.title }}</div>
            <n-text depth="3" class="notification-body">{{ n.body }}</n-text>
            <div class="notification-actions">
              <n-tag v-if="n.acknowledged_at" size="small" type="success">{{ '已确认收到' }}</n-tag>
              <n-button
                v-else size="tiny" type="primary" data-testid="notif-ack"
                @click="onAcknowledge(n)"
              >
                {{ '确认收到' }}
              </n-button>
            </div>
          </div>
        </n-space>
      </div>
    </div>
  </n-popover>
</template>

<style scoped>
.notification-panel {
  width: min(360px, 80vw);
  max-width: calc(100vw - 32px);
}

.notification-scroll {
  max-height: min(360px, calc(100dvh - 88px));
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: var(--app-space-1);
}

.notification-empty { padding: var(--app-space-5) 0; }
.notification-list { padding-right: var(--app-space-2); }

.notification-item {
  border-bottom: 1px solid var(--app-border);
  padding-bottom: var(--app-space-2);
}

.notification-unread { font-size: 12px; }
.notification-title { margin: var(--app-space-1) 0; font-weight: 600; }
.notification-body { font-size: 13px; white-space: pre-wrap; }
.notification-actions { margin-top: var(--app-space-2); }

@media (max-width: 767px) {
  .notification-panel {
    width: min(320px, calc(100vw - 32px));
  }

  .notification-scroll {
    max-height: calc(100dvh - 96px);
  }
}
</style>
