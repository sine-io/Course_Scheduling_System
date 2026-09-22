<script setup lang="ts">
// PROTOTYPE ONLY: Question: which structure best supports a five-step
// scheduling workbench while keeping semester management in the current-semester context?
// The route is intentionally read-only and uses in-memory sample data.
// The user described five labels (班级, 课时, 科目, 教师, 自动排课); the mention of ⑥
// is treated as a typo until a sixth business step is explicitly defined.
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CalendarDays,
  CalendarRange,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  ClipboardList,
  Clock3,
  Copy,
  Database,
  FileUp,
  GraduationCap,
  ListChecks,
  Menu,
  MoreHorizontal,
  Play,
  RefreshCw,
  Settings2,
  Sparkles,
  Table2,
  Upload,
  UserRound,
  Users,
  X,
} from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'

type VariantKey = 'A' | 'B' | 'C'
type StepKey = 'classes' | 'periods' | 'subjects' | 'teachers' | 'auto'
type AutoPanelKey = 'calendar' | 'resources' | null

interface StepMeta {
  key: StepKey
  number: string
  label: string
  short: string
  description: string
  summary: string
  state: 'done' | 'active' | 'blocked'
  icon: typeof Users
}

interface ActivityItem {
  time: string
  text: string
  tone: 'blue' | 'green' | 'orange'
}

const route = useRoute()
const router = useRouter()
const showPrototypeSwitcher = import.meta.env.DEV

const variants = [
  { key: 'A', label: '步骤轨道', subtitle: '当前学期摘要下直接推进五个步骤' },
  { key: 'B', label: '左侧流程导航', subtitle: '固定流程入口，右侧承载长详情页' },
  { key: 'C', label: '总览 / 详情双栏', subtitle: '同时看准备度与当前步骤的业务内容' },
] as const

const selectedStep = ref<StepKey | null>(null)
const semesterPanelOpen = ref(false)
const autoPanel = ref<AutoPanelKey>(null)
const mobileNavOpen = ref(false)
const notice = ref('点击任意流程按钮，在下方查看对应详情页。')
const noticeTone = ref<'neutral' | 'success' | 'warning'>('neutral')
const running = ref(false)
const calendarConfirmed = ref(false)
const imported = ref(false)
const runTimer = ref<number | null>(null)

const currentVariant = computed<VariantKey>(() => {
  const value = String(route.query.variant ?? 'A').toUpperCase()
  return value === 'B' || value === 'C' ? value : 'A'
})

const currentVariantMeta = computed(() => variants.find((item) => item.key === currentVariant.value) ?? variants[0])

const activity = ref<ActivityItem[]>([
  { time: '09:24', text: '当前学期摘要已加载', tone: 'blue' },
  { time: '09:18', text: '教师安排模板已完成预览', tone: 'green' },
  { time: '09:10', text: '校历准备还有 2 项提醒', tone: 'orange' },
])

const steps = computed<StepMeta[]>(() => [
  {
    key: 'classes', number: '01', label: '班级', short: '设置班级',
    description: '维护本学期参与排课的班级与作息分组。',
    summary: '12 个班级 · 1 项待确认', state: 'done', icon: Users,
  },
  {
    key: 'periods', number: '02', label: '课时', short: '设置课时',
    description: '配置作息时间表、常规课节次与可排容量。',
    summary: '2 套作息 · 课时容量正常', state: 'done', icon: Clock3,
  },
  {
    key: 'subjects', number: '03', label: '科目', short: '科目节数',
    description: '维护科目档案，并录入各班每周科目节数。',
    summary: '18 个科目 · 46 项课程', state: 'done', icon: BookOpen,
  },
  {
    key: 'teachers', number: '04', label: '教师', short: '教师任课',
    description: '维护教师档案，为每项课程指定授课教师。',
    summary: '31 位教师 · 44/46 项已任课', state: 'active', icon: UserRound,
  },
  {
    key: 'auto', number: '05', label: '自动排课', short: '开始排课',
    description: '完成前置检查，确认准备后生成课表草稿。',
    summary: '2 项提醒 · 尚未生成草稿', state: 'blocked', icon: Sparkles,
  },
])

const activeStep = computed(() => steps.value.find((step) => step.key === selectedStep.value) ?? null)
const nextStep = computed(() => steps.value.find((step) => step.state !== 'done') ?? steps.value[steps.value.length - 1])

function firstQueryValue(value: unknown): string | undefined {
  const candidate = Array.isArray(value) ? value[0] : value
  return typeof candidate === 'string' && candidate.length > 0 ? candidate : undefined
}

function stepFromQuery(value: unknown): StepKey | null {
  const candidate = firstQueryValue(value)
  return steps.value.some((step) => step.key === candidate) ? candidate as StepKey : null
}

function syncStepFromRoute() {
  selectedStep.value = stepFromQuery(route.query.step)
}

function selectStep(step: StepKey) {
  selectedStep.value = step
  autoPanel.value = null
  noticeTone.value = 'neutral'
  notice.value = `已打开「${steps.value.find((item) => item.key === step)?.label ?? ''}」详情。`
  void router.replace({
    name: 'scheduling-workbench-prototype',
    query: { ...route.query, step },
  })
}

function returnToOverview() {
  selectedStep.value = null
  autoPanel.value = null
  noticeTone.value = 'neutral'
  notice.value = '已返回排课工作台总览。'
  const query = { ...route.query }
  delete query.step
  void router.replace({ name: 'scheduling-workbench-prototype', query })
}

function chooseVariant(key: VariantKey) {
  void router.replace({
    name: 'scheduling-workbench-prototype',
    query: { ...route.query, variant: key },
  })
  noticeTone.value = 'neutral'
  notice.value = `已切换到方案 ${key} · ${variants.find((item) => item.key === key)?.label ?? ''}。`
}

function cycleVariant(delta: number) {
  const index = variants.findIndex((variant) => variant.key === currentVariant.value)
  const next = (index + delta + variants.length) % variants.length
  chooseVariant(variants[next].key)
}

function onPrototypeKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target?.matches('input, textarea, select, [contenteditable="true"]')) return
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    cycleVariant(-1)
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    cycleVariant(1)
  }
}

function addActivity(text: string, tone: ActivityItem['tone'] = 'blue') {
  const now = new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date())
  activity.value.unshift({ time: now, text, tone })
  activity.value.splice(4)
  notice.value = text
  noticeTone.value = tone === 'green' ? 'success' : tone === 'orange' ? 'warning' : 'neutral'
}

function openSemesterPanel() {
  semesterPanelOpen.value = true
  mobileNavOpen.value = false
  addActivity('打开当前学期管理面板', 'blue')
}

function saveSemesterPanel() {
  semesterPanelOpen.value = false
  addActivity('学期日期修改已保存，准备度会重新检查', 'green')
}

function openAutoPanel(panel: AutoPanelKey) {
  autoPanel.value = panel
  if (panel !== null) {
    addActivity(panel === 'calendar' ? '打开校历与排课准备' : '打开资源与导入', 'blue')
  }
}

function confirmCalendar() {
  calendarConfirmed.value = true
  addActivity('校历与排课准备已确认', 'green')
}

function revokeCalendar() {
  calendarConfirmed.value = false
  addActivity('校历与排课准备确认已撤回，自动排课需要重新确认', 'orange')
}

function previewImport() {
  imported.value = true
  addActivity('资源与导入预览已完成，新增 3 项、无冲突', 'green')
}

function runAutoSchedule() {
  if (running.value) return
  if (!calendarConfirmed.value) {
    openAutoPanel('calendar')
    addActivity('自动排课暂缓：请先确认校历与排课准备', 'orange')
    return
  }
  running.value = true
  addActivity('正在生成当前学期课表草稿', 'blue')
  if (runTimer.value !== null) window.clearTimeout(runTimer.value)
  runTimer.value = window.setTimeout(() => {
    running.value = false
    addActivity('自动排课完成：生成 1 份待检查课表草稿', 'green')
  }, 900)
}

function onTopAction(label: string) {
  addActivity(`${label}为原型演示动作，未写入后端`, 'blue')
}

watch(() => route.query.step, syncStepFromRoute, { immediate: true })
onMounted(() => window.addEventListener('keydown', onPrototypeKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onPrototypeKeydown)
  if (runTimer.value !== null) window.clearTimeout(runTimer.value)
})
</script>

