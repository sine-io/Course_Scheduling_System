<script setup lang="ts">
import {
  ArrowLeft, ArrowRight, CheckCircle2, Clock3, GraduationCap, ListChecks, Play, RefreshCw, Users,
} from '@lucide/vue'
import { NAlert, NButton, NSelect, NSpin, NTag, useMessage } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import { listAssignments } from '@/api/assignments'
import type { Assignment } from '@/api/assignments'
import { listClassUnits, listTeachers } from '@/api/basedata'
import type { ClassUnit, Teacher } from '@/api/basedata'
import { getPeriodSetup, getSemester, listSemesters } from '@/api/semesters'
import type { PeriodSetupDraft, Semester, SemesterListItem } from '@/api/semesters'
import { preflight } from '@/api/solver'
import type { PreflightReport } from '@/api/solver'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import { useAuthStore } from '@/stores/auth'
import { useSemesterContextStore } from '@/stores/semesterContext'
import ClassesTab from '@/views/basedata/ClassesTab.vue'
import PeriodTableEditor from '@/views/settings/PeriodTableEditor.vue'
import Semesters from '@/views/settings/Semesters.vue'
import Assignments from './Assignments.vue'
import AutoSchedule from './AutoSchedule.vue'
import './scheduling-workspace.css'

type StepKey = 'classes' | 'periods' | 'subjects' | 'teachers' | 'start'
type StepState = 'done' | 'active' | 'blocked'
const STEP_KEYS: readonly StepKey[] = ['classes', 'periods', 'subjects', 'teachers', 'start']

interface FlowStep {
  key: StepKey
  title: string
  description: string
  summary: string
  state: StepState
  route: RouteLocationRaw
}

const message = useMessage()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const semesterContext = useSemesterContextStore()

const semesters = ref<SemesterListItem[]>([])
const semester = ref<Semester | null>(null)
const sid = ref<number | null>(null)
const classes = ref<ClassUnit[]>([])
const assignments = ref<Assignment[]>([])
const teachers = ref<Teacher[]>([])
const periodSetup = ref<PeriodSetupDraft | null>(null)
const check = ref<PreflightReport | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref<string | null>(null)

const canEdit = computed(() => (
  (auth.hasRole('admin') || auth.hasRole('director'))
  && (!semesterContext.authoritative || semesterContext.isCurrent(sid.value))
))
const canDelete = computed(() => (
  auth.hasRole('admin')
  && (!semesterContext.authoritative || semesterContext.isCurrent(sid.value))
))

const activeStep = computed<StepKey | null>(() => {
  const raw = Array.isArray(route.query.step) ? route.query.step[0] : route.query.step
  return STEP_KEYS.includes(raw as StepKey) ? raw as StepKey : null
})
const activePeriodTableId = computed<number | null>(() => {
  if (activeStep.value !== 'periods') return null
  const raw = Array.isArray(route.query.table) ? route.query.table[0] : route.query.table
  const id = Number(raw)
  return Number.isInteger(id) && id > 0 ? id : null
})

const semesterOptions = computed(() => semesters.value.map((item) => ({
  label: item.label,
  value: item.id,
})))

const classesReady = computed(() => classes.value.length > 0)
const periodsReady = computed(() => {
  if (periodSetup.value) {
    // Suggested groups are a preview; the timetable needs persisted periods.
    return periodSetup.value.source === 'existing' && periodSetup.value.ready
  }
  const tables = semester.value?.period_tables ?? []
  if (!classes.value.length || !tables.length) return false
  const defaultTable = tables.find((table) => table.is_default) ?? tables[0]
  const tableById = new Map(tables.map((table) => [table.id, table]))
  return classes.value.every((item) => {
    const table = (item.period_table_id ? tableById.get(item.period_table_id) : null) ?? defaultTable
    return table.periods.some((period) => period.type === 'regular')
  })
})
const subjectsReady = computed(() => assignments.value.length > 0)
const assignedTeacherCount = computed(() => assignments.value.filter((item) => item.teachers.length > 0).length)
const teachersReady = computed(() => subjectsReady.value && assignedTeacherCount.value === assignments.value.length)
const totalPeriods = computed(() => assignments.value.reduce((total, item) => total + item.periods_per_week, 0))
const nextStepKey = computed<StepKey>(() => {
  if (!classesReady.value) return 'classes'
  if (!periodsReady.value) return 'periods'
  if (!subjectsReady.value) return 'subjects'
  if (!teachersReady.value) return 'teachers'
  return 'start'
})

function routeFor(key: StepKey): RouteLocationRaw {
  const query: Record<string, string> = { step: key }
  if (sid.value) query.semester = String(sid.value)
  return { name: 'scheduling-flow', query }
}

