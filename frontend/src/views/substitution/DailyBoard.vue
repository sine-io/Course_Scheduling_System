<script setup lang="ts">
import { CalendarDays, ClipboardCheck, Printer, RefreshCw } from '@lucide/vue'
import { NButton, NDatePicker, NEmpty, NSelect, NSpin, NTag, NText } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import { getDailyBoard } from '@/api/substitutionLog'
import type { DailyBoard, LogEntry } from '@/api/substitutionLog'
import { listSemesters } from '@/api/semesters'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import './operations-workspace.css'

const WEEKDAYS = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

// NDatePicker 给的是毫秒时间戳;以本机日期组出 YYYY-MM-DD,避免 toISOString 的 UTC 倒退
function toISODate(ts: number): string {
  const date = new Date(ts)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

function todayTs(): number {
  const date = new Date()
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
}

function parseISODate(iso: string): number {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day).getTime()
}

const route = useRoute()
const semesters = ref<{ id: number; label: string }[]>([])
const sid = ref<number | null>(null)
const dateTs = ref<number>(
  typeof route.query.date === 'string' ? parseISODate(route.query.date) : todayTs(),
)
const board = ref<DailyBoard | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)

const semesterOptions = computed(() => semesters.value.map((semester) => ({
  label: semester.label,
  value: semester.id,
})))
const dateLabel = computed(() =>
  board.value ? `${board.value.date}（${WEEKDAYS[board.value.weekday % 7]}）` : '')
const pendingCount = computed(() =>
  (board.value?.entries ?? []).filter((entry) => !entry.disposed).length)
const handledCount = computed(() =>
  (board.value?.entries ?? []).filter((entry) => entry.disposed).length)

