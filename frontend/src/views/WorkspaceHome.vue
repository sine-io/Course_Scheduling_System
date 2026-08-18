<script setup lang="ts">
import {
  ArrowUpRight,
  Bell,
  BookOpen,
  CalendarClock,
  CalendarDays,
  ChartNoAxesColumnIncreasing,
  CheckCircle2,
  CircleAlert,
  ClipboardCheck,
  ClipboardList,
  Clock3,
  History,
  ListChecks,
  LoaderCircle,
  RefreshCw,
  School,
  Sparkles,
  Table2,
  Users,
  WandSparkles,
} from '@lucide/vue'
import type { Component, CSSProperties } from 'vue'
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import {
  getWorkspaceOverview,
  type WorkspaceActionItem,
  type WorkspaceOverview,
} from '@/api/workspaceOverview'
import { canEditCore } from '@/permissions'
import { useAuthStore } from '@/stores/auth'
import { useSemesterContextStore } from '@/stores/semesterContext'

interface FeatureEntry {
  key: string
  label: string
  description: string
  route: RouteLocationRaw
  icon: Component
}

interface MetricEntry {
  key: string
  label: string
  value: string
  context: string
  icon: Component
  tone: string
}

const SCHOOL_TIMEZONE = 'Asia/Shanghai'

const auth = useAuthStore()
const semesterContext = useSemesterContextStore()
const overview = ref<WorkspaceOverview | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref<string | null>(null)
const focusSection = ref<HTMLElement | null>(null)

const canConfigureSemester = computed(() => canEditCore(auth.user?.roles))
const displayName = computed(() => (
  auth.user?.display_name?.trim() || auth.user?.username || '教务同仁'
))
const hasCurrentSemester = computed(() => semesterContext.currentSemesterId !== null)
const focusCount = computed(() => overview.value?.focus_items.length ?? 0)

const schedulerFeatures: FeatureEntry[] = [
  {
    key: 'assignments',
    label: '教学任务',
    description: '维护课程、教师与每周课时',
    route: { name: 'assignments' },
    icon: ClipboardList,
  },
  {
    key: 'auto-schedule',
    label: '自动排课',
    description: '检查条件并生成排课方案',
    route: { name: 'auto-schedule' },
    icon: WandSparkles,
  },
  {
    key: 'workbench',
    label: '排课工作台',
    description: '继续查看或调整课表草稿',
    route: { name: 'workbench' },
    icon: BookOpen,
  },
  {
    key: 'versions',
    label: '版本与发布',
    description: '检查完整性与发布记录',
    route: { name: 'versions' },
    icon: History,
  },
  {
    key: 'daily-board',
    label: '今日看板',
    description: '掌握今日调课与代课变动',
    route: { name: 'daily-board' },
    icon: CalendarDays,
  },
]

const directorFeatures: FeatureEntry[] = [
  {
    key: 'timetable-query',
    label: '课表查询',
    description: '查询班级、教师和教室课表',
    route: { name: 'timetable-query' },
    icon: Table2,
  },
  {
    key: 'daily-board',
    label: '今日看板',
    description: '掌握今日调课与代课变动',
    route: { name: 'daily-board' },
    icon: CalendarDays,
  },
  {
    key: 'versions',
    label: '版本与发布',
    description: '查看课表完整性与发布记录',
    route: { name: 'versions' },
    icon: History,
  },
  {
    key: 'substitution-stats',
    label: '代课课时统计',
    description: '查看全校代课汇总与明细',
    route: { name: 'substitution-stats' },
    icon: ChartNoAxesColumnIncreasing,
  },
  {
    key: 'notifications',
    label: '通知',
    description: '查看全校通知与确认状态',
    route: { name: 'notifications', query: { view: 'board' } },
    icon: Bell,
  },
]

const featureEntries = computed(() => (
  canConfigureSemester.value ? schedulerFeatures : directorFeatures
))

const actionRoutes: Record<string, RouteLocationRaw> = {
  wizard: { name: 'wizard' },
  auto_schedule: { name: 'auto-schedule' },
  substitutions: { name: 'substitutions' },
  workbench: { name: 'workbench' },
  notifications: { name: 'notifications', query: { view: 'board' } },
  versions: { name: 'versions' },
  basedata: { name: 'basedata' },
  calendar: { name: 'calendar' },
  semesters: { name: 'semesters' },
}

