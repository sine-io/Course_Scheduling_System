<script setup lang="ts">
import {
  ArrowUpRight, BookOpen, CalendarDays, ClipboardList, DoorOpen, GraduationCap,
  RefreshCw, Users,
} from '@lucide/vue'
import { NButton, NEmpty, NSpin, NStatistic, NTag } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { STATUS_LABELS } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'
import { getDailyBoard } from '@/api/substitutionLog'
import type { DailyBoard } from '@/api/substitutionLog'
import { getSemesterSummary } from '@/api/wizard'
import type { SemesterSummary } from '@/api/wizard'
import { useSemesterContextStore } from '@/stores/semesterContext'

const semesterContext = useSemesterContextStore()
const semester = ref<SemesterListItem | null>(null)
const summary = ref<SemesterSummary | null>(null)
const board = ref<DailyBoard | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
const summaryError = ref<string | null>(null)
const summaryLoading = ref(false)
const boardError = ref<string | null>(null)
const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

const boardDateLabel = computed(() => (
  board.value ? `${board.value.date}（${weekdays[board.value.weekday % 7]}）` : ''
))
const pendingCount = computed(() => (
  board.value ? board.value.entries.filter((entry) => !entry.disposed).length : 0
))

const semesterStatusLabel = computed(() => (
  semester.value ? STATUS_LABELS[semester.value.status] : ''
))

function entryOutcome(entry: DailyBoard['entries'][number]): string {
  if (!entry.disposed) return '待安排'
  return entry.handler_name
    ? `${entry.sub_type_label || entry.status_label}：${entry.handler_name}`
    : (entry.sub_type_label || entry.status_label)
}

async function loadDashboard() {
  loading.value = true
  loadError.value = null
  summaryError.value = null
  summaryLoading.value = false
  boardError.value = null
  semester.value = null
  summary.value = null
  board.value = null

  try {
    await semesterContext.load()
    semester.value = semesterContext.currentSemester
    if (!semester.value) return
    const [summaryResult, boardResult] = await Promise.allSettled([
      getSemesterSummary(semester.value.id),
      getDailyBoard(semester.value.id),
    ])

    if (summaryResult.status === 'fulfilled') {
      summary.value = summaryResult.value
    } else {
      summaryError.value = '无法读取学期摘要，请稍后重试。'
    }

    if (boardResult.status === 'fulfilled') {
      board.value = boardResult.value
    } else {
      boardError.value = '无法读取今日调课与代课。'
    }
  } catch {
    loadError.value = '无法读取仪表盘数据，请稍后重试。'
  } finally {
    loading.value = false
  }
}

async function retrySummary() {
  if (!semester.value || summaryLoading.value) return

  summaryLoading.value = true
  summaryError.value = null
  try {
    summary.value = await getSemesterSummary(semester.value.id)
  } catch {
    summary.value = null
    summaryError.value = '无法读取学期摘要，请稍后重试。'
  } finally {
    summaryLoading.value = false
  }
}

onMounted(loadDashboard)
</script>

