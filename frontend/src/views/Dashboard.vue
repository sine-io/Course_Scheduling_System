<script setup lang="ts">
import {
  ArrowUpRight, Bell, BookOpen, CalendarDays, ClipboardClock, ClipboardList, DoorOpen,
  GraduationCap, History, RefreshCw, Table2, Users,
} from '@lucide/vue'
import { NButton, NEmpty, NSpin, NStatistic, NTag } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { STATUS_LABELS } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'
import { getDailyBoard } from '@/api/substitutionLog'
import type { DailyBoard } from '@/api/substitutionLog'
import { getSemesterSummary, getWizardState } from '@/api/wizard'
import type { SemesterSummary, WizardState } from '@/api/wizard'
import { canEditCore, canOperateDaily, canViewCore } from '@/permissions'
import { useAuthStore } from '@/stores/auth'
import { useSemesterContextStore } from '@/stores/semesterContext'

const auth = useAuthStore()
const semesterContext = useSemesterContextStore()
const semester = ref<SemesterListItem | null>(null)
const summary = ref<SemesterSummary | null>(null)
const board = ref<DailyBoard | null>(null)
const wizardState = ref<WizardState | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
const summaryError = ref<string | null>(null)
const summaryLoading = ref(false)
const boardError = ref<string | null>(null)
const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
const canManageCore = computed(() => canEditCore(auth.user?.roles))
const canViewSummary = computed(() => canViewCore(auth.user?.roles))
const dashboardIntro = computed(() => (
  canViewSummary.value
    ? '从当前学期摘要开始，快速回到正在处理的教务工作。'
    : '查看当前学期，并从快捷入口进入个人教务工作。'
))
const dashboardHeaderRoute = computed(() => (
  canManageCore.value ? { name: 'workbench' } : { name: 'timetable-query' }
))
const dashboardHeaderLabel = computed(() => (
  canManageCore.value ? '进入排课工作台' : '进入课表查询'
))
const dashboardShortcuts = computed(() => {
  if (auth.hasRole('teacher') && !canViewSummary.value) {
    return [
      { key: 'timetable-query', label: '课表查询', description: '查询已发布的班级、教师和教室课表。', route: { name: 'timetable-query' }, icon: Table2 },
      { key: 'leaves', label: '请假登记', description: '登记本人请假并查看受影响节次。', route: { name: 'leaves' }, icon: ClipboardClock },
      { key: 'notifications', label: '通知', description: '阅读通知并确认本人收到的消息。', route: { name: 'notifications' }, icon: Bell },
    ]
  }
  if (auth.hasRole('director') && !auth.hasRole('scheduler') && !auth.hasRole('admin')) {
    return [
      { key: 'timetable-query', label: '课表查询', description: '查询已发布的班级、教师和教室课表。', route: { name: 'timetable-query' }, icon: Table2 },
      { key: 'daily-board', label: '今日看板', description: '查看调课与代课安排。', route: { name: 'daily-board' }, icon: CalendarDays },
      { key: 'versions', label: '版本与发布', description: '检查课表版本、完整性和发布记录。', route: { name: 'versions' }, icon: History },
    ]
  }
  return [
    { key: 'workbench', label: '排课工作台', description: '继续处理排课草稿。', route: { name: 'workbench' }, icon: BookOpen },
    { key: 'assignments', label: '教学任务', description: '维护课程与课时。', route: { name: 'assignments' }, icon: ClipboardList },
    { key: 'daily-board', label: '今日看板', description: '查看调课与代课安排。', route: { name: 'daily-board' }, icon: CalendarDays },
  ]
})

const boardDateLabel = computed(() => (
  board.value ? `${board.value.date}（${weekdays[board.value.weekday % 7]}）` : ''
))
const pendingCount = computed(() => (
  board.value ? board.value.entries.filter((entry) => !entry.disposed).length : 0
))
const shouldResumeWizard = computed(() => (
  !!semester.value
  && canManageCore.value
  && !!wizardState.value
  && !wizardState.value.completed
))
const resumeStepLabel = computed(() => {
  const labels = ['学校与学期', '基础数据', '作息安排', '完成检查']
  const index = wizardState.value?.resume_step ?? 0
  return labels[Math.max(0, Math.min(index, labels.length - 1))]
})

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
  wizardState.value = null

  try {
    await semesterContext.load()
    semester.value = semesterContext.currentSemester
    if (!semester.value) return
    const [summaryResult, boardResult, wizardResult] = await Promise.allSettled([
      canViewSummary.value ? getSemesterSummary(semester.value.id) : Promise.resolve(null),
      canOperateDaily(auth.user?.roles)
        ? getDailyBoard(semester.value.id)
        : Promise.resolve(null),
      canManageCore.value ? getWizardState() : Promise.resolve(null),
    ])

    if (summaryResult.status === 'fulfilled' && summaryResult.value) {
      summary.value = summaryResult.value
    } else if (canViewSummary.value) {
      summaryError.value = '无法读取学期摘要，请稍后重试。'
    }

    if (boardResult.status === 'fulfilled') {
      board.value = boardResult.value
    } else {
      boardError.value = '无法读取今日调课与代课。'
    }

    if (wizardResult.status === 'fulfilled' && isWizardState(wizardResult.value)) {
      wizardState.value = wizardResult.value
    }
  } catch {
    loadError.value = '无法读取仪表盘数据，请稍后重试。'
  } finally {
    loading.value = false
  }
}

