<script setup lang="ts">
import {
  ArrowLeft, ArrowRight, CalendarDays, CheckCircle2, Clock3, Database, GraduationCap, ListChecks,
  Play, RefreshCw, Users,
} from '@lucide/vue'
import {
  NAlert, NButton, NDatePicker, NInputNumber, NRadioButton, NRadioGroup, NSelect, NSpin, NTag,
  useMessage,
} from 'naive-ui'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import { classLoad, listAssignments } from '@/api/assignments'
import type { Assignment, ClassLoad } from '@/api/assignments'
import { listClassUnits, listSubjects, listTeachers } from '@/api/basedata'
import type { ClassUnit, Subject, Teacher } from '@/api/basedata'
import { createSemester, getPeriodSetup, getSemester, listSemesters } from '@/api/semesters'
import type { PeriodSetupDraft, Semester, SemesterListItem } from '@/api/semesters'
import { preflight } from '@/api/solver'
import type { PreflightIssue, PreflightReport } from '@/api/solver'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import { useAuthStore } from '@/stores/auth'
import { useAppConfigStore } from '@/stores/appConfig'
import { useSemesterContextStore } from '@/stores/semesterContext'
import ClassesTab from '@/views/basedata/ClassesTab.vue'
import CommonSubjectsQuickAdd from '@/views/basedata/CommonSubjectsQuickAdd.vue'
import SubjectsTab from '@/views/basedata/SubjectsTab.vue'
import TeachersTab from '@/views/basedata/TeachersTab.vue'
import type { BaseDataSection } from '@/views/basedata/BaseData.vue'
import PeriodTableEditor from '@/views/settings/PeriodTableEditor.vue'
import Assignments from './Assignments.vue'
import AutoSchedule from './AutoSchedule.vue'
import PeriodSetupWorkspace from './PeriodSetupWorkspace.vue'
import SchedulingSupportWorkspace from './SchedulingSupportWorkspace.vue'
import type { SupportPanel } from './SchedulingSupportWorkspace.vue'
import './scheduling-workspace.css'

type StepKey = 'classes' | 'periods' | 'subjects' | 'teachers' | 'start'
type StepState = 'done' | 'active' | 'blocked'
type ResourceView = 'work' | 'archive'
const STEP_KEYS: readonly StepKey[] = ['classes', 'periods', 'subjects', 'teachers', 'start']
const ROOM_ISSUE_CODES = new Set([
  'room_supply',
  'room_type_supply',
  'room_no_candidate',
])
const SEMESTER_ISSUE_CODES = new Set([
  'semester_dates_missing',
  'semester_dates_invalid',
])
const PERIOD_ISSUE_CODES = new Set([
  'no_period_table',
  'period_table_missing',
  'regular_period_missing',
  'period_time_invalid',
  'class_period_table_missing',
  'class_period_capacity_exceeded',
])
const TEACHER_ISSUE_CODES = new Set([
  'assignment_without_teacher',
  'assignment_teacher_missing',
  'teacher_overload',
])
const SUBJECT_ISSUE_CODES = new Set([
  'assignment_without_class',
  'class_assignment_periods_mismatch',
  'group_shape_mismatch',
  'class_overload',
  'block_infeasible',
  'block_exceeds_periods',
])

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
const appConfig = useAppConfigStore()
const semesterContext = useSemesterContextStore()

const semesters = ref<SemesterListItem[]>([])
const semester = ref<Semester | null>(null)
const sid = ref<number | null>(null)
const classes = ref<ClassUnit[]>([])
const assignments = ref<Assignment[]>([])
const classLoads = ref<ClassLoad[]>([])
const subjects = ref<Subject[]>([])
const teachers = ref<Teacher[]>([])
const periodSetup = ref<PeriodSetupDraft | null>(null)
const check = ref<PreflightReport | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref<string | null>(null)
const creatingSemester = ref(false)
const subjectArchiveRevision = ref(0)

const currentYear = new Date().getFullYear()
const semesterForm = ref({
  academic_year: currentYear,
  term: 1,
  start_date: null as string | null,
  end_date: null as string | null,
})
const yearMin = computed(() => appConfig.config.academic_year.min)
const yearMax = computed(() => appConfig.config.academic_year.max)
const termOptions = [
  { label: '第一学期', value: 1 },
  { label: '第二学期', value: 2 },
]