function stepState(key: StepKey): StepState {
  if (key === 'classes') return classesReady.value ? 'done' : 'active'
  if (key === 'periods') return periodsReady.value ? 'done' : (classesReady.value ? 'active' : 'blocked')
  if (key === 'subjects') return subjectsReady.value ? 'done' : (periodsReady.value ? 'active' : 'blocked')
  if (key === 'teachers') return teachersReady.value ? 'done' : (subjectsReady.value ? 'active' : 'blocked')
  return teachersReady.value ? (check.value?.ok ? 'done' : 'active') : 'blocked'
}

const steps = computed<FlowStep[]>(() => [
  {
    key: 'classes',
    title: '设置班级',
    description: '确认本学期参与排课的班级。',
    summary: classesReady.value ? `已设置 ${classes.value.length} 个班级` : '尚未设置班级',
    state: stepState('classes'),
    route: routeFor('classes'),
  },
  {
    key: 'periods',
    title: '设置课时',
    description: '完成作息分组和常规课节次，确定可排容量。',
    summary: periodsReady.value
      ? `${periodSetup.value?.groups.length ?? 0} 组作息已就绪`
      : (periodSetup.value?.blockers[0] ?? '作息分组和节次尚未就绪'),
    state: stepState('periods'),
    route: routeFor('periods'),
  },
  {
    key: 'subjects',
    title: '科目节数',
    description: '为班级录入每门科目每周需要安排的节数。',
    summary: subjectsReady.value ? `${assignments.value.length} 项课程 · ${totalPeriods.value} 节/周` : '尚未录入科目节数',
    state: stepState('subjects'),
    route: routeFor('subjects'),
  },
  {
    key: 'teachers',
    title: '教师任课',
    description: '为每项课程指定授课教师，完成排课输入。',
    summary: subjectsReady.value
      ? `${assignedTeacherCount.value}/${assignments.value.length} 项课程已任课`
      : '先录入科目节数',
    state: stepState('teachers'),
    route: routeFor('teachers'),
  },
  {
    key: 'start',
    title: '开始排课',
    description: '运行前置检查并生成课表草稿。',
    summary: check.value?.ok
      ? '前置检查通过，可以开始'
      : (check.value && check.value.error_count > 0
        ? `${check.value.error_count} 项问题待处理`
        : '完成教师任课后开始检查'),
    state: stepState('start'),
    route: routeFor('start'),
  },
])

const currentStep = computed(() => steps.value.find((step) => step.key === nextStepKey.value) ?? steps.value[0])
const activeStepMeta = computed(() => (
  activeStep.value ? steps.value.find((step) => step.key === activeStep.value) ?? null : null
))
const flowSemesterId = computed(() => sid.value ?? 0)
const errorIssues = computed(() => (check.value?.issues ?? []).filter((issue) => issue.level === 'error'))
const currentStepLabel = computed(() => currentStep.value?.title ?? '设置班级')

async function loadSemesterData(id: number) {
  sid.value = id
  const [semesterData, listedClasses, listedAssignments, listedTeachers, report, setup] = await Promise.all([
    getSemester(id),
    listClassUnits(id),
    listAssignments(id),
    listTeachers(id),
    preflight(id),
    getPeriodSetup(id).catch(() => null),
  ])
  semester.value = semesterData
  classes.value = listedClasses
  assignments.value = listedAssignments
  teachers.value = listedTeachers
  check.value = report
  periodSetup.value = setup
}

async function loadPage() {
  loading.value = true
  loadError.value = null
  try {
    await semesterContext.load()
    semesters.value = await listSemesters()
    const rawSemester = Array.isArray(route.query.semester) ? route.query.semester[0] : route.query.semester
    const requestedSemesterId = Number(rawSemester)
    const currentId = semesters.value.find((item) => item.id === requestedSemesterId)?.id
      ?? semesters.value.find((item) => item.is_current)?.id
      ?? semesterContext.currentSemesterId
      ?? semesters.value[0]?.id
    if (currentId) await loadSemesterData(currentId)
    else {
      sid.value = null
      semester.value = null
      classes.value = []
      assignments.value = []
      teachers.value = []
      periodSetup.value = null
      check.value = null
    }
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取排课工作台，请重试。')
  } finally {
    loading.value = false
  }
}

async function onSemesterChange(id: number) {
  if (refreshing.value) return
  refreshing.value = true
  loadError.value = null
  try {
    await loadSemesterData(id)
    await router.replace({ query: { ...route.query, semester: String(id) } })
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取排课工作台，请重试。')
  } finally {
    refreshing.value = false
  }
}

