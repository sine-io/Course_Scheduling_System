<script setup lang="ts">
// PROTOTYPE ONLY: Question: can MyZan's five-step memory path become a six-stage
// short path without a cross-page wizard? Three variants share ?variant=.
// Remove this route after a direction is chosen and rewrite the winner for production.
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Bell,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  ClipboardList,
  Clock3,
  Copy,
  FileCheck2,
  Filter,
  History,
  LayoutDashboard,
  ListChecks,
  LockKeyhole,
  Menu,
  MoreHorizontal,
  Play,
  RefreshCw,
  Search,
  Settings2,
  SlidersHorizontal,
  Sparkles,
  Table2,
  Users,
  WandSparkles,
  X,
  Zap,
} from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

type VariantKey = 'A' | 'B' | 'C'
type StageKey = 'prepare' | 'assignments' | 'rules' | 'schedule' | 'review' | 'publish'
type IssueKey = 'assignments' | 'preflight' | 'unscheduled' | 'conflict'
type RunState = 'idle' | 'running' | 'done'

interface VariantMeta {
  key: VariantKey
  label: string
  subtitle: string
}

interface ActivityEntry {
  id: number
  time: string
  text: string
  tone: 'blue' | 'green' | 'orange' | 'red' | 'neutral'
}

interface PrototypeState {
  stage: StageKey
  runState: RunState
  dataReady: boolean
  assignmentTotal: number
  assignmentReady: number
  rulesReady: boolean
  preplaceTotal: number
  preplaceReady: number
  preflightPassed: boolean
  generated: boolean
  completion: number
  remaining: number
  conflicts: number
  locked: number
  preflightErrors: number
  preflightWarnings: number
  draftStatus: '草稿' | '待发布' | '已发布'
  lastAction: string
  activity: ActivityEntry[]
}

const variants: VariantMeta[] = [
  { key: 'A', label: '流程指挥台', subtitle: '用一条短路径告诉你现在该做什么' },
  { key: 'B', label: '问题收件箱', subtitle: '先处理阻塞项，再推进课表状态' },
  { key: 'C', label: '课表画布', subtitle: '把排课与检查放在同一张可视网格里' },
]

const stageMeta: Array<{ key: StageKey; label: string; short: string }> = [
  { key: 'prepare', label: '学期准备', short: '准备' },
  { key: 'assignments', label: '教学任务', short: '任务' },
  { key: 'rules', label: '规则与预排', short: '规则/预排' },
  { key: 'schedule', label: '自动排课', short: '生成' },
  { key: 'review', label: '检查调整', short: '检查' },
  { key: 'publish', label: '发布与输出', short: '发布' },
]

const route = useRoute()
const router = useRouter()
const showPrototypeSwitcher = import.meta.env.DEV
const batchPanelOpen = ref(false)
const publishPanelOpen = ref(false)
const forcePublishReason = ref('')
const advancedRulesOpen = ref(false)
const selectedIssue = ref<IssueKey>('assignments')
const selectedCell = ref('周二 · 第 3 节')
const runTimer = ref<number | null>(null)
const activitySequence = ref(4)

const state = reactive<PrototypeState>({
  stage: 'assignments',
  runState: 'idle',
  dataReady: true,
  assignmentTotal: 184,
  assignmentReady: 176,
  rulesReady: false,
  preplaceTotal: 8,
  preplaceReady: 6,
  preflightPassed: false,
  generated: false,
  completion: 92,
  remaining: 14,
  conflicts: 3,
  locked: 6,
  preflightErrors: 0,
  preflightWarnings: 2,
  draftStatus: '草稿',
  lastAction: '已加载示范学期与上次课表预览',
  activity: [
    { id: 1, time: '09:24', text: '上次课表预览已加载，保留 6 个锁定课位', tone: 'blue' },
    { id: 2, time: '09:18', text: '导入 176 / 184 项教学任务', tone: 'green' },
    { id: 3, time: '09:10', text: '发现 2 条非阻断排课提醒', tone: 'orange' },
  ],
})

const currentVariant = computed<VariantKey>(() => {
  const value = String(route.query.variant ?? route.params.variant ?? 'A').toUpperCase()
  return value === 'B' || value === 'C' ? value : 'A'
})

const currentVariantMeta = computed(() => variants.find((item) => item.key === currentVariant.value) ?? variants[0])
const progressLabel = computed(() => `${state.completion}%`)
const assignmentLabel = computed(() => `${state.assignmentReady} / ${state.assignmentTotal}`)
const issueCount = computed(() => state.remaining + state.conflicts + state.preflightWarnings + (state.assignmentTotal - state.assignmentReady))
const canConfirmPublish = computed(() => state.generated
  && state.preflightPassed
  && state.rulesReady
  && state.assignmentReady >= state.assignmentTotal)
const canSubmitPublish = computed(() => canConfirmPublish.value
  && (!state.remaining || forcePublishReason.value.trim().length > 0))
const selectedIssueLabel = computed(() => ({
  assignments: '教学任务缺项',
  preflight: '排课提醒',
  unscheduled: '未排课时',
  conflict: '教室/场地冲突',
}[selectedIssue.value]))
const selectedIssueTone = computed(() => ({
  assignments: 'red',
  preflight: 'orange',
  unscheduled: 'blue',
  conflict: 'blue',
}[selectedIssue.value]))
const selectedIssueHeading = computed(() => {
  switch (selectedIssue.value) {
    case 'assignments': {
      const missing = state.assignmentTotal - state.assignmentReady
      return missing ? `还有 ${missing} 项教学任务没有完整信息` : '教学任务已完整，可以确认规则与预排'
    }
    case 'preflight': return state.preflightWarnings ? `有 ${state.preflightWarnings} 条规则值得在排课前确认` : '排课前置检查已通过'
    case 'unscheduled': return state.remaining ? `还有 ${state.remaining} 节课没有找到合适时段` : '所有课时均已安排'
    case 'conflict': return state.conflicts ? '机房在周二第 3 节被两个班同时占用' : '教室/场地冲突已清零'
  }
  return ''
})
const selectedIssueBody = computed(() => {
  switch (selectedIssue.value) {
    case 'assignments': return state.assignmentTotal - state.assignmentReady
      ? '缺少教师或教室/场地的任务无法进入求解器，系统已经按年级聚合。'
      : '任务输入已完整，下一步是确认本次排课使用的规则版本。'
    case 'preflight': return state.preflightWarnings
      ? '这些提醒不会阻止生成，但处理后更容易得到均衡课表。'
      : '没有剩余提醒；如果输入发生变化，仍可重新运行前置检查。'
    case 'unscheduled': return state.remaining
      ? '可以只重排数学科目，不影响已经锁定的 6 个课位。'
      : '所有课时均已找到位置，可以进入发布检查。'
    case 'conflict': return state.conflicts
      ? '从教室/场地视角查看关联课程，调整后会实时重新检查冲突。'
      : '当前草稿没有教室/场地冲突，仍可从教室/场地视角复核容量。'
  }
  return ''
})

function stageIsDone(key: StageKey): boolean {
  switch (key) {
    case 'prepare': return state.dataReady
    case 'assignments': return state.assignmentReady >= state.assignmentTotal
    case 'rules': return state.rulesReady && state.preplaceReady >= state.preplaceTotal
    case 'schedule': return state.generated
    case 'review': return state.generated && state.remaining === 0 && state.conflicts === 0
    case 'publish': return state.draftStatus === '已发布'
  }
}

const stageState = (key: StageKey): 'done' | 'active' | 'blocked' | 'idle' => {
  if (stageIsDone(key)) return 'done'
  if (key === state.stage) {
    if (key === 'assignments' && state.assignmentReady < state.assignmentTotal) return 'blocked'
    if (key === 'schedule' && state.preflightErrors > 0) return 'blocked'
    return 'active'
  }
  return 'idle'
}

const commandCopy = computed(() => {
  if (!state.dataReady) {
    return { title: '先补齐学期准备，再进入排课', body: '作息、校历或基础数据还不完整，系统会把你带回对应页面。' }
  }
  if (state.stage === 'prepare') {
    return { title: '学期准备已完成，可以进入教学任务', body: '作息、校历和基础数据已具备；后续缺项会在教学任务和前置检查中单独提示。' }
  }
  if (state.assignmentReady < state.assignmentTotal || state.stage === 'assignments') {
    return { title: '先补齐教学任务，再确认规则与预排', body: '系统已定位缺项，不需要先浏览其他设置页面；完成后会进入规则与预排。' }
  }
  if (!state.rulesReady) {
    return { title: '确认这次排课使用的规则版本', body: '硬约束、软规则和来源会随草稿固定，确认后再处理需要固定的课位。' }
  }
  if (state.preplaceReady < state.preplaceTotal) {
    return { title: '确认固定课位，再运行自动排课', body: '把一定排、尽量排和不排的时段集中确认，合班与场室限制也会一并带入。' }
  }
  if (state.runState === 'running') {
    return { title: '正在生成当前学期课表', body: '可以等待全校结果，也可以在完成后从未排列表进入局部重排。' }
  }
  if (!state.preflightPassed) {
    return { title: '先运行排课前置检查，再开始生成', body: '阻断问题必须先处理；非阻断提醒会保留在发布检查中，由教务主任明确确认。' }
  }
  if (state.stage === 'schedule') {
    return { title: '前置检查已通过，可以生成课表草稿', body: '选择全校或局部范围开始求解；结果会保留未排课时和规则版本，供下一步检查。' }
  }
  if (state.stage === 'review') {
    return { title: '检查调整草稿，处理未排课时和冲突', body: '从班级、教师或教室/场地视角检查，锁定的课位不会被局部重排移动。' }
  }
  if (state.draftStatus === '已发布' && state.remaining > 0) {
    return { title: `课表已强制发布，${state.remaining} 节未排课时未进入正式课表`, body: '发布快照和强制发布审计已生成；可以继续查看输出，或复制版本后补排。' }
  }
  if (state.draftStatus === '已发布') {
    return { title: '课表已发布，可以查看输出', body: '已生成发布快照和通知；导出、打印和学期中调课与代课进入各自的业务入口。' }
  }
  if (state.stage === 'publish') {
    return { title: '检查调整已完成，可以确认发布', body: '发布检查会固定学期、版本和完整性结果，确认后生成不可变快照与审计记录。' }
  }
  return { title: '课表已生成，可以开始检查调整', body: '结果页会保留规则版本、锁定课位和未排列表，方便继续处理。' }
})

function nowLabel(): string {
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date())
}

function record(text: string, tone: ActivityEntry['tone'] = 'blue') {
  state.lastAction = text
  activitySequence.value += 1
  state.activity.unshift({ id: activitySequence.value, time: nowLabel(), text, tone })
  state.activity.splice(5)
}

function chooseVariant(key: VariantKey) {
  const query = { ...route.query, variant: key }
  void router.replace({ name: 'paike-flow-prototype', query })
  record(`切换到方案 ${key} · ${variants.find((item) => item.key === key)?.label ?? ''}`, 'neutral')
}