const actionIcons: Record<string, Component> = {
  setup_blockers: ClipboardCheck,
  preflight_errors: CircleAlert,
  today_pending_periods: CalendarClock,
  remaining_periods: Clock3,
  unacknowledged_notifications: Bell,
  no_timetable: History,
}

function routeForAction(item: WorkspaceActionItem): RouteLocationRaw {
  return actionRoutes[item.target] ?? { name: 'dashboard' }
}

function iconForAction(item: WorkspaceActionItem): Component {
  return actionIcons[item.code] ?? Sparkles
}

function parseSchoolDate(iso: string): Date {
  return new Date(iso)
}

function schoolHour(iso: string): number {
  const parts = new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    hour12: false,
    timeZone: SCHOOL_TIMEZONE,
  }).formatToParts(parseSchoolDate(iso))
  return Number(parts.find((part) => part.type === 'hour')?.value ?? 0) % 24
}

const greeting = computed(() => {
  if (!overview.value) return '你好'
  const hour = schoolHour(overview.value.generated_at)
  if (hour < 6) return '夜深了'
  if (hour < 11) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const schoolDateLabel = computed(() => {
  if (!overview.value) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
    timeZone: SCHOOL_TIMEZONE,
  }).format(parseSchoolDate(overview.value.generated_at))
})

const generatedTimeLabel = computed(() => {
  if (!overview.value) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: SCHOOL_TIMEZONE,
  }).format(parseSchoolDate(overview.value.generated_at))
})

function shortDate(value: string): string {
  const [, month = '', day = ''] = value.split('-')
  return `${Number(month)}月${Number(day)}日`
}

const timetableContext = computed(() => {
  const timetable = overview.value?.timetable
  if (!timetable?.id) return '尚未创建课表'
  return timetable.status === 'draft' ? '最近更新草稿' : '当前发布版本'
})

const metricEntries = computed<MetricEntry[]>(() => {
  if (!overview.value) return []
  const data = overview.value
  const timetable = data.timetable
  const preflightCount = data.preflight.error_count + data.preflight.warning_count
  return [
    {
      key: 'teachers',
      label: '在校教师',
      value: String(data.metrics.active_teacher_count),
      context: data.semester_label,
      icon: Users,
      tone: 'blue',
    },
    {
      key: 'classes',
      label: '行政班级',
      value: String(data.metrics.class_count),
      context: data.semester_label,
      icon: School,
      tone: 'green',
    },
    {
      key: 'remaining',
      label: '待排课时',
      value: timetable.id ? String(timetable.remaining_periods) : '--',
      context: timetableContext.value,
      icon: Clock3,
      tone: 'orange',
    },
    {
      key: 'completion',
      label: '排课完成率',
      value: timetable.completion_rate === null ? '--' : `${timetable.completion_rate}%`,
      context: timetable.required_periods
        ? `${timetable.placed_periods} / ${timetable.required_periods} 课时`
        : '尚无教学任务',
      icon: ChartNoAxesColumnIncreasing,
      tone: 'violet',
    },
    {
      key: 'preflight',
      label: '前置检查问题',
      value: data.preflight.available ? String(preflightCount) : '--',
      context: data.preflight.available
        ? (preflightCount
            ? `${data.preflight.error_count} 个错误 · ${data.preflight.warning_count} 个提醒`
            : '检查通过')
        : data.preflight.unavailable_message,
      icon: CircleAlert,
      tone: 'red',
    },
    {
      key: 'weekly-affected',
      label: '本周调代课',
      value: String(data.metrics.weekly_affected_periods),
      context: `${shortDate(data.metrics.week_start)} 至 ${shortDate(data.metrics.week_end)}`,
      icon: CalendarClock,
      tone: 'teal',
    },
  ]
})

const progressValue = computed(() => {
  const rate = overview.value?.timetable.completion_rate
  return rate === null || rate === undefined ? 0 : Math.max(0, Math.min(rate, 100))
})

const progressStyle = computed<CSSProperties>(() => ({
  '--overview-progress': `${progressValue.value}%`,
}))