<template>
  <div class="swp-app" data-testid="scheduling-workbench-prototype">
    <aside class="swp-sidebar" :class="{ 'is-open': mobileNavOpen }" aria-label="原型导航">
      <div class="swp-brand">
        <span class="swp-brand-mark" aria-hidden="true"><CalendarDays :size="19" /></span>
        <span><strong>教务排课</strong><small>排课 · 调课 · 代课</small></span>
        <button class="swp-icon-button swp-mobile-close" type="button" aria-label="关闭导航" title="关闭导航" @click="mobileNavOpen = false"><X :size="17" /></button>
      </div>
      <nav class="swp-nav">
        <p class="swp-nav-label">工作空间</p>
        <button class="swp-nav-link" type="button" @click="returnToOverview"><Table2 :size="16" />仪表盘</button>
        <button class="swp-nav-link is-active" type="button" @click="returnToOverview"><ListChecks :size="16" />排课工作台</button>
        <p class="swp-nav-label swp-nav-label-spaced">排课主流程</p>
        <button class="swp-nav-link" type="button" @click="onTopAction('课程表调整')"><BookOpen :size="16" />课程表调整</button>
        <button class="swp-nav-link" type="button" @click="onTopAction('版本与发布')"><ClipboardList :size="16" />版本与发布</button>
      </nav>
      <div class="swp-school"><span class="swp-school-mark"><GraduationCap :size="15" /></span><span><strong>示范学校</strong><small>教务主任视角</small></span></div>
    </aside>

    <main class="swp-main">
      <header class="swp-topbar">
        <button class="swp-icon-button swp-menu-button" type="button" aria-label="打开导航" title="打开导航" @click="mobileNavOpen = true"><Menu :size="18" /></button>
        <div class="swp-breadcrumb"><span>工作空间</span><ArrowRight :size="13" /><strong>排课工作台</strong><span class="swp-dev-badge">PROTOTYPE</span></div>
        <div class="swp-top-actions">
          <span class="swp-top-semester"><CalendarRange :size="14" />2025-2026 学年第一学期</span>
          <button class="swp-icon-button" type="button" aria-label="刷新示范数据" title="刷新示范数据" @click="onTopAction('刷新示范数据')"><RefreshCw :size="16" /></button>
          <span class="swp-avatar" aria-label="教务主任">教</span>
        </div>
      </header>

      <div v-if="mobileNavOpen" class="swp-scrim" aria-hidden="true" @click="mobileNavOpen = false" />

      <div class="swp-content">
        <header class="swp-page-head">
          <div>
            <p class="swp-eyebrow">排课工作台 · 方案 {{ currentVariant }}</p>
            <h1>从班级到自动排课</h1>
            <p>围绕当前学期，在同一入口完成五个排课步骤。</p>
          </div>
          <div class="swp-page-actions">
            <span class="swp-role-chip"><UserRound :size="14" />教务主任</span>
            <button class="swp-button swp-button-secondary" type="button" @click="onTopAction('查看帮助')"><CircleAlert :size="15" />查看帮助</button>
          </div>
        </header>

        <section class="swp-semester-context" data-testid="prototype-current-semester">
          <div class="swp-semester-main">
            <span class="swp-semester-icon" aria-hidden="true"><GraduationCap :size="22" /></span>
            <div>
              <p class="swp-section-kicker">当前学期</p>
              <h2>2025-2026 学年第一学期</h2>
              <p>2025-09-01 至 2026-01-20 · 进行中 · 下一步：教师任课</p>
            </div>
          </div>
          <div class="swp-semester-stats">
            <span><Users :size="15" />12 个班级</span>
            <span><UserRound :size="15" />31 位教师</span>
            <span><BookOpen :size="15" />18 个科目</span>
          </div>
          <div class="swp-semester-actions">
            <button class="swp-button swp-button-primary" type="button" data-testid="prototype-semester-management" @click="openSemesterPanel"><Settings2 :size="15" />学期管理</button>
            <button class="swp-button swp-button-quiet" type="button" @click="onTopAction('切换学期')">切换学期 <ChevronDown :size="14" /></button>
          </div>
        </section>

        <section class="swp-notice" :class="`is-${noticeTone}`" aria-live="polite">
          <span class="swp-notice-icon"><CheckCircle2 v-if="noticeTone === 'success'" :size="15" /><CircleAlert v-else-if="noticeTone === 'warning'" :size="15" /><Sparkles v-else :size="15" /></span>
          <span>{{ notice }}</span>
          <span class="swp-notice-meta">示范数据 · 不写入后端</span>
        </section>

        <!-- Variant A: horizontal rail, with the detail replacing the lower overview area. -->
        <section v-if="currentVariant === 'A'" class="swp-variant swp-variant-a" data-testid="prototype-variant-a">
          <div class="swp-variant-heading">
            <div><p class="swp-section-kicker">方案 A · {{ currentVariantMeta.label }}</p><h2>{{ selectedStep ? activeStep?.label : '排课流程' }}</h2><p>{{ selectedStep ? activeStep?.description : '先看五步状态，再进入对应详情。总览不再放置独立的准备辅助工作面。' }}</p></div>
            <button v-if="selectedStep" class="swp-button swp-button-secondary" type="button" @click="returnToOverview"><ArrowLeft :size="15" />返回总览</button>
          </div>

          <nav class="swp-step-rail" aria-label="排课流程">
            <button v-for="(step, index) in steps" :key="step.key" class="swp-step-rail-item" :class="{ 'is-active': selectedStep === step.key, 'is-done': step.state === 'done', 'is-blocked': step.state === 'blocked' }" type="button" :data-testid="`prototype-step-a-${step.key}`" @click="selectStep(step.key)">
              <span class="swp-step-index"><Check v-if="step.state === 'done'" :size="14" /><span v-else>{{ index + 1 }}</span></span>
              <span><strong>{{ step.label }}</strong><small>{{ step.summary }}</small></span>
              <ArrowRight v-if="index < steps.length - 1" class="swp-step-arrow" :size="14" aria-hidden="true" />
            </button>
          </nav>

          <div v-if="!selectedStep" class="swp-overview-grid">
            <article class="swp-panel swp-next-panel"><div class="swp-panel-heading"><span class="swp-panel-icon is-blue"><Play :size="17" /></span><div><p class="swp-section-kicker">下一步</p><h3>{{ nextStep.label }}</h3></div></div><p>{{ nextStep.description }}</p><button class="swp-button swp-button-primary" type="button" @click="selectStep(nextStep.key)">进入{{ nextStep.label }}<ArrowRight :size="15" /></button></article>
            <article class="swp-panel swp-health-panel"><div class="swp-panel-heading"><span class="swp-panel-icon is-green"><CheckCircle2 :size="17" /></span><div><p class="swp-section-kicker">当前准备度</p><h3>4 / 5 步骤已具备数据</h3></div></div><div class="swp-progress"><span style="width: 78%" /></div><div class="swp-health-facts"><span>44 / 46 项已任课</span><span class="is-warning">2 项提醒</span></div></article>
            <article class="swp-panel swp-activity-panel"><div class="swp-panel-heading"><span class="swp-panel-icon is-orange"><Clock3 :size="17" /></span><div><p class="swp-section-kicker">最近动作</p><h3>工作台活动</h3></div></div><ul class="swp-activity-list"><li v-for="item in activity.slice(0, 3)" :key="`${item.time}-${item.text}`"><i :class="`is-${item.tone}`" /><span><strong>{{ item.text }}</strong><small>{{ item.time }}</small></span></li></ul></article>
          </div>
          <div v-else class="swp-detail-wrap"><PrototypeStepDetail :step="selectedStep" :auto-panel="autoPanel" :calendar-confirmed="calendarConfirmed" :imported="imported" :running="running" @open-auto-panel="openAutoPanel" @confirm-calendar="confirmCalendar" @revoke-calendar="revokeCalendar" @preview-import="previewImport" @run-auto="runAutoSchedule" @action="onTopAction" /></div>
        </section>

        <!-- Variant B: fixed vertical rail and a dedicated detail canvas. -->
        <section v-else-if="currentVariant === 'B'" class="swp-variant swp-variant-b" data-testid="prototype-variant-b">
          <div class="swp-variant-heading"><div><p class="swp-section-kicker">方案 B · {{ currentVariantMeta.label }}</p><h2>流程导航</h2><p>适合详情较长、需要频繁在步骤之间往返的排课准备。</p></div><span class="swp-quiet-caption">当前选择：{{ selectedStep ? activeStep?.label : '总览' }}</span></div>
          <div class="swp-b-layout">
            <aside class="swp-b-rail" aria-label="排课步骤导航"><div class="swp-b-rail-title"><span>排课步骤</span><small>按当前数据推导</small></div><button v-for="(step, index) in steps" :key="step.key" class="swp-b-step" :class="{ 'is-active': selectedStep === step.key, 'is-done': step.state === 'done', 'is-blocked': step.state === 'blocked' }" type="button" :data-testid="`prototype-step-b-${step.key}`" @click="selectStep(step.key)"><span class="swp-b-step-number"><Check v-if="step.state === 'done'" :size="14" /><span v-else>{{ index + 1 }}</span></span><span><strong>{{ step.label }}</strong><small>{{ step.summary }}</small></span><ArrowRight :size="14" /></button><div class="swp-b-rail-foot"><span class="swp-legend-dot is-warning" /> 2 项待处理提醒</div></aside>
            <div class="swp-b-detail"><div v-if="!selectedStep" class="swp-b-overview"><div class="swp-b-overview-head"><div><p class="swp-section-kicker">排课工作台总览</p><h3>选择一个步骤开始</h3><p>步骤详情会在右侧区域替换，不离开当前学期上下文。</p></div><button class="swp-button swp-button-primary" type="button" @click="selectStep(nextStep.key)">继续：{{ nextStep.label }}<ArrowRight :size="15" /></button></div><div class="swp-b-stat-row"><div><strong>12</strong><span>班级</span></div><div><strong>46</strong><span>课程项</span></div><div><strong>44/46</strong><span>已任课</span></div><div><strong>0</strong><span>阻断错误</span></div></div><div class="swp-b-callout"><Sparkles :size="17" /><div><strong>自动排课还需要一个明确动作</strong><span>先在“教师”中补齐 2 项任课，再进入自动排课检查。</span></div></div></div><PrototypeStepDetail v-else :step="selectedStep" :auto-panel="autoPanel" :calendar-confirmed="calendarConfirmed" :imported="imported" :running="running" @open-auto-panel="openAutoPanel" @confirm-calendar="confirmCalendar" @revoke-calendar="revokeCalendar" @preview-import="previewImport" @run-auto="runAutoSchedule" @action="onTopAction" /></div>
          </div>
        </section>

        <!-- Variant C: a persistent overview column beside the selected detail. -->
        <section v-else class="swp-variant swp-variant-c" data-testid="prototype-variant-c">
          <div class="swp-variant-heading"><div><p class="swp-section-kicker">方案 C · {{ currentVariantMeta.label }}</p><h2>{{ selectedStep ? activeStep?.label : '排课准备总览' }}</h2><p>左侧保留事实摘要，右侧随选择切换详情。</p></div><span class="swp-quiet-caption">{{ selectedStep ? '详情视图' : '总览视图' }}</span></div>
          <div class="swp-c-layout">
            <aside class="swp-c-overview"><div class="swp-c-overview-title"><div><p class="swp-section-kicker">五步进度</p><h3>当前学期</h3></div><button class="swp-icon-button" type="button" aria-label="刷新进度" title="刷新进度" @click="onTopAction('刷新进度')"><RefreshCw :size="15" /></button></div><div class="swp-c-progress"><strong>78%</strong><span>准备度</span><div class="swp-progress"><span style="width: 78%" /></div></div><button v-for="step in steps" :key="step.key" class="swp-c-step" :class="{ 'is-active': selectedStep === step.key, 'is-done': step.state === 'done', 'is-blocked': step.state === 'blocked' }" type="button" :data-testid="`prototype-step-c-${step.key}`" @click="selectStep(step.key)"><span class="swp-c-index"><Check v-if="step.state === 'done'" :size="13" /><span v-else>{{ step.number }}</span></span><span><strong>{{ step.label }}</strong><small>{{ step.summary }}</small></span><ArrowRight :size="14" /></button><div class="swp-c-activity"><div class="swp-panel-heading"><span class="swp-panel-icon is-orange"><Clock3 :size="15" /></span><div><p class="swp-section-kicker">最近动作</p><h3>活动</h3></div></div><ul class="swp-activity-list"><li v-for="item in activity.slice(0, 2)" :key="`${item.time}-${item.text}`"><i :class="`is-${item.tone}`" /><span><strong>{{ item.text }}</strong><small>{{ item.time }}</small></span></li></ul></div></aside>
            <div class="swp-c-detail"><div v-if="!selectedStep" class="swp-c-empty"><span class="swp-empty-icon"><ListChecks :size="24" /></span><p class="swp-section-kicker">详情区域</p><h3>从左侧选择一个步骤</h3><p>班级、课时、科目、教师和自动排课都在当前学期内完成；选择后这里显示该步骤的完整业务工作面。</p><button class="swp-button swp-button-primary" type="button" @click="selectStep(nextStep.key)">进入{{ nextStep.label }}<ArrowRight :size="15" /></button></div><PrototypeStepDetail v-else :step="selectedStep" :auto-panel="autoPanel" :calendar-confirmed="calendarConfirmed" :imported="imported" :running="running" @open-auto-panel="openAutoPanel" @confirm-calendar="confirmCalendar" @revoke-calendar="revokeCalendar" @preview-import="previewImport" @run-auto="runAutoSchedule" @action="onTopAction" /></div>
          </div>
        </section>
      </div>
    </main>

    <div v-if="semesterPanelOpen" class="swp-overlay" role="presentation" @click.self="semesterPanelOpen = false">
      <section class="swp-modal" role="dialog" aria-modal="true" aria-labelledby="swp-semester-dialog-title"><header><div><p class="swp-section-kicker">当前学期 · 学期管理</p><h2 id="swp-semester-dialog-title">学期与作息时间表</h2></div><button class="swp-icon-button" type="button" aria-label="关闭学期管理" title="关闭学期管理" @click="semesterPanelOpen = false"><X :size="17" /></button></header><p class="swp-modal-copy">这里承接创建、日期维护和作息时间表入口；保存后工作台会重新计算步骤状态。</p><div class="swp-modal-summary"><div><span>学期状态</span><strong>进行中</strong></div><div><span>起止日期</span><strong>2025-09-01 至 2026-01-20</strong></div></div><div class="swp-modal-fields"><label><span>开始日期</span><input value="2025-09-01" aria-label="开始日期" /></label><label><span>结束日期</span><input value="2026-01-20" aria-label="结束日期" /></label></div><div class="swp-modal-links"><button type="button" @click="onTopAction('打开作息时间表')"><Clock3 :size="15" />管理作息时间表<ArrowRight :size="14" /></button><button type="button" @click="onTopAction('打开学期复制')"><Copy :size="15" />复制学期数据<ArrowRight :size="14" /></button></div><footer><button class="swp-button swp-button-secondary" type="button" @click="semesterPanelOpen = false">取消</button><button class="swp-button swp-button-primary" type="button" @click="saveSemesterPanel"><Check :size="15" />保存修改</button></footer></section>
    </div>

    <nav v-if="showPrototypeSwitcher" class="swp-switcher" aria-label="原型方案切换"><button type="button" title="上一个方案（←）" aria-label="上一个方案" @click="cycleVariant(-1)"><ArrowLeft :size="16" /></button><div><span>DEV PROTOTYPE</span><strong>{{ currentVariant }} · {{ currentVariantMeta.label }}</strong><small>{{ currentVariantMeta.subtitle }}</small></div><button type="button" title="下一个方案（→）" aria-label="下一个方案" @click="cycleVariant(1)"><ArrowRight :size="16" /></button></nav>
  </div>
