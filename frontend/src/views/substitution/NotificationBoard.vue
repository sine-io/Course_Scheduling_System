<script setup lang="ts">
import { Bell, BellRing, Inbox, RefreshCw } from '@lucide/vue'
import { NButton, NCheckbox, NEmpty, NSelect, NSpin, NTag, NText, useMessage } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import { notificationBoard, remind } from '@/api/notifications'
import type { BoardEntry } from '@/api/notifications'
import { listSemesters } from '@/api/semesters'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import './operations-workspace.css'

const message = useMessage()

const semesters = ref<{ id: number; label: string }[]>([])
const sid = ref<number | null>(null)
const entries = ref<BoardEntry[]>([])
const unackOnly = ref(true)
const loading = ref(true)
const loadError = ref<string | null>(null)
const remindingId = ref<number | null>(null)

const semesterOptions = computed(() => semesters.value.map((semester) => ({
  label: semester.label,
  value: semester.id,
})))
const unconfirmedCount = computed(() =>
  entries.value.filter((entry) => !entry.acknowledged_at).length)

const TYPE_LABEL: Record<string, string> = {
  substitution_assigned: '代课通知',
  substitution_cancelled: '代课取消',
  leave_registered: '请假登记',
  leave_cancelled: '销假',
  timetable_published: '课表发布',
}

async function reload() {
  if (sid.value === null) return
  loading.value = true
  loadError.value = null
  try {
    entries.value = await notificationBoard(sid.value, {
      unacknowledgedOnly: unackOnly.value,
    })
  } catch (error) {
    entries.value = []
    loadError.value = apiErrorMessage(error, '暂时无法读取通知确认状态，请重试。')
  } finally {
    loading.value = false
  }
}

async function onSemesterChange(id: number) {
  sid.value = id
  await reload()
}

async function loadPage() {
  loading.value = true
  loadError.value = null
  try {
    semesters.value = await listSemesters()
    if (!semesters.value.length) {
      sid.value = null
      entries.value = []
      return
    }
    sid.value = semesters.value[0].id
    entries.value = await notificationBoard(sid.value, {
      unacknowledgedOnly: unackOnly.value,
    })
  } catch (error) {
    entries.value = []
    loadError.value = apiErrorMessage(error, '暂时无法读取通知确认看板，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(loadPage)

async function onRemind(entry: BoardEntry) {
  if (remindingId.value !== null) return
  remindingId.value = entry.id
  try {
    await remind(entry.id)
    message.success(`已再次提醒 ${entry.teacher_name}`)
    await reload()
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
</script>

<template>
  <main class="operations-page report-page" data-testid="notification-board-page">
    <header class="operations-page-header">
      <div>
        <p class="operations-eyebrow">{{ '调课与代课' }}</p>
        <h1>{{ '通知确认看板' }}</h1>
      </div>
      <div class="operations-header-actions">
        <n-select
          v-if="semesters.length"
          v-accessible-select="'选择工作学期'"
          :value="sid"
          :options="semesterOptions"
          :placeholder="'选择学期'"
          data-testid="notification-semester"
          @update:value="onSemesterChange"
        />
      </div>
    </header>

    <section v-if="loading" class="operations-state" data-testid="notification-board-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取通知确认状态' }}</strong>
    </section>

    <section v-else-if="loadError" class="operations-state operations-state-error" data-testid="notification-board-error" role="alert">
      <RefreshCw :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <n-button type="primary" data-testid="notification-board-retry" @click="loadPage">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>

    <section v-else-if="sid === null" class="operations-state" data-testid="notification-board-no-semester">
      <Inbox :size="24" aria-hidden="true" />
      <strong>{{ '暂无可查看的学期' }}</strong>
    </section>

    <template v-else>
      <section class="operations-panel report-filter-panel" data-testid="notification-filters">
        <header class="operations-panel-heading">
          <div>
            <p class="operations-eyebrow">{{ '追踪范围' }}</p>
            <h2>{{ '通知状态筛选' }}</h2>
            <p>{{ unackOnly ? '当前只列出尚未确认的通知' : '当前列出全部通知状态' }}</p>
          </div>
          <Bell :size="20" class="operations-heading-icon" aria-hidden="true" />
        </header>

        <div class="report-filter-row">
          <label class="report-check-filter">
            <n-checkbox
              v-model:checked="unackOnly"
              data-testid="board-unackonly"
              @update:checked="reload"
            />
            <span>
              <strong>{{ '只看未确认' }}</strong>
              <small>{{ '隐藏已经确认收到的通知' }}</small>
            </span>
          </label>
          <div class="report-status-summary" aria-label="通知确认概览">
            <span><strong>{{ entries.length }}</strong>{{ ' 条通知' }}</span>
            <span><strong>{{ unconfirmedCount }}</strong>{{ ' 未确认' }}</span>
          </div>
        </div>
      </section>

      <section class="operations-panel report-results-panel" data-testid="notification-results">
        <header class="operations-panel-heading">
          <div>
            <p class="operations-eyebrow">{{ '确认队列' }}</p>
            <h2>{{ '教师通知' }}</h2>
            <p>{{ entries.length ? `当前显示 ${entries.length} 条通知` : '没有符合当前筛选条件的通知' }}</p>
          </div>
          <BellRing :size="20" class="operations-heading-icon" aria-hidden="true" />
        </header>

        <div v-if="!entries.length" class="operations-inline-empty">
          <n-empty :description="'没有符合条件的通知'" data-testid="notification-empty" />
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
              <tr>
                <th>{{ '教师' }}</th>
                <th>{{ '类型' }}</th>
                <th>{{ '内容' }}</th>
                <th>{{ '状态' }}</th>
                <th>{{ '操作' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in entries" :key="entry.id" data-testid="board-row">
                <td data-label="教师"><strong>{{ entry.teacher_name }}</strong></td>
                <td data-label="类型">{{ TYPE_LABEL[entry.type] ?? entry.type }}</td>
                <td data-label="内容">{{ entry.title }}</td>
                <td data-label="状态">
                  <n-tag size="small" :type="ackTag(entry).type as never">{{ ackTag(entry).label }}</n-tag>
                </td>
                <td data-label="操作" class="report-action-cell">
                  <n-button
                    v-if="!entry.acknowledged_at"
                    size="small"
                    :loading="remindingId === entry.id"
                    :disabled="remindingId !== null"
                    data-testid="board-remind"
                    @click="onRemind(entry)"
                  >
                    <template #icon><BellRing :size="14" aria-hidden="true" /></template>
                    {{ remindingId === entry.id ? '提醒中' : '再次提醒' }}
                  </n-button>
                  <n-text v-else depth="3">{{ '无需操作' }}</n-text>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </main>
</template>