async function loadOverview(manual = false) {
  if (manual) refreshing.value = true
  else loading.value = true
  loadError.value = null

  try {
    await semesterContext.load()
    const semesterId = semesterContext.currentSemesterId
    if (semesterId === null) {
      overview.value = null
      if (semesterContext.error) loadError.value = semesterContext.error
      return
    }
    overview.value = await getWorkspaceOverview(semesterId)
  } catch (cause) {
    loadError.value = apiErrorMessage(cause, '无法读取首页总览，请稍后重试。')
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function scrollToFocus() {
  focusSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => loadOverview())
</script>

<template>
  <div class="workspace-home-page">
    <header class="workspace-home-header">
      <div>
        <p class="workspace-home-eyebrow">工作空间</p>
        <h1>首页总览</h1>
        <p>掌握当前学期运行状态，处理需要关注的教务事项</p>
      </div>
      <button
        type="button"
        class="workspace-home-refresh"
        :disabled="loading || refreshing"
        data-testid="overview-refresh"
        @click="loadOverview(true)"
      >
        <RefreshCw :size="16" :class="{ 'is-spinning': refreshing }" aria-hidden="true" />
        <span>{{ refreshing ? '正在刷新' : '刷新数据' }}</span>
      </button>
    </header>

    <section
      v-if="loading"
      class="workspace-home-state"
      data-testid="overview-loading"
      role="status"
      aria-live="polite"
    >
      <LoaderCircle class="is-spinning" :size="24" aria-hidden="true" />
      <strong>正在读取首页总览</strong>
      <span>当前学期的排课与日常运行数据加载完成后会显示在这里。</span>
    </section>

    <section
      v-else-if="loadError"
      class="workspace-home-state workspace-home-state-error"
      data-testid="overview-error"
      role="alert"
    >
      <CircleAlert :size="24" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>页面没有使用过期数据，请重新读取当前学期状态。</span>
      <button type="button" class="workspace-home-primary-button" @click="loadOverview(true)">
        <RefreshCw :size="15" aria-hidden="true" />
        重新加载
      </button>
    </section>

    <section
      v-else-if="!hasCurrentSemester"
      class="workspace-home-state workspace-home-empty-semester"
      data-testid="overview-no-semester"
    >
      <CalendarDays :size="28" aria-hidden="true" />
      <strong>尚未建立当前工作学期</strong>
      <span v-if="canConfigureSemester">完成学校与学期设置后，首页总览会显示真实运行数据。</span>
      <span v-else>当前尚无可供查看的工作学期，请联系排课管理员完成设置。</span>
      <RouterLink v-if="canConfigureSemester" class="workspace-home-primary-button" :to="{ name: 'wizard' }">
        <ClipboardCheck :size="15" aria-hidden="true" />
        前往设置向导
      </RouterLink>
    </section>

    <template v-else-if="overview">
      <section class="workspace-hero" data-testid="overview-hero">
        <div class="workspace-hero-copy">
          <span class="workspace-summary-label">
            <ClipboardCheck :size="14" aria-hidden="true" />
            今日运行摘要
          </span>
          <h2>{{ greeting }}，{{ displayName }}</h2>
          <p>
            今天是 {{ schoolDateLabel }}。
            <template v-if="focusCount">当前有 {{ focusCount }} 项需要优先关注的教务事项。</template>
            <template v-else>当前没有需要优先关注的教务事项。</template>
          </p>
          <div class="workspace-hero-actions">
            <button
              v-if="focusCount"
              type="button"
              class="workspace-home-primary-button"
              data-testid="overview-focus-button"
              @click="scrollToFocus"
            >
              <ListChecks :size="15" aria-hidden="true" />
              查看重点事项
            </button>
            <RouterLink class="workspace-home-secondary-button" :to="{ name: 'versions' }">
              <ChartNoAxesColumnIncreasing :size="15" aria-hidden="true" />
              查看排课进度
            </RouterLink>
            <span class="workspace-generated-at">
              <CheckCircle2 :size="13" aria-hidden="true" />
              数据读取于 {{ generatedTimeLabel }}
            </span>
          </div>
        </div>
        <div class="workspace-hero-visual" aria-hidden="true">
          <div class="workspace-orbit">
            <span class="workspace-orbit-line" />
            <span class="workspace-orbit-core"><CalendarClock :size="31" :stroke-width="1.7" /></span>
            <span class="workspace-orbit-chip is-course">课</span>
            <span class="workspace-orbit-chip is-arrange">排</span>
            <span class="workspace-orbit-chip is-adjust">调</span>
            <span class="workspace-orbit-chip is-table">表</span>
          </div>
        </div>
      </section>

      <section class="workspace-metric-grid" aria-label="当前学期核心指标">
        <article
          v-for="metric in metricEntries"
          :key="metric.key"
          class="workspace-metric"
          :data-testid="`overview-metric-${metric.key}`"
        >
          <span class="workspace-metric-icon" :class="`is-${metric.tone}`" aria-hidden="true">
            <component :is="metric.icon" :size="18" :stroke-width="1.8" />
          </span>
          <strong>{{ metric.value }}</strong>
          <span class="workspace-metric-label">{{ metric.label }}</span>
          <small>{{ metric.context }}</small>
        </article>
      </section>

      <section class="workspace-dashboard-grid">
        <article class="workspace-panel workspace-feature-panel">
          <header class="workspace-panel-header">
            <div>
              <h2>核心功能入口</h2>
              <p>按当前账号权限显示可用入口</p>
            </div>
          </header>
          <div class="workspace-feature-grid">
            <RouterLink
              v-for="(feature, index) in featureEntries"
              :key="feature.key"
              :to="feature.route"
              class="workspace-feature-link"
              :class="{ 'is-primary': index === 0 }"
              :data-testid="`overview-feature-${feature.key}`"
            >
              <span class="workspace-feature-icon" aria-hidden="true">
                <component :is="feature.icon" :size="18" :stroke-width="1.8" />
              </span>
              <strong>{{ feature.label }}</strong>
              <span>{{ feature.description }}</span>
              <ArrowUpRight class="workspace-feature-arrow" :size="14" aria-hidden="true" />
            </RouterLink>
          </div>
        </article>

        <article ref="focusSection" class="workspace-panel workspace-focus-panel" data-testid="overview-focus">
          <header class="workspace-panel-header">
            <div>
              <h2>重点事项</h2>
              <p>按业务影响优先级排列</p>
            </div>
            <span v-if="overview.focus_items.length" class="workspace-count-label">
              {{ overview.focus_items.length }} 项
            </span>
          </header>
          <div v-if="overview.focus_items.length" class="workspace-focus-list">
            <RouterLink
              v-for="item in overview.focus_items"
              :key="item.code"
              :to="routeForAction(item)"
              class="workspace-focus-item"
              :class="`is-${item.tone}`"
            >
              <span class="workspace-focus-icon" aria-hidden="true">
                <component :is="iconForAction(item)" :size="16" :stroke-width="1.8" />
              </span>
              <span class="workspace-focus-copy">
                <strong>{{ item.title }}</strong>
                <small>{{ item.description }}</small>
              </span>
              <span v-if="item.count !== null" class="workspace-item-count">{{ item.count }}</span>
              <ArrowUpRight v-else :size="14" aria-hidden="true" />
            </RouterLink>
          </div>
          <div v-else class="workspace-positive-state">
            <CheckCircle2 :size="24" aria-hidden="true" />
            <strong>当前没有重点事项</strong>
            <span>学期准备、排课与今日运行均无待优先处理项目。</span>
          </div>
        </article>

        <article class="workspace-panel workspace-progress-panel" data-testid="overview-progress">
          <header class="workspace-panel-header">
            <div>
              <h2>排课进度概览</h2>
              <p>{{ overview.timetable.id ? overview.timetable.name : '尚未创建课表' }}</p>
            </div>
            <RouterLink class="workspace-panel-link" :to="{ name: 'versions' }">
              {{ overview.timetable.id ? '查看详情' : '创建课表' }}
              <ArrowUpRight :size="13" aria-hidden="true" />
            </RouterLink>
          </header>
          <div class="workspace-progress-body">
            <div class="workspace-progress-ring" :style="progressStyle">
              <span>
                <strong>{{ overview.timetable.completion_rate === null ? '--' : `${overview.timetable.completion_rate}%` }}</strong>
                <small>完成率</small>
              </span>
            </div>
            <dl class="workspace-progress-legend">
              <div>
                <dt><i class="is-placed" />已排课时</dt>
                <dd>{{ overview.timetable.placed_periods }}</dd>
              </div>
              <div>
                <dt><i class="is-remaining" />待排课时</dt>
                <dd>{{ overview.timetable.id ? overview.timetable.remaining_periods : '--' }}</dd>
              </div>
              <div>
                <dt><i class="is-total" />教学任务课时</dt>
                <dd>{{ overview.timetable.required_periods }}</dd>
              </div>
              <div>
                <dt><i class="is-check" />前置检查</dt>
                <dd v-if="overview.preflight.available">
                  {{ overview.preflight.error_count + overview.preflight.warning_count }} 项
                </dd>
                <dd v-else>暂不可用</dd>
              </div>
            </dl>
          </div>
        </article>
      </section>

      <section class="workspace-panel workspace-recommendations" data-testid="overview-recommendations">
        <header class="workspace-panel-header">
          <div>
            <h2>运行建议</h2>
            <p>来自非阻断设置检查和排课提醒</p>
          </div>
          <span v-if="overview.recommendations.length" class="workspace-count-label">
            {{ overview.recommendations.length }} 条
          </span>
        </header>
        <div v-if="overview.recommendations.length" class="workspace-recommendation-grid">
          <RouterLink
            v-for="item in overview.recommendations"
            :key="item.code"
            :to="routeForAction(item)"
            class="workspace-recommendation"
          >
            <span class="workspace-recommendation-kicker">
              <Sparkles :size="14" aria-hidden="true" />
              运行提醒
            </span>
            <strong>{{ item.title }}</strong>
            <p>{{ item.description }}</p>
            <span class="workspace-recommendation-action">
              查看并处理
              <ArrowUpRight :size="13" aria-hidden="true" />
            </span>
          </RouterLink>
        </div>
        <div v-else class="workspace-positive-state workspace-recommendation-empty">
          <CheckCircle2 :size="24" aria-hidden="true" />
          <strong>当前没有运行建议</strong>
          <span>非阻断设置检查和排课提醒均已处理。</span>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.workspace-home-page {
  --overview-teal: #0f7d7a;
  --overview-teal-soft: #e7f5f4;
  --overview-violet: #6b55b8;
  --overview-violet-soft: #f1eefb;
  --overview-orange: #ad630d;
  --overview-orange-soft: #fff3e4;
  display: grid;
  min-width: 0;
  gap: 14px;
}

.workspace-home-header {
  display: flex;
  min-width: 0;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--app-space-5);
}

.workspace-home-eyebrow {
  margin: 0 0 var(--app-space-1);
  color: var(--app-primary-strong);
  font-size: 11px;
  font-weight: 700;
}

.workspace-home-header h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.2;
}