const canEdit = computed(() => (
  (auth.hasRole('admin') || auth.hasRole('director'))
  && (!semesterContext.authoritative || semesterContext.isCurrent(sid.value))
))
const canDelete = computed(() => (
  auth.hasRole('admin')
  && (!semesterContext.authoritative || semesterContext.isCurrent(sid.value))
))
const canManageSemesters = computed(() => (
  !auth.user || auth.hasRole('admin') || auth.hasRole('director')
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
const activeResourceView = computed<ResourceView>(() => {
  const raw = Array.isArray(route.query.view) ? route.query.view[0] : route.query.view
  return raw === 'archive' ? 'archive' : 'work'
})
const activeSupportPanel = computed<SupportPanel | null>(() => {
  const raw = Array.isArray(route.query.panel) ? route.query.panel[0] : route.query.panel
  return raw === 'semester' || raw === 'calendar' || raw === 'resources' ? raw : null
})
const resourceSection = computed<BaseDataSection>(() => {
  const raw = Array.isArray(route.query.resource) ? route.query.resource[0] : route.query.resource
  return raw === 'template' || raw === 'reference' || raw === 'teacher-accounts' || raw === 'rooms'
    ? raw
    : 'rooms'
})

const semesterOptions = computed(() => semesters.value.map((item) => ({
  label: item.label,
  value: item.id,
})))

function requestedSemesterId(): number | null {
  const raw = Array.isArray(route.query.semester) ? route.query.semester[0] : route.query.semester
  const id = Number(raw)
  return semesters.value.some((item) => item.id === id) ? id : null
}

function selectedSemesterId(): number | null {
  const contextId = semesterContext.currentSemesterId
  return requestedSemesterId()
    ?? semesters.value.find((item) => item.is_current)?.id
    ?? (contextId && semesters.value.some((item) => item.id === contextId) ? contextId : null)
    ?? semesters.value[0]?.id
    ?? null
}

const classesReady = computed(() => classes.value.length > 0)
const periodStructureReady = computed(() => {
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
const capacityIssues = computed(() => classLoads.value.filter((load) => load.over_capacity || load.assigned > load.capacity))
const periodsReady = computed(() => periodStructureReady.value && capacityIssues.value.length === 0)
const subjectsReady = computed(() => assignments.value.length > 0)
const assignedTeacherCount = computed(() => assignments.value.filter((item) => item.teachers.length > 0).length)
const teachersReady = computed(() => subjectsReady.value && assignedTeacherCount.value === assignments.value.length)
const startReady = computed(() => periodsReady.value && teachersReady.value)
const startBlockerMessage = computed(() => {
  if (!periodsReady.value) {
    return capacityIssues.value.length
      ? '请先补足常规课容量；当前设置可以保存，但不能进入后续排课。'
      : '先保存一套有效作息并完成常规课容量检查。'
  }
  return '每项课程都需要至少一位授课教师，排课引擎才能计算。'
})
const totalPeriods = computed(() => assignments.value.reduce((total, item) => total + item.periods_per_week, 0))
const nextStepKey = computed<StepKey>(() => {
  if (!classesReady.value) return 'classes'
  if (!periodsReady.value) return 'periods'
  if (!subjectsReady.value) return 'subjects'
  if (!teachersReady.value) return 'teachers'
  return 'start'
})

function routeFor(key: StepKey, view?: ResourceView): RouteLocationRaw {
  const query: Record<string, string> = { step: key }
  if (sid.value) query.semester = String(sid.value)
  if (view === 'archive') query.view = view
  return { name: 'scheduling-workbench', query }
}

function stepState(key: StepKey): StepState {
  if (key === 'classes') return classesReady.value ? 'done' : 'active'
  if (key === 'periods') return periodsReady.value ? 'done' : (classesReady.value ? 'active' : 'blocked')
  if (key === 'subjects') return !periodsReady.value ? 'blocked' : (subjectsReady.value ? 'done' : 'active')
  if (key === 'teachers') return !periodsReady.value || !subjectsReady.value
    ? 'blocked'
    : (teachersReady.value ? 'done' : 'active')
  return !periodsReady.value || !teachersReady.value
    ? 'blocked'
    : (check.value?.ok ? 'done' : 'active')
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
      ? `${periodSetup.value?.groups.length ?? 0} 组作息可用`
      : (capacityIssues.value[0]
        ? `${capacityIssues.value[0].name}课程量 ${capacityIssues.value[0].assigned} 节，常规容量仅 ${capacityIssues.value[0].capacity} 节`
        : (periodSetup.value?.blockers[0] ?? '作息分组和节次尚未就绪')),
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
const activeStepTitle = computed(() => activeStepMeta.value?.title ?? '')
const activeStepDescription = computed(() => activeStepMeta.value?.description ?? '')
const activeSurfaceMeta = computed(() => {
  if (activeSupportPanel.value === 'semester') {
    return {
      eyebrow: '排课工作台 · 学期管理',
      title: '学期与作息时间表',
      description: '维护学期日期、作息时间表和历史学期；保存后会同步回排课准备度。',
    }
  }
  if (activeSupportPanel.value === 'calendar') {
    return {
      eyebrow: '排课工作台 · 校历准备',
      title: '校历与排课准备',
      description: '维护停课与补课日期，并确认或撤销当前学期的排课准备状态。',
    }
  }
  if (activeSupportPanel.value === 'resources') {
    return {
      eyebrow: '排课工作台 · 基础数据',
      title: '基础数据',
      description: '维护教室/场地、模板导入、参考文件和教师账号绑定。',
    }
  }
  if (activeStepMeta.value) {
    return {
      eyebrow: `排课工作台 · ${activeStepMeta.value.title}`,
      title: activeStepMeta.value.title,
      description: activeStepMeta.value.description,
    }
  }
  return {
    eyebrow: '排课工作台',
    title: '排课工作台',
    description: '在一个入口内准备当前学期的排课数据、检查条件并生成课表草稿。',
  }
})
const flowSemesterId = computed(() => sid.value ?? 0)
const errorIssues = computed(() => (check.value?.issues ?? []).filter((issue) => issue.level === 'error'))
const currentStepLabel = computed(() => currentStep.value?.title ?? '设置班级')
const issueActionLabel = computed(() => {
  const issue = errorIssues.value[0]
  if (!issue) return '查看排课准备'
  if (SEMESTER_ISSUE_CODES.has(issue.code)) return '维护学期日期'
  if (ROOM_ISSUE_CODES.has(issue.code)) return '管理教室/场地'
  return `前往${steps.value.find((step) => step.key === issueStepKey(issue))?.title ?? '开始排课'}`
})

function clearSemesterData() {
  sid.value = null
  semester.value = null
  classes.value = []
  assignments.value = []
  classLoads.value = []
  subjects.value = []
  teachers.value = []
  periodSetup.value = null
  check.value = null
}

async function loadSemesterData(id: number) {
  const [semesterData, listedClasses, listedAssignments, listedSubjects, listedTeachers, report, setup, listedClassLoads] = await Promise.all([
    getSemester(id),
    listClassUnits(id),
    listAssignments(id),
    listSubjects(id),
    listTeachers(id),
    preflight(id),
    getPeriodSetup(id).catch(() => null),
    classLoad(id),
  ])
  // Commit all derived readiness data together so a URL switch never mixes semesters.
  sid.value = id
  semester.value = semesterData
  classes.value = listedClasses
  assignments.value = listedAssignments
  classLoads.value = listedClassLoads
  subjects.value = listedSubjects
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
    const currentId = selectedSemesterId()
    if (currentId) await loadSemesterData(currentId)
    else clearSemesterData()
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取排课工作台，请重试。')
  } finally {
    loading.value = false
    // Reconcile a history navigation that happened while the initial load was in flight.
    if (!loadError.value) void syncRouteSemester()
  }
}

async function syncRouteSemester() {
  if (loading.value || refreshing.value) return
  const id = requestedSemesterId()
  if (!id || id === sid.value) return

  refreshing.value = true
  loadError.value = null
  try {
    await loadSemesterData(id)
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取排课工作台，请重试。')
  } finally {
    refreshing.value = false
    // A history navigation can happen while the previous semester is loading.
    if (requestedSemesterId() !== sid.value) void syncRouteSemester()
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

function stepButtonLabel(step: FlowStep): string {
  if (step.key === 'start') return '开始排课'
  if ((step.key === 'subjects' || step.key === 'teachers') && step.state === 'blocked') return '维护档案'
  return step.state === 'done' ? '查看' : '去设置'
}

function isResourceStep(key: StepKey): boolean {
  return key === 'subjects' || key === 'teachers'
}

function canOpenStep(step: FlowStep): boolean {
  return step.state !== 'blocked' || isResourceStep(step.key)
}

function issueStepKey(issue: PreflightIssue): StepKey {
  if (PERIOD_ISSUE_CODES.has(issue.code) || issue.subject_type === 'period') return 'periods'
  if (TEACHER_ISSUE_CODES.has(issue.code) || issue.subject_type === 'teacher') {
    return 'teachers'
  }
  if (
    SUBJECT_ISSUE_CODES.has(issue.code)
    || issue.subject_type === 'assignment'
    || issue.subject_type === 'class'
  ) return 'subjects'
  return 'start'
}

async function goToStep(step: FlowStep) {
  if (!canOpenStep(step)) {
    message.info(`请先完成“${currentStepLabel.value}”`)
    return
  }
  const route = step.state === 'blocked' && isResourceStep(step.key)
    ? routeFor(step.key, 'archive')
    : step.route
  await router.push(route)
}

async function goToIssueSource() {
  const issue = errorIssues.value[0]
  if (!issue) return
  if (SEMESTER_ISSUE_CODES.has(issue.code)) {
    await openSupportPanel('semester')
    return
  }
  if (ROOM_ISSUE_CODES.has(issue.code)) {
    await openSupportPanel('resources', 'rooms')
    return
  }
  const step = steps.value.find((item) => item.key === issueStepKey(issue))
  // Preflight already identifies the owning maintenance surface. Open it directly
  // even when an earlier step is blocked, so every error has a useful destination.
  if (step) await router.push(step.route)
}

async function setResourceView(view: ResourceView) {
  const query = { ...route.query }
  if (view === 'archive') query.view = 'archive'
  else delete query.view
  await router.replace({ query })
}

async function returnToOverview() {
  if (sid.value) await refresh()
  const query = sid.value ? { semester: String(sid.value) } : undefined
  await router.replace({ name: 'scheduling-workbench', query })
}

async function openSupportPanel(panel: SupportPanel, section?: BaseDataSection) {
  if (!sid.value) return
  const query: Record<string, string> = {
    panel,
    semester: String(sid.value),
  }
  if (panel === 'resources') query.resource = section ?? 'rooms'
  await router.push({ name: 'scheduling-workbench', query })
}

async function openPeriodTable(id: number) {
  if (!sid.value || !Number.isInteger(id) || id <= 0) return
  await router.push({
    name: 'scheduling-workbench',
    query: { semester: String(sid.value), step: 'periods', table: String(id) },
  })
}

async function onEmbeddedChanged() {
  if (activeStep.value === 'subjects' && activeResourceView.value === 'archive') {
    subjectArchiveRevision.value += 1
  }
  await refresh()
}

async function onEmbeddedSemestersChanged(preferredSemesterId?: number) {
  const query = preferredSemesterId ? { semester: String(preferredSemesterId) } : undefined
  await router.replace({ name: 'scheduling-workbench', query })
  await loadPage()
}

async function onCreateSemester() {
  if (!canManageSemesters.value || creatingSemester.value) return
  if (!semesterForm.value.start_date || !semesterForm.value.end_date) {
    message.warning('请选择学期的起止日期')
    return
  }
  creatingSemester.value = true
  try {
    const created = await createSemester({
      academic_year: semesterForm.value.academic_year,
      term: semesterForm.value.term,
      start_date: semesterForm.value.start_date,
      end_date: semesterForm.value.end_date,
    })
    message.success('学期已创建')
    await router.replace({
      name: 'scheduling-workbench',
      query: { semester: String(created.id) },
    })
    await loadPage()
  } catch (error) {
    message.error(apiErrorMessage(error, '暂时无法创建学期，请重试。'))
  } finally {
    creatingSemester.value = false
  }
}

onMounted(loadPage)
watch(() => route.query.semester, () => {
  void syncRouteSemester()
})
</script>

<template>
  <div class="scheduling-page scheduling-flow-page" data-testid="scheduling-flow-page">
    <header class="scheduling-page-header">
      <div>
        <p class="scheduling-eyebrow">{{ activeSurfaceMeta.eyebrow }}</p>
        <h1>{{ activeSurfaceMeta.title }}</h1>
        <p>{{ activeSurfaceMeta.description }}</p>
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

    <section v-else-if="!sid" class="scheduling-panel flow-empty-panel" data-testid="flow-empty">
      <div class="flow-empty-heading">
        <Clock3 :size="24" aria-hidden="true" />
        <div>
          <strong>{{ '尚未创建可用学期' }}</strong>
          <p>{{ '先在当前排课工作台创建学期，随后即可继续设置班级、作息和课程。' }}</p>
        </div>
      </div>
      <div v-if="canManageSemesters" class="flow-create-form" data-testid="flow-semester-create-form">
        <div class="scheduling-form-grid">
          <div class="scheduling-field">
            <label for="flow-semester-academic-year">{{ '学年起始年' }}</label>
            <n-input-number id="flow-semester-academic-year" v-model:value="semesterForm.academic_year" :min="yearMin" :max="yearMax" data-testid="flow-semester-academic-year" />
          </div>
          <div class="scheduling-field">
            <label for="flow-semester-term">{{ '学期' }}</label>
            <n-select id="flow-semester-term" v-model:value="semesterForm.term" :options="termOptions" data-testid="flow-semester-term" />
          </div>
          <div class="scheduling-field">
            <label for="flow-semester-start-date">{{ '开始日期' }}</label>
            <n-date-picker id="flow-semester-start-date" v-model:formatted-value="semesterForm.start_date" data-testid="flow-semester-start-date" value-format="yyyy-MM-dd" type="date" />
          </div>
          <div class="scheduling-field">
            <label for="flow-semester-end-date">{{ '结束日期' }}</label>
            <n-date-picker id="flow-semester-end-date" v-model:formatted-value="semesterForm.end_date" data-testid="flow-semester-end-date" value-format="yyyy-MM-dd" type="date" />
          </div>
        </div>
        <div class="flow-create-actions">
          <n-button type="primary" data-testid="flow-semester-create" :loading="creatingSemester" :disabled="creatingSemester || !semesterForm.start_date || !semesterForm.end_date" @click="onCreateSemester">
            <template #icon><GraduationCap :size="16" aria-hidden="true" /></template>
            {{ '创建学期并继续' }}
          </n-button>
        </div>
      </div>
      <span v-else>{{ '当前角色没有创建学期的权限，请联系教务主任。' }}</span>
    </section>

    <template v-else>
      <n-alert v-if="!canEdit" type="info" data-testid="flow-readonly">
        {{ '当前角色仅可查看准备度，编辑和启动排课仅对教务主任开放。' }}
      </n-alert>

      <template v-if="activeSupportPanel">
        <SchedulingSupportWorkspace
          :key="`flow-support-${activeSupportPanel}-${resourceSection}-${flowSemesterId}`"
          :panel="activeSupportPanel"
          :semester-id="flowSemesterId"
          :resource-section="resourceSection"
          @back="returnToOverview"
          @changed="onEmbeddedChanged"
          @semesters-changed="onEmbeddedSemestersChanged"
          @edit-period-table="openPeriodTable"
        />
      </template>

      <template v-else-if="activeStepMeta">
        <section class="flow-embedded-step" data-testid="flow-embedded-step">
          <div v-if="!activePeriodTableId" class="flow-embedded-toolbar">
            <div>
              <p class="scheduling-eyebrow">{{ '当前步骤' }}</p>
              <h2>{{ activeStepMeta.title }}</h2>
              <p>{{ activeStepMeta.description }}</p>
            </div>
            <div class="flow-embedded-toolbar-actions">
              <n-radio-group
                v-if="activeStep === 'subjects' || activeStep === 'teachers'"
                :value="activeResourceView"
                size="small"
                :aria-label="activeStep === 'subjects' ? '选择科目设置视图' : '选择教师设置视图'"
                :data-testid="`flow-${activeStep}-view`"
                @update:value="setResourceView"
              >
                <n-radio-button value="archive" :data-testid="`flow-${activeStep}-archive`">
                  {{ activeStep === 'subjects' ? '科目档案' : '教师档案' }}
                </n-radio-button>
                <n-radio-button value="work" :data-testid="`flow-${activeStep}-work`">
                  {{ activeStep === 'subjects' ? '科目节数' : '教师任课' }}
                </n-radio-button>
              </n-radio-group>
              <n-button data-testid="flow-step-back" @click="returnToOverview">
                <template #icon><ArrowLeft :size="16" aria-hidden="true" /></template>
                {{ '返回排课工作台' }}
              </n-button>
            </div>
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
          <PeriodSetupWorkspace
            v-else-if="activeStep === 'periods'"
            :key="`flow-periods-${flowSemesterId}`"
            :semester-id="flowSemesterId"
            :assignments="assignments"
            :class-loads="classLoads"
            :can-edit="canEdit"
            @changed="onEmbeddedChanged"
            @edit-period-table="openPeriodTable"
          />
          <section
            v-else-if="activeStep === 'subjects' && activeResourceView === 'archive'"
            class="flow-subject-archive"
            data-testid="flow-subject-archive"
          >
            <CommonSubjectsQuickAdd
              :key="`flow-common-subjects-${flowSemesterId}`"
              :semester-id="flowSemesterId"
              :subjects="subjects"
              :can-edit="canEdit"
              @changed="onEmbeddedChanged"
            />
            <SubjectsTab
              :key="`flow-subject-archive-${flowSemesterId}-${subjectArchiveRevision}`"
              :semester-id="flowSemesterId"
              :can-edit="canEdit"
              :can-delete="canDelete"
              @changed="onEmbeddedChanged"
            />
          </section>
          <Assignments
            v-else-if="activeStep === 'subjects'"
            :key="`flow-subjects-${flowSemesterId}`"
            :embedded="true"
            :embedded-semester-id="flowSemesterId"
            embedded-mode="periods"
            @changed="onEmbeddedChanged"
          />
          <TeachersTab
            v-else-if="activeStep === 'teachers' && activeResourceView === 'archive'"
            :key="`flow-teacher-archive-${flowSemesterId}`"
            :semester-id="flowSemesterId"
            :can-edit="canEdit"
            :can-delete="canDelete"
            :can-manage-accounts="false"
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
            <span><Users :size="15" aria-hidden="true" />{{ teachers.length }} 位教师</span>
            <span><ListChecks :size="15" aria-hidden="true" />{{ subjects.length }} 个科目</span>
            <span><ListChecks :size="15" aria-hidden="true" />{{ assignments.length }} 项课程</span>
            <n-tag v-if="check" size="small" :type="check.ok ? 'success' : 'warning'">
              {{ check.ok ? '检查通过' : `${check.error_count} 项问题` }}
            </n-tag>
          </div>
        </section>

        <section class="flow-c-layout" data-testid="flow-c-layout">
          <aside class="scheduling-panel flow-c-overview" data-testid="flow-c-overview">
            <div class="flow-c-overview-heading">
              <div>
                <p class="scheduling-eyebrow">{{ '五步进度' }}</p>
                <h2>{{ '当前学期' }}</h2>
              </div>
              <n-button quaternary circle size="small" aria-label="刷新准备度" title="刷新准备度" @click="refresh">
                <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
              </n-button>
            </div>
            <div class="flow-c-progress">
              <strong>{{ `${Math.round((steps.filter((step) => step.state === 'done').length / steps.length) * 100)}%` }}</strong>
              <span>{{ '准备度' }}</span>
              <div class="flow-c-progress-bar"><span :style="{ width: `${(steps.filter((step) => step.state === 'done').length / steps.length) * 100}%` }" /></div>
            </div>
            <div class="flow-c-step-list" data-testid="scheduling-flow-steps">
              <button
                v-for="(step, index) in steps"
                :key="step.key"
                class="flow-c-step"
                :class="`is-${step.state}`"
                type="button"
                :data-testid="`flow-go-${step.key}`"
                :data-flow-step-key="step.key"
                :aria-label="stepButtonLabel(step)"
                @click="goToStep(step)"
              >
                <span class="flow-c-step-number"><CheckCircle2 v-if="step.state === 'done'" :size="15" /><span v-else>{{ index + 1 }}</span></span>
                <span class="flow-c-step-copy"><strong>{{ step.title }}</strong><small>{{ step.summary }}</small></span>
                <ArrowRight :size="14" aria-hidden="true" />
              </button>
            </div>
            <div class="flow-c-activity">
              <p class="scheduling-eyebrow">{{ '辅助入口' }}</p>
              <div class="flow-c-support-links">
                <n-button text size="small" data-testid="flow-open-semester-support" @click="openSupportPanel('semester')"><template #icon><GraduationCap :size="14" /></template>{{ '学期管理' }}</n-button>
                <n-button text size="small" data-testid="flow-open-calendar-support" @click="openSupportPanel('calendar')"><template #icon><CalendarDays :size="14" /></template>{{ '校历与排课准备' }}</n-button>
                <n-button text size="small" data-testid="flow-open-resources-support" @click="openSupportPanel('resources', 'rooms')"><template #icon><Database :size="14" /></template>{{ '基础数据' }}</n-button>
              </div>
            </div>
          </aside>

          <section class="scheduling-panel flow-c-detail" data-testid="flow-c-detail">
            <div v-if="!activeStepMeta" class="flow-c-detail-empty">
              <span class="flow-c-detail-icon"><ListChecks :size="24" aria-hidden="true" /></span>
              <p class="scheduling-eyebrow">{{ '详情区域' }}</p>
              <h2>{{ '从左侧选择一个步骤' }}</h2>
              <p>{{ '班级、课时、科目、教师和自动排课都在当前学期内完成；选择后这里显示该步骤的完整业务工作面。' }}</p>
              <n-button type="primary" @click="goToStep(currentStep)">
                <template #icon><Play :size="15" aria-hidden="true" /></template>
                {{ `进入${currentStep.title}` }}
              </n-button>
            </div>
            <template v-else>
              <div class="flow-c-detail-heading">
                <div>
                  <p class="scheduling-eyebrow">{{ `排课工作台 · ${activeStepTitle}` }}</p>
                  <h2>{{ activeStepTitle }}</h2>
                  <p>{{ activeStepDescription }}</p>
                </div>
                <n-button data-testid="flow-step-back" @click="returnToOverview">
                  <template #icon><ArrowLeft :size="16" aria-hidden="true" /></template>
                  {{ '返回总览' }}
                </n-button>
              </div>
              <div class="flow-c-detail-body">
                <ClassesTab v-if="activeStep === 'classes'" :key="`flow-classes-${flowSemesterId}`" :semester-id="flowSemesterId" :can-edit="canEdit" :can-delete="canDelete" @changed="onEmbeddedChanged" />
                <PeriodTableEditor v-else-if="activeStep === 'periods' && activePeriodTableId" :key="`flow-period-editor-${activePeriodTableId}`" :embedded="true" :embedded-table-id="activePeriodTableId" @back="returnToOverview" @changed="onEmbeddedChanged" />
                <PeriodSetupWorkspace v-else-if="activeStep === 'periods'" :key="`flow-periods-${flowSemesterId}`" :semester-id="flowSemesterId" :assignments="assignments" :class-loads="classLoads" :can-edit="canEdit" @changed="onEmbeddedChanged" @edit-period-table="openPeriodTable" />
                <section v-else-if="activeStep === 'subjects' && activeResourceView === 'archive'" class="flow-subject-archive" data-testid="flow-subject-archive"><CommonSubjectsQuickAdd :key="`flow-common-subjects-${flowSemesterId}`" :semester-id="flowSemesterId" :subjects="subjects" :can-edit="canEdit" @changed="onEmbeddedChanged" /><SubjectsTab :key="`flow-subject-archive-${flowSemesterId}-${subjectArchiveRevision}`" :semester-id="flowSemesterId" :can-edit="canEdit" :can-delete="canDelete" @changed="onEmbeddedChanged" /></section>
                <div v-else-if="activeStep === 'subjects'" class="flow-c-embedded"><n-radio-group v-if="activeResourceView === 'work'" :value="activeResourceView" size="small" aria-label="选择科目设置视图" @update:value="setResourceView"><n-radio-button value="archive" data-testid="flow-subjects-archive">{{ '科目档案' }}</n-radio-button><n-radio-button value="work" data-testid="flow-subjects-work">{{ '科目节数' }}</n-radio-button></n-radio-group><Assignments :key="`flow-subjects-${flowSemesterId}`" :embedded="true" :embedded-semester-id="flowSemesterId" embedded-mode="periods" @changed="onEmbeddedChanged" /></div>
                <TeachersTab v-else-if="activeStep === 'teachers' && activeResourceView === 'archive'" :key="`flow-teacher-archive-${flowSemesterId}`" :semester-id="flowSemesterId" :can-edit="canEdit" :can-delete="canDelete" :can-manage-accounts="false" @changed="onEmbeddedChanged" />
                <div v-else-if="activeStep === 'teachers'" class="flow-c-embedded"><n-radio-group v-if="activeResourceView === 'work'" :value="activeResourceView" size="small" aria-label="选择教师设置视图" @update:value="setResourceView"><n-radio-button value="archive" data-testid="flow-teachers-archive">{{ '教师档案' }}</n-radio-button><n-radio-button value="work" data-testid="flow-teachers-work">{{ '教师任课' }}</n-radio-button></n-radio-group><Assignments :key="`flow-teachers-${flowSemesterId}`" :embedded="true" :embedded-semester-id="flowSemesterId" embedded-mode="teachers" @changed="onEmbeddedChanged" /></div>
                <AutoSchedule v-else :key="`flow-start-${flowSemesterId}`" :embedded="true" :embedded-semester-id="flowSemesterId" />
              </div>
            </template>
          </section>
        </section>

        <div v-if="errorIssues.length" class="flow-issues" data-testid="flow-issues">
          <n-alert type="warning" :bordered="false">
            <template #header>{{ '开始排课前仍有问题' }}</template>
            <ul class="flow-issue-list">
              <li v-for="issue in errorIssues.slice(0, 3)" :key="`${issue.code}-${issue.subject_id}`">{{ issue.message }}</li>
            </ul>
          </n-alert>
          <n-button size="small" data-testid="flow-go-issue" @click="goToIssueSource">
            {{ issueActionLabel }}
          </n-button>
        </div>

        <section class="scheduling-panel flow-start-panel" data-testid="flow-start-panel">
          <div>
            <p class="scheduling-eyebrow">{{ '生成结果' }}</p>
            <h2>{{ startReady ? '准备生成课表草稿' : (!periodsReady ? '先完成设置课时' : '先完成教师任课') }}</h2>
            <p>{{ startReady ? '开始后会先做一次前置检查；生成的草稿将自动打开课程表调整。' : startBlockerMessage }}</p>
          </div>
          <n-button
            type="primary"
            size="large"
            :disabled="!periodsReady || !teachersReady || !canEdit"
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
.flow-empty-panel { display: grid; gap: var(--app-space-5); padding: var(--app-space-panel); }
.flow-empty-heading { display: flex; align-items: flex-start; gap: var(--app-space-3); }
.flow-empty-heading > svg { flex: 0 0 auto; margin-top: 2px; color: var(--app-primary-strong); }
.flow-empty-heading strong { display: block; color: var(--app-text); font-size: 16px; }
.flow-empty-heading p { margin: 5px 0 0; color: var(--app-text-muted); font-size: 13px; line-height: 1.55; }
.flow-create-form { display: grid; gap: var(--app-space-4); }
.flow-create-actions { display: flex; justify-content: flex-start; flex-wrap: wrap; gap: var(--app-space-2); }
.flow-embedded-step { display: grid; gap: var(--app-space-4); }
.flow-subject-archive { display: grid; min-width: 0; gap: var(--app-space-4); }
.flow-embedded-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
  padding: 2px 0;
}
.flow-embedded-toolbar h2 { margin: 0; font-size: 18px; }
.flow-embedded-toolbar p:last-child { margin: 5px 0 0; color: var(--app-text-muted); font-size: 13px; line-height: 1.5; }
.flow-embedded-toolbar-actions { display: flex; align-items: center; flex-wrap: wrap; justify-content: flex-end; gap: var(--app-space-2); }
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
.flow-c-layout { display: grid; min-width: 0; grid-template-columns: minmax(230px, 275px) minmax(0, 1fr); align-items: start; gap: var(--app-space-4); }
.flow-c-overview, .flow-c-detail { min-width: 0; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); background: var(--app-surface); }
.flow-c-overview { display: grid; gap: var(--app-space-4); padding: var(--app-space-4); }
.flow-c-overview-heading, .flow-c-detail-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--app-space-3); }
.flow-c-overview-heading h2, .flow-c-detail-heading h2 { margin: 0; font-size: 17px; }
.flow-c-progress { display: grid; grid-template-columns: auto 1fr; align-items: baseline; gap: 3px 8px; padding: 0 5px; }
.flow-c-progress strong { color: var(--app-primary-strong); font-size: 26px; }
.flow-c-progress span { color: var(--app-text-muted); font-size: 11px; }
.flow-c-progress-bar { grid-column: 1 / -1; height: 6px; overflow: hidden; border-radius: 99px; background: var(--app-surface-muted); }
.flow-c-progress-bar span { display: block; height: 100%; border-radius: inherit; background: var(--app-primary); transition: width .2s ease; }
.flow-c-step-list { display: grid; gap: 5px; }
.flow-c-step { display: grid; width: 100%; min-width: 0; grid-template-columns: 28px minmax(0, 1fr) 14px; align-items: center; gap: 8px; padding: 9px 7px; border: 1px solid transparent; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-muted); text-align: left; cursor: pointer; }
.flow-c-step:hover { background: var(--app-surface-muted); }
.flow-c-step.is-active { border-color: var(--app-primary-border); background: var(--app-primary-soft); color: var(--app-primary-strong); }
.flow-c-step.is-done { color: var(--app-success-pressed); }
.flow-c-step.is-blocked { color: var(--app-text-faint); }
.flow-c-step-number { display: grid; width: 25px; height: 25px; place-items: center; border: 1px solid currentColor; border-radius: 50%; font-size: 10px; font-weight: 750; }
.flow-c-step-copy { display: grid; min-width: 0; gap: 3px; }
.flow-c-step-copy strong { overflow-wrap: anywhere; font-size: 12px; }
.flow-c-step-copy small { overflow: hidden; color: var(--app-text-faint); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.flow-c-step > svg { margin-left: auto; }
.flow-c-activity { display: grid; gap: 8px; padding-top: var(--app-space-3); border-top: 1px solid var(--app-border); }
.flow-c-support-links { display: grid; justify-items: start; gap: 4px; }
.flow-c-support-links .n-button { justify-content: flex-start; padding-inline: 0; }
.flow-c-detail { min-height: 510px; padding: var(--app-space-panel); }
.flow-c-detail-empty { display: grid; min-height: 440px; place-items: center; align-content: center; gap: 8px; text-align: center; }
.flow-c-detail-icon { display: grid; width: 50px; height: 50px; place-items: center; margin-bottom: 6px; border-radius: var(--app-radius-sm); background: var(--app-primary-soft); color: var(--app-primary-strong); }
.flow-c-detail-empty h2 { margin: 0; font-size: 20px; }
.flow-c-detail-empty p:last-of-type { max-width: 480px; margin: 0 0 8px; color: var(--app-text-muted); font-size: 12px; line-height: 1.6; }
.flow-c-detail-heading { margin-bottom: var(--app-space-4); }
.flow-c-detail-heading p:last-child { margin: 5px 0 0; color: var(--app-text-muted); font-size: 13px; line-height: 1.55; }
.flow-c-detail-body { display: grid; min-width: 0; gap: var(--app-space-4); }
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
  .flow-empty-panel { padding: var(--app-space-4); }
  .flow-embedded-toolbar { align-items: stretch; flex-direction: column; }
  .flow-embedded-toolbar-actions { align-items: stretch; justify-content: flex-start; }
  .flow-embedded-toolbar-actions > .n-radio-group { display: flex; }
  .flow-embedded-toolbar-actions > .n-radio-group .n-radio-button { flex: 1 1 0; }
  .flow-embedded-toolbar .n-button { align-self: flex-start; }
  .flow-summary-panel { grid-template-columns: auto minmax(0, 1fr); }
  .flow-summary-stats { grid-column: 1 / -1; justify-content: flex-start; }
  .flow-c-layout { grid-template-columns: minmax(0, 1fr); }
  .flow-c-overview { order: 0; }
  .flow-c-detail { order: 1; padding: var(--app-space-4); }
  .flow-c-detail-heading { align-items: stretch; flex-direction: column; }
  .flow-c-detail-heading .n-button { align-self: flex-start; }
  .flow-step { grid-template-columns: 32px minmax(0, 1fr); align-items: start; }
  .flow-step > .n-button { grid-column: 2; justify-self: start; }
  .flow-start-panel { align-items: flex-start; flex-direction: column; }
}
</style>