function cycleVariant(delta: number) {
  const index = variants.findIndex((item) => item.key === currentVariant.value)
  const nextIndex = (index + delta + variants.length) % variants.length
  chooseVariant(variants[nextIndex].key)
}

function onPrototypeKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target?.matches('input, textarea, select, [contenteditable="true"]')) return
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    cycleVariant(-1)
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    cycleVariant(1)
  }
}

function goToStage(stage: StageKey) {
  record(`打开「${stageMeta.find((item) => item.key === stage)?.label ?? stage}」业务入口，流程事实保持不变`, 'neutral')
}

function openBatchPanel() {
  if (state.assignmentReady >= state.assignmentTotal) {
    state.stage = 'rules'
    record('教学任务已完整，请确认规则版本', 'blue')
    return
  }
  batchPanelOpen.value = true
  record('打开教学任务批量编辑', 'blue')
}

function applyBatchPanel() {
  state.assignmentReady = state.assignmentTotal
  state.preflightWarnings = Math.max(0, state.preflightWarnings - 1)
  state.stage = 'rules'
  batchPanelOpen.value = false
  record('已复制上一班配置并补齐 8 项教学任务，进入规则确认', 'green')
}

function confirmRules() {
  if (state.assignmentReady < state.assignmentTotal) {
    state.stage = 'assignments'
    record('规则确认暂缓：仍有教学任务缺项', 'orange')
    return
  }
  state.rulesReady = true
  state.preflightWarnings = Math.max(0, state.preflightWarnings - 1)
  state.stage = 'rules'
  record('已确认规则集 v3：硬约束 12 条、偏好 5 条；请继续确认预排', 'green')
}

function confirmPreplace() {
  if (!state.rulesReady) {
    state.stage = 'rules'
    record('请先确认规则，再完成预排', 'orange')
    return
  }
  state.preplaceReady = state.preplaceTotal
  state.stage = 'schedule'
  record('已确认 8 个固定/尽量课位，规则与预排完成', 'green')
}

function runPreflight() {
  if (state.assignmentReady < state.assignmentTotal) {
    state.stage = 'assignments'
    record('前置检查未运行：请先补齐教学任务', 'orange')
    return
  }
  if (!state.rulesReady) {
    state.stage = 'rules'
    record('前置检查未运行：请先确认规则版本', 'orange')
    return
  }
  if (state.preplaceReady < state.preplaceTotal) {
    state.stage = 'rules'
    record('前置检查未运行：请先完成规则与预排', 'orange')
    return
  }
  state.preflightErrors = 0
  state.preflightPassed = true
  state.stage = 'schedule'
  state.preflightWarnings = Math.max(0, state.preflightWarnings - 1)
  record(`前置检查完成：无阻断错误，剩 ${state.preflightWarnings} 条提醒`, 'green')
}

function openWorkbench() {
  if (state.generated) state.stage = 'review'
  record(state.generated ? '打开检查调整工作台' : '打开上次课表预览（生成新草稿后将更新）', 'blue')
}

function runAutoSchedule(scope: 'all' | 'subject' = 'all') {
  if (state.runState === 'running') return
  const isLocalRepair = scope === 'subject' && state.generated
  if (scope === 'subject' && !isLocalRepair) {
    record('请先生成课表草稿，再运行局部重排', 'orange')
    return
  }
  if (scope === 'all' && !state.preflightPassed) {
    state.stage = 'schedule'
    record('开始生成前需要先完成排课前置检查', 'orange')
    return
  }
  if (state.assignmentReady < state.assignmentTotal || !state.rulesReady || state.preplaceReady < state.preplaceTotal) {
    state.stage = state.assignmentReady < state.assignmentTotal
      ? 'assignments'
      : 'rules'
    record('当前输入尚未就绪，已定位到需要处理的阶段', 'orange')
    return
  }
  state.stage = 'schedule'
  state.runState = 'running'
  state.generated = false
  record(scope === 'all' ? '开始全校自动排课' : '开始重排数学科目', 'blue')
  if (runTimer.value !== null) window.clearTimeout(runTimer.value)
  runTimer.value = window.setTimeout(() => {
    state.runState = 'done'
    state.generated = true
    if (isLocalRepair) {
      state.stage = 'publish'
      state.completion = 100
      state.remaining = 0
      state.conflicts = 0
      state.draftStatus = '待发布'
      record('局部重排完成：剩余课时与冲突已清零，可以发布', 'green')
    } else {
      state.stage = 'review'
      state.completion = 98
      state.remaining = 4
      state.conflicts = 1
      record('自动排课完成：98% 课时已安排', 'green')
    }
    runTimer.value = null
  }, 850)
}

function lockSelectedCell() {
  state.locked += 1
  record(`已锁定 ${selectedCell.value} 的英语课`, 'green')
}

function selectIssue(issue: IssueKey) {
  selectedIssue.value = issue
  record(`查看问题：${selectedIssueLabel.value}`, 'orange')
}

function openPublishPanel() {
  if (state.draftStatus === '已发布') {
    record('课表已发布，发布快照保持只读', 'neutral')
    return
  }
  forcePublishReason.value = ''
  publishPanelOpen.value = true
  record('打开发布前检查', 'blue')
}

function confirmPublish() {
  if (state.draftStatus === '已发布' || !canSubmitPublish.value) return
  const publishReason = forcePublishReason.value.trim()
  publishPanelOpen.value = false
  state.stage = 'publish'
  state.draftStatus = '已发布'
  record(
    state.remaining
      ? `已强制发布「春季学期 · 初版课表」；${state.remaining} 节未排课时未进入正式课表；原因：${publishReason}`
      : '已发布「春季学期 · 初版课表」并生成站内通知',
    state.remaining ? 'orange' : 'green',
  )
}

function openOutput() {
  record('打开已发布课表的导出与打印入口', 'blue')
}

function resetDemo() {
  state.stage = 'assignments'
  state.runState = 'idle'
  state.dataReady = true
  state.assignmentReady = 176
  state.rulesReady = false
  state.preplaceReady = 6
  state.preflightPassed = false
  state.generated = false
  state.completion = 92
  state.remaining = 14
  state.conflicts = 3
  state.locked = 6
  state.preflightErrors = 0
  state.preflightWarnings = 2
  state.draftStatus = '草稿'
  forcePublishReason.value = ''
  record('已重置示范状态', 'neutral')
}

onMounted(() => window.addEventListener('keydown', onPrototypeKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onPrototypeKeydown)
  if (runTimer.value !== null) window.clearTimeout(runTimer.value)
})
</script>