.workspace-home-header > div > p:last-child {
  margin: var(--app-space-2) 0 0;
  color: var(--app-text-muted);
  font-size: 13px;
  line-height: 1.55;
}

.workspace-home-refresh,
.workspace-home-primary-button,
.workspace-home-secondary-button {
  display: inline-flex;
  min-height: 36px;
  align-items: center;
  justify-content: center;
  gap: var(--app-space-2);
  padding: 0 var(--app-space-3);
  border-radius: var(--app-radius-sm);
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
  transition:
    border-color var(--app-motion-duration) var(--app-motion-ease),
    background-color var(--app-motion-duration) var(--app-motion-ease),
    color var(--app-motion-duration) var(--app-motion-ease);
}

.workspace-home-refresh,
.workspace-home-secondary-button {
  border: 1px solid var(--app-border);
  background: var(--app-surface);
  color: var(--app-text-muted);
}

.workspace-home-primary-button {
  border: 1px solid var(--app-primary);
  background: var(--app-primary);
  color: var(--app-on-primary);
}

.workspace-home-refresh:hover,
.workspace-home-secondary-button:hover {
  border-color: var(--app-primary-border);
  background: var(--app-primary-soft);
  color: var(--app-primary-strong);
}

.workspace-home-primary-button:hover {
  border-color: var(--app-primary-hover);
  background: var(--app-primary-hover);
}

