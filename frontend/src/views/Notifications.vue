<script setup lang="ts">
import {
  Bell,
  BellRing,
  Check,
  CheckCheck,
  Inbox,
  RefreshCw,
} from '@lucide/vue'
import {
  NAlert,
  NButton,
  NCheckbox,
  NEmpty,
  NSelect,
  NSpin,
  NTag,
  NText,
  useMessage,
} from 'naive-ui'
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import {
  acknowledge,
  markRead,
  myNotifications,
  notificationBoard,
  remind,
} from '@/api/notifications'
import type { BoardEntry, Notification } from '@/api/notifications'
import { publishedSemesters } from '@/api/timetables'
import { listSemesters } from '@/api/semesters'
import { canOperateDaily, canViewCore } from '@/permissions'
import { useAuthStore } from '@/stores/auth'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import { useSemesterContextStore } from '@/stores/semesterContext'
import './substitution/operations-workspace.css'

type NotificationView = 'mine' | 'board'

const message = useMessage()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const semesterContext = useSemesterContextStore()

const isOperator = computed(() => canOperateDaily(auth.user?.roles))
const activeView = computed<NotificationView>(() => (
  isOperator.value && route.query.view === 'board' ? 'board' : 'mine'
))

const items = ref<Notification[]>([])
const semesterLabel = ref('')
const mineLoading = ref(true)
const mineRefreshing = ref(false)
const mineError = ref<string | null>(null)
const busyId = ref<number | null>(null)
const mineLoaded = ref(false)

const semesters = ref<{ id: number; label: string }[]>([])
const sid = ref<number | null>(null)
const entries = ref<BoardEntry[]>([])
const unackOnly = ref(true)
const boardLoading = ref(false)
const boardError = ref<string | null>(null)
const remindingId = ref<number | null>(null)
const boardLoaded = ref(false)

const unread = computed(() => items.value.filter((item) => !item.read_at).length)
const semesterOptions = computed(() => semesters.value.map((semester) => ({
  label: semester.label,
  value: semester.id,
})))
const unconfirmedCount = computed(() => (
  entries.value.filter((entry) => !entry.acknowledged_at).length
))
const canEditBoard = computed(() => (
  isOperator.value
  && (!semesterContext.authoritative || semesterContext.isCurrent(sid.value))
))
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
  const published = await publishedSemesters()
  semesterLabel.value = published[0]?.label ?? ''
  return published[0]?.id ?? null
}