<template>
  <div class="prototype-app" data-testid="paike-flow-prototype">
    <aside class="prototype-sidebar" aria-label="原型导航">
      <div class="prototype-brand">
        <span class="prototype-brand-mark" aria-hidden="true"><CalendarDays :size="19" /></span>
        <span>
          <strong>教务排课</strong>
          <small>流程原型</small>
        </span>
        <button class="prototype-icon-button prototype-sidebar-close" type="button" title="收起导航" aria-label="收起导航">
          <Menu :size="17" />
        </button>
      </div>

      <nav class="prototype-nav">
        <p class="prototype-nav-label">排课流程</p>
        <a class="prototype-nav-link is-active" href="#" @click.prevent="record('停留在排课工作台', 'neutral')">
          <LayoutDashboard :size="17" />
          <span>排课工作台</span>
        </a>
        <a class="prototype-nav-link" href="#" @click.prevent="record('查看教学任务入口', 'neutral')">
          <ClipboardList :size="17" />
          <span>教学任务</span>
          <small v-if="state.assignmentTotal - state.assignmentReady">{{ state.assignmentTotal - state.assignmentReady }}</small>
        </a>
        <a class="prototype-nav-link" href="#" @click.prevent="record('查看规则与预排入口', 'neutral')">
          <Settings2 :size="17" />
          <span>规则与预排</span>
        </a>
        <a class="prototype-nav-link" href="#" @click.prevent="record('查看发布与输出入口', 'neutral')">
          <History :size="17" />
          <span>版本与发布</span>
        </a>
        <p class="prototype-nav-label prototype-nav-label-spaced">日常运行</p>
        <a class="prototype-nav-link" href="#" @click.prevent="record('查看今日看板入口', 'neutral')">
          <Clock3 :size="17" />
          <span>今日看板</span>
        </a>
        <a class="prototype-nav-link" href="#" @click.prevent="record('查看通知入口', 'neutral')">
          <Bell :size="17" />
          <span>通知</span>
          <small>3</small>
        </a>
      </nav>

      <div class="prototype-school">
        <span class="prototype-school-mark" aria-hidden="true"><Users :size="16" /></span>
        <span>
          <strong>示范学校</strong>
          <small>2026 春季学期</small>
        </span>
      </div>
    </aside>

    <div class="prototype-main">
      <header class="prototype-topbar">
        <button class="prototype-icon-button prototype-menu-button" type="button" title="打开导航" aria-label="打开导航">
          <Menu :size="18" />
        </button>
        <div class="prototype-breadcrumb">
          <span>排课流程</span>
          <ArrowRight :size="14" aria-hidden="true" />
          <strong>排课主流程</strong>
          <span class="prototype-dev-badge">PROTOTYPE</span>
        </div>
        <div class="prototype-topbar-actions">
          <span class="prototype-semester"><CalendarDays :size="15" /> 2026 春季学期</span>
          <div v-if="showPrototypeSwitcher" class="prototype-switcher" aria-label="切换原型方案">
            <button type="button" class="prototype-switcher-arrow" title="上一个方案" aria-label="上一个方案" @click="cycleVariant(-1)"><ArrowLeft :size="16" /></button>
            <div class="prototype-switcher-label"><span>原型方案 {{ currentVariant }}</span><strong>{{ currentVariantMeta.label }}</strong><small>{{ currentVariantMeta.subtitle }}</small></div>
            <button type="button" class="prototype-switcher-arrow" title="下一个方案" aria-label="下一个方案" @click="cycleVariant(1)"><ArrowRight :size="16" /></button>
          </div>
          <button class="prototype-icon-button" type="button" title="通知" aria-label="通知" @click="record('查看 3 条未读通知', 'orange')">
            <Bell :size="17" />
            <i class="prototype-notification-dot" aria-hidden="true" />
          </button>
          <span class="prototype-user"><span class="prototype-avatar">李</span><span>李主任</span></span>
        </div>
      </header>

      <main class="prototype-content">
        <div class="prototype-context-line">
          <span>生产流程采用 MyZan 五步路径；此原型保留用于复杂场景评审。</span>
          <button type="button" class="prototype-text-button" @click="resetDemo">
            <RefreshCw :size="14" /> 重置演示状态
          </button>
        </div>

        <section v-if="currentVariant === 'A'" class="prototype-variant variant-a" data-testid="variant-a">
          <header class="variant-page-head">
            <div>
              <p class="prototype-eyebrow">方案 A · {{ currentVariantMeta.label }}</p>
              <h1>春季学期排课工作台</h1>
              <p>保留一条短路径，状态来自现有业务数据，复杂设置仍可展开查看。</p>
            </div>
            <div class="variant-head-actions">
              <span class="draft-status" :class="`is-${state.draftStatus === '已发布' ? 'published' : 'draft'}`">
                <span class="status-dot" /> {{ state.draftStatus }} · 春季学期初版
              </span>
              <button type="button" class="button button-secondary" :disabled="state.draftStatus === '已发布'" @click="openPublishPanel">
                <FileCheck2 :size="15" /> {{ state.draftStatus === '已发布' ? '已发布' : '检查并发布' }}
              </button>
            </div>
          </header>

          <nav class="flow-rail" aria-label="排课流程">
            <button
              v-for="(stage, index) in stageMeta"
              :key="stage.key"
              type="button"
              class="flow-step"
              :class="`is-${stageState(stage.key)}`"
              @click="goToStage(stage.key)"
            >
              <span class="flow-step-index">
                <Check v-if="stageState(stage.key) === 'done'" :size="14" />
                <span v-else>{{ index + 1 }}</span>
              </span>
              <span><strong>{{ stage.label }}</strong><small>{{ stage.short }}</small></span>
              <ArrowRight v-if="index < stageMeta.length - 1" class="flow-step-arrow" :size="14" aria-hidden="true" />
            </button>
          </nav>

          <div class="a-command-grid">
            <section class="command-panel" aria-labelledby="command-title">
              <div class="command-panel-kicker"><Sparkles :size="15" /> 现在做什么</div>
              <h2 id="command-title">{{ commandCopy.title }}</h2>
              <p>{{ commandCopy.body }}</p>
              <div class="command-primary-row">
                <button v-if="state.assignmentReady < state.assignmentTotal" type="button" class="button button-primary" @click="openBatchPanel">
                  <Copy :size="16" /> 批量补齐 8 项任务
                </button>
                <button v-else-if="!state.rulesReady" type="button" class="button button-primary" @click="confirmRules">
                  <Settings2 :size="16" /> 确认规则并进入预排
                </button>
                <button v-else-if="state.preplaceReady < state.preplaceTotal" type="button" class="button button-primary" @click="confirmPreplace">
                  <CheckCircle2 :size="16" /> 确认预排并进入检查
                </button>
                <button v-else-if="!state.preflightPassed" type="button" class="button button-primary" @click="runPreflight">
                  <ListChecks :size="16" /> 运行排课前置检查
                </button>
                <button v-else-if="state.runState === 'running'" type="button" class="button button-primary" disabled>
                  <RefreshCw class="is-spinning" :size="16" /> 正在生成课表
                </button>
                <button v-else-if="state.stage === 'review'" type="button" class="button button-primary" @click="runAutoSchedule('subject')">
                  <WandSparkles :size="16" /> 局部重排 {{ state.remaining + state.conflicts }} 个待处理项
                </button>
                <button v-else-if="state.stage === 'publish' && state.draftStatus !== '已发布'" type="button" class="button button-primary" @click="openPublishPanel">
                  <FileCheck2 :size="16" /> 检查并发布
                </button>
                <button v-else-if="state.draftStatus === '已发布'" type="button" class="button button-primary" @click="openOutput">
                  <ArrowUpRight :size="16" /> 查看输出入口
                </button>
                <button v-else type="button" class="button button-primary" @click="runAutoSchedule('all')">
                  <Play :size="16" /> 开始全校自动排课
                </button>
                <button type="button" class="button button-quiet" @click="state.stage === 'review' ? openWorkbench() : goToStage('assignments')">
                  {{ state.stage === 'review' ? '打开完整工作台' : '查看全部任务' }} <ArrowUpRight :size="14" />
                </button>
              </div>
              <div class="command-trust-row">
                <span><CheckCircle2 :size="14" /> 已自动保存</span>
                <span><LockKeyhole :size="14" /> {{ state.locked }} 个课位已锁定</span>
                <span><Zap :size="14" /> {{ state.rulesReady ? '规则版本 v3 已确认' : '规则版本待确认' }}</span>
              </div>
            </section>

            <aside class="a-state-panel" aria-label="当前状态">
              <div class="panel-heading-line"><div><p class="panel-kicker">当前状态</p><h2>课表健康度</h2></div><MoreHorizontal :size="18" /></div>
              <div class="health-score"><strong>{{ progressLabel }}</strong><span>课时已安排</span></div>
              <div class="health-meter"><span :style="{ width: `${state.completion}%` }" /></div>
              <dl class="compact-stats">
                <div><dt>已排 / 总课时</dt><dd>{{ state.completion >= 100 ? '184 / 184' : `${184 - state.remaining} / 184` }}</dd></div>
                <div><dt>待处理课时</dt><dd class="is-orange">{{ state.remaining }}</dd></div>
                <div><dt>冲突</dt><dd class="is-red">{{ state.conflicts }}</dd></div>
                <div><dt>预排课位</dt><dd class="is-orange">{{ state.preplaceReady }} / {{ state.preplaceTotal }}</dd></div>
              </dl>
              <button type="button" class="panel-link-button" @click="runPreflight"><ListChecks :size="14" /> 重新检查条件 <ArrowRight :size="13" /></button>
            </aside>
          </div>

          <div class="a-lower-grid">
            <section class="preview-panel">
              <div class="panel-heading-line"><div><p class="panel-kicker">检查预览</p><h2>三视角课表摘要</h2></div><button type="button" class="icon-inline-button" title="切换视角" aria-label="切换视角" @click="record('切换到教师视角预览', 'neutral')"><SlidersHorizontal :size="16" /></button></div>
              <div class="mini-timetable">
                <div class="mini-timetable-head"><span>班级</span><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span></div>
                <div v-for="row in [{ name: '高一 1 班', cells: ['语文','数学','英语','物理','历史'] }, { name: '高一 2 班', cells: ['数学','英语','化学','语文','体育'] }, { name: '高二 3 班', cells: ['物理','语文','数学','英语','生物'] }]" :key="row.name" class="mini-timetable-row"><strong>{{ row.name }}</strong><span v-for="cell in row.cells" :key="`${row.name}-${cell}`" :class="{ 'is-alert': cell === '物理' && state.conflicts > 0 }">{{ cell }}</span></div>
              </div>
              <div class="preview-foot"><span><i class="legend-dot is-blue" />已排</span><span><i class="legend-dot is-orange" />需要检查</span><button type="button" class="panel-link-button" @click="openWorkbench">进入完整工作台 <ArrowRight :size="13" /></button></div>
            </section>
            <section class="activity-panel">
              <div class="panel-heading-line"><div><p class="panel-kicker">变更记录</p><h2>最近发生了什么</h2></div><span class="live-label"><i />实时</span></div>
              <ol class="activity-list"><li v-for="item in state.activity" :key="item.id"><i class="activity-dot" :class="`is-${item.tone}`" /><span><strong>{{ item.text }}</strong><small>{{ item.time }}</small></span></li></ol>
              <div class="last-action" aria-live="polite"><span>刚刚</span>{{ state.lastAction }}</div>
            </section>
          </div>
        </section>

        <section v-else-if="currentVariant === 'B'" class="prototype-variant variant-b" data-testid="variant-b">
          <header class="variant-page-head">
            <div><p class="prototype-eyebrow">方案 B · {{ currentVariantMeta.label }}</p><h1>先清空问题，再发布课表</h1><p>把所有“下一步”变成可点击的收件箱，不要求用户自己找页面。</p></div>
            <div class="variant-head-actions"><button type="button" class="button button-secondary" :disabled="state.draftStatus === '已发布'" @click="openPublishPanel"><FileCheck2 :size="15" /> {{ state.draftStatus === '已发布' ? '已发布' : '发布检查' }}</button><button type="button" class="button button-primary" @click="runAutoSchedule('subject')"><WandSparkles :size="15" /> 局部重排</button></div>
          </header>

          <nav class="flow-rail flow-rail-compact" aria-label="排课流程">
            <button v-for="(stage, index) in stageMeta" :key="stage.key" type="button" class="flow-step" :class="`is-${stageState(stage.key)}`" @click="goToStage(stage.key)">
              <span class="flow-step-index"><Check v-if="stageState(stage.key) === 'done'" :size="14" /><span v-else>{{ index + 1 }}</span></span>
              <span><strong>{{ stage.label }}</strong><small>{{ stage.short }}</small></span>
              <ArrowRight v-if="index < stageMeta.length - 1" class="flow-step-arrow" :size="14" aria-hidden="true" />
            </button>
          </nav>

          <div class="inbox-layout">
            <aside class="issue-inbox" aria-label="待处理问题">
              <div class="inbox-heading"><div><p class="panel-kicker">待处理收件箱</p><h2>{{ issueCount }} 个事项</h2></div><button type="button" class="icon-inline-button" title="筛选问题" aria-label="筛选问题" @click="record('打开问题筛选', 'neutral')"><Filter :size="16" /></button></div>
              <p class="inbox-caption">按阻塞程度排序，处理完一项就会减少一项。</p>
              <button type="button" class="issue-row" :class="{ 'is-selected': selectedIssue === 'assignments' }" @click="selectIssue('assignments')"><span class="issue-icon is-red"><ClipboardList :size="16" /></span><span><strong>教学任务缺项</strong><small>{{ state.assignmentTotal - state.assignmentReady }} 项 · 会阻止自动排课</small></span><b>{{ state.assignmentTotal - state.assignmentReady }}</b></button>
              <button type="button" class="issue-row" :class="{ 'is-selected': selectedIssue === 'preflight' }" @click="selectIssue('preflight')"><span class="issue-icon is-orange"><CircleAlert :size="16" /></span><span><strong>排课提醒</strong><small>非阻断 · 建议在生成前处理</small></span><b>{{ state.preflightWarnings }}</b></button>
              <button type="button" class="issue-row" :class="{ 'is-selected': selectedIssue === 'unscheduled' }" @click="selectIssue('unscheduled')"><span class="issue-icon is-blue"><Clock3 :size="16" /></span><span><strong>未排课时</strong><small>可以局部重排或转人工处理</small></span><b>{{ state.remaining }}</b></button>
              <button type="button" class="issue-row" :class="{ 'is-selected': selectedIssue === 'conflict' }" @click="selectIssue('conflict')"><span class="issue-icon is-purple"><Users :size="16" /></span><span><strong>教室/场地冲突</strong><small>跳转到教室/场地视角定位</small></span><b>{{ state.conflicts }}</b></button>
              <div class="inbox-progress"><div><span>发布准备度</span><strong>{{ state.completion }}%</strong></div><div class="health-meter"><span :style="{ width: `${state.completion}%` }" /></div></div>
            </aside>

            <section class="issue-detail" aria-live="polite">
              <div class="detail-topline"><span class="detail-breadcrumb">问题收件箱 / {{ selectedIssueLabel }}</span><span class="detail-time"><Clock3 :size="13" /> 更新于 09:24</span></div>
              <div class="detail-heading"><span class="detail-icon" :class="`is-${selectedIssueTone}`"><CircleAlert :size="22" /></span><div><h2>{{ selectedIssueHeading }}</h2><p>{{ selectedIssueBody }}</p></div></div>
              <div class="detail-action-bar"><button v-if="selectedIssue === 'assignments' && state.assignmentTotal > state.assignmentReady" type="button" class="button button-primary" @click="openBatchPanel"><Copy :size="16" /> 批量补齐任务</button><button v-else-if="selectedIssue === 'assignments'" type="button" class="button button-primary" @click="confirmRules"><Settings2 :size="16" /> 确认规则并进入预排</button><button v-else-if="selectedIssue === 'preflight'" type="button" class="button button-primary" @click="runPreflight"><CheckCircle2 :size="16" /> {{ state.preflightWarnings ? '处理提醒' : '重新检查' }}</button><button v-else-if="selectedIssue === 'unscheduled'" type="button" class="button button-primary" @click="runAutoSchedule('subject')"><WandSparkles :size="16" /> 仅重排数学</button><button v-else type="button" class="button button-primary" @click="record('已打开教室/场地视角定位冲突', 'blue')"><Table2 :size="16" /> 打开教室/场地视角</button><button type="button" class="button button-quiet" @click="record('已标记当前问题稍后处理', 'neutral')">稍后处理</button></div>
              <div class="detail-evidence"><div class="evidence-header"><span>影响范围</span><button type="button" class="prototype-text-button" @click="advancedRulesOpen = !advancedRulesOpen"><Settings2 :size="14" /> {{ advancedRulesOpen ? '收起规则详情' : '查看规则详情' }}</button></div><div class="evidence-grid"><div><strong>{{ selectedIssue === 'assignments' ? '3 个班级' : selectedIssue === 'conflict' ? '2 个班级' : '1 个科目' }}</strong><small>受影响对象</small></div><div><strong>{{ selectedIssue === 'unscheduled' ? `${state.remaining} 节` : selectedIssue === 'assignments' ? `${state.assignmentTotal - state.assignmentReady} 项` : `${state.preflightWarnings || state.conflicts} 条` }}</strong><small>待处理数量</small></div><div><strong>{{ selectedIssue === 'conflict' ? '周二第 3 节' : '自动排课前' }}</strong><small>建议处理时机</small></div></div><div v-if="advancedRulesOpen" class="advanced-rule-box"><strong>相关规则</strong><span>教师可排时段、教室/场地容量、固定课位</span><span>点击任意规则可回到对应设置页</span></div></div>
              <div class="detail-timetable"><div class="evidence-header"><span>受影响课表片段</span><button type="button" class="icon-inline-button" title="放大课表" aria-label="放大课表" @click="openWorkbench"><ArrowUpRight :size="16" /></button></div><div class="detail-grid"><span class="detail-grid-label">班级</span><span>周一</span><span>周二</span><span>周三</span><span>周四</span><strong>高一 1 班</strong><i>语文</i><i class="is-alert">待处理</i><i>物理</i><i>数学</i><strong>高一 2 班</strong><i>英语</i><i>数学</i><i>化学</i><i>语文</i></div></div>
            </section>

            <aside class="release-sidebar" aria-label="发布状态">
              <div class="release-heading"><p class="panel-kicker">发布前检查</p><h2>{{ state.draftStatus === '已发布' ? '课表已生效' : '还差最后几步' }}</h2></div>
              <ol class="check-list"><li :class="{ 'is-done': state.assignmentReady === state.assignmentTotal }"><span><Check v-if="state.assignmentReady === state.assignmentTotal" :size="14" /><span v-else>1</span></span><div><strong>教学任务完整</strong><small>{{ assignmentLabel }}</small></div></li><li :class="{ 'is-done': state.preflightPassed }"><span><Check v-if="state.preflightPassed" :size="14" /><span v-else>2</span></span><div><strong>前置检查</strong><small>{{ state.preflightPassed ? '无阻断错误' : '尚未运行' }}</small></div></li><li :class="{ 'is-done': state.remaining === 0 }"><span><Check v-if="state.remaining === 0" :size="14" /><span v-else>3</span></span><div><strong>未排课时</strong><small>{{ state.remaining ? `剩余 ${state.remaining} 节` : '全部安排' }}</small></div></li><li :class="{ 'is-done': state.draftStatus === '已发布' }"><span><Check v-if="state.draftStatus === '已发布'" :size="14" /><span v-else>4</span></span><div><strong>通知与审计</strong><small>{{ state.draftStatus === '已发布' ? '已生成站内通知' : '发布后自动生成' }}</small></div></li></ol>
              <button type="button" class="button button-primary button-block" :disabled="state.draftStatus === '已发布'" @click="openPublishPanel"><FileCheck2 :size="16" /> {{ state.draftStatus === '已发布' ? '已发布' : '检查并发布' }}</button>
              <button type="button" class="button button-secondary button-block" @click="openWorkbench"><Table2 :size="16" /> 打开课表工作台</button>
              <div class="release-note"><LockKeyhole :size="14" /><span>发布会生成不可变快照，草稿仍可继续复制调整。</span></div>
            </aside>
          </div>
        </section>

        <section v-else class="prototype-variant variant-c" data-testid="variant-c">
          <header class="variant-page-head">
            <div><p class="prototype-eyebrow">方案 C · {{ currentVariantMeta.label }}</p><h1>春季学期 · 课表画布</h1><p>把排课、冲突和锁定状态放在同一张网格里，减少视角来回切换。</p></div>
            <div class="variant-head-actions"><span class="canvas-view-select"><Table2 :size="14" /> 班级视角 <ChevronDown :size="14" /></span><button type="button" class="button button-secondary" :disabled="state.draftStatus === '已发布'" @click="openPublishPanel"><FileCheck2 :size="15" /> {{ state.draftStatus === '已发布' ? '已发布' : '发布检查' }}</button></div>
          </header>

          <nav class="flow-rail flow-rail-compact" aria-label="排课流程">
            <button v-for="(stage, index) in stageMeta" :key="stage.key" type="button" class="flow-step" :class="`is-${stageState(stage.key)}`" @click="goToStage(stage.key)">
              <span class="flow-step-index"><Check v-if="stageState(stage.key) === 'done'" :size="14" /><span v-else>{{ index + 1 }}</span></span>
              <span><strong>{{ stage.label }}</strong><small>{{ stage.short }}</small></span>
              <ArrowRight v-if="index < stageMeta.length - 1" class="flow-step-arrow" :size="14" aria-hidden="true" />
            </button>
          </nav>

          <div class="canvas-toolbar"><div class="canvas-toolbar-left"><button type="button" class="toolbar-chip is-active" @click="record('保持班级视角', 'neutral')">班级</button><button type="button" class="toolbar-chip" @click="record('切换到教师视角', 'neutral')">教师</button><button type="button" class="toolbar-chip" @click="record('切换到教室/场地视角', 'neutral')">教室/场地</button><span class="toolbar-divider" /><span class="toolbar-context">高一 1 班 <ChevronDown :size="14" /></span></div><div class="canvas-toolbar-right"><span class="toolbar-summary"><i class="legend-dot is-blue" /> 已排 {{ 184 - state.remaining }} <i class="legend-dot is-orange" /> 待处理 {{ state.remaining }}</span><button type="button" class="icon-inline-button" title="筛选课程" aria-label="筛选课程" @click="record('打开课程筛选', 'neutral')"><Search :size="16" /></button><button type="button" class="icon-inline-button" title="更多画布设置" aria-label="更多画布设置" @click="record('打开画布设置', 'neutral')"><SlidersHorizontal :size="16" /></button></div></div>

          <div class="canvas-layout">
            <section class="canvas-panel" aria-label="周课表画布">
              <div class="canvas-grid-wrap"><div class="canvas-grid-head"><span class="period-corner">节次</span><span>周一</span><span>周二</span><span>周三</span><span>周四</span><span>周五</span></div><div v-for="(period, periodIndex) in ['第 1 节','第 2 节','第 3 节','第 4 节','第 5 节','第 6 节']" :key="period" class="canvas-grid-row"><span class="period-label">{{ period }}<small>{{ ['08:00','08:50','10:10','11:00','14:00','14:50'][periodIndex] }}</small></span><button v-for="(cell, dayIndex) in [['语文','数学','英语','物理','历史'],['数学','待处理','化学','语文','体育'],['英语','物理','数学','英语','生物'],['物理','语文','历史','数学','地理'],['历史','体育','语文','化学','数学']][periodIndex]" :key="`${period}-${dayIndex}`" type="button" class="canvas-cell" :class="{ 'is-alert': cell === '待处理' || (cell === '物理' && periodIndex === 2), 'is-locked': cell === '英语' && dayIndex === 2 && periodIndex === 0, 'is-selected': selectedCell === `周${['一','二','三','四','五'][dayIndex]} · ${period}` }" @click="selectedCell = `周${['一','二','三','四','五'][dayIndex]} · ${period}`; record(`选中 ${selectedCell}`, cell === '待处理' ? 'orange' : 'blue')"><strong>{{ cell }}</strong><small v-if="cell === '待处理'">缺少时段</small><LockKeyhole v-if="cell === '英语' && dayIndex === 2 && periodIndex === 0" :size="11" aria-label="已锁定" /></button></div></div><div class="canvas-legend"><span><i class="legend-dot is-blue" />已排课</span><span><i class="legend-dot is-orange" />需要处理</span><span><LockKeyhole :size="12" />锁定课位</span><span class="canvas-selection">已选：{{ selectedCell }}</span></div>
            </section>

            <aside class="canvas-inspector" aria-label="课程检查面板">
              <div class="inspector-heading"><div><p class="panel-kicker">选中课程</p><h2>{{ selectedCell }}</h2></div><button type="button" class="icon-inline-button" title="关闭详情" aria-label="关闭详情" @click="record('保留课程详情面板', 'neutral')"><X :size="16" /></button></div>
              <div class="course-inspector-card"><span class="course-subject">英语</span><strong>高一 1 班 · 李老师</strong><small>普通教室 · 每周 4 节</small><span class="course-state is-locked"><LockKeyhole :size="13" /> 已锁定</span></div>
              <div class="inspector-section"><div class="inspector-section-head"><span>检查结果</span><span class="issue-pill" :class="{ 'is-clear': state.conflicts === 0 }">{{ state.conflicts }} 个问题</span></div><div v-if="state.conflicts" class="inspector-alert"><CircleAlert :size="15" /><div><strong>机房资源冲突</strong><small>周二第 3 节，另一个班也需要机房。</small></div></div><div v-else class="inspector-alert is-clear"><CheckCircle2 :size="15" /><div><strong>没有阻断冲突</strong><small>教室/场地、教师和班级硬约束均通过。</small></div></div><button type="button" class="button button-secondary button-block" @click="record('打开关联教室/场地课表', 'blue')"><Table2 :size="15" /> 查看教室/场地视角</button></div>
              <div class="inspector-section"><div class="inspector-section-head"><span>课程动作</span><MoreHorizontal :size="16" /></div><div class="inspector-actions"><button type="button" class="inspector-action" @click="lockSelectedCell"><LockKeyhole :size="15" /><span>锁定此课位</span><ArrowRight :size="13" /></button><button type="button" class="inspector-action" @click="record('已加入局部重排范围', 'blue')"><WandSparkles :size="15" /><span>加入局部重排</span><ArrowRight :size="13" /></button><button type="button" class="inspector-action" @click="record('已撤销最近一次调整', 'neutral')"><History :size="15" /><span>撤销最近调整</span><ArrowRight :size="13" /></button></div></div>
              <div class="inspector-score"><span>发布准备度</span><strong>{{ state.completion }}%</strong><div class="health-meter"><span :style="{ width: `${state.completion}%` }" /></div><small>硬约束通过 · 仍有 {{ state.remaining }} 节待处理</small></div>
            </aside>
          </div>
          <div class="canvas-command-dock"><div><span class="dock-kicker"><Zap :size="14" /> 当前动作</span><strong>{{ state.lastAction }}</strong></div><div class="dock-actions"><button type="button" class="button button-secondary" @click="runPreflight"><ListChecks :size="15" /> 检查冲突</button><button type="button" class="button button-secondary" @click="runAutoSchedule('subject')"><WandSparkles :size="15" /> 局部重排</button><button type="button" class="button button-primary" :disabled="state.draftStatus === '已发布'" @click="openPublishPanel"><FileCheck2 :size="15" /> {{ state.draftStatus === '已发布' ? '已发布' : '检查并发布' }}</button></div></div>
        </section>

        <section class="prototype-state-strip" aria-live="polite">
          <div class="state-strip-main"><span class="state-strip-label"><Zap :size="13" /> 原型状态</span><strong>{{ state.lastAction }}</strong></div><div class="state-strip-facts"><span>阶段：{{ stageMeta.find((item) => item.key === state.stage)?.label }}</span><span>课表：{{ state.completion }}%</span><span>待处理：{{ state.remaining + state.conflicts }}</span><span>预排：{{ state.preplaceReady }} / {{ state.preplaceTotal }}</span><span>锁定：{{ state.locked }}</span></div>
        </section>
      </main>
    </div>

    <div v-if="batchPanelOpen" class="prototype-overlay" role="presentation" @click.self="batchPanelOpen = false">
      <section class="prototype-modal" role="dialog" aria-modal="true" aria-labelledby="batch-title"><header><div><p class="panel-kicker">教学任务批量编辑</p><h2 id="batch-title">复制上一班配置</h2></div><button type="button" class="icon-inline-button" title="关闭" aria-label="关闭" @click="batchPanelOpen = false"><X :size="17" /></button></header><p class="modal-copy">一次补齐同年级的周课时、连堂和教室/场地需求，写入前仍会显示变更范围。</p><div class="batch-preview"><div><span>来源</span><strong>高一 1 班</strong><small>已配置 46 项</small></div><ArrowRight :size="18" /><div><span>目标</span><strong>高一 2 / 3 班</strong><small>将补齐 8 项缺口</small></div></div><label class="modal-check"><input type="checkbox" checked><span>只复制缺失字段，不覆盖已有设置</span></label><footer><button type="button" class="button button-secondary" @click="batchPanelOpen = false">取消</button><button type="button" class="button button-primary" @click="applyBatchPanel"><Check :size="15" /> 预览并应用</button></footer></section>
    </div>

    <div v-if="publishPanelOpen" class="prototype-overlay" role="presentation" @click.self="publishPanelOpen = false">
      <section class="prototype-modal publish-modal" role="dialog" aria-modal="true" aria-labelledby="publish-title"><header><div><p class="panel-kicker">发布与输出</p><h2 id="publish-title">{{ state.remaining ? '确认发布未完整课表' : '确认发布课表' }}</h2></div><button type="button" class="icon-inline-button" title="关闭" aria-label="关闭" @click="publishPanelOpen = false"><X :size="17" /></button></header><div class="publish-summary"><div class="publish-summary-number"><strong>{{ state.completion }}%</strong><span>课时已安排</span></div><div><strong>春季学期 · 初版课表</strong><span>{{ state.remaining }} 节待处理 · {{ state.conflicts }} 个冲突</span></div></div><ul class="publish-checks"><li :class="{ 'is-ok': state.assignmentReady === state.assignmentTotal }"><CheckCircle2 :size="16" /><span>教学任务完整</span><strong>{{ assignmentLabel }}</strong></li><li :class="{ 'is-ok': state.preflightPassed }"><CheckCircle2 v-if="state.preflightPassed" :size="16" /><CircleAlert v-else :size="16" /><span>硬约束检查</span><strong>{{ state.preflightPassed ? '通过' : '尚未运行' }}</strong></li><li :class="{ 'is-ok': state.remaining === 0 }"><CircleAlert v-if="state.remaining" :size="16" /><CheckCircle2 v-else :size="16" /><span>未排课时</span><strong>{{ state.remaining ? `剩余 ${state.remaining} 节` : '全部安排' }}</strong></li><li><Bell :size="16" /><span>发布后动作</span><strong>生成站内通知 + 审计记录</strong></li></ul><p v-if="!canConfirmPublish" class="modal-warning">当前流程尚未完成。请先补齐教学任务、确认规则与预排，并运行前置检查和自动排课。</p><template v-else-if="state.remaining"><label class="modal-reason"><span>强制发布原因</span><textarea v-model="forcePublishReason" rows="3" maxlength="200" placeholder="说明未排课时的处理安排" /></label><p v-if="!forcePublishReason.trim()" class="modal-field-hint">填写原因后才能确认强制发布。</p><p v-else class="modal-warning">发布检查未通过。确认后仍会发布，未排教学任务不会出现在正式课表中，审计记录会标记为强制发布。</p></template><footer><button type="button" class="button button-secondary" @click="publishPanelOpen = false">回到工作台</button><button type="button" class="button button-primary" :disabled="!canSubmitPublish" @click="confirmPublish"><FileCheck2 :size="15" /> {{ !canConfirmPublish ? '先完成排课流程' : state.remaining && !forcePublishReason.trim() ? '填写发布原因' : state.remaining ? '确认强制发布' : '确认发布' }}</button></footer></section>
    </div>
  </div>