.workspace-home-refresh:disabled {
  cursor: wait;
  opacity: .6;
}

.is-spinning { animation: overview-spin .8s linear infinite; }

@keyframes overview-spin { to { transform: rotate(360deg); } }

.workspace-home-state {
  display: grid;
  min-height: 320px;
  place-items: center;
  align-content: center;
  gap: var(--app-space-3);
  padding: var(--app-space-state);
  border: 1px dashed var(--app-border-strong);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  color: var(--app-text-muted);
  text-align: center;
}

.workspace-home-state > svg { color: var(--app-primary-strong); }
.workspace-home-state-error { border-style: solid; }
.workspace-home-state-error > svg { color: var(--app-danger); }
.workspace-home-state strong { color: var(--app-text); }
.workspace-home-state span { max-width: 540px; font-size: 13px; line-height: 1.55; }

.workspace-hero,
.workspace-metric,
.workspace-panel {
  min-width: 0;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-sm);
}

.workspace-hero {
  display: grid;
  min-height: 154px;
  grid-template-columns: minmax(0, 1.25fr) minmax(260px, .75fr);
  gap: var(--app-space-4);
  overflow: hidden;
  padding: 22px 24px;
  border-color: #cfddf4;
  background: linear-gradient(118deg, #edf4ff 0%, #f8fbff 56%, #edf8f5 100%);
}

.workspace-hero-copy { align-self: center; min-width: 0; }

.workspace-summary-label,
.workspace-generated-at,
.workspace-count-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: var(--app-radius-xs);
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}