</template>

<!-- A deliberately small, local detail component keeps the prototype runnable without importing production forms. -->
<script lang="ts">
import { defineComponent, h, type PropType } from 'vue'

type PrototypeStep = 'classes' | 'periods' | 'subjects' | 'teachers' | 'auto'
type PrototypeAutoPanel = 'calendar' | 'resources' | null

export const PrototypeStepDetail = defineComponent({
  name: 'PrototypeStepDetail',
  props: {
    step: { type: String as PropType<PrototypeStep>, required: true },
    autoPanel: { type: String as PropType<PrototypeAutoPanel>, default: null },
    calendarConfirmed: { type: Boolean, default: false },
    imported: { type: Boolean, default: false },
    running: { type: Boolean, default: false },
  },
  emits: ['open-auto-panel', 'confirm-calendar', 'revoke-calendar', 'preview-import', 'run-auto', 'action'],
  setup(props, { emit }) {
    const action = (label: string) => emit('action', label)
    const button = (label: string, icon: Component = ArrowRight, primary = false) => h('button', {
      class: ['swp-button', primary ? 'swp-button-primary' : 'swp-button-secondary'],
      type: 'button',
      onClick: () => action(label),
    }, [h(icon, { size: 15 }), label])
    const sectionHeading = (kicker: string, title: string, copy: string) => h('div', { class: 'swp-detail-heading' }, [
      h('div', [h('p', { class: 'swp-section-kicker' }, kicker), h('h3', title), h('p', copy)]),
    ])
    const statusPill = (text: string, tone: string) => h('span', { class: ['swp-status-pill', `is-${tone}`] }, text)
    const tableRows = (rows: Array<{ name: string; meta: string; status: string; tone: string }>) => h('div', { class: 'swp-data-list' }, rows.map((row) => h('div', { class: 'swp-data-row', key: row.name }, [
      h('div', [h('strong', row.name), h('small', row.meta)]), statusPill(row.status, row.tone), h('button', { class: 'swp-row-more', type: 'button', 'aria-label': `编辑${row.name}`, title: `编辑${row.name}`, onClick: () => action(`编辑${row.name}`) }, [h(Table2, { size: 15 })]),
    ])))

    return () => {
      if (props.step === 'classes') {
        return h('div', { class: 'swp-detail swp-detail-classes' }, [
          sectionHeading('① 班级', '设置班级', '确认参与本学期排课的班级，并为班级分配作息分组。'),
          h('div', { class: 'swp-detail-toolbar' }, [h('span', { class: 'swp-filter-chip' }, '全部年级'), h('span', { class: 'swp-filter-chip' }, '初中'), button('批量新增班级', Users, true)]),
          h('div', { class: 'swp-detail-columns' }, [
            h('section', { class: 'swp-panel swp-panel-flat' }, [h('div', { class: 'swp-panel-heading' }, [h(Users, { size: 17 }), h('div', [h('p', { class: 'swp-section-kicker' }, '班级清单'), h('h3', '12 个班级')])]), tableRows([{ name: '七年级 1 班', meta: '42 人 · 初中 · 作息 A', status: '已设置', tone: 'green' }, { name: '七年级 2 班', meta: '40 人 · 初中 · 作息 A', status: '已设置', tone: 'green' }, { name: '八年级 1 班', meta: '38 人 · 初中 · 作息 B', status: '待确认', tone: 'orange' }]), h('button', { class: 'swp-inline-link', type: 'button', onClick: () => action('查看全部班级') }, ['查看全部 12 个班级', h(ArrowRight, { size: 14 })])]),
            h('aside', { class: 'swp-panel swp-panel-flat swp-side-note' }, [h('span', { class: 'swp-panel-icon is-green' }, [h(CheckCircle2, { size: 17 })]), h('h3', '班级数据已具备'), h('p', '班级数量、人数和作息分组会在后续课时容量检查中继续使用。'), button('打开班级导入', Upload)]),
          ]),
        ])
      }
      if (props.step === 'periods') {
        return h('div', { class: 'swp-detail swp-detail-periods' }, [
          sectionHeading('② 课时', '设置课时', '配置作息时间表、常规课节次和班级可排容量。'),
          h('div', { class: 'swp-detail-toolbar' }, [h('span', { class: 'swp-filter-chip is-selected' }, '作息 A · 初中'), h('span', { class: 'swp-filter-chip' }, '作息 B · 高中'), button('编辑作息表', Clock3, true)]),
          h('div', { class: 'swp-period-layout' }, [
            h('section', { class: 'swp-panel swp-panel-flat' }, [
              h('div', { class: 'swp-panel-heading' }, [
                h(Clock3, { size: 17 }),
                h('div', [h('p', { class: 'swp-section-kicker' }, '作息 A'), h('h3', '周一至周五 · 8 个常规课时')]),
              ]),
              h('div', { class: 'swp-period-grid' }, [
                '08:00 第一节', '08:50 第二节', '09:50 第三节', '10:40 第四节',
                '14:00 第五节', '14:50 第六节', '15:50 第七节', '16:40 第八节',
              ].map((period, index) => h('div', { class: ['swp-period-cell', index === 4 ? 'is-break' : ''] }, [
                h('span', period.split(' ')[0]),
                h('strong', period.slice(6)),
                index === 4 ? h('small', '午休后') : null,
              ]))),
              h('div', { class: 'swp-period-foot' }, [h(CheckCircle2, { size: 15 }), h('span', '当前 12 个班级均已绑定作息时间表')]),
            ]),
            h('aside', { class: 'swp-panel swp-panel-flat swp-side-note' }, [h('span', { class: 'swp-panel-icon is-orange' }, [h(CircleAlert, { size: 17 })]), h('h3', '容量提醒 1 项'), h('p', '八年级 1 班的计划周课时接近常规课时上限，录入科目节数时会继续提示。'), button('查看容量明细', ListChecks)]),
          ]),
        ])
      }
      if (props.step === 'subjects') {
        return h('div', { class: 'swp-detail swp-detail-subjects' }, [
          sectionHeading('③ 科目', '科目节数', '在同一个步骤里维护科目档案，并录入班级每周课时。'),
          h('div', { class: 'swp-detail-toolbar' }, [h('div', { class: 'swp-segmented' }, [h('button', { class: 'is-active', type: 'button', onClick: () => action('切换到科目节数') }, [h(BookOpen, { size: 14 }), '科目节数']), h('button', { type: 'button', onClick: () => action('切换到科目档案') }, [h(Database, { size: 14 }), '科目档案'])]), button('添加科目', BookOpen, true)]),
          h('div', { class: 'swp-detail-columns' }, [
            h('section', { class: 'swp-panel swp-panel-flat' }, [
              h('div', { class: 'swp-panel-heading' }, [
                h(BookOpen, { size: 17 }),
                h('div', [h('p', { class: 'swp-section-kicker' }, '本周课时'), h('h3', '七年级 1 班')]),
              ]),
              h('div', { class: 'swp-subject-list' }, [
                { name: '语文', hours: '5 节 / 周', tone: 'blue' },
                { name: '数学', hours: '5 节 / 周', tone: 'green' },
                { name: '英语', hours: '4 节 / 周', tone: 'purple' },
                { name: '物理', hours: '2 节 / 周', tone: 'orange' },
              ].map((item) => h('div', { class: 'swp-subject-row' }, [
                h('span', { class: ['swp-subject-mark', `is-${item.tone}`] }, item.name.slice(0, 1)),
                h('strong', item.name),
                h('span', item.hours),
                h('button', { type: 'button', class: 'swp-row-more', title: `编辑${item.name}`, 'aria-label': `编辑${item.name}`, onClick: () => action(`编辑${item.name}课时`) }, [h(MoreHorizontal, { size: 16 })]),
              ]))),
              h('button', { class: 'swp-inline-link', type: 'button', onClick: () => action('打开批量课时设置') }, ['批量设置其他班级', h(ArrowRight, { size: 14 })]),
            ]),
            h('aside', { class: 'swp-panel swp-panel-flat swp-side-note' }, [h('span', { class: 'swp-panel-icon is-blue' }, [h(Sparkles, { size: 17 })]), h('h3', '常用科目快捷添加'), h('p', '语文、数学、英语等快捷项逐项确认后写入当前学期，不自动成套创建。'), button('打开科目档案', Database)]),
          ]),
        ])
      }
      if (props.step === 'teachers') {
        return h('div', { class: 'swp-detail swp-detail-teachers' }, [
          sectionHeading('④ 教师', '教师任课', '在同一个步骤里维护教师档案，并为课程指定授课教师。'),
          h('div', { class: 'swp-detail-toolbar' }, [h('div', { class: 'swp-segmented' }, [h('button', { class: 'is-active', type: 'button', onClick: () => action('切换到教师任课') }, [h(UserRound, { size: 14 }), '教师任课']), h('button', { type: 'button', onClick: () => action('切换到教师档案') }, [h(Users, { size: 14 }), '教师档案'])]), button('批量指定教师', UserRound, true)]),
          h('section', { class: 'swp-panel swp-panel-flat' }, [
            h('div', { class: 'swp-table-head' }, [h('span', '课程'), h('span', '班级'), h('span', '授课教师'), h('span', '状态')]),
            h('div', { class: 'swp-assignment-table' }, [
              { course: '语文', className: '七年级 1 班', teacher: '陈老师', status: '已完成', tone: 'green' },
              { course: '数学', className: '七年级 1 班', teacher: '李老师', status: '已完成', tone: 'green' },
              { course: '物理', className: '八年级 1 班', teacher: '待指定', status: '待处理', tone: 'orange' },
              { course: '英语', className: '八年级 1 班', teacher: '王老师', status: '已完成', tone: 'green' },
            ].map((row) => h('div', { class: 'swp-assignment-row' }, [
              h('strong', row.course),
              h('span', row.className),
              h('span', { class: row.teacher === '待指定' ? 'is-empty' : '' }, row.teacher),
              statusPill(row.status, row.tone),
              h('button', { class: 'swp-row-more', type: 'button', title: `编辑${row.course}任课`, 'aria-label': `编辑${row.course}任课`, onClick: () => action(`编辑${row.course}任课`) }, [h(MoreHorizontal, { size: 16 })]),
            ]))),
            h('div', { class: 'swp-table-foot' }, [h(CircleAlert, { size: 15 }), h('span', '还有 2 项课程待指定教师，完成后可进入自动排课。')]),
          ]),
        ])
      }
      const calendarContent = props.autoPanel === 'calendar'
        ? h('section', { class: 'swp-auto-subpanel', 'data-testid': 'prototype-calendar-panel' }, [h('div', { class: 'swp-subpanel-head' }, [h('div', [h('p', { class: 'swp-section-kicker' }, '自动排课 · 校历与准备'), h('h3', '校历与排课准备')]), h('button', { class: 'swp-icon-button', type: 'button', 'aria-label': '关闭校历面板', title: '关闭校历面板', onClick: () => emit('open-auto-panel', null) }, [h(CircleAlert, { size: 16 })])]), h('div', { class: 'swp-calendar-checks' }, [h('div', [h(CheckCircle2, { size: 16 }), h('span', [h('strong', '学期日期'), h('small', '2025-09-01 至 2026-01-20')])]), h('div', [h(CheckCircle2, { size: 16 }), h('span', [h('strong', '特殊日期'), h('small', '停课 2 天 · 补课 1 天')])]), h('div', { class: props.calendarConfirmed ? 'is-done' : 'is-warning' }, [props.calendarConfirmed ? h(CheckCircle2, { size: 16 }) : h(CircleAlert, { size: 16 }), h('span', [h('strong', props.calendarConfirmed ? '排课准备已确认' : '排课准备待确认'), h('small', props.calendarConfirmed ? '可以进入生成' : '确认后才能开始排课')])])]), h('div', { class: 'swp-subpanel-actions' }, [h('button', { class: 'swp-button swp-button-secondary', type: 'button', onClick: () => action('打开校历完整页面') }, [h(CalendarDays, { size: 15 }), '查看校历']), props.calendarConfirmed ? h('button', { class: 'swp-button swp-button-secondary', type: 'button', onClick: () => emit('revoke-calendar') }, [h(CircleAlert, { size: 15 }), '撤回确认']) : h('button', { class: 'swp-button swp-button-primary', type: 'button', onClick: () => emit('confirm-calendar') }, [h(Check, { size: 15 }), '确认准备'])])])
        : null
      const resourceContent = props.autoPanel === 'resources'
        ? h('section', { class: 'swp-auto-subpanel' }, [h('div', { class: 'swp-subpanel-head' }, [h('div', [h('p', { class: 'swp-section-kicker' }, '自动排课 · 资源与导入'), h('h3', '资源与导入')]), h('button', { class: 'swp-icon-button', type: 'button', 'aria-label': '关闭资源面板', title: '关闭资源面板', onClick: () => emit('open-auto-panel', null) }, [h(Database, { size: 16 })])]), h('div', { class: 'swp-resource-actions' }, [h('button', { type: 'button', onClick: () => action('管理教室与场地') }, [h(Database, { size: 17 }), h('span', [h('strong', '教室与场地'), h('small', '已配置 8 间 · 0 项阻断')]), h(ArrowRight, { size: 14 })]), h('button', { type: 'button', onClick: () => emit('preview-import') }, [h(FileUp, { size: 17 }), h('span', [h('strong', '模板与组合导入'), h('small', props.imported ? '预览完成 · 3 项新增' : '可预览新增、修改和冲突')]), h(ArrowRight, { size: 14 })]), h('button', { type: 'button', onClick: () => action('绑定教师账号') }, [h(UserRound, { size: 17 }), h('span', [h('strong', '教师账号绑定'), h('small', '管理员专用 · 不参与排课计算')]), h(ArrowRight, { size: 14 })])])])
        : null
      return h('div', { class: 'swp-detail swp-detail-auto' }, [
        sectionHeading('⑤ 自动排课', '自动排课', '先完成前置检查，再生成当前学期的课表草稿。'),
        h('div', { class: 'swp-auto-command' }, [h('div', { class: 'swp-auto-score' }, [h('span', { class: 'swp-score-ring' }, [h('strong', '92'), h('small', '准备度')]), h('div', [h('strong', props.calendarConfirmed ? '可以开始检查' : '还有准备动作'), h('p', props.calendarConfirmed ? '当前没有阻断错误，可以运行自动排课。' : '校历与排课准备尚未确认。')])]), h('button', { class: ['swp-button', 'swp-button-primary', 'swp-auto-run'], type: 'button', disabled: props.running, onClick: () => emit('run-auto') }, [h(Play, { size: 16 }), props.running ? '正在生成…' : '开始自动排课'])]),
        h('div', { class: 'swp-auto-check-grid' }, [h('button', { class: 'swp-auto-check', type: 'button', onClick: () => emit('open-auto-panel', 'calendar') }, [h(CalendarDays, { size: 19 }), h('span', [h('strong', '校历与排课准备'), h('small', props.calendarConfirmed ? '已确认 · 查看详情' : '待确认 · 2 项提醒')]), h(ArrowRight, { size: 15 })]), h('button', { class: 'swp-auto-check', type: 'button', onClick: () => emit('open-auto-panel', 'resources') }, [h(Database, { size: 19 }), h('span', [h('strong', '资源与导入'), h('small', props.imported ? '预览完成 · 3 项新增' : '教室、导入和账号绑定')]), h(ArrowRight, { size: 15 })]), h('div', { class: 'swp-auto-check is-pass' }, [h(CheckCircle2, { size: 19 }), h('span', [h('strong', '数据前置检查'), h('small', '班级、课时和科目数据可用')])])]), calendarContent, resourceContent, h('section', { class: 'swp-panel swp-panel-flat swp-preflight-panel' }, [h('div', { class: 'swp-panel-heading' }, [h(ListChecks, { size: 17 }), h('div', [h('p', { class: 'swp-section-kicker' }, '生成前检查'), h('h3', '当前检查结果')])]), h('div', { class: 'swp-check-list' }, [h('div', [h(CheckCircle2, { size: 16 }), h('span', '班级与作息分组'), h('strong', '通过')]), h('div', [h(CheckCircle2, { size: 16 }), h('span', '课程与教师任课'), h('strong', '44 / 46')]), h('div', [h(CircleAlert, { size: 16 }), h('span', '校历与排课准备'), h('strong', props.calendarConfirmed ? '通过' : '待确认')]), h('div', [h(CheckCircle2, { size: 16 }), h('span', '教室/场地供给'), h('strong', '通过')])])]),
      ])
    }
  },
})