async function reload() {
  if (sid.value === null) return
  loading.value = true
  loadError.value = null
  try {
    board.value = await getDailyBoard(sid.value, toISODate(dateTs.value))
  } catch (error) {
    board.value = null
    loadError.value = apiErrorMessage(error, '暂时无法读取当日变动，请重试。')
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
      board.value = null
      return
    }
    const querySemesterId = Number(route.query.semester_id)
    sid.value = semesters.value.find((semester) => semester.id === querySemesterId)?.id
      ?? semesters.value[0].id
    board.value = await getDailyBoard(sid.value, toISODate(dateTs.value))
  } catch (error) {
    board.value = null
    loadError.value = apiErrorMessage(error, '暂时无法读取今日调课与代课，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(loadPage)

function openPrint() {
  if (sid.value === null) return
  const url = `/daily-board/print?semester_id=${sid.value}&date=${toISODate(dateTs.value)}`
  window.open(url, '_blank')
}

function dispositionText(entry: LogEntry): string {
  if (!entry.disposed) return '待安排'
  if (entry.sub_type === 'swap' && entry.swap_period_name) {
    return `调课 · ${entry.handler_name}（补 ${entry.swap_date} ${entry.swap_period_name}）`
  }
  if (entry.handler_name) return `${entry.sub_type_label} · ${entry.handler_name}`
  return entry.sub_type_label ?? ''
}

function statusType(entry: LogEntry): string {
  if (entry.status === 'pending') return 'warning'
  if (entry.status === 'completed') return 'info'
  return 'success'
}
</script>

<template>
  <main class="operations-page report-page" data-testid="daily-board-page">
    <header class="operations-page-header">
      <div>
        <p class="operations-eyebrow">{{ '调课与代课' }}</p>
        <h1>{{ '今日调课与代课' }}</h1>
      </div>
      <div class="operations-header-actions">
        <n-select
          v-if="semesters.length"
          v-accessible-select="'选择工作学期'"
          :value="sid"
          :options="semesterOptions"
          :placeholder="'选择学期'"
          data-testid="board-semester"
          @update:value="onSemesterChange"
        />
      </div>
    </header>

    <section v-if="loading" class="operations-state" data-testid="daily-board-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取当日变动' }}</strong>
    </section>

    <section v-else-if="loadError" class="operations-state operations-state-error" data-testid="daily-board-error" role="alert">
      <RefreshCw :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <n-button type="primary" data-testid="daily-board-retry" @click="loadPage">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>

    <section v-else-if="sid === null" class="operations-state" data-testid="daily-board-no-semester">
      <CalendarDays :size="24" aria-hidden="true" />
      <strong>{{ '暂无可查看的学期' }}</strong>
    </section>

    <template v-else>
      <section class="operations-panel report-filter-panel" data-testid="daily-board-filters">
        <header class="operations-panel-heading">
          <div>
            <p class="operations-eyebrow">{{ '日期视图' }}</p>
            <h2 data-testid="board-datelabel">{{ dateLabel }}</h2>
            <p v-if="board">{{ `共 ${board.entries.length} 条变动` }}</p>
          </div>
          <CalendarDays :size="20" class="operations-heading-icon" aria-hidden="true" />
        </header>

        <div class="report-filter-row">
          <div class="operations-field report-date-field">
            <label>{{ '日期' }}</label>
            <n-date-picker
              v-model:value="dateTs"
              type="date"
              :input-props="{ 'aria-label': '看板日期' }"
              data-testid="board-date"
              @update:value="reload"
            />
          </div>

          <div v-if="board" class="report-status-summary" aria-label="当日处理概览">
            <span><strong>{{ pendingCount }}</strong>{{ ' 待处理' }}</span>
            <span><strong>{{ handledCount }}</strong>{{ ' 已处理' }}</span>
          </div>

          <n-button
            v-if="board?.entries.length"
            type="primary"
            class="report-primary-action"
            data-testid="board-print"
            @click="openPrint"
          >
            <template #icon><Printer :size="15" aria-hidden="true" /></template>
            {{ '打印通知单' }}
          </n-button>
        </div>
      </section>

      <section class="operations-panel report-results-panel" data-testid="daily-board-results">
        <header class="operations-panel-heading">
          <div>
            <p class="operations-eyebrow">{{ '当日变动' }}</p>
            <h2>{{ '处理状态' }}</h2>
            <p>{{ board?.entries.length ? `${pendingCount} 条待处理，${handledCount} 条已处理` : '当前日期没有变动' }}</p>
          </div>
          <ClipboardCheck :size="20" class="operations-heading-icon" aria-hidden="true" />
        </header>

        <div v-if="board && !board.entries.length" class="operations-inline-empty">
          <n-empty
            :description="'今日无调课与代课'"
            data-testid="board-empty"
          />
        </div>

        <div
          v-else-if="board?.entries.length"
          class="operations-table-scroll report-table-scroll"
          data-testid="board-table-scroll"
          tabindex="0"
          aria-label="当日调课与代课列表，可横向滚动"
        >
          <table class="operations-data-table report-data-table daily-board-table" data-testid="board-table">
            <thead>
              <tr>
                <th>{{ '节次' }}</th>
                <th>{{ '班级' }}</th>
                <th>{{ '科目' }}</th>
                <th>{{ '原授课教师' }}</th>
                <th>{{ '请假类型' }}</th>
                <th>{{ '处理方式' }}</th>
                <th>{{ '状态' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in board.entries" :key="entry.affected_period_id" data-testid="board-row">
                <td data-label="节次"><strong>{{ entry.period_name }}</strong></td>
                <td data-label="班级">
                  {{ entry.class_names }}
                  <n-text v-if="entry.room_name" depth="3"> @{{ entry.room_name }}</n-text>
                </td>
                <td data-label="科目">{{ entry.subject_name }}</td>
                <td data-label="原授课教师">{{ entry.absent_teacher_name }}</td>
                <td data-label="请假类型">{{ entry.leave_type_label }}</td>
                <td data-label="处理方式" :class="{ 'report-pending-text': !entry.disposed }">
                  {{ dispositionText(entry) }}
                </td>
                <td data-label="状态">
                  <n-tag size="small" :type="statusType(entry) as never">{{ entry.status_label }}</n-tag>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </main>
</template>