.workspace-summary-label {
  padding: 4px 7px;
  background: var(--app-primary-soft);
  color: var(--app-primary-strong);
}

.workspace-hero h2 {
  margin: var(--app-space-2) 0 0;
  font-size: 24px;
  line-height: 1.25;
}

.workspace-hero p {
  margin: var(--app-space-2) 0 var(--app-space-3);
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.55;
}

.workspace-hero-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.workspace-generated-at {
  min-height: 30px;
  padding: 0 var(--app-space-2);
  background: var(--app-success-soft);
  color: var(--app-success);
}

.workspace-hero-visual {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: center;
}

.workspace-orbit { position: relative; width: 238px; height: 108px; }
.workspace-orbit-line {
  position: absolute;
  inset: 7px 12px;
  border: 1px dashed rgba(40, 100, 220, .3);
  border-radius: 50%;
}

.workspace-orbit-core {
  position: absolute;
  top: 50%;
  left: 50%;
  display: grid;
  width: 72px;
  height: 72px;
  place-items: center;
  border-radius: var(--app-radius-md);
  background: var(--app-primary);
  box-shadow: 0 14px 28px rgba(40, 100, 220, .24);
  color: var(--app-on-primary);
  transform: translate(-50%, -50%);
}

.workspace-orbit-chip {
  position: absolute;
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border: 1px solid #d8e2f1;
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-md);
  color: var(--app-text);
  font-size: 15px;
  font-weight: 800;
}

.workspace-orbit-chip.is-course { top: 16px; left: 0; color: var(--app-primary-strong); }
.workspace-orbit-chip.is-arrange { top: 8px; right: 0; color: var(--overview-teal); }
.workspace-orbit-chip.is-adjust { bottom: 0; left: 37px; color: var(--overview-orange); }
.workspace-orbit-chip.is-table { right: 43px; bottom: 0; color: var(--overview-violet); }

.workspace-metric-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: var(--app-space-3);
}

.workspace-metric { min-height: 112px; padding: 14px; }

.workspace-metric-icon {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: var(--app-radius-sm);
}

.workspace-metric-icon.is-blue { background: var(--app-primary-soft); color: var(--app-primary-strong); }
.workspace-metric-icon.is-green { background: var(--app-success-soft); color: var(--app-success); }
.workspace-metric-icon.is-orange { background: var(--overview-orange-soft); color: var(--overview-orange); }
.workspace-metric-icon.is-violet { background: var(--overview-violet-soft); color: var(--overview-violet); }
.workspace-metric-icon.is-red { background: var(--app-danger-soft); color: var(--app-danger); }
.workspace-metric-icon.is-teal { background: var(--overview-teal-soft); color: var(--overview-teal); }

.workspace-metric > strong {
  display: block;
  margin-top: var(--app-space-2);
  font-size: 24px;
  line-height: 1.1;
}

.workspace-metric-label {
  display: block;
  margin-top: 3px;
  color: var(--app-text-muted);
  font-size: 11px;
  font-weight: 650;
}