function isWizardState(value: unknown): value is WizardState {
  return !!value
    && typeof value === 'object'
    && 'completed' in value
    && typeof value.completed === 'boolean'
    && 'resume_step' in value
    && typeof value.resume_step === 'number'
}

async function retrySummary() {
  if (!canViewSummary.value || !semester.value || summaryLoading.value) return

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
        <p>{{ dashboardIntro }}</p>
      </div>
      <RouterLink v-if="semester" class="dashboard-header-link" :to="dashboardHeaderRoute">
        <component :is="canManageCore ? BookOpen : Table2" :size="16" aria-hidden="true" />
        {{ dashboardHeaderLabel }}
        <ArrowUpRight :size="15" aria-hidden="true" />
      </RouterLink>
    </header>

    <section v-if="shouldResumeWizard" class="dashboard-setup-banner" data-testid="dash-setup-resume">
      <div>
        <p class="dashboard-eyebrow">{{ '当前学期设置' }}</p>
        <strong>{{ `基础设置尚未完成 · 下一步：${resumeStepLabel}` }}</strong>
        <span>{{ '可以从上次保存的位置继续，已完成的数据不会被重复创建。' }}</span>
      </div>
      <RouterLink class="dashboard-setup-link" :to="{ name: 'wizard' }">
        <RefreshCw :size="15" aria-hidden="true" />
        {{ '继续设置' }}
        <ArrowUpRight :size="14" aria-hidden="true" />
      </RouterLink>
    </section>

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
      <section v-if="semester && canViewSummary" class="dashboard-panel dashboard-summary-panel" data-testid="dash-summary">
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

      <section v-else-if="semester" class="dashboard-panel dashboard-context-panel" data-testid="dash-context">
        <div class="dashboard-panel-heading">
          <div>
            <p class="dashboard-eyebrow">{{ '当前学期' }}</p>
            <h2>{{ semester.label }}</h2>
          </div>
          <span class="dashboard-status-badge">{{ semesterStatusLabel }}</span>
        </div>
        <p class="dashboard-context-copy">{{ '当前账号可从下方快捷入口进入个人教务工作。' }}</p>
      </section>

      <section v-else class="dashboard-panel dashboard-empty-panel">
        <n-empty :description="'尚未创建任何学期数据'">
          <template v-if="canManageCore" #extra>
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

      <section class="dashboard-shortcuts" aria-labelledby="dashboard-shortcuts-title">
        <div class="dashboard-section-heading">
          <div>
            <p class="dashboard-eyebrow">{{ '常用工作' }}</p>
            <h2 id="dashboard-shortcuts-title">{{ '快捷入口' }}</h2>
          </div>
        </div>
        <div class="dashboard-shortcut-grid">
          <RouterLink
            v-for="shortcut in dashboardShortcuts"
            :key="shortcut.key"
            :data-testid="`dash-shortcut-${shortcut.key}`"
            class="dashboard-shortcut"
            :to="shortcut.route"
          >
            <span class="dashboard-shortcut-icon" aria-hidden="true"><component :is="shortcut.icon" :size="17" /></span>
            <strong>{{ shortcut.label }}</strong><span>{{ shortcut.description }}</span><ArrowUpRight :size="15" aria-hidden="true" />
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
.dashboard-setup-banner { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 18px; padding: 14px 16px; border: 1px solid var(--app-primary-border); border-left: 4px solid var(--app-primary); border-radius: var(--app-radius-sm); background: var(--app-primary-soft); }
.dashboard-setup-banner > div { display: grid; min-width: 0; gap: 3px; }
.dashboard-setup-banner .dashboard-eyebrow { margin-bottom: 1px; }
.dashboard-setup-banner strong { overflow-wrap: anywhere; font-size: 14px; }
.dashboard-setup-banner span { color: var(--app-text-muted); font-size: 12px; line-height: 1.5; }
.dashboard-setup-link { display: inline-flex; min-height: 34px; flex: 0 0 auto; align-items: center; gap: 6px; padding: 0 11px; border: 1px solid var(--app-primary); border-radius: var(--app-radius-sm); background: var(--app-surface); color: var(--app-primary-strong); font-size: 13px; font-weight: 650; text-decoration: none; }
.dashboard-setup-link:hover { background: var(--app-primary); color: var(--app-on-primary); }
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
.dashboard-context-panel { min-height: 148px; }
.dashboard-context-copy { margin: 0; color: var(--app-text-muted); font-size: 13px; line-height: 1.7; }
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
  .dashboard-setup-banner { align-items: flex-start; flex-direction: column; }
  .dashboard-setup-link { align-self: flex-start; }
  .dashboard-panel { padding: 18px 16px; }
  .dashboard-summary-grid { gap: 8px; }
  .dashboard-metric { align-items: flex-start; flex-direction: column; gap: 7px; padding: 11px; }
  .dashboard-change-list li { align-items: flex-start; }
  .dashboard-change-list li > .n-tag { flex: 0 0 auto; }
}
</style>