async function loadNotifications(initial = false) {
  if (initial) mineLoading.value = true
  else mineRefreshing.value = true
  mineError.value = null
  try {
    const semesterId = await resolveSemester()
    if (!semesterId) {
      items.value = []
      return
    }
    const result = await myNotifications(semesterId)
    items.value = result.items
    mineLoaded.value = true
  } catch (cause) {
    mineError.value = apiErrorMessage(cause, '暂时无法读取通知，请稍后重试。')
  } finally {
    mineLoading.value = false
    mineRefreshing.value = false
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

async function reloadBoard() {
  if (sid.value === null) return
  boardLoading.value = true
  boardError.value = null
  try {
    entries.value = await notificationBoard(sid.value, { unacknowledgedOnly: unackOnly.value })
    boardLoaded.value = true
  } catch (error) {
    entries.value = []
    boardError.value = apiErrorMessage(error, '暂时无法读取通知确认状态，请重试。')
  } finally {
    boardLoading.value = false
  }
}

async function loadBoardPage() {
  boardLoading.value = true
  boardError.value = null
  try {
    await semesterContext.load()
    semesters.value = await listSemesters()
    if (!semesters.value.length) {
      sid.value = null
      entries.value = []
      boardLoaded.value = true
      return
    }
    sid.value = semesters.value.find((semester) => semester.id === semesterContext.currentSemesterId)?.id
      ?? semesterContext.currentSemesterId
      ?? semesters.value[0].id
    entries.value = await notificationBoard(sid.value, { unacknowledgedOnly: unackOnly.value })
    boardLoaded.value = true
  } catch (error) {
    entries.value = []
    boardError.value = apiErrorMessage(error, '暂时无法读取通知确认看板，请重试。')
  } finally {
    boardLoading.value = false
  }
}

async function onBoardSemesterChange(id: number) {
  sid.value = id
  await reloadBoard()
}

async function onRemind(entry: BoardEntry) {
  if (!canEditBoard.value || remindingId.value !== null) return
  remindingId.value = entry.id
  try {
    await remind(entry.id)
    message.success(`已再次提醒 ${entry.teacher_name}`)
    await reloadBoard()
  } catch (error) {
    message.error(apiErrorMessage(error, '提醒失败'))
  } finally {
    remindingId.value = null
  }
}

function ackTag(entry: BoardEntry): { type: string; label: string } {
  if (entry.acknowledged_at) return { type: 'success', label: '已确认' }
  if (entry.read_at) return { type: 'info', label: '已读未确认' }
  return { type: 'warning', label: '未读' }
}

async function setView(view: NotificationView) {
  const query = { ...route.query }
  if (view === 'board') query.view = 'board'
  else delete query.view
  await router.replace({ name: 'notifications', query })
}

function formatTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' })
}

onMounted(() => {
  if (activeView.value === 'board') {
    void loadBoardPage()
  } else {
    void loadNotifications(true)
  }
})

watch(activeView, (view) => {
  if (view === 'board' && !boardLoaded.value) void loadBoardPage()
  if (view === 'mine' && !mineLoaded.value) void loadNotifications(true)
})
watch(() => semesterContext.revision, () => {
  if (semesterContext.loaded && activeView.value === 'mine' && !mineLoading.value) void loadNotifications()
})
</script>

<template>
  <div class="notifications-page" data-testid="notifications-page">
    <header class="notifications-header">
      <div>
        <p class="notifications-eyebrow">日常运行</p>
        <h1>通知</h1>
        <p v-if="activeView === 'mine' && semesterLabel">
          {{ semesterLabel }} · {{ unread ? `${unread} 条未读` : '全部已读' }}
        </p>
        <p v-else-if="activeView === 'board'">查看全校通知确认状态并再次提醒。</p>
        <p v-else>查看课表发布、请假和调课与代课通知。</p>
      </div>
      <div class="notifications-header-actions">
        <div v-if="isOperator" class="notifications-view-tabs" role="tablist" aria-label="通知视图">
          <button
            type="button"
            role="tab"
            class="notifications-view-tab"
            :class="{ 'is-active': activeView === 'mine' }"
            :aria-selected="activeView === 'mine'"
            data-testid="notifications-tab-mine"
            @click="setView('mine')"
          >
            我的通知
          </button>
          <button
            type="button"
            role="tab"
            class="notifications-view-tab"
            :class="{ 'is-active': activeView === 'board' }"
            :aria-selected="activeView === 'board'"
            data-testid="notifications-tab-board"
            @click="setView('board')"
          >
            确认看板
          </button>
        </div>
        <n-button
          v-if="activeView === 'mine'"
          quaternary
          circle
          :loading="mineRefreshing"
          :disabled="mineLoading || mineRefreshing"
          aria-label="刷新通知"
          title="刷新通知"
          data-testid="notifications-refresh"
          @click="loadNotifications()"
        >
          <template #icon><RefreshCw :size="17" aria-hidden="true" /></template>
        </n-button>
        <n-button
          v-else
          quaternary
          circle
          :loading="boardLoading"
          :disabled="boardLoading"
          aria-label="刷新通知确认看板"
          title="刷新通知确认看板"
          data-testid="notification-board-refresh"
          @click="loadBoardPage"
        >
          <template #icon><RefreshCw :size="17" aria-hidden="true" /></template>
        </n-button>
        <RouterLink class="notifications-back" :to="homeRoute">{{ homeLabel }}</RouterLink>
      </div>
    </header>

    <template v-if="activeView === 'mine'">
      <section v-if="mineLoading" class="notifications-state" data-testid="notifications-loading" role="status" aria-live="polite">
        <n-spin size="small" />
        <strong>正在读取通知</strong>
      </section>
      <section v-else-if="mineError" class="notifications-state notifications-error" data-testid="notifications-error" role="alert">
        <Bell :size="22" aria-hidden="true" />
        <strong>{{ mineError }}</strong>
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
    </template>

    <section v-else class="operations-page report-page notification-board-view" data-testid="notification-board-page">
      <header class="operations-page-header">
        <div>
          <p class="operations-eyebrow">调课与代课</p>
          <h2>通知确认看板</h2>
        </div>
        <div class="operations-header-actions">
          <n-select
            v-if="semesters.length"
            v-accessible-select="'选择工作学期'"
            :value="sid"
            :options="semesterOptions"
            placeholder="选择学期"
            data-testid="notification-semester"
            @update:value="onBoardSemesterChange"
          />
        </div>
      </header>

      <section v-if="boardLoading" class="operations-state" data-testid="notification-board-loading" role="status" aria-live="polite">
        <n-spin size="small" />
        <strong>正在读取通知确认状态</strong>
      </section>
      <section v-else-if="boardError" class="operations-state operations-state-error" data-testid="notification-board-error" role="alert">
        <RefreshCw :size="22" aria-hidden="true" />
        <strong>{{ boardError }}</strong>
        <n-button type="primary" data-testid="notification-board-retry" @click="loadBoardPage">
          <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
          重新读取
        </n-button>
      </section>
      <section v-else-if="sid === null" class="operations-state" data-testid="notification-board-no-semester">
        <Inbox :size="24" aria-hidden="true" />
        <strong>暂无可查看的学期</strong>
      </section>
      <template v-else>
        <section class="operations-panel report-filter-panel" data-testid="notification-filters">
          <header class="operations-panel-heading">
            <div>
              <p class="operations-eyebrow">追踪范围</p>
              <h3>通知状态筛选</h3>
              <p>{{ unackOnly ? '当前只列出尚未确认的通知' : '当前列出全部通知状态' }}</p>
            </div>
            <Bell :size="20" class="operations-heading-icon" aria-hidden="true" />
          </header>
          <div class="report-filter-row">
            <label class="report-check-filter">
              <n-checkbox v-model:checked="unackOnly" data-testid="board-unackonly" @update:checked="reloadBoard" />
              <span>
                <strong>只看未确认</strong>
                <small>隐藏已经确认收到的通知</small>
              </span>
            </label>
            <div class="report-status-summary" aria-label="通知确认概览">
              <span><strong>{{ entries.length }}</strong> 条通知</span>
              <span><strong>{{ unconfirmedCount }}</strong> 未确认</span>
            </div>
          </div>
        </section>

        <n-alert v-if="!canEditBoard" type="info" data-testid="notification-readonly">
          所选学期不是当前工作学期，历史通知只允许查看，不能再次提醒。
        </n-alert>

        <section class="operations-panel report-results-panel" data-testid="notification-results">
          <header class="operations-panel-heading">
            <div>
              <p class="operations-eyebrow">确认队列</p>
              <h3>教师通知</h3>
              <p>{{ entries.length ? `当前显示 ${entries.length} 条通知` : '没有符合当前筛选条件的通知' }}</p>
            </div>
            <BellRing :size="20" class="operations-heading-icon" aria-hidden="true" />
          </header>
          <div v-if="!entries.length" class="operations-inline-empty">
            <n-empty description="没有符合条件的通知" data-testid="notification-empty" />
          </div>
          <div
            v-else
            class="operations-table-scroll report-table-scroll"
            data-testid="notification-table-scroll"
            tabindex="0"
            aria-label="教师通知确认列表，可横向滚动"
          >
            <table class="operations-data-table report-data-table notification-board-table" data-testid="board-table">
              <thead>
                <tr><th>教师</th><th>类型</th><th>内容</th><th>状态</th><th>操作</th></tr>
              </thead>
              <tbody>
                <tr v-for="entry in entries" :key="entry.id" data-testid="board-row">
                  <td data-label="教师"><strong>{{ entry.teacher_name }}</strong></td>
                  <td data-label="类型">{{ typeLabels[entry.type] ?? entry.type }}</td>
                  <td data-label="内容">{{ entry.title }}</td>
                  <td data-label="状态"><n-tag size="small" :type="ackTag(entry).type as never">{{ ackTag(entry).label }}</n-tag></td>
                  <td data-label="操作" class="report-action-cell">
                    <n-button
                      v-if="!entry.acknowledged_at"
                      size="small"
                      :loading="remindingId === entry.id"
                      :disabled="remindingId !== null || !canEditBoard"
                      data-testid="board-remind"
                      @click="onRemind(entry)"
                    >
                      <template #icon><BellRing :size="14" aria-hidden="true" /></template>
                      {{ remindingId === entry.id ? '提醒中' : '再次提醒' }}
                    </n-button>
                    <n-text v-else depth="3">无需操作</n-text>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
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
.notifications-view-tabs { display: inline-flex; align-items: center; gap: 2px; padding: 3px; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); background: var(--app-surface-muted); }
.notifications-view-tab { min-height: 30px; padding: 0 10px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-muted); cursor: pointer; font: inherit; font-size: 12px; font-weight: 650; }
.notifications-view-tab:hover { color: var(--app-text); }
.notifications-view-tab.is-active { background: var(--app-surface); color: var(--app-primary-strong); box-shadow: var(--app-shadow-sm); }
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
.notification-board-view { min-width: 0; }
@media (max-width: 820px) {
  .notifications-header { align-items: flex-start; flex-direction: column; }
  .notifications-header-actions { width: 100%; justify-content: space-between; flex-wrap: wrap; }
}
@media (max-width: 520px) {
  .notifications-header h1 { font-size: 25px; }
  .notifications-panel { padding: 16px; }
  .notification-card-heading { align-items: flex-start; }
  .notification-card-footer { align-items: flex-start; flex-direction: column; }
  .notification-card-actions { width: 100%; justify-content: flex-end; }
  .notifications-view-tabs { order: 3; width: 100%; }
  .notifications-view-tab { flex: 1; }
}
</style>