async function refresh() {
  if (!sid.value || refreshing.value) return
  await onSemesterChange(sid.value)
}

function stepStateLabel(state: StepState): string {
  if (state === 'done') return '已完成'
  if (state === 'active') return '下一步'
  return '待前置'
}

function stepButtonLabel(step: FlowStep): string {
  if (step.key === 'start') return '开始排课'
  return step.state === 'done' ? '查看' : '去设置'
}

async function goToStep(step: FlowStep) {
  if (step.state === 'blocked') {
    message.info(`请先完成“${currentStepLabel.value}”`)
    return
  }
  await router.push(step.route)
}

async function returnToOverview() {
  if (sid.value) await refresh()
  const query = sid.value ? { semester: String(sid.value) } : undefined
  await router.replace({ name: 'scheduling-flow', query })
}

async function openPeriodTable(id: number) {
  if (!sid.value || !Number.isInteger(id) || id <= 0) return
  await router.push({
    name: 'scheduling-flow',
    query: { semester: String(sid.value), step: 'periods', table: String(id) },
  })
}

async function onEmbeddedChanged() {
  await refresh()
}

onMounted(loadPage)
</script>

<template>
  <div class="scheduling-page scheduling-flow-page" data-testid="scheduling-flow-page">
    <header class="scheduling-page-header">
      <div>
        <p class="scheduling-eyebrow">{{ activeStepMeta ? `排课工作台 · ${activeStepMeta.title}` : '排课工作台' }}</p>
        <h1>{{ activeStepMeta?.title ?? '开始排课' }}</h1>
        <p>{{ activeStepMeta?.description ?? '在一个入口内准备当前学期的排课数据、检查条件并生成课表草稿。' }}</p>
      </div>
      <div class="scheduling-header-actions">
        <n-select
          v-if="semesters.length"
          v-accessible-select="'选择工作学期'"
          :value="sid"
          :options="semesterOptions"
          :placeholder="'选择学期'"
          data-testid="flow-semester"
          :disabled="refreshing"
          @update:value="onSemesterChange"
        />
        <n-button quaternary :loading="refreshing" data-testid="flow-refresh" @click="refresh">
          <template #icon><RefreshCw :size="16" aria-hidden="true" /></template>
          {{ '刷新准备度' }}
        </n-button>
      </div>
    </header>

    <section v-if="loading" class="scheduling-state" data-testid="flow-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取排课工作台' }}</strong>
      <span>{{ '班级、作息、课程和前置检查加载完成后会显示在这里。' }}</span>
    </section>

    <section v-else-if="loadError" class="scheduling-state scheduling-state-error" data-testid="flow-error" role="alert">
      <RefreshCw :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '当前页面没有写入任何更改。' }}</span>
      <n-button type="primary" data-testid="flow-retry" @click="loadPage">{{ '重新读取' }}</n-button>
    </section>

    <section v-else-if="!sid" class="scheduling-state" data-testid="flow-empty">
      <Clock3 :size="24" aria-hidden="true" />
      <strong>{{ '尚未创建可用学期' }}</strong>
      <span>{{ '创建一个学期后，就可以从排课工作台开始操作。' }}</span>
      <n-button type="primary" @click="router.push({ name: 'semesters' })">{{ '创建学期' }}</n-button>
    </section>

    <template v-else>
      <n-alert v-if="!canEdit" type="info" data-testid="flow-readonly">
        {{ '当前角色仅可查看准备度，编辑和启动排课仅对教务主任开放。' }}
      </n-alert>

      <template v-if="activeStepMeta">
        <section class="flow-embedded-step" data-testid="flow-embedded-step">
          <div v-if="!activePeriodTableId" class="flow-embedded-toolbar">
            <div>
              <p class="scheduling-eyebrow">{{ '当前步骤' }}</p>
              <h2>{{ activeStepMeta.title }}</h2>
              <p>{{ activeStepMeta.description }}</p>
            </div>
            <n-button data-testid="flow-step-back" @click="returnToOverview">
              <template #icon><ArrowLeft :size="16" aria-hidden="true" /></template>
              {{ '返回排课工作台' }}
            </n-button>
          </div>

          <ClassesTab
            v-if="activeStep === 'classes'"
            :key="`flow-classes-${flowSemesterId}`"
            :semester-id="flowSemesterId"
            :can-edit="canEdit"
            :can-delete="canDelete"
            @changed="onEmbeddedChanged"
          />
          <PeriodTableEditor
            v-else-if="activeStep === 'periods' && activePeriodTableId"
            :key="`flow-period-editor-${activePeriodTableId}`"
            :embedded="true"
            :embedded-table-id="activePeriodTableId"
            @back="returnToOverview"
            @changed="onEmbeddedChanged"
          />
          <Semesters
            v-else-if="activeStep === 'periods'"
            :key="`flow-periods-${flowSemesterId}`"
            :embedded="true"
            :embedded-semester-id="flowSemesterId"
            @changed="onEmbeddedChanged"
            @edit-period-table="openPeriodTable"
          />
          <Assignments
            v-else-if="activeStep === 'subjects'"
            :key="`flow-subjects-${flowSemesterId}`"
            :embedded="true"
            :embedded-semester-id="flowSemesterId"
            embedded-mode="periods"
            @changed="onEmbeddedChanged"
          />
          <Assignments
            v-else-if="activeStep === 'teachers'"
            :key="`flow-teachers-${flowSemesterId}`"
            :embedded="true"
            :embedded-semester-id="flowSemesterId"
            embedded-mode="teachers"
            @changed="onEmbeddedChanged"
          />
          <AutoSchedule
            v-else
            :key="`flow-start-${flowSemesterId}`"
            :embedded="true"
            :embedded-semester-id="flowSemesterId"
          />
        </section>
      </template>

      <template v-else>
        <section class="scheduling-panel flow-summary-panel" data-testid="flow-summary">
          <div class="flow-summary-icon" aria-hidden="true"><GraduationCap :size="22" /></div>
          <div class="flow-summary-copy">
            <p class="scheduling-eyebrow">{{ '当前学期' }}</p>
            <h2>{{ semester?.label }}</h2>
            <p>{{ `下一步：${currentStepLabel}` }}</p>
          </div>
          <div class="flow-summary-stats">
            <span><Users :size="15" aria-hidden="true" />{{ classes.length }} 个班级</span>
            <span><ListChecks :size="15" aria-hidden="true" />{{ assignments.length }} 项课程</span>
            <n-tag v-if="check" size="small" :type="check.ok ? 'success' : 'warning'">
              {{ check.ok ? '检查通过' : `${check.error_count} 项问题` }}
            </n-tag>
          </div>
        </section>

        <section class="scheduling-panel flow-steps-panel" data-testid="scheduling-flow-steps">
          <header class="scheduling-panel-heading compact-heading">
            <div>
              <p class="scheduling-eyebrow">{{ '排课流程' }}</p>
              <h2>{{ '从准备到课表草稿' }}</h2>
              <p>{{ '每一步都在当前工作台内完成，完成状态由当前数据自动判断。' }}</p>
            </div>
            <ArrowRight :size="20" class="scheduling-heading-icon" aria-hidden="true" />
          </header>

          <div class="flow-step-list">
            <article
              v-for="(step, index) in steps"
              :key="step.key"
              class="flow-step"
              :class="`is-${step.state}`"
              :data-testid="`flow-step-${step.key}`"
            >
              <span class="flow-step-number" aria-hidden="true">
                <CheckCircle2 v-if="step.state === 'done'" :size="18" />
                <span v-else>{{ index + 1 }}</span>
              </span>
              <div class="flow-step-copy">
                <div class="flow-step-title-line">
                  <h3>{{ step.title }}</h3>
                  <n-tag size="small" :type="step.state === 'done' ? 'success' : step.state === 'active' ? 'info' : 'default'">
                    {{ stepStateLabel(step.state) }}
                  </n-tag>
                </div>
                <p>{{ step.description }}</p>
                <span>{{ step.summary }}</span>
              </div>
              <n-button
                :type="step.state === 'active' ? 'primary' : 'default'"
                :disabled="step.state === 'blocked' || (step.key === 'start' && !canEdit)"
                :data-testid="`flow-go-${step.key}`"
                @click="goToStep(step)"
              >
                <template #icon><Play v-if="step.key === 'start'" :size="15" aria-hidden="true" /><ArrowRight v-else :size="15" aria-hidden="true" /></template>
                {{ stepButtonLabel(step) }}
              </n-button>
            </article>
          </div>
        </section>

        <div v-if="errorIssues.length" class="flow-issues" data-testid="flow-issues">
          <n-alert type="warning" :bordered="false">
            <template #header>{{ '开始排课前仍有问题' }}</template>
            <ul class="flow-issue-list">
              <li v-for="issue in errorIssues.slice(0, 3)" :key="`${issue.code}-${issue.subject_id}`">{{ issue.message }}</li>
            </ul>
          </n-alert>
          <n-button size="small" @click="goToStep(steps.find((step) => step.key === (teachersReady ? 'start' : 'teachers'))!)">
            {{ teachersReady ? '打开自动排课' : '补齐教师任课' }}
          </n-button>
        </div>

        <section class="scheduling-panel flow-start-panel" data-testid="flow-start-panel">
          <div>
            <p class="scheduling-eyebrow">{{ '生成结果' }}</p>
            <h2>{{ teachersReady ? '准备生成课表草稿' : '先完成教师任课' }}</h2>
            <p>{{ teachersReady ? '开始后会先做一次前置检查；生成的草稿将自动打开课程表调整。' : '每项课程都需要至少一位授课教师，排课引擎才能计算。' }}</p>
          </div>
          <n-button
            type="primary"
            size="large"
            :disabled="!teachersReady || !canEdit"
            data-testid="flow-start"
            @click="goToStep(steps.find((step) => step.key === 'start')!)"
          >
            <template #icon><Play :size="17" aria-hidden="true" /></template>
            {{ '进入开始排课' }}
          </n-button>
        </section>
      </template>
    </template>
  </div>