.workspace-metric small {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  color: var(--app-text-faint);
  font-size: 9px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, .9fr) minmax(0, .9fr);
  gap: 14px;
}

.workspace-panel { overflow: hidden; }

.workspace-panel-header {
  display: flex;
  min-height: 61px;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-3);
  padding: 14px 16px 12px;
  border-bottom: 1px solid var(--app-border);
}

.workspace-panel-header h2 { margin: 0; font-size: 14px; line-height: 1.35; }
.workspace-panel-header p {
  margin: 3px 0 0;
  color: var(--app-text-muted);
  font-size: 10px;
  line-height: 1.4;
}

.workspace-count-label {
  padding: 4px 7px;
  background: var(--app-surface-muted);
  color: var(--app-text-muted);
}

.workspace-feature-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--app-space-2);
  padding: 14px;
}

.workspace-feature-link {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: 150px;
  flex-direction: column;
  padding: 12px 10px;
  overflow: hidden;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  color: var(--app-text);
  text-decoration: none;
  transition:
    border-color var(--app-motion-duration) var(--app-motion-ease),
    box-shadow var(--app-motion-duration) var(--app-motion-ease),
    transform var(--app-motion-duration) var(--app-motion-ease);
}

.workspace-feature-link:hover {
  border-color: var(--app-primary-border);
  box-shadow: var(--app-shadow-md);
  transform: translateY(-2px);
}

.workspace-feature-link.is-primary {
  border-color: var(--app-primary-border);
  background: var(--app-primary-soft);
}

.workspace-feature-icon {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: var(--app-radius-sm);
  background: var(--app-primary-soft);
  color: var(--app-primary-strong);
}

.workspace-feature-link.is-primary .workspace-feature-icon {
  background: var(--app-primary);
  color: var(--app-on-primary);
}

.workspace-feature-link strong {
  margin-top: var(--app-space-3);
  overflow-wrap: anywhere;
  font-size: 12px;
  line-height: 1.35;
}

.workspace-feature-link > span:not(.workspace-feature-icon) {
  display: block;
  margin-top: 4px;
  color: var(--app-text-muted);
  font-size: 10px;
  line-height: 1.45;
}

.workspace-feature-arrow {
  position: absolute;
  right: 9px;
  bottom: 9px;
  color: var(--app-text-faint);
}

.workspace-focus-list { padding: 5px 14px; }

.workspace-focus-item {
  display: flex;
  min-width: 0;
  min-height: 50px;
  align-items: center;
  gap: var(--app-space-2);
  padding: 8px 0;
  border-bottom: 1px dashed var(--app-border);
  color: var(--app-text);
  text-decoration: none;
}

.workspace-focus-item:last-child { border-bottom: 0; }
.workspace-focus-item:hover strong { color: var(--app-primary-strong); }

.workspace-focus-icon {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: var(--app-radius-sm);
  background: var(--app-primary-soft);
  color: var(--app-primary-strong);
}

.workspace-focus-item.is-critical .workspace-focus-icon { background: var(--app-danger-soft); color: var(--app-danger); }
.workspace-focus-item.is-warning .workspace-focus-icon { background: var(--app-warning-soft); color: var(--app-warning); }