</template>

<style scoped>
:global(body) { background: #eef2f6; }

.prototype-app {
  --p-ink: #1c2738;
  --p-muted: #647185;
  --p-faint: #8a96a6;
  --p-line: #dfe5ec;
  --p-soft: #f6f8fb;
  --p-blue: #2864dc;
  --p-blue-soft: #edf3ff;
  --p-green: #16764f;
  --p-green-soft: #eaf7f0;
  --p-orange: #a65d00;
  --p-orange-soft: #fff4e5;
  --p-red: #c2383f;
  --p-red-soft: #fff0f1;
  --p-purple: #7059aa;
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  min-height: 100vh;
  color: var(--p-ink);
  background: #eef2f6;
  font-family: var(--app-font-sans);
}

button, a { -webkit-tap-highlight-color: transparent; }
button { font: inherit; }

.prototype-sidebar {
  display: flex;
  min-height: 100vh;
  flex-direction: column;
  border-right: 1px solid var(--p-line);
  background: #fff;
}

.prototype-brand { display: flex; min-height: 70px; align-items: center; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--p-line); }
.prototype-brand-mark { display: grid; width: 34px; height: 34px; place-items: center; border-radius: 7px; background: var(--p-blue); color: #fff; }
.prototype-brand > span:nth-child(2) { display: grid; min-width: 0; gap: 2px; }
.prototype-brand strong { font-size: 14px; line-height: 1.3; }
.prototype-brand small { color: var(--p-muted); font-size: 11px; }
.prototype-sidebar-close { display: none !important; margin-left: auto; }

.prototype-nav { flex: 1; padding: 16px 10px; }
.prototype-nav-label { margin: 0 8px 6px; color: var(--p-faint); font-size: 11px; font-weight: 700; letter-spacing: .02em; }
.prototype-nav-label-spaced { margin-top: 22px; }
.prototype-nav-link { display: flex; min-height: 39px; align-items: center; gap: 9px; margin: 2px 0; padding: 0 9px; border: 1px solid transparent; border-radius: 6px; color: var(--p-muted); font-size: 13px; text-decoration: none; }
.prototype-nav-link:hover { border-color: var(--p-line); background: var(--p-soft); color: var(--p-ink); }
.prototype-nav-link.is-active { border-color: #c6d5f6; background: var(--p-blue-soft); color: #1f50b2; font-weight: 700; }
.prototype-nav-link small { min-width: 19px; margin-left: auto; padding: 2px 5px; border-radius: 4px; background: var(--p-red-soft); color: var(--p-red); font-size: 10px; text-align: center; }
.prototype-school { display: flex; align-items: center; gap: 9px; padding: 13px; border-top: 1px solid var(--p-line); background: var(--p-soft); }
.prototype-school-mark { display: grid; width: 29px; height: 29px; place-items: center; border-radius: 6px; background: var(--p-blue-soft); color: var(--p-blue); }
.prototype-school > span:last-child { display: grid; min-width: 0; gap: 2px; }
.prototype-school strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.prototype-school small { color: var(--p-muted); font-size: 10px; }

.prototype-main { display: grid; min-width: 0; min-height: 100vh; grid-template-rows: 66px minmax(0, 1fr); }
.prototype-topbar { display: flex; min-width: 0; align-items: center; gap: 12px; padding: 0 22px; border-bottom: 1px solid var(--p-line); background: #fff; }
.prototype-breadcrumb { display: flex; min-width: 0; align-items: center; gap: 7px; color: var(--p-muted); font-size: 12px; }
.prototype-breadcrumb strong { color: var(--p-ink); }
.prototype-dev-badge { padding: 3px 6px; border: 1px solid #cbd6e5; border-radius: 4px; color: var(--p-muted); font-size: 9px; font-weight: 800; letter-spacing: .08em; }
.prototype-topbar-actions { display: flex; min-width: 0; align-items: center; gap: 10px; margin-left: auto; }
.prototype-semester { display: inline-flex; align-items: center; gap: 5px; padding: 8px 9px; border: 1px solid var(--p-line); border-radius: 6px; background: var(--p-soft); color: var(--p-muted); font-size: 11px; white-space: nowrap; }
.prototype-user { display: inline-flex; align-items: center; gap: 7px; color: var(--p-muted); font-size: 12px; white-space: nowrap; }
.prototype-avatar { display: grid; width: 28px; height: 28px; place-items: center; border-radius: 50%; background: #dbe7ff; color: #1f50b2; font-weight: 700; }
.prototype-notification-dot { position: absolute; width: 6px; height: 6px; margin: -14px 0 0 10px; border: 1px solid #fff; border-radius: 50%; background: var(--p-red); }
.prototype-icon-button { position: relative; display: inline-flex; width: 34px; height: 34px; flex: 0 0 auto; align-items: center; justify-content: center; border: 1px solid var(--p-line); border-radius: 6px; background: #fff; color: var(--p-muted); cursor: pointer; }
.prototype-icon-button:hover { border-color: #b9c9ea; background: var(--p-blue-soft); color: var(--p-blue); }
.prototype-menu-button { display: none; }

.prototype-content { min-width: 0; overflow: auto; padding: 20px 24px 100px; }
.prototype-context-line { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 12px; margin: 0 auto 16px; color: var(--p-muted); font-size: 12px; }
.prototype-text-button { display: inline-flex; align-items: center; gap: 5px; padding: 0; border: 0; background: transparent; color: var(--p-blue); font-size: 12px; cursor: pointer; }
.prototype-text-button:hover { text-decoration: underline; }
.prototype-variant { width: min(1500px, 100%); margin: 0 auto; }
.variant-page-head { display: flex; min-width: 0; align-items: flex-end; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
.prototype-eyebrow { margin: 0 0 6px; color: var(--p-blue); font-size: 11px; font-weight: 800; letter-spacing: .04em; }
.variant-page-head h1 { margin: 0; font-size: clamp(23px, 2.2vw, 30px); line-height: 1.2; letter-spacing: 0; }
.variant-page-head > div:first-child > p:last-child { margin: 7px 0 0; color: var(--p-muted); font-size: 13px; line-height: 1.55; }
.variant-head-actions { display: flex; min-width: 0; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 8px; }
.button { display: inline-flex; min-height: 36px; align-items: center; justify-content: center; gap: 7px; padding: 0 12px; border: 1px solid transparent; border-radius: 6px; font-size: 12px; font-weight: 700; cursor: pointer; white-space: nowrap; }
.button:disabled { cursor: wait; opacity: .62; }
.button-primary { border-color: var(--p-blue); background: var(--p-blue); color: #fff; }
.button-primary:hover:not(:disabled) { background: #2358c4; }
.button-secondary { border-color: var(--p-line); background: #fff; color: var(--p-ink); }
.button-secondary:hover:not(:disabled) { border-color: #bac9e7; background: var(--p-blue-soft); color: #1f50b2; }
.button-quiet { min-height: 32px; padding: 0 4px; background: transparent; color: var(--p-blue); }
.button-block { width: 100%; }
.draft-status { display: inline-flex; align-items: center; gap: 6px; padding: 8px 9px; border: 1px solid var(--p-line); border-radius: 5px; color: var(--p-muted); font-size: 11px; white-space: nowrap; }
.draft-status.is-published { border-color: #b7dfca; background: var(--p-green-soft); color: var(--p-green); }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--p-orange); }
.is-published .status-dot { background: var(--p-green); }

/* Variant A: a flow-first command centre. */
.flow-rail { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); margin-bottom: 16px; border: 1px solid var(--p-line); border-radius: 7px; background: #fff; overflow: hidden; }
.flow-rail-compact { margin-top: -4px; }
.flow-step { position: relative; display: flex; min-width: 0; align-items: center; gap: 8px; min-height: 66px; padding: 10px 13px; border: 0; border-right: 1px solid var(--p-line); background: #fff; color: var(--p-muted); text-align: left; cursor: pointer; }
.flow-step:last-child { border-right: 0; }
.flow-step:hover { background: var(--p-soft); }
.flow-step.is-active { background: var(--p-blue-soft); color: #1f50b2; }
.flow-step.is-done { color: var(--p-green); }
.flow-step.is-blocked { background: #fffafa; color: var(--p-red); }
.flow-step-index { display: grid; width: 24px; height: 24px; flex: 0 0 auto; place-items: center; border: 1px solid currentColor; border-radius: 50%; font-size: 11px; font-weight: 800; }
.flow-step.is-done .flow-step-index { background: var(--p-green-soft); }
.flow-step > span:nth-child(2) { display: grid; min-width: 0; gap: 2px; }
.flow-step strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.flow-step small { color: var(--p-faint); font-size: 10px; }
.flow-step-arrow { position: absolute; top: 26px; right: 7px; color: var(--p-faint); }

.a-command-grid { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 16px; }
.command-panel, .a-state-panel, .preview-panel, .activity-panel { min-width: 0; border: 1px solid var(--p-line); border-radius: 7px; background: #fff; box-shadow: 0 1px 2px rgba(28,39,56,.04); }
.command-panel { min-height: 250px; padding: 25px; border-top: 3px solid var(--p-blue); }
.command-panel-kicker { display: inline-flex; align-items: center; gap: 6px; margin: 0 0 12px; color: var(--p-blue); font-size: 12px; font-weight: 800; }
.command-panel h2 { max-width: 700px; margin: 0; font-size: clamp(20px, 2.5vw, 28px); line-height: 1.28; }
.command-panel > p { max-width: 630px; margin: 10px 0 0; color: var(--p-muted); font-size: 13px; line-height: 1.6; }
.command-primary-row { display: flex; min-width: 0; flex-wrap: wrap; align-items: center; gap: 10px; margin-top: 23px; }
.command-trust-row { display: flex; min-width: 0; flex-wrap: wrap; gap: 12px; margin-top: 25px; padding-top: 14px; border-top: 1px solid var(--p-line); color: var(--p-muted); font-size: 11px; }
.command-trust-row span { display: inline-flex; align-items: center; gap: 5px; }
.command-trust-row span:first-child { color: var(--p-green); }
.a-state-panel { padding: 18px; }
.panel-heading-line { display: flex; min-width: 0; align-items: flex-start; justify-content: space-between; gap: 10px; color: var(--p-faint); }
.panel-heading-line > div { min-width: 0; }
.panel-kicker { margin: 0 0 4px; color: var(--p-faint); font-size: 10px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
.panel-heading-line h2, .preview-panel h2, .activity-panel h2 { margin: 0; font-size: 16px; line-height: 1.35; }
.health-score { display: flex; align-items: baseline; gap: 8px; margin-top: 22px; }
.health-score strong { color: var(--p-blue); font-size: 34px; line-height: 1; }
.health-score span { color: var(--p-muted); font-size: 11px; }
.health-meter { height: 7px; margin-top: 12px; overflow: hidden; border-radius: 4px; background: #e8edf4; }
.health-meter span { display: block; height: 100%; border-radius: inherit; background: var(--p-blue); transition: width .3s ease; }
.compact-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 10px; margin: 20px 0 16px; }
.compact-stats div { display: grid; gap: 3px; }
.compact-stats dt { color: var(--p-muted); font-size: 10px; }
.compact-stats dd { margin: 0; color: var(--p-ink); font-size: 15px; font-weight: 800; }
.compact-stats dd.is-orange { color: var(--p-orange); }
.compact-stats dd.is-red { color: var(--p-red); }
.panel-link-button { display: inline-flex; align-items: center; gap: 6px; padding: 0; border: 0; background: transparent; color: var(--p-blue); font-size: 11px; cursor: pointer; }
.panel-link-button:hover { text-decoration: underline; }
.a-lower-grid { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(280px, .85fr); gap: 16px; margin-top: 16px; }
.preview-panel, .activity-panel { padding: 18px; }
.icon-inline-button { display: inline-flex; width: 30px; height: 30px; align-items: center; justify-content: center; border: 1px solid var(--p-line); border-radius: 5px; background: #fff; color: var(--p-muted); cursor: pointer; }
.icon-inline-button:hover { border-color: #b9c9ea; background: var(--p-blue-soft); color: var(--p-blue); }
.mini-timetable { margin-top: 15px; overflow: hidden; border: 1px solid var(--p-line); border-radius: 5px; }
.mini-timetable-head, .mini-timetable-row { display: grid; grid-template-columns: minmax(92px, 1.2fr) repeat(5, minmax(60px, 1fr)); align-items: center; }
.mini-timetable-head { background: var(--p-soft); color: var(--p-muted); font-size: 10px; font-weight: 700; }
.mini-timetable-head span, .mini-timetable-row > * { min-width: 0; padding: 9px 8px; border-right: 1px solid var(--p-line); border-bottom: 1px solid var(--p-line); text-align: center; }
.mini-timetable-head span:last-child, .mini-timetable-row > *:last-child { border-right: 0; }
.mini-timetable-row:last-child > * { border-bottom: 0; }
.mini-timetable-row strong { overflow: hidden; color: var(--p-ink); font-size: 11px; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.mini-timetable-row span { color: #385477; font-size: 11px; }
.mini-timetable-row span.is-alert { background: var(--p-orange-soft); color: var(--p-orange); font-weight: 700; }
.preview-foot { display: flex; min-width: 0; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 12px; color: var(--p-muted); font-size: 10px; }
.preview-foot > span { display: inline-flex; align-items: center; gap: 5px; }
.preview-foot .panel-link-button { margin-left: auto; }
.legend-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--p-blue); }
.legend-dot.is-orange { background: #e39a34; }
.activity-panel { display: flex; min-height: 0; flex-direction: column; }
.live-label { display: inline-flex; align-items: center; gap: 5px; color: var(--p-green); font-size: 10px; }
.live-label i { width: 6px; height: 6px; border-radius: 50%; background: var(--p-green); }
.activity-list { display: grid; gap: 13px; margin: 17px 0; padding: 0; list-style: none; }
.activity-list li { display: flex; align-items: flex-start; gap: 8px; }
.activity-dot { width: 7px; height: 7px; flex: 0 0 auto; margin-top: 5px; border-radius: 50%; background: var(--p-blue); }
.activity-dot.is-green { background: var(--p-green); }.activity-dot.is-orange { background: #e39a34; }.activity-dot.is-red { background: var(--p-red); }.activity-dot.is-neutral { background: var(--p-faint); }
.activity-list li > span { display: grid; min-width: 0; gap: 3px; }
.activity-list strong { color: var(--p-ink); font-size: 11px; font-weight: 600; line-height: 1.45; }
.activity-list small { color: var(--p-faint); font-size: 10px; }
.last-action { display: flex; align-items: flex-start; gap: 8px; margin-top: auto; padding: 10px; border-radius: 5px; background: var(--p-soft); color: var(--p-muted); font-size: 10px; line-height: 1.45; }
.last-action span { flex: 0 0 auto; color: var(--p-blue); font-weight: 800; }

/* Variant B: an inbox where the next action is the primary navigation. */
.inbox-layout { display: grid; min-width: 0; grid-template-columns: 270px minmax(0, 1fr) 245px; align-items: stretch; border: 1px solid var(--p-line); border-radius: 7px; background: #fff; overflow: hidden; box-shadow: 0 1px 2px rgba(28,39,56,.04); }
.issue-inbox, .issue-detail, .release-sidebar { min-width: 0; }
.issue-inbox { padding: 18px 14px; border-right: 1px solid var(--p-line); background: #fbfcfe; }
.inbox-heading, .detail-topline, .evidence-header, .release-heading, .inspector-heading, .inspector-section-head { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 8px; }
.inbox-heading h2, .release-heading h2, .detail-heading h2, .inspector-heading h2 { margin: 0; font-size: 16px; line-height: 1.35; }
.inbox-caption { margin: 9px 0 15px; color: var(--p-muted); font-size: 11px; line-height: 1.5; }
.issue-row { display: grid; width: 100%; grid-template-columns: 28px minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 10px 8px; border: 1px solid transparent; border-radius: 5px; background: transparent; color: var(--p-ink); text-align: left; cursor: pointer; }
.issue-row:hover { background: #fff; border-color: var(--p-line); }.issue-row.is-selected { border-color: #c6d5f6; background: var(--p-blue-soft); }
.issue-icon { display: grid; width: 28px; height: 28px; place-items: center; border-radius: 5px; }.issue-icon.is-red { background: var(--p-red-soft); color: var(--p-red); }.issue-icon.is-orange { background: var(--p-orange-soft); color: var(--p-orange); }.issue-icon.is-blue { background: var(--p-blue-soft); color: var(--p-blue); }.issue-icon.is-purple { background: #f0edfa; color: var(--p-purple); }
.issue-row > span:nth-child(2) { display: grid; min-width: 0; gap: 3px; }.issue-row strong { overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.issue-row small { overflow: hidden; color: var(--p-muted); font-size: 10px; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }.issue-row b { color: var(--p-muted); font-size: 13px; }
.inbox-progress { margin-top: 20px; padding-top: 14px; border-top: 1px solid var(--p-line); }.inbox-progress > div:first-child { display: flex; justify-content: space-between; color: var(--p-muted); font-size: 10px; }.inbox-progress strong { color: var(--p-blue); font-size: 12px; }
.issue-detail { padding: 22px 24px; }.detail-topline { color: var(--p-faint); font-size: 10px; }.detail-breadcrumb { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.detail-time { display: inline-flex; flex: 0 0 auto; align-items: center; gap: 4px; }
.detail-heading { display: flex; align-items: flex-start; gap: 12px; margin-top: 25px; }.detail-icon { display: grid; width: 42px; height: 42px; flex: 0 0 auto; place-items: center; border-radius: 7px; }.detail-icon.is-red { background: var(--p-red-soft); color: var(--p-red); }.detail-icon.is-orange { background: var(--p-orange-soft); color: var(--p-orange); }.detail-icon.is-blue { background: var(--p-blue-soft); color: var(--p-blue); }.detail-heading h2 { max-width: 640px; font-size: clamp(18px, 2.2vw, 24px); }.detail-heading p { max-width: 700px; margin: 8px 0 0; color: var(--p-muted); font-size: 12px; line-height: 1.6; }
.detail-action-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; padding-bottom: 20px; border-bottom: 1px solid var(--p-line); }.detail-evidence, .detail-timetable { margin-top: 18px; }.evidence-header { color: var(--p-muted); font-size: 11px; font-weight: 700; }.evidence-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }.evidence-grid > div { display: grid; gap: 4px; padding: 12px; border: 1px solid var(--p-line); border-radius: 5px; background: var(--p-soft); }.evidence-grid strong { font-size: 14px; }.evidence-grid small { color: var(--p-muted); font-size: 10px; }.advanced-rule-box { display: grid; gap: 5px; margin-top: 8px; padding: 10px; border-left: 3px solid var(--p-blue); background: var(--p-blue-soft); color: var(--p-muted); font-size: 10px; }.advanced-rule-box strong { color: var(--p-ink); }
.detail-grid { display: grid; grid-template-columns: 82px repeat(4, minmax(50px, 1fr)); margin-top: 10px; overflow: hidden; border: 1px solid var(--p-line); border-radius: 5px; }.detail-grid > * { min-width: 0; padding: 9px 6px; border-right: 1px solid var(--p-line); border-bottom: 1px solid var(--p-line); color: var(--p-muted); font-size: 10px; text-align: center; }.detail-grid > *:nth-child(5n) { border-right: 0; }.detail-grid > *:nth-last-child(-n+5) { border-bottom: 0; }.detail-grid-label { background: var(--p-soft); }.detail-grid strong { color: var(--p-ink); text-align: left; }.detail-grid i { background: #f8fbff; color: #385477; font-style: normal; }.detail-grid i.is-alert { background: var(--p-orange-soft); color: var(--p-orange); font-weight: 700; }
.release-sidebar { display: flex; flex-direction: column; gap: 15px; padding: 20px 16px; border-left: 1px solid var(--p-line); background: #fff; }.release-heading { align-items: flex-start; }.check-list { display: grid; gap: 14px; margin: 5px 0 8px; padding: 0; list-style: none; }.check-list li { display: grid; grid-template-columns: 22px minmax(0, 1fr); gap: 8px; align-items: start; }.check-list li > span { display: grid; width: 21px; height: 21px; place-items: center; border: 1px solid var(--p-line); border-radius: 50%; color: var(--p-faint); font-size: 10px; }.check-list li.is-done > span { border-color: #b7dfca; background: var(--p-green-soft); color: var(--p-green); }.check-list li > div { display: grid; gap: 3px; }.check-list strong { font-size: 11px; }.check-list small { color: var(--p-muted); font-size: 10px; }.release-note { display: flex; align-items: flex-start; gap: 6px; margin-top: auto; padding: 10px; background: var(--p-soft); color: var(--p-muted); font-size: 10px; line-height: 1.45; }

/* Variant C: the timetable is the primary surface. */
.canvas-view-select { display: inline-flex; align-items: center; gap: 5px; padding: 8px 9px; border: 1px solid var(--p-line); border-radius: 5px; background: #fff; color: var(--p-muted); font-size: 11px; }
.canvas-toolbar { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; padding: 9px 11px; border: 1px solid var(--p-line); border-radius: 6px; background: #fff; }.canvas-toolbar-left, .canvas-toolbar-right { display: flex; min-width: 0; align-items: center; flex-wrap: wrap; gap: 7px; }.toolbar-chip { min-height: 28px; padding: 0 10px; border: 1px solid transparent; border-radius: 4px; background: transparent; color: var(--p-muted); font-size: 11px; cursor: pointer; }.toolbar-chip:hover, .toolbar-chip.is-active { border-color: #c6d5f6; background: var(--p-blue-soft); color: #1f50b2; font-weight: 700; }.toolbar-divider { width: 1px; height: 20px; background: var(--p-line); }.toolbar-context { display: inline-flex; align-items: center; gap: 3px; color: var(--p-ink); font-size: 11px; font-weight: 700; }.toolbar-summary { display: inline-flex; align-items: center; gap: 5px; color: var(--p-muted); font-size: 10px; white-space: nowrap; }.toolbar-summary .legend-dot.is-orange { margin-left: 4px; }
.canvas-layout { display: grid; min-width: 0; grid-template-columns: minmax(0, 1fr) 285px; align-items: start; gap: 12px; }.canvas-panel, .canvas-inspector { min-width: 0; border: 1px solid var(--p-line); border-radius: 6px; background: #fff; box-shadow: 0 1px 2px rgba(28,39,56,.04); }.canvas-panel { padding: 12px; }.canvas-grid-wrap { overflow-x: auto; border: 1px solid var(--p-line); border-radius: 5px; }.canvas-grid-head, .canvas-grid-row { display: grid; grid-template-columns: 72px repeat(5, minmax(98px, 1fr)); min-width: 560px; }.canvas-grid-head { background: var(--p-soft); color: var(--p-muted); font-size: 10px; font-weight: 800; text-align: center; }.canvas-grid-head > span { padding: 11px 5px; border-right: 1px solid var(--p-line); }.canvas-grid-head > span:last-child { border-right: 0; }.period-corner { text-align: left; }.canvas-grid-row { border-top: 1px solid var(--p-line); }.period-label { display: grid; align-content: center; gap: 3px; padding: 7px; border-right: 1px solid var(--p-line); color: var(--p-muted); font-size: 10px; }.period-label small { color: var(--p-faint); font-size: 9px; }.canvas-cell { position: relative; display: grid; min-height: 67px; align-content: center; justify-items: center; gap: 4px; padding: 7px 4px; border: 0; border-right: 1px solid var(--p-line); background: #fff; color: #385477; cursor: pointer; }.canvas-cell:last-child { border-right: 0; }.canvas-cell:hover, .canvas-cell.is-selected { background: var(--p-blue-soft); }.canvas-cell.is-alert { background: var(--p-orange-soft); color: var(--p-orange); }.canvas-cell.is-alert:hover, .canvas-cell.is-alert.is-selected { background: #ffe8c7; }.canvas-cell.is-locked::after { position: absolute; top: 5px; right: 5px; width: 5px; height: 5px; border-radius: 50%; background: var(--p-green); content: ''; }.canvas-cell strong { font-size: 12px; }.canvas-cell small { color: var(--p-orange); font-size: 9px; }.canvas-cell > svg { color: var(--p-green); }.canvas-legend { display: flex; min-width: 0; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 10px; color: var(--p-muted); font-size: 10px; }.canvas-legend > span { display: inline-flex; align-items: center; gap: 5px; }.canvas-selection { margin-left: auto; color: var(--p-blue); font-weight: 700; }
.canvas-inspector { padding: 15px; }.inspector-heading { align-items: flex-start; }.inspector-heading h2 { font-size: 15px; }.course-inspector-card { display: grid; gap: 5px; margin-top: 15px; padding: 13px; border: 1px solid #c6d5f6; border-radius: 5px; background: var(--p-blue-soft); }.course-subject { color: var(--p-blue); font-size: 17px; font-weight: 800; }.course-inspector-card strong { font-size: 12px; }.course-inspector-card small { color: var(--p-muted); font-size: 10px; }.course-state { display: inline-flex; width: fit-content; align-items: center; gap: 4px; margin-top: 3px; color: var(--p-green); font-size: 10px; font-weight: 700; }.inspector-section { margin-top: 17px; padding-top: 15px; border-top: 1px solid var(--p-line); }.inspector-section-head { color: var(--p-muted); font-size: 11px; font-weight: 700; }.issue-pill { padding: 3px 5px; border-radius: 4px; background: var(--p-red-soft); color: var(--p-red); font-size: 10px; }.inspector-alert { display: flex; align-items: flex-start; gap: 7px; margin: 10px 0; padding: 9px; border-radius: 5px; background: var(--p-orange-soft); color: var(--p-orange); }.inspector-alert div { display: grid; gap: 3px; }.inspector-alert strong { font-size: 11px; }.inspector-alert small { color: #8b5b1c; font-size: 10px; line-height: 1.4; }.inspector-actions { display: grid; gap: 3px; margin-top: 8px; }.inspector-action { display: flex; min-height: 34px; align-items: center; gap: 7px; padding: 0 7px; border: 1px solid transparent; border-radius: 4px; background: transparent; color: var(--p-muted); font-size: 11px; text-align: left; cursor: pointer; }.inspector-action:hover { border-color: var(--p-line); background: var(--p-soft); color: var(--p-blue); }.inspector-action span { flex: 1; }.inspector-score { margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--p-line); }.inspector-score > span { color: var(--p-muted); font-size: 10px; }.inspector-score > strong { float: right; color: var(--p-blue); font-size: 13px; }.inspector-score small { display: block; margin-top: 7px; color: var(--p-muted); font-size: 10px; }.canvas-command-dock { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 15px; margin-top: 12px; padding: 12px 14px; border: 1px solid #cbd6e5; border-radius: 6px; background: #fff; }.canvas-command-dock > div:first-child { display: grid; min-width: 0; gap: 3px; }.dock-kicker { display: inline-flex; align-items: center; gap: 4px; color: var(--p-blue); font-size: 10px; font-weight: 800; }.canvas-command-dock strong { overflow: hidden; color: var(--p-ink); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.dock-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 7px; }
.issue-pill.is-clear { background: var(--p-green-soft); color: var(--p-green); }
.inspector-alert.is-clear { background: var(--p-green-soft); color: var(--p-green); }
.inspector-alert.is-clear small { color: #356d56; }

.prototype-state-strip { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 16px; margin-top: 16px; padding: 10px 12px; border: 1px solid #cbd6e5; border-radius: 6px; background: #f9fbfe; }.state-strip-main { display: flex; min-width: 0; align-items: center; gap: 8px; }.state-strip-label { display: inline-flex; flex: 0 0 auto; align-items: center; gap: 5px; color: var(--p-blue); font-size: 10px; font-weight: 800; }.state-strip-main strong { overflow: hidden; color: var(--p-muted); font-size: 11px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }.state-strip-facts { display: flex; flex: 0 0 auto; flex-wrap: wrap; gap: 10px; color: var(--p-faint); font-size: 10px; }

.prototype-overlay { position: fixed; z-index: 50; inset: 0; display: grid; place-items: center; padding: 20px; background: rgba(20, 31, 49, .42); }.prototype-modal { width: min(510px, 100%); max-height: calc(100vh - 40px); overflow: auto; padding: 20px; border: 1px solid var(--p-line); border-radius: 7px; background: #fff; box-shadow: 0 16px 40px rgba(20,31,49,.2); }.prototype-modal > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }.prototype-modal h2 { margin: 0; font-size: 19px; }.modal-copy { margin: 12px 0 18px; color: var(--p-muted); font-size: 12px; line-height: 1.6; }.batch-preview { display: grid; grid-template-columns: 1fr 24px 1fr; align-items: center; gap: 10px; padding: 14px; border: 1px solid var(--p-line); border-radius: 5px; background: var(--p-soft); }.batch-preview > div { display: grid; gap: 4px; }.batch-preview span, .batch-preview small { color: var(--p-muted); font-size: 10px; }.batch-preview strong { font-size: 13px; }.modal-check { display: flex; align-items: center; gap: 7px; margin-top: 15px; color: var(--p-muted); font-size: 11px; }.prototype-modal footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 22px; padding-top: 15px; border-top: 1px solid var(--p-line); }.publish-summary { display: flex; align-items: center; gap: 14px; margin-top: 17px; padding: 13px; border: 1px solid #c6d5f6; border-radius: 5px; background: var(--p-blue-soft); }.publish-summary-number { display: grid; flex: 0 0 auto; gap: 2px; padding-right: 14px; border-right: 1px solid #c6d5f6; }.publish-summary-number strong { color: var(--p-blue); font-size: 26px; }.publish-summary span, .publish-summary > div:last-child span { display: block; color: var(--p-muted); font-size: 10px; }.publish-summary > div:last-child { display: grid; gap: 5px; }.publish-summary > div:last-child strong { font-size: 12px; }.publish-checks { display: grid; gap: 10px; margin: 16px 0 0; padding: 0; list-style: none; }.publish-checks li { display: grid; grid-template-columns: 18px minmax(0, 1fr) auto; align-items: center; gap: 7px; padding: 8px 0; border-bottom: 1px solid var(--p-line); color: var(--p-muted); font-size: 11px; }.publish-checks li svg { color: var(--p-orange); }.publish-checks li.is-ok svg { color: var(--p-green); }.publish-checks strong { color: var(--p-ink); font-size: 10px; font-weight: 600; text-align: right; }.modal-warning { margin: 13px 0 0; padding: 9px; border-left: 3px solid #e39a34; background: var(--p-orange-soft); color: #7e5319; font-size: 10px; line-height: 1.5; }

.prototype-switcher { display: flex; width: min(300px, 32vw); min-height: 38px; align-items: center; gap: 5px; padding: 3px 5px; border: 1px solid #263a56; border-radius: 6px; background: #1c2a3d; color: #fff; box-shadow: 0 4px 12px rgba(13, 26, 45, .16); }.prototype-switcher-arrow { display: grid; width: 30px; height: 30px; flex: 0 0 auto; place-items: center; border: 1px solid #4e6380; border-radius: 5px; background: transparent; color: #fff; cursor: pointer; }.prototype-switcher-arrow:hover { background: #2a3d58; }.prototype-switcher-label { display: grid; min-width: 0; flex: 1; gap: 1px; text-align: center; }.prototype-switcher-label span { color: #aebdd0; font-size: 8px; letter-spacing: .06em; text-transform: uppercase; }.prototype-switcher-label strong { overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.prototype-switcher-label small { overflow: hidden; color: #c4cfdd; font-size: 8px; text-overflow: ellipsis; white-space: nowrap; }

.is-spinning { animation: prototype-spin 1s linear infinite; }
@keyframes prototype-spin { to { transform: rotate(360deg); } }

@media (max-width: 1180px) {
  .prototype-app { grid-template-columns: 64px minmax(0, 1fr); }.prototype-brand { justify-content: center; padding: 13px 8px; }.prototype-brand > span:nth-child(2), .prototype-nav-label, .prototype-nav-link span, .prototype-school > span:last-child { display: none; }.prototype-brand-mark { width: 34px; }.prototype-nav-link { justify-content: center; padding: 0; }.prototype-nav-link small { position: absolute; margin: -22px 0 0 20px; }.prototype-nav { padding-inline: 7px; }.prototype-school { justify-content: center; padding-inline: 7px; }.prototype-topbar { padding-inline: 16px; }.a-command-grid { grid-template-columns: minmax(0, 1fr) 260px; }.inbox-layout { grid-template-columns: 230px minmax(0, 1fr) 220px; }.canvas-layout { grid-template-columns: minmax(0, 1fr) 250px; }
}

@media (max-width: 900px) {
  .prototype-content { padding-inline: 16px; }.variant-page-head { align-items: flex-start; flex-direction: column; gap: 13px; }.variant-head-actions { justify-content: flex-start; }.a-command-grid, .a-lower-grid { grid-template-columns: 1fr; }.inbox-layout { grid-template-columns: 220px minmax(0, 1fr); }.release-sidebar { grid-column: 1 / -1; border-top: 1px solid var(--p-line); border-left: 0; }.check-list { grid-template-columns: repeat(4, minmax(0, 1fr)); }.release-sidebar .button-block { width: auto; }.release-note { margin-top: 0; }.canvas-layout { grid-template-columns: 1fr; }.canvas-inspector { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 18px; }.inspector-heading, .course-inspector-card { grid-column: 1 / -1; }.inspector-section { margin-top: 0; }.inspector-score { margin-top: 0; }.canvas-command-dock { align-items: flex-start; flex-direction: column; }.dock-actions { justify-content: flex-start; }
}

@media (max-width: 680px) {
  .prototype-app { display: block; }.prototype-sidebar { display: none; }.prototype-main { min-height: 100vh; }.prototype-menu-button { display: inline-flex; }.prototype-topbar { min-height: 60px; padding-inline: 11px; }.prototype-breadcrumb > span:first-child, .prototype-dev-badge, .prototype-semester, .prototype-user > span:last-child { display: none; }.prototype-topbar-actions { gap: 6px; }.prototype-switcher { width: min(178px, 47vw); min-height: 34px; padding: 2px 4px; }.prototype-switcher-arrow { width: 27px; height: 27px; }.prototype-switcher-label small { display: none; }.prototype-content { padding: 14px 11px 90px; }.prototype-context-line { align-items: flex-start; flex-direction: column; gap: 6px; }.flow-rail { grid-template-columns: repeat(6, minmax(74px, 1fr)); overflow-x: auto; }.flow-step { min-width: 90px; min-height: 59px; padding: 8px; }.flow-step > span:nth-child(2) { display: none; }.flow-step-index { margin: 0 auto; }.flow-step-arrow { display: none; }.command-panel { padding: 18px; }.command-panel h2 { font-size: 21px; }.command-trust-row { display: grid; gap: 7px; }.mini-timetable { overflow-x: auto; }.mini-timetable-head, .mini-timetable-row { min-width: 430px; }.preview-foot .panel-link-button { width: 100%; margin-left: 0; }.inbox-layout { display: block; }.issue-inbox { border-right: 0; border-bottom: 1px solid var(--p-line); }.issue-row { display: inline-grid; width: calc(50% - 4px); vertical-align: top; }.inbox-progress { margin-top: 13px; }.issue-detail { padding: 18px 14px; }.release-sidebar { display: grid; grid-template-columns: 1fr 1fr; padding: 16px 14px; }.release-heading, .check-list, .release-note { grid-column: 1 / -1; }.check-list { grid-template-columns: 1fr 1fr; }.release-sidebar .button-block { width: auto; }.release-note { margin-top: 0; }.evidence-grid { grid-template-columns: 1fr; }.detail-grid { min-width: 410px; overflow-x: auto; }.canvas-toolbar { align-items: flex-start; flex-direction: column; }.canvas-toolbar-right { width: 100%; justify-content: space-between; }.canvas-selection { margin-left: 0; }.canvas-inspector { display: block; }.inspector-section { margin-top: 17px; }.inspector-score { margin-top: 18px; }.prototype-state-strip { align-items: flex-start; flex-direction: column; gap: 8px; }.state-strip-facts { gap: 7px; }
  .flow-rail .flow-step { min-width: 126px; }
  .flow-rail .flow-step > span:nth-child(2) { display: grid; }
  .flow-rail .flow-step-index { margin: 0; }
}

@media (max-width: 420px) {
  .variant-head-actions { width: 100%; }.variant-head-actions .button, .variant-head-actions .draft-status, .variant-head-actions .canvas-view-select { flex: 1; }.command-primary-row .button-primary { width: 100%; }.command-primary-row .button-quiet { width: 100%; justify-content: flex-start; }.issue-row { width: 100%; }.release-sidebar { display: block; }.release-sidebar > * { margin-top: 13px; }.release-sidebar > *:first-child { margin-top: 0; }.check-list { grid-template-columns: 1fr; }.canvas-command-dock .button { flex: 1; }.dock-actions { width: 100%; }.dock-actions .button { flex: 1; min-width: 0; padding-inline: 7px; }.prototype-switcher-label small { display: none; }
}
.modal-reason { display: grid; gap: 6px; margin-top: 13px; color: var(--p-ink); font-size: 11px; font-weight: 600; }
.modal-reason textarea { width: 100%; min-height: 72px; resize: vertical; padding: 8px 9px; border: 1px solid #c6d0dc; border-radius: 4px; color: var(--p-ink); background: #fff; font: inherit; font-weight: 400; line-height: 1.5; }
.modal-reason textarea:focus { outline: 2px solid rgba(40,100,220,.18); border-color: var(--p-blue); }
.modal-field-hint { margin: 8px 0 0; color: var(--p-orange); font-size: 10px; line-height: 1.5; }
</style>