<template>
  <div class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <p class="dashboard-eyebrow">{{ '教学运行概览' }}</p>
        <h1>{{ '仪表盘' }}</h1>
        <p>{{ '从当前学期摘要开始，快速回到正在处理的教务工作。' }}</p>
      </div>
      <RouterLink v-if="semester" class="dashboard-header-link" :to="{ name: 'workbench' }">
        <BookOpen :size="16" aria-hidden="true" />
        {{ '进入排课工作台' }}
        <ArrowUpRight :size="15" aria-hidden="true" />
      </RouterLink>
    </header>

    <section v-if="loading" class="dashboard-state" data-testid="dash-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取仪表盘数据' }}</strong>
      <span>{{ '学期摘要和今日变动加载完成后会显示在这里。' }}</span>
    </section>

    <section v-else-if="loadError" class="dashboard-state dashboard-error" data-testid="dash-error" role="alert">
      <RefreshCw :size="21" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '仪表盘数据未更新，已保留当前页面。' }}</span>
      <n-button data-testid="dash-retry" type="primary" @click="loadDashboard">
        {{ '重新加载' }}
      </n-button>
    </section>

    <template v-else>
      <section v-if="semester" class="dashboard-panel dashboard-summary-panel" data-testid="dash-summary">
        <div class="dashboard-panel-heading">
          <div>
            <p class="dashboard-eyebrow">{{ '当前学期' }}</p>
            <h2>{{ `${semester.label} · ${'数据摘要'}` }}</h2>
          </div>
          <span class="dashboard-status-badge">{{ semesterStatusLabel }}</span>
        </div>
        <div v-if="summary" class="dashboard-summary-grid">
          <div class="dashboard-metric">
            <span class="dashboard-metric-icon" aria-hidden="true"><BookOpen :size="18" /></span>
            <n-statistic :label="'科目'" :value="summary.subjects" />
          </div>
          <div class="dashboard-metric">
            <span class="dashboard-metric-icon" aria-hidden="true"><Users :size="18" /></span>
            <n-statistic :label="'教师'" :value="summary.teachers" />
          </div>
          <div class="dashboard-metric">
            <span class="dashboard-metric-icon" aria-hidden="true"><GraduationCap :size="18" /></span>
            <n-statistic :label="'班级'" :value="summary.classes" />
          </div>
          <div class="dashboard-metric">
            <span class="dashboard-metric-icon" aria-hidden="true"><DoorOpen :size="18" /></span>
            <n-statistic :label="'教室/场地'" :value="summary.rooms" />
          </div>
        </div>
        <div
          v-else-if="summaryError"
          class="dashboard-state dashboard-error dashboard-inline-state"
          data-testid="dash-summary-error"
          role="status"
        >
          <RefreshCw :size="21" aria-hidden="true" />
          <strong>{{ summaryError }}</strong>
          <span>{{ '今日运行和快捷入口仍可继续使用。' }}</span>
          <n-button
            data-testid="dash-summary-retry"
            type="primary"
            :loading="summaryLoading"
            :disabled="summaryLoading"
            @click="retrySummary"
          >
            {{ '重新读取摘要' }}
          </n-button>
        </div>
        <div v-else class="dashboard-state dashboard-inline-state" role="status" aria-live="polite">
          <n-spin size="small" />
          <strong>{{ '正在读取学期摘要' }}</strong>
        </div>
      </section>

      <section v-else class="dashboard-panel dashboard-empty-panel">
        <n-empty :description="'尚未创建任何学期数据'">
          <template #extra>
            <RouterLink class="dashboard-primary-link" :to="{ name: 'wizard' }">
              {{ '前往设置向导' }}
            </RouterLink>
          </template>
        </n-empty>
      </section>

      <section
        v-if="semester && board"
        class="dashboard-panel dashboard-today-panel"
        data-testid="dash-today"
      >
        <div class="dashboard-panel-heading">
          <div>
            <p class="dashboard-eyebrow">{{ '今日运行' }}</p>
            <h2>{{ `${'今日调课与代课'} · ${boardDateLabel}` }}</h2>
          </div>
          <CalendarDays :size="20" class="dashboard-heading-icon" aria-hidden="true" />
        </div>

        <div v-if="board.entries.length" class="dashboard-today-content">
          <div class="dashboard-today-summary">
            <div class="dashboard-today-count">
              <strong>{{ board.entries.length }}</strong>
              <span>{{ '今日变动' }}</span>
            </div>
            <n-tag v-if="pendingCount" type="warning" data-testid="dash-pending">
              {{ '尚有' }} {{ pendingCount }} {{ '节待安排' }}
            </n-tag>
            <n-tag v-else type="success">{{ '今日均已安排' }}</n-tag>
          </div>
          <ul class="dashboard-change-list" aria-label="今日调课与代课变动">
            <li
              v-for="entry in board.entries"
              :key="entry.affected_period_id"
              :data-testid="`dash-entry-${entry.affected_period_id}`"
            >
              <div>
                <strong>{{ entry.period_name }} · {{ entry.class_names }} · {{ entry.subject_name }}</strong>
                <span>{{ entry.absent_teacher_name }}<template v-if="entry.handler_name"> → {{ entry.handler_name }}</template></span>
              </div>
              <n-tag :type="entry.disposed ? 'success' : 'warning'" size="small">
                {{ entryOutcome(entry) }}
              </n-tag>
            </li>
          </ul>
          <RouterLink class="dashboard-action-link" :to="{ name: 'daily-board' }">
            <CalendarDays :size="15" aria-hidden="true" />
            {{ '查看今日看板' }}
            <ArrowUpRight :size="14" aria-hidden="true" />
          </RouterLink>
        </div>
        <div v-else class="dashboard-no-changes">
          <n-empty :description="'今日无调课与代课'" data-testid="dash-noboard" />
        </div>
      </section>

      <section
        v-else-if="semester && boardError"
        class="dashboard-state dashboard-error dashboard-board-error"
        data-testid="dash-board-error"
        role="status"
      >
        <RefreshCw :size="21" aria-hidden="true" />
        <strong>{{ boardError }}</strong>
        <span>{{ '学期摘要仍可查看。' }}</span>
        <n-button type="primary" @click="loadDashboard">{{ '重新加载' }}</n-button>
      </section>

      <section v-if="semester" class="dashboard-shortcuts" aria-labelledby="dashboard-shortcuts-title">
        <div class="dashboard-section-heading">
          <div>
            <p class="dashboard-eyebrow">{{ '常用工作' }}</p>
            <h2 id="dashboard-shortcuts-title">{{ '快捷入口' }}</h2>
          </div>
        </div>
        <div class="dashboard-shortcut-grid">
          <RouterLink data-testid="dash-shortcut-workbench" class="dashboard-shortcut" :to="{ name: 'workbench' }">
            <span class="dashboard-shortcut-icon" aria-hidden="true"><BookOpen :size="17" /></span>
            <strong>{{ '排课工作台' }}</strong><span>{{ '继续处理排课草稿' }}</span><ArrowUpRight :size="15" aria-hidden="true" />
          </RouterLink>
          <RouterLink data-testid="dash-shortcut-assignments" class="dashboard-shortcut" :to="{ name: 'assignments' }">
            <span class="dashboard-shortcut-icon" aria-hidden="true"><ClipboardList :size="17" /></span>
            <strong>{{ '教学任务' }}</strong><span>{{ '维护课程与课时' }}</span><ArrowUpRight :size="15" aria-hidden="true" />
          </RouterLink>
          <RouterLink data-testid="dash-shortcut-daily-board" class="dashboard-shortcut" :to="{ name: 'daily-board' }">
            <span class="dashboard-shortcut-icon" aria-hidden="true"><CalendarDays :size="17" /></span>
            <strong>{{ '今日看板' }}</strong><span>{{ '查看调课与代课安排' }}</span><ArrowUpRight :size="15" aria-hidden="true" />
          </RouterLink>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.dashboard-page { display: grid; min-width: 0; gap: 20px; }