</script>

<style scoped>
:global(body) { margin: 0; background: #eef2f6; }
:global(button), :global(input) { font: inherit; }

.swp-app {
  --ink: #1d2a3a;
  --muted: #657286;
  --faint: #8b97a8;
  --line: #dce4ec;
  --soft: #f5f8fb;
  --blue: #2864d8;
  --blue-soft: #edf3ff;
  --green: #17764f;
  --green-soft: #eaf7f0;
  --orange: #a2600c;
  --orange-soft: #fff4e4;
  --red: #c03d49;
  --purple: #7557ad;
  display: grid;
  min-height: 100vh;
  grid-template-columns: 220px minmax(0, 1fr);
  color: var(--ink);
  background: #eef2f6;
  font-family: var(--app-font-sans, Inter, "Noto Sans SC", sans-serif);
  letter-spacing: 0;
}
.swp-app button { -webkit-tap-highlight-color: transparent; }
.swp-sidebar { display: flex; min-height: 100vh; flex-direction: column; border-right: 1px solid var(--line); background: #fff; }
.swp-brand { display: flex; min-height: 70px; align-items: center; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--line); }
.swp-brand-mark, .swp-school-mark { display: grid; place-items: center; flex: 0 0 auto; border-radius: 7px; background: var(--blue-soft); color: var(--blue); }
.swp-brand-mark { width: 34px; height: 34px; background: var(--blue); color: #fff; }
.swp-brand > span:nth-child(2), .swp-school > span:last-child { display: grid; min-width: 0; gap: 2px; }
.swp-brand strong { font-size: 14px; }
.swp-brand small, .swp-school small { color: var(--muted); font-size: 10px; }
.swp-mobile-close { display: none !important; margin-left: auto; }
.swp-nav { flex: 1; padding: 16px 10px; }
.swp-nav-label { margin: 0 8px 7px; color: var(--faint); font-size: 10px; font-weight: 800; letter-spacing: .04em; }
.swp-nav-label-spaced { margin-top: 23px; }
.swp-nav-link { display: flex; width: 100%; min-height: 39px; align-items: center; gap: 9px; margin: 2px 0; padding: 0 10px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: var(--muted); font-size: 12px; text-align: left; cursor: pointer; }
.swp-nav-link:hover { border-color: var(--line); background: var(--soft); color: var(--ink); }
.swp-nav-link.is-active { border-color: #c6d5f6; background: var(--blue-soft); color: #1f50b2; font-weight: 750; }
.swp-school { display: flex; align-items: center; gap: 9px; padding: 13px; border-top: 1px solid var(--line); background: var(--soft); }
.swp-school-mark { width: 29px; height: 29px; }
.swp-school strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.swp-main { display: grid; min-width: 0; min-height: 100vh; grid-template-rows: 66px minmax(0, 1fr); }
.swp-topbar { display: flex; min-width: 0; align-items: center; gap: 12px; padding: 0 22px; border-bottom: 1px solid var(--line); background: #fff; }
.swp-breadcrumb { display: flex; min-width: 0; align-items: center; gap: 7px; color: var(--muted); font-size: 12px; }
.swp-breadcrumb strong { color: var(--ink); }
.swp-dev-badge { padding: 3px 6px; border: 1px solid #cbd6e5; border-radius: 4px; color: var(--muted); font-size: 9px; font-weight: 800; letter-spacing: .08em; }
.swp-top-actions { display: flex; min-width: 0; align-items: center; gap: 10px; margin-left: auto; }
.swp-top-semester { display: inline-flex; align-items: center; gap: 5px; padding: 8px 9px; border: 1px solid var(--line); border-radius: 6px; background: var(--soft); color: var(--muted); font-size: 11px; white-space: nowrap; }
.swp-avatar { display: grid; width: 29px; height: 29px; place-items: center; border-radius: 50%; background: #dbe7ff; color: #1f50b2; font-size: 12px; font-weight: 800; }
.swp-icon-button { display: inline-grid; width: 33px; height: 33px; flex: 0 0 auto; place-items: center; border: 1px solid var(--line); border-radius: 6px; background: #fff; color: var(--muted); cursor: pointer; }
.swp-icon-button:hover { border-color: #b9c9ea; background: var(--blue-soft); color: var(--blue); }
.swp-menu-button { display: none; }
.swp-content { min-width: 0; overflow: auto; padding: 22px 25px 100px; }
.swp-page-head, .swp-variant-heading { display: flex; min-width: 0; align-items: flex-end; justify-content: space-between; gap: 20px; }
.swp-page-head { width: min(1420px, 100%); margin: 0 auto 17px; }
.swp-eyebrow, .swp-section-kicker { margin: 0 0 5px; color: var(--blue); font-size: 10px; font-weight: 800; letter-spacing: .05em; }
.swp-page-head h1 { margin: 0; font-size: 26px; line-height: 1.2; }
.swp-page-head p:last-child { margin: 7px 0 0; color: var(--muted); font-size: 13px; }
.swp-page-actions, .swp-semester-actions, .swp-detail-toolbar, .swp-subpanel-actions { display: flex; min-width: 0; flex-wrap: wrap; align-items: center; gap: 8px; }
.swp-role-chip, .swp-quiet-caption { display: inline-flex; align-items: center; gap: 5px; color: var(--muted); font-size: 11px; }
.swp-button { display: inline-flex; min-height: 35px; align-items: center; justify-content: center; gap: 7px; padding: 0 12px; border: 1px solid transparent; border-radius: 6px; font-size: 12px; font-weight: 700; cursor: pointer; white-space: nowrap; }
.swp-button:disabled { cursor: wait; opacity: .6; }
.swp-button-primary { border-color: var(--blue); background: var(--blue); color: #fff; }
.swp-button-primary:hover:not(:disabled) { background: #2358c4; }
.swp-button-secondary { border-color: var(--line); background: #fff; color: var(--ink); }
.swp-button-secondary:hover:not(:disabled) { border-color: #b9c9ea; background: var(--blue-soft); color: #1f50b2; }
.swp-button-quiet { min-height: 31px; padding-inline: 4px; background: transparent; color: var(--blue); }
.swp-semester-context { display: grid; width: min(1420px, 100%); min-width: 0; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 18px; margin: 0 auto 13px; padding: 17px 18px; border: 1px solid #cddaf0; border-radius: 7px; background: #fff; box-shadow: 0 1px 2px rgb(28 39 56 / 4%); }
.swp-semester-main { display: flex; min-width: 0; align-items: center; gap: 12px; }
.swp-semester-icon { display: grid; width: 43px; height: 43px; flex: 0 0 auto; place-items: center; border-radius: 7px; background: var(--blue-soft); color: var(--blue); }
.swp-semester-main h2 { margin: 0; overflow-wrap: anywhere; font-size: 17px; }
.swp-semester-main p:last-child { margin: 5px 0 0; color: var(--muted); font-size: 11px; }
.swp-semester-stats { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 11px; color: var(--muted); font-size: 11px; }
.swp-semester-stats span { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
.swp-semester-actions { justify-content: flex-end; }
.swp-notice { display: flex; width: min(1420px, 100%); min-width: 0; align-items: center; gap: 8px; margin: 0 auto 18px; padding: 9px 12px; border: 1px solid var(--line); border-radius: 6px; background: #f9fbfe; color: var(--muted); font-size: 11px; }
.swp-notice-icon { display: inline-grid; place-items: center; flex: 0 0 auto; color: var(--blue); }
.swp-notice.is-success { border-color: #b7dfca; background: var(--green-soft); color: var(--green); }.swp-notice.is-success .swp-notice-icon { color: var(--green); }
.swp-notice.is-warning { border-color: #efd3a4; background: var(--orange-soft); color: var(--orange); }.swp-notice.is-warning .swp-notice-icon { color: var(--orange); }
.swp-notice-meta { margin-left: auto; color: var(--faint); font-size: 10px; white-space: nowrap; }
.swp-variant { width: min(1420px, 100%); min-width: 0; margin: 0 auto; }
.swp-variant-heading { align-items: flex-start; margin-bottom: 14px; }
.swp-variant-heading h2 { margin: 0; font-size: 19px; }
.swp-variant-heading p:last-child { margin: 5px 0 0; color: var(--muted); font-size: 12px; line-height: 1.5; }
.swp-step-rail { display: grid; min-width: 0; grid-template-columns: repeat(5, minmax(0, 1fr)); margin-bottom: 15px; border: 1px solid var(--line); border-radius: 7px; background: #fff; overflow: hidden; }
.swp-step-rail-item { position: relative; display: flex; min-width: 0; min-height: 71px; align-items: center; gap: 9px; padding: 11px 16px; border: 0; border-right: 1px solid var(--line); background: #fff; color: var(--muted); text-align: left; cursor: pointer; }
.swp-step-rail-item:last-child { border-right: 0; }.swp-step-rail-item:hover { background: var(--soft); }.swp-step-rail-item.is-active { background: var(--blue-soft); color: #1f50b2; }.swp-step-rail-item.is-done { color: var(--green); }.swp-step-rail-item.is-blocked { background: #fffaf5; color: var(--orange); }
.swp-step-index { display: grid; width: 25px; height: 25px; flex: 0 0 auto; place-items: center; border: 1px solid currentColor; border-radius: 50%; font-size: 10px; font-weight: 800; }.swp-step-rail-item.is-done .swp-step-index { background: var(--green-soft); }.swp-step-rail-item > span:nth-child(2) { display: grid; min-width: 0; gap: 3px; }.swp-step-rail-item strong { overflow: hidden; color: inherit; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }.swp-step-rail-item small { overflow: hidden; color: var(--faint); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.swp-step-arrow { position: absolute; top: 28px; right: 6px; color: var(--faint); }
.swp-overview-grid { display: grid; min-width: 0; grid-template-columns: minmax(0, 1.1fr) minmax(240px, .75fr) minmax(240px, .8fr); gap: 13px; }
.swp-panel { min-width: 0; border: 1px solid var(--line); border-radius: 7px; background: #fff; box-shadow: 0 1px 2px rgb(28 39 56 / 4%); }.swp-panel-flat { padding: 17px; box-shadow: none; }.swp-next-panel, .swp-health-panel, .swp-activity-panel { min-height: 176px; padding: 17px; }.swp-panel-heading { display: flex; min-width: 0; align-items: center; gap: 9px; }.swp-panel-heading > div { min-width: 0; }.swp-panel-heading h3 { margin: 0; font-size: 15px; }.swp-panel-icon { display: grid; width: 30px; height: 30px; flex: 0 0 auto; place-items: center; border-radius: 6px; }.swp-panel-icon.is-blue { background: var(--blue-soft); color: var(--blue); }.swp-panel-icon.is-green { background: var(--green-soft); color: var(--green); }.swp-panel-icon.is-orange { background: var(--orange-soft); color: var(--orange); }.swp-next-panel > p { margin: 15px 0 16px; color: var(--muted); font-size: 12px; line-height: 1.55; }.swp-progress { height: 7px; margin-top: 18px; overflow: hidden; border-radius: 5px; background: #e8edf4; }.swp-progress span { display: block; height: 100%; border-radius: inherit; background: var(--blue); }.swp-health-facts { display: flex; flex-wrap: wrap; gap: 9px; margin-top: 12px; color: var(--muted); font-size: 11px; }.swp-health-facts .is-warning { color: var(--orange); }.swp-activity-list { display: grid; gap: 11px; margin: 15px 0 0; padding: 0; list-style: none; }.swp-activity-list li { display: flex; align-items: flex-start; gap: 7px; }.swp-activity-list i, .swp-legend-dot { width: 7px; height: 7px; flex: 0 0 auto; margin-top: 5px; border-radius: 50%; background: var(--blue); }.swp-activity-list i.is-green, .swp-legend-dot.is-green { background: var(--green); }.swp-activity-list i.is-orange, .swp-legend-dot.is-warning { background: #df9630; }.swp-activity-list span { display: grid; min-width: 0; gap: 2px; }.swp-activity-list strong { overflow: hidden; font-size: 11px; font-weight: 600; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }.swp-activity-list small { color: var(--faint); font-size: 10px; }.swp-detail-wrap { min-width: 0; }.swp-detail { display: grid; min-width: 0; gap: 14px; }.swp-detail-heading h3 { margin: 0; font-size: 19px; }.swp-detail-heading p:last-child { max-width: 680px; margin: 5px 0 0; color: var(--muted); font-size: 12px; line-height: 1.55; }.swp-detail-toolbar { justify-content: space-between; }.swp-filter-chip { display: inline-flex; min-height: 30px; align-items: center; padding: 0 10px; border: 1px solid var(--line); border-radius: 5px; background: #fff; color: var(--muted); font-size: 11px; }.swp-filter-chip.is-selected { border-color: #c6d5f6; background: var(--blue-soft); color: #1f50b2; }.swp-detail-columns, .swp-period-layout { display: grid; min-width: 0; grid-template-columns: minmax(0, 1fr) minmax(240px, .42fr); gap: 13px; }.swp-side-note { align-content: start; }.swp-side-note .swp-panel-icon { margin-bottom: 12px; }.swp-side-note h3 { margin: 0; font-size: 15px; }.swp-side-note p { margin: 7px 0 16px; color: var(--muted); font-size: 12px; line-height: 1.55; }.swp-data-list { display: grid; margin-top: 13px; }.swp-data-row, .swp-subject-row { display: grid; min-width: 0; grid-template-columns: minmax(0, 1fr) auto 28px; align-items: center; gap: 10px; padding: 11px 0; border-top: 1px solid var(--line); }.swp-data-row > div { display: grid; min-width: 0; gap: 3px; }.swp-data-row strong, .swp-subject-row strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }.swp-data-row small { overflow: hidden; color: var(--muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.swp-status-pill { display: inline-flex; min-height: 22px; align-items: center; justify-content: center; padding: 0 7px; border-radius: 4px; background: var(--soft); color: var(--muted); font-size: 10px; white-space: nowrap; }.swp-status-pill.is-green { background: var(--green-soft); color: var(--green); }.swp-status-pill.is-orange { background: var(--orange-soft); color: var(--orange); }.swp-row-more { display: inline-grid; width: 27px; height: 27px; place-items: center; border: 1px solid transparent; border-radius: 5px; background: transparent; color: var(--muted); cursor: pointer; }.swp-row-more:hover { border-color: var(--line); background: var(--soft); color: var(--blue); }.swp-inline-link { display: inline-flex; align-items: center; gap: 5px; margin-top: 12px; padding: 0; border: 0; background: transparent; color: var(--blue); font-size: 11px; cursor: pointer; }.swp-inline-link:hover { text-decoration: underline; }.swp-period-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; margin-top: 14px; }.swp-period-cell { display: grid; min-height: 52px; align-content: center; gap: 3px; padding: 8px 9px; border: 1px solid var(--line); border-radius: 5px; background: var(--soft); }.swp-period-cell.is-break { border-color: #d7c9ef; background: #f7f2ff; }.swp-period-cell span, .swp-period-cell small { color: var(--muted); font-size: 10px; }.swp-period-cell strong { font-size: 11px; }.swp-period-foot, .swp-table-foot { display: flex; align-items: center; gap: 7px; margin-top: 13px; padding-top: 12px; border-top: 1px solid var(--line); color: var(--green); font-size: 11px; }.swp-segmented { display: inline-flex; min-width: 0; overflow: hidden; border: 1px solid var(--line); border-radius: 5px; }.swp-segmented button { display: inline-flex; min-height: 30px; align-items: center; gap: 5px; padding: 0 9px; border: 0; border-right: 1px solid var(--line); background: #fff; color: var(--muted); font-size: 11px; cursor: pointer; }.swp-segmented button:last-child { border-right: 0; }.swp-segmented button.is-active { background: var(--blue-soft); color: #1f50b2; font-weight: 700; }.swp-subject-list { display: grid; margin-top: 12px; }.swp-subject-row { grid-template-columns: 25px minmax(0, 1fr) auto 28px; }.swp-subject-row > span:nth-child(3) { color: var(--muted); font-size: 11px; }.swp-subject-mark { display: grid; width: 24px; height: 24px; place-items: center; border-radius: 5px; color: #fff; font-size: 11px; font-weight: 800; }.swp-subject-mark.is-blue { background: var(--blue); }.swp-subject-mark.is-green { background: var(--green); }.swp-subject-mark.is-purple { background: var(--purple); }.swp-subject-mark.is-orange { background: #cf8630; }.swp-table-head, .swp-assignment-row { display: grid; grid-template-columns: 1fr 1.2fr 1.1fr auto 28px; align-items: center; gap: 9px; }.swp-table-head { padding: 0 0 9px; color: var(--faint); font-size: 10px; }.swp-assignment-table { border-top: 1px solid var(--line); }.swp-assignment-row { min-height: 48px; border-bottom: 1px solid var(--line); font-size: 11px; }.swp-assignment-row span { color: var(--muted); }.swp-assignment-row span.is-empty { color: var(--orange); }.swp-table-foot { color: var(--orange); }.swp-auto-command { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 15px; padding: 16px 17px; border: 1px solid #cddaf0; border-radius: 7px; background: #fff; }.swp-auto-score { display: flex; min-width: 0; align-items: center; gap: 13px; }.swp-score-ring { display: grid; width: 62px; height: 62px; flex: 0 0 auto; place-items: center; align-content: center; border: 5px solid #cfe0ff; border-right-color: var(--blue); border-radius: 50%; color: var(--blue); }.swp-score-ring strong { font-size: 19px; line-height: 1; }.swp-score-ring small { margin-top: 3px; color: var(--muted); font-size: 9px; }.swp-auto-score > div { display: grid; min-width: 0; gap: 4px; }.swp-auto-score > div > strong { font-size: 15px; }.swp-auto-score p { margin: 0; color: var(--muted); font-size: 11px; }.swp-auto-run { min-height: 41px; padding-inline: 16px; }.swp-auto-check-grid { display: grid; min-width: 0; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }.swp-auto-check { display: flex; min-width: 0; min-height: 74px; align-items: center; gap: 9px; padding: 12px; border: 1px solid var(--line); border-radius: 6px; background: #fff; color: var(--blue); text-align: left; cursor: pointer; }.swp-auto-check:hover { border-color: #b9c9ea; background: var(--blue-soft); }.swp-auto-check > span { display: grid; min-width: 0; gap: 4px; }.swp-auto-check strong { color: var(--ink); font-size: 12px; }.swp-auto-check small { overflow: hidden; color: var(--muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.swp-auto-check > svg:last-child { margin-left: auto; flex: 0 0 auto; }.swp-auto-check.is-pass { border-color: #b7dfca; background: var(--green-soft); color: var(--green); }.swp-preflight-panel { padding: 16px; }.swp-check-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; margin-top: 14px; }.swp-check-list > div { display: grid; grid-template-columns: 18px minmax(0, 1fr) auto; align-items: center; gap: 6px; padding: 9px; border: 1px solid var(--line); border-radius: 5px; color: var(--green); font-size: 11px; }.swp-check-list > div:nth-child(3) { color: var(--orange); }.swp-check-list span { color: var(--muted); }.swp-check-list strong { color: var(--ink); font-size: 10px; }.swp-auto-subpanel { display: grid; gap: 13px; padding: 15px; border: 1px solid #cddaf0; border-radius: 7px; background: #fafdff; }.swp-subpanel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }.swp-subpanel-head h3 { margin: 0; font-size: 15px; }.swp-calendar-checks { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }.swp-calendar-checks > div { display: flex; min-width: 0; align-items: flex-start; gap: 7px; padding: 10px; border: 1px solid var(--line); border-radius: 5px; background: #fff; color: var(--green); }.swp-calendar-checks > div.is-warning { border-color: #efd3a4; background: var(--orange-soft); color: var(--orange); }.swp-calendar-checks span { display: grid; min-width: 0; gap: 3px; }.swp-calendar-checks strong { color: var(--ink); font-size: 11px; }.swp-calendar-checks small { color: var(--muted); font-size: 10px; line-height: 1.4; }.swp-resource-actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }.swp-resource-actions button { display: flex; min-width: 0; align-items: center; gap: 8px; padding: 11px; border: 1px solid var(--line); border-radius: 5px; background: #fff; color: var(--blue); text-align: left; cursor: pointer; }.swp-resource-actions button:hover { border-color: #b9c9ea; background: var(--blue-soft); }.swp-resource-actions span { display: grid; min-width: 0; gap: 3px; }.swp-resource-actions strong { color: var(--ink); font-size: 11px; }.swp-resource-actions small { overflow: hidden; color: var(--muted); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }.swp-resource-actions button > svg:last-child { margin-left: auto; flex: 0 0 auto; }.swp-subpanel-actions { justify-content: flex-end; }

/* Variant B */
.swp-b-layout { display: grid; min-width: 0; grid-template-columns: 238px minmax(0, 1fr); align-items: stretch; border: 1px solid var(--line); border-radius: 7px; background: #fff; overflow: hidden; box-shadow: 0 1px 2px rgb(28 39 56 / 4%); }.swp-b-rail { min-width: 0; padding: 15px 12px; border-right: 1px solid var(--line); background: #fbfcfe; }.swp-b-rail-title { display: grid; gap: 3px; margin: 2px 7px 13px; }.swp-b-rail-title span { font-size: 13px; font-weight: 800; }.swp-b-rail-title small { color: var(--faint); font-size: 10px; }.swp-b-step { display: grid; width: 100%; min-width: 0; grid-template-columns: 27px minmax(0, 1fr) 14px; align-items: center; gap: 8px; margin: 3px 0; padding: 10px 8px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: var(--muted); text-align: left; cursor: pointer; }.swp-b-step:hover { background: var(--soft); }.swp-b-step.is-active { border-color: #c6d5f6; background: var(--blue-soft); color: #1f50b2; }.swp-b-step.is-done { color: var(--green); }.swp-b-step.is-blocked { color: var(--orange); }.swp-b-step-number { display: grid; width: 25px; height: 25px; place-items: center; border: 1px solid currentColor; border-radius: 50%; font-size: 10px; font-weight: 800; }.swp-b-step > span:nth-child(2) { display: grid; min-width: 0; gap: 3px; }.swp-b-step strong { font-size: 12px; }.swp-b-step small { overflow: hidden; color: var(--faint); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.swp-b-step > svg { margin-left: auto; }.swp-b-rail-foot { display: flex; align-items: center; gap: 6px; margin: 22px 7px 0; color: var(--orange); font-size: 10px; }.swp-b-detail { min-width: 0; padding: 22px; }.swp-b-overview { display: grid; gap: 17px; }.swp-b-overview-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 15px; }.swp-b-overview-head h3 { margin: 0; font-size: 21px; }.swp-b-overview-head p:last-child { margin: 6px 0 0; color: var(--muted); font-size: 12px; }.swp-b-stat-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }.swp-b-stat-row > div { display: grid; gap: 4px; padding: 16px 13px; border-right: 1px solid var(--line); }.swp-b-stat-row > div:last-child { border-right: 0; }.swp-b-stat-row strong { font-size: 22px; }.swp-b-stat-row span { color: var(--muted); font-size: 10px; }.swp-b-callout { display: flex; align-items: flex-start; gap: 9px; padding: 13px; border-left: 3px solid #df9630; background: var(--orange-soft); color: var(--orange); }.swp-b-callout div { display: grid; gap: 4px; }.swp-b-callout strong { color: var(--ink); font-size: 12px; }.swp-b-callout span { color: var(--muted); font-size: 11px; line-height: 1.45; }

/* Variant C */
.swp-c-layout { display: grid; min-width: 0; grid-template-columns: 275px minmax(0, 1fr); align-items: start; gap: 13px; }.swp-c-overview, .swp-c-detail { min-width: 0; border: 1px solid var(--line); border-radius: 7px; background: #fff; }.swp-c-overview { padding: 16px 13px; }.swp-c-overview-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }.swp-c-overview-title h3 { margin: 0; font-size: 16px; }.swp-c-progress { display: grid; grid-template-columns: auto 1fr; align-items: baseline; gap: 5px 8px; margin: 17px 7px 14px; }.swp-c-progress strong { color: var(--blue); font-size: 26px; }.swp-c-progress > span { color: var(--muted); font-size: 10px; }.swp-c-progress .swp-progress { grid-column: 1 / -1; width: 100%; margin-top: 2px; }.swp-c-step { display: grid; width: 100%; min-width: 0; grid-template-columns: 26px minmax(0, 1fr) 14px; align-items: center; gap: 8px; margin: 3px 0; padding: 10px 7px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: var(--muted); text-align: left; cursor: pointer; }.swp-c-step:hover { background: var(--soft); }.swp-c-step.is-active { border-color: #c6d5f6; background: var(--blue-soft); color: #1f50b2; }.swp-c-step.is-done { color: var(--green); }.swp-c-step.is-blocked { color: var(--orange); }.swp-c-index { display: grid; width: 24px; height: 24px; place-items: center; border: 1px solid currentColor; border-radius: 50%; font-size: 9px; font-weight: 800; }.swp-c-step > span:nth-child(2) { display: grid; min-width: 0; gap: 3px; }.swp-c-step strong { font-size: 12px; }.swp-c-step small { overflow: hidden; color: var(--faint); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.swp-c-step > svg { margin-left: auto; }.swp-c-activity { margin-top: 19px; padding-top: 15px; border-top: 1px solid var(--line); }.swp-c-activity .swp-panel-heading { gap: 7px; }.swp-c-activity .swp-panel-icon { width: 26px; height: 26px; }.swp-c-detail { min-height: 470px; padding: 22px; }.swp-c-empty { display: grid; min-height: 420px; place-items: center; align-content: center; gap: 7px; text-align: center; }.swp-empty-icon { display: grid; width: 49px; height: 49px; place-items: center; margin-bottom: 7px; border-radius: 8px; background: var(--blue-soft); color: var(--blue); }.swp-c-empty h3 { margin: 0; font-size: 21px; }.swp-c-empty p:last-of-type { max-width: 450px; margin: 0 0 10px; color: var(--muted); font-size: 12px; line-height: 1.55; }

.swp-overlay { position: fixed; z-index: 40; inset: 0; display: grid; place-items: center; padding: 20px; background: rgb(20 31 49 / 42%); }.swp-modal { width: min(530px, 100%); max-height: calc(100vh - 40px); overflow: auto; padding: 20px; border: 1px solid var(--line); border-radius: 7px; background: #fff; box-shadow: 0 16px 40px rgb(20 31 49 / 20%); }.swp-modal > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }.swp-modal h2 { margin: 0; font-size: 19px; }.swp-modal-copy { margin: 12px 0 16px; color: var(--muted); font-size: 12px; line-height: 1.6; }.swp-modal-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; }.swp-modal-summary > div { display: grid; gap: 4px; padding: 11px; border: 1px solid var(--line); border-radius: 5px; background: var(--soft); }.swp-modal-summary span { color: var(--muted); font-size: 10px; }.swp-modal-summary strong { font-size: 12px; }.swp-modal-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 15px; }.swp-modal-fields label { display: grid; gap: 6px; color: var(--muted); font-size: 11px; }.swp-modal-fields input { min-height: 34px; box-sizing: border-box; padding: 0 9px; border: 1px solid #c6d0dc; border-radius: 5px; color: var(--ink); background: #fff; font-size: 12px; }.swp-modal-links { display: grid; gap: 5px; margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--line); }.swp-modal-links button { display: flex; min-width: 0; align-items: center; gap: 8px; padding: 9px 0; border: 0; background: transparent; color: var(--blue); text-align: left; cursor: pointer; }.swp-modal-links button > svg:last-child { margin-left: auto; }.swp-modal footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--line); }
.swp-switcher { position: fixed; z-index: 60; bottom: 18px; left: 50%; display: flex; width: min(330px, calc(100vw - 30px)); min-height: 42px; align-items: center; gap: 6px; transform: translateX(-50%); padding: 4px 6px; border: 1px solid #263a56; border-radius: 7px; background: #1c2a3d; color: #fff; box-shadow: 0 5px 16px rgb(13 26 45 / 22%); }.swp-switcher > button { display: grid; width: 31px; height: 31px; flex: 0 0 auto; place-items: center; border: 1px solid #4e6380; border-radius: 5px; background: transparent; color: #fff; cursor: pointer; }.swp-switcher > button:hover { background: #2a3d58; }.swp-switcher > div { display: grid; min-width: 0; flex: 1; gap: 1px; text-align: center; }.swp-switcher span { color: #aebdd0; font-size: 8px; letter-spacing: .08em; }.swp-switcher strong { overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.swp-switcher small { overflow: hidden; color: #c4cfdd; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.swp-scrim { display: none; }

@media (max-width: 1120px) { .swp-app { grid-template-columns: 64px minmax(0, 1fr); }.swp-brand { justify-content: center; padding-inline: 8px; }.swp-brand > span:nth-child(2), .swp-nav-label, .swp-nav-link:not(.is-active)::after, .swp-nav-link { font-size: 0; }.swp-brand > span:nth-child(2), .swp-school > span:last-child { display: none; }.swp-nav-link { justify-content: center; padding-inline: 0; }.swp-nav-link svg { width: 18px; height: 18px; }.swp-school { justify-content: center; padding-inline: 7px; }.swp-topbar { padding-inline: 16px; }.swp-overview-grid { grid-template-columns: minmax(0, 1fr) minmax(240px, .8fr); }.swp-activity-panel { grid-column: 1 / -1; min-height: auto; }.swp-c-layout { grid-template-columns: 240px minmax(0, 1fr); } }
@media (max-width: 900px) { .swp-content { padding-inline: 16px; }.swp-semester-context { grid-template-columns: minmax(0, 1fr) auto; }.swp-semester-stats { grid-column: 1 / -1; justify-content: flex-start; }.swp-semester-actions { grid-column: 2; grid-row: 1; }.swp-step-rail { grid-template-columns: repeat(5, minmax(115px, 1fr)); overflow-x: auto; }.swp-step-rail-item { min-width: 115px; }.swp-overview-grid, .swp-detail-columns, .swp-period-layout { grid-template-columns: minmax(0, 1fr); }.swp-side-note { display: grid; grid-template-columns: auto minmax(0, 1fr); column-gap: 10px; }.swp-side-note .swp-panel-icon { grid-row: 1 / span 2; margin: 0; }.swp-side-note p, .swp-side-note .swp-button { grid-column: 2; }.swp-b-layout, .swp-c-layout { grid-template-columns: minmax(0, 1fr); }.swp-b-rail { border-right: 0; border-bottom: 1px solid var(--line); }.swp-b-step { display: inline-grid; width: calc(20% - 6px); vertical-align: top; }.swp-b-step > svg, .swp-b-rail-foot { display: none; }.swp-b-step > span:nth-child(2) { display: none; }.swp-b-step-number { margin: 0 auto; }.swp-c-overview { order: 0; }.swp-c-detail { order: 1; }.swp-auto-check-grid, .swp-resource-actions, .swp-calendar-checks { grid-template-columns: repeat(2, minmax(0, 1fr)); }.swp-auto-check:last-child { grid-column: 1 / -1; } }
@media (max-width: 680px) { .swp-app { display: block; }.swp-sidebar { position: fixed; z-index: 55; inset: 0 auto 0 0; width: 238px; transform: translateX(-100%); transition: transform .18s ease; box-shadow: 10px 0 24px rgb(20 31 49 / 16%); }.swp-sidebar.is-open { transform: translateX(0); }.swp-sidebar .swp-brand > span:nth-child(2), .swp-sidebar .swp-school > span:last-child, .swp-sidebar .swp-nav-label, .swp-sidebar .swp-nav-link { font-size: initial; }.swp-brand { justify-content: flex-start; padding-inline: 16px; }.swp-brand > span:nth-child(2), .swp-school > span:last-child { display: grid; }.swp-nav-link { justify-content: flex-start; padding-inline: 10px; font-size: 12px; }.swp-mobile-close, .swp-menu-button { display: inline-grid !important; }.swp-scrim { position: fixed; z-index: 50; inset: 0; display: block; background: rgb(20 31 49 / 38%); }.swp-main { min-height: 100vh; }.swp-topbar { min-height: 60px; padding-inline: 11px; }.swp-breadcrumb > span:first-child, .swp-dev-badge, .swp-top-semester { display: none; }.swp-top-actions { gap: 6px; }.swp-content { padding: 14px 11px 88px; }.swp-page-head, .swp-variant-heading { align-items: flex-start; flex-direction: column; gap: 12px; }.swp-page-head h1 { font-size: 23px; }.swp-page-actions { width: 100%; justify-content: flex-start; }.swp-semester-context { grid-template-columns: minmax(0, 1fr); gap: 13px; padding: 14px; }.swp-semester-actions, .swp-semester-stats { grid-column: auto; grid-row: auto; justify-content: flex-start; }.swp-semester-actions { width: 100%; }.swp-semester-actions .swp-button-primary { flex: 1; }.swp-notice { align-items: flex-start; flex-wrap: wrap; }.swp-notice-meta { width: 100%; margin-left: 23px; }.swp-step-rail { display: flex; overflow-x: auto; }.swp-step-rail-item { min-width: 132px; }.swp-overview-grid { grid-template-columns: minmax(0, 1fr); }.swp-b-detail, .swp-c-detail { padding: 16px; }.swp-b-step { width: calc(20% - 5px); min-height: 54px; padding: 7px 4px; }.swp-b-step-number { width: 23px; height: 23px; }.swp-b-step > span:nth-child(2) { display: none; }.swp-detail-toolbar { align-items: stretch; flex-direction: column; }.swp-detail-toolbar .swp-button { align-self: flex-start; }.swp-table-head { display: none; }.swp-assignment-row { grid-template-columns: minmax(0, 1fr) auto 28px; gap: 5px; padding: 10px 0; }.swp-assignment-row > span:nth-child(2) { grid-column: 1; grid-row: 2; }.swp-assignment-row > span:nth-child(3) { grid-column: 1; grid-row: 3; }.swp-assignment-row > .swp-status-pill { grid-column: 2; grid-row: 1 / span 2; }.swp-auto-command { align-items: flex-start; flex-direction: column; }.swp-auto-run { width: 100%; }.swp-auto-check-grid, .swp-resource-actions, .swp-calendar-checks, .swp-check-list, .swp-modal-summary, .swp-modal-fields { grid-template-columns: minmax(0, 1fr); }.swp-auto-check:last-child { grid-column: auto; }.swp-period-grid { grid-template-columns: minmax(0, 1fr); }.swp-modal { padding: 16px; }.swp-switcher { bottom: 11px; width: min(280px, calc(100vw - 22px)); }.swp-switcher small { display: none; } }
@media (max-width: 400px) { .swp-semester-main h2 { font-size: 15px; }.swp-semester-stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }.swp-b-step { min-width: 0; }.swp-b-step-number { width: 22px; height: 22px; } }
</style>