</template>

<style scoped>
.scheduling-flow-page { width: 100%; }
.flow-embedded-step { display: grid; gap: var(--app-space-4); }
.flow-embedded-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
  padding: 2px 0;
}
.flow-embedded-toolbar h2 { margin: 0; font-size: 18px; }
.flow-embedded-toolbar p:last-child { margin: 5px 0 0; color: var(--app-text-muted); font-size: 13px; line-height: 1.5; }
.flow-summary-panel {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--app-space-4);
}
.flow-summary-icon {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border-radius: var(--app-radius-sm);
  background: var(--app-primary-soft);
  color: var(--app-primary-strong);
}
.flow-summary-copy { min-width: 0; }
.flow-summary-copy h2 { margin: 0; overflow-wrap: anywhere; font-size: 18px; }
.flow-summary-copy p:last-child { margin: 5px 0 0; color: var(--app-text-muted); font-size: 12px; }
.flow-summary-stats { display: flex; align-items: center; flex-wrap: wrap; justify-content: flex-end; gap: 10px; color: var(--app-text-muted); font-size: 12px; }
.flow-summary-stats span { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
.flow-steps-panel { display: grid; gap: var(--app-space-4); }
.flow-step-list { display: grid; gap: 10px; }
.flow-step {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
}
.flow-step.is-active { border-color: var(--app-primary-border); background: var(--app-primary-soft); }
.flow-step.is-done { border-color: var(--app-success-border); }
.flow-step.is-blocked { background: var(--app-surface-muted); }
.flow-step-number { display: grid; width: 30px; height: 30px; place-items: center; border-radius: 50%; background: var(--app-surface-muted); color: var(--app-text-muted); font-size: 13px; font-weight: 700; }
.flow-step.is-active .flow-step-number { background: var(--app-primary); color: var(--app-on-primary); }
.flow-step.is-done .flow-step-number { background: var(--app-success-soft); color: var(--app-success-pressed); }
.flow-step-copy { min-width: 0; }
.flow-step-title-line { display: flex; min-width: 0; align-items: center; flex-wrap: wrap; gap: 8px; }
.flow-step-title-line h3 { margin: 0; font-size: 14px; }
.flow-step-copy p { margin: 4px 0 2px; color: var(--app-text-muted); font-size: 12px; line-height: 1.5; }
.flow-step-copy > span { display: block; overflow-wrap: anywhere; color: var(--app-text-faint); font-size: 11px; }
.flow-step > .n-button { min-width: 84px; }
.flow-issue-list { display: grid; gap: 4px; margin: 0; padding-left: 18px; font-size: 12px; line-height: 1.5; }
.flow-issues { display: grid; gap: 8px; }
.flow-start-panel { display: flex; align-items: center; justify-content: space-between; gap: var(--app-space-4); }
.flow-start-panel h2 { margin: 0; font-size: 16px; }
.flow-start-panel p:last-child { margin: 5px 0 0; color: var(--app-text-muted); font-size: 12px; line-height: 1.5; }

@media (max-width: 700px) {
  .flow-embedded-toolbar { align-items: stretch; flex-direction: column; }
  .flow-embedded-toolbar .n-button { align-self: flex-start; }
  .flow-summary-panel { grid-template-columns: auto minmax(0, 1fr); }
  .flow-summary-stats { grid-column: 1 / -1; justify-content: flex-start; }
  .flow-step { grid-template-columns: 32px minmax(0, 1fr); align-items: start; }
  .flow-step > .n-button { grid-column: 2; justify-self: start; }
  .flow-start-panel { align-items: flex-start; flex-direction: column; }
}
</style>