.dashboard-header { display: flex; min-width: 0; align-items: flex-end; justify-content: space-between; gap: 18px; }
.dashboard-header h1 { margin: 0; font-size: 28px; line-height: 1.2; }
.dashboard-header > div > p:last-child { margin: 8px 0 0; color: var(--app-text-muted); font-size: 13px; line-height: 1.6; }
.dashboard-eyebrow { margin: 0 0 7px; color: var(--app-primary-strong); font-size: 11px; font-weight: 700; }
.dashboard-header-link,
.dashboard-action-link,
.dashboard-primary-link { display: inline-flex; min-height: 36px; align-items: center; justify-content: center; gap: 7px; border-radius: var(--app-radius-sm); font-size: 13px; font-weight: 650; text-decoration: none; }
.dashboard-header-link { padding: 0 11px; border: 1px solid var(--app-border); background: var(--app-surface); color: var(--app-text); }
.dashboard-header-link:hover { border-color: var(--app-primary-border); background: var(--app-primary-soft); }
.dashboard-panel,
.dashboard-shortcuts { min-width: 0; border: 1px solid var(--app-border); border-radius: var(--app-radius-md); background: var(--app-surface); box-shadow: var(--app-shadow-sm); }
.dashboard-panel { padding: 22px; }
.dashboard-panel-heading { display: flex; min-width: 0; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 20px; }
.dashboard-panel-heading h2 { margin: 0; overflow-wrap: anywhere; font-size: 17px; line-height: 1.4; }
.dashboard-heading-icon { flex: 0 0 auto; color: var(--app-primary-strong); }
.dashboard-status-badge { flex: 0 0 auto; padding: 4px 8px; border: 1px solid var(--app-primary-border); border-radius: 999px; background: var(--app-primary-soft); color: var(--app-primary-strong); font-size: 11px; font-weight: 700; }
.dashboard-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.dashboard-metric { display: flex; min-width: 0; align-items: center; gap: 10px; padding: 13px; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); background: var(--app-surface-muted); }
.dashboard-metric-icon { display: grid; width: 32px; height: 32px; flex: 0 0 auto; place-items: center; border-radius: var(--app-radius-sm); background: var(--app-primary-soft); color: var(--app-primary-strong); }
.dashboard-metric :deep(.n-statistic) { min-width: 0; }
.dashboard-metric :deep(.n-statistic__label) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dashboard-metric :deep(.n-statistic-value__content) { font-size: 22px; font-weight: 700; }
.dashboard-empty-panel { min-height: 250px; display: grid; place-items: center; }
.dashboard-primary-link { padding: 0 14px; border: 1px solid var(--app-primary); background: var(--app-primary); color: var(--app-on-primary); }
.dashboard-today-content { display: grid; gap: 16px; }
.dashboard-today-summary { display: flex; align-items: center; gap: 14px; }
.dashboard-today-count { display: grid; gap: 1px; }
.dashboard-today-count strong { font-size: 28px; line-height: 1; }
.dashboard-today-count span { color: var(--app-text-muted); font-size: 12px; }
.dashboard-change-list { display: grid; gap: 1px; margin: 0; padding: 0; list-style: none; }
.dashboard-change-list li { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 0; border-top: 1px solid var(--app-border); }
.dashboard-change-list li > div { display: grid; min-width: 0; gap: 3px; }
.dashboard-change-list strong,
.dashboard-change-list span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dashboard-change-list strong { font-size: 13px; }
.dashboard-change-list span { color: var(--app-text-muted); font-size: 12px; }
.dashboard-action-link { justify-self: start; padding: 0 12px; border: 1px solid var(--app-primary); background: var(--app-primary); color: var(--app-on-primary); }
.dashboard-no-changes { min-height: 150px; display: grid; place-items: center; }
.dashboard-shortcuts { display: grid; gap: 14px; padding: 20px; }
.dashboard-section-heading h2 { margin: 0; font-size: 16px; }
.dashboard-shortcut-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.dashboard-shortcut { display: grid; min-width: 0; grid-template-columns: 28px minmax(0, 1fr) auto; grid-template-rows: auto auto; column-gap: 9px; align-items: center; padding: 13px; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); color: var(--app-text); text-decoration: none; }
.dashboard-shortcut:hover { border-color: var(--app-primary-border); background: var(--app-primary-soft); }
.dashboard-shortcut-icon { display: grid; width: 28px; height: 28px; grid-row: 1 / span 2; place-items: center; border-radius: var(--app-radius-sm); background: var(--app-primary-soft); color: var(--app-primary-strong); }
.dashboard-shortcut strong { min-width: 0; overflow-wrap: anywhere; font-size: 13px; }
.dashboard-shortcut span:not(.dashboard-shortcut-icon) { min-width: 0; color: var(--app-text-muted); font-size: 12px; line-height: 1.45; }
.dashboard-shortcut > svg { grid-column: 3; grid-row: 1 / span 2; color: var(--app-text-faint); }
.dashboard-state { display: grid; min-height: 230px; place-items: center; align-content: center; gap: 10px; padding: 28px; border: 1px dashed var(--app-border-strong); border-radius: var(--app-radius-md); background: var(--app-surface); color: var(--app-text-muted); text-align: center; }
.dashboard-state strong { color: var(--app-text); }
.dashboard-state span { font-size: 13px; }
.dashboard-error { border-style: solid; }
.dashboard-error > svg { color: var(--app-danger); }
.dashboard-inline-state { min-height: 150px; padding: 20px; box-shadow: none; }

@media (max-width: 820px) {
  .dashboard-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dashboard-shortcut-grid { grid-template-columns: 1fr; }
}

@media (max-width: 520px) {
  .dashboard-header { align-items: flex-start; flex-direction: column; }
  .dashboard-header h1 { font-size: 25px; }
  .dashboard-panel { padding: 18px 16px; }
  .dashboard-summary-grid { gap: 8px; }
  .dashboard-metric { align-items: flex-start; flex-direction: column; gap: 7px; padding: 11px; }
  .dashboard-change-list li { align-items: flex-start; }
  .dashboard-change-list li > .n-tag { flex: 0 0 auto; }
}
</style>