.workspace-focus-copy { display: block; min-width: 0; flex: 1; }
.workspace-focus-copy strong {
  display: block;
  overflow: hidden;
  font-size: 11px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workspace-focus-copy small {
  display: block;
  margin-top: 2px;
  overflow: hidden;
  color: var(--app-text-muted);
  font-size: 9px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-item-count {
  display: grid;
  min-width: 24px;
  height: 24px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-pressed);
  color: var(--app-text);
  font-size: 10px;
  font-weight: 750;
}

.workspace-panel-link {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: var(--app-primary-strong);
  font-size: 10px;
  font-weight: 700;
  text-decoration: none;
  white-space: nowrap;
}
.workspace-panel-link:hover { text-decoration: underline; }

.workspace-progress-body { padding: 12px 16px 14px; }
.workspace-progress-ring {
  position: relative;
  display: grid;
  width: 104px;
  height: 104px;
  margin: 0 auto 12px;
  place-items: center;
  border-radius: 50%;
  background: conic-gradient(var(--overview-teal) 0 var(--overview-progress), #edf1f5 var(--overview-progress) 100%);
}
.workspace-progress-ring::before {
  position: absolute;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--app-surface);
  content: '';
}
.workspace-progress-ring > span { position: relative; display: grid; z-index: 1; text-align: center; }
.workspace-progress-ring strong { font-size: 19px; line-height: 1.25; }
.workspace-progress-ring small { color: var(--app-text-muted); font-size: 9px; }

.workspace-progress-legend { display: grid; gap: 6px; margin: 0; }
.workspace-progress-legend > div { display: flex; align-items: center; justify-content: space-between; gap: var(--app-space-2); }
.workspace-progress-legend dt {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
  color: var(--app-text-muted);
  font-size: 10px;
}
.workspace-progress-legend dd { margin: 0; font-size: 10px; font-weight: 750; }
.workspace-progress-legend i { width: 7px; height: 7px; flex: 0 0 auto; border-radius: 50%; }
.workspace-progress-legend i.is-placed { background: var(--overview-teal); }
.workspace-progress-legend i.is-remaining { background: var(--app-primary); }
.workspace-progress-legend i.is-total { background: var(--app-border-strong); }
.workspace-progress-legend i.is-check { background: var(--app-warning); }

.workspace-positive-state {
  display: grid;
  min-height: 198px;
  place-items: center;
  align-content: center;
  gap: var(--app-space-2);
  padding: var(--app-space-4);
  color: var(--app-success);
  text-align: center;
}
.workspace-positive-state strong { color: var(--app-text); font-size: 12px; }
.workspace-positive-state span { max-width: 270px; color: var(--app-text-muted); font-size: 10px; line-height: 1.5; }

.workspace-recommendation-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--app-space-3);
  padding: 14px;
}

.workspace-recommendation {
  display: flex;
  min-width: 0;
  min-height: 132px;
  flex-direction: column;
  padding: 12px;
  border: 1px solid #d8e2f1;
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
  color: var(--app-text);
  text-decoration: none;
  transition:
    border-color var(--app-motion-duration) var(--app-motion-ease),
    box-shadow var(--app-motion-duration) var(--app-motion-ease);
}
.workspace-recommendation:hover { border-color: var(--app-primary-border); box-shadow: var(--app-shadow-md); }
.workspace-recommendation-kicker,
.workspace-recommendation-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--app-primary-strong);
  font-size: 10px;
  font-weight: 700;
}
.workspace-recommendation strong { margin-top: var(--app-space-2); font-size: 11px; line-height: 1.4; }
.workspace-recommendation p {
  margin: 4px 0 var(--app-space-2);
  color: var(--app-text-muted);
  font-size: 9px;
  line-height: 1.55;
}
.workspace-recommendation-action { margin-top: auto; }
.workspace-recommendation-empty { min-height: 126px; }

@media (max-width: 1100px) {
  .workspace-metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .workspace-dashboard-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .workspace-feature-panel { grid-column: 1 / -1; }
  .workspace-recommendation-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 700px) {
  .workspace-home-page { gap: var(--app-space-3); }
  .workspace-home-header { align-items: flex-start; }
  .workspace-home-header h1 { font-size: 24px; }
  .workspace-home-refresh { width: 38px; padding: 0; }
  .workspace-home-refresh span { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); }
  .workspace-hero { grid-template-columns: minmax(0, 1fr); padding: 18px; }
  .workspace-hero h2 { font-size: 21px; }
  .workspace-hero-visual { min-height: 100px; }
  .workspace-orbit { transform: scale(.88); }
  .workspace-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--app-space-2); }
  .workspace-metric { min-height: 108px; padding: 12px; }
  .workspace-dashboard-grid { grid-template-columns: minmax(0, 1fr); gap: var(--app-space-3); }
  .workspace-feature-panel { grid-column: auto; }
  .workspace-feature-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .workspace-feature-link { min-height: 132px; }
  .workspace-recommendation-grid { grid-template-columns: minmax(0, 1fr); }
  .workspace-focus-copy strong,
  .workspace-focus-copy small { white-space: normal; }
}

@media (max-width: 390px) {
  .workspace-hero-actions > :is(.workspace-home-primary-button, .workspace-home-secondary-button) { flex: 1 1 100%; }
  .workspace-generated-at { width: 100%; justify-content: center; }
}
</style>
