<script setup lang="ts">
import {
  AlertTriangle, CheckCircle2, Clock3, FileWarning, Play, RefreshCw, ShieldCheck, SlidersHorizontal,
  Square, XCircle,
} from '@lucide/vue'
import {
  NAlert, NButton, NCheckbox, NCheckboxGroup, NInputNumber, NPopconfirm, NProgress,
  NSelect, NSpin, NTag, NText, useMessage,
} from 'naive-ui'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiErrorMessage, type ApiError } from '@/api/client'
import { listSemesters } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'
import {
  cancelSolveJob, getConstraintConfig, getSolveJob, listRelaxable, preflight, startAutoSchedule, stopSolveJob,
} from '@/api/solver'
import type {
  ConstraintConfig, PreflightIssue, PreflightReport, RelaxableOption, SolveJob,
} from '@/api/solver'
import { listTimetables } from '@/api/timetables'
import type { TimetableBrief } from '@/api/timetables'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import { useAuthStore } from '@/stores/auth'
import './scheduling-workspace.css'

const message = useMessage()
const router = useRouter()
const auth = useAuthStore()

const POLL_MS = 2000
const LAST_JOB_KEY = 'scheduling:auto-schedule-last-job'

const semesters = ref<SemesterListItem[]>([])
const sid = ref<number | null>(null)
const drafts = ref<TimetableBrief[]>([])
const sourceId = ref<number | null>(null)
const minutes = ref(10) // timeout 默认 10 分钟

const check = ref<PreflightReport | null>(null)
const constraints = ref<ConstraintConfig | null>(null)
const job = ref<SolveJob | null>(null)
const blockingIssues = ref<PreflightIssue[]>([])
const starting = ref(false)
const loading = ref(true)
const loadError = ref<string | null>(null)
const restoringJob = ref(false)

const relaxable = ref<RelaxableOption[]>([])
const allowPartial = ref(false)
const relax = ref<string[]>([])

let timer: ReturnType<typeof setInterval> | null = null
let pollGeneration = 0

const canEdit = computed(() => auth.hasRole('admin') || auth.hasRole('scheduler'))
const activeJobKey = computed(() => `${LAST_JOB_KEY}:${auth.user?.id ?? 'anonymous'}`)

const semesterOptions = computed(() => semesters.value.map((s) => ({ label: s.label, value: s.id })))
const draftOptions = computed(() =>
  drafts.value.map((t) => ({ label: `${t.name}(${t.entry_count} 格)`, value: t.id })))

const running = computed(() => job.value?.status === 'queued' || job.value?.status === 'running')
const explaining = computed(() => running.value && job.value?.phase === 'explaining')
const conflict = computed(() => job.value?.conflict ?? null)
const conflictCauses = computed(() => conflict.value?.causes ?? [])
const unscheduled = computed(() => job.value?.unscheduled ?? [])

// 进行中显示「已用掉多少时间预算」;结束后统一填满——提前结束时 elapsed 可能只有 1%,
// 进度条停在最左边却写着「已完成」会让人以为排课出了问题。
const progressPercent = computed(() => {
  if (!job.value) return 0
  if (!running.value) return 100
  return Math.min(100, Math.round((job.value.elapsed / job.value.max_seconds) * 100))
})

const statusTagType = computed(() => {
  if (running.value) return 'info'
  if (job.value?.status === 'finished') return 'success'
  if (job.value?.status === 'cancelled') return 'warning'
  return 'error'
})

const STATUS_LABELS = computed<Record<string, string>>(() => ({
  queued: '排队中', running: '排课中',
  finished: '已完成', failed: '失败', cancelled: '已取消',
}))
const statusLabel = computed(() =>
  (explaining.value ? '正在定位无解原因' : STATUS_LABELS.value[job.value?.status ?? ''] ?? ''))

const codeName = (code: string) => relaxable.value.find((o) => o.code === code)?.name ?? code

// 有试解在时限内没判定出来。each 的每一项仍是验证过的,只是列表可能不全;
// joint 则连「这组是不是最小」都没把握。两者要说不同的话。
const incompleteNote = computed(() => {
  if (conflict.value?.mode === 'joint') {
    return '（时间有限，这组未必是最小组合）'
  }
  return '（时间有限，可能还有其他原因未列出）'
})

const elapsedText = computed(() => {
  const s = job.value?.elapsed ?? 0
  return s < 1 ? '不到 1 秒' : `${Math.round(s)} ${'秒'}`
})
const unplacedPeriods = computed(() => unscheduled.value.reduce((n, u) => n + u.periods, 0))

function saveActiveJob(next: SolveJob | null) {
  if (typeof sessionStorage === 'undefined') return
  if (next) {
    sessionStorage.setItem(activeJobKey.value, JSON.stringify({ jobId: next.job_id, semesterId: next.semester_id }))
  } else {
    sessionStorage.removeItem(activeJobKey.value)
  }
}

function readActiveJob(): { jobId: string; semesterId: number } | null {
  if (typeof sessionStorage === 'undefined') return null
  try {
    const parsed = JSON.parse(sessionStorage.getItem(activeJobKey.value) ?? 'null') as Partial<{
      jobId: string
      semesterId: number
    }> | null
    if (typeof parsed?.jobId === 'string' && typeof parsed.semesterId === 'number') return parsed as {
      jobId: string
      semesterId: number
    }
  } catch {
    sessionStorage.removeItem(activeJobKey.value)
  }
  return null
}

function stopPolling() {
  pollGeneration += 1
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}
onUnmounted(() => stopPolling())

async function reload() {
  if (!sid.value) return
  const [all, report, config] = await Promise.all([
    listTimetables(sid.value),
    preflight(sid.value),
    getConstraintConfig(sid.value),
  ])
  drafts.value = all.filter((t) => t.status === 'draft')
  if (!drafts.value.some((draft) => draft.id === sourceId.value)) {
    sourceId.value = drafts.value[0]?.id ?? null
  }
  check.value = report
  constraints.value = config
}

async function onSemesterChange(id: number) {
  if (running.value || starting.value || restoringJob.value) return
  loading.value = true
  loadError.value = null
  if (sid.value !== id) {
    job.value = null
    saveActiveJob(null)
  }
  sid.value = id
  blockingIssues.value = []
  stopPolling()
  try {
    await reload()
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取自动排课设置，请重试。')
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  const generation = pollGeneration
  timer = setInterval(() => {
    if (generation === pollGeneration) void poll(generation)
  }, POLL_MS)
}

async function settleTerminalJob(announce = true) {
  if (!job.value || running.value) return
  stopPolling()
  if (announce && job.value.status === 'finished') message.success(`已生成“${job.value.result_name}”`)
  if (announce && job.value.status === 'cancelled') message.info('已取消排课')
  if (announce && job.value.status === 'failed') message.error(job.value.error ?? '排课失败')
  try {
    await reload()
  } catch (error) {
    message.error(apiErrorMessage(error, '结果已返回，但课表列表刷新失败。'))
  }
}

async function restoreActiveJob() {
  const saved = readActiveJob()
  if (!saved || saved.semesterId !== sid.value) return
  restoringJob.value = true
  try {
    const restored = await getSolveJob(saved.jobId)
    job.value = restored
    if (restored.status === 'queued' || restored.status === 'running') startPolling()
    else {
      saveActiveJob(restored)
      await settleTerminalJob(false)
    }
  } catch {
    saveActiveJob(null)
  } finally {
    restoringJob.value = false
  }
}

async function loadPage() {
  loading.value = true
  loadError.value = null
  try {
    ;[semesters.value, relaxable.value] = await Promise.all([listSemesters(), listRelaxable()])
    if (semesters.value.length) {
      const saved = readActiveJob()
      sid.value = semesters.value.find((semester) => semester.id === saved?.semesterId)?.id
        ?? semesters.value[0].id
      await reload()
      await restoreActiveJob()
    } else {
      sid.value = null
      drafts.value = []
      check.value = null
      constraints.value = null
    }
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取自动排课设置，请重试。')
  } finally {
    loading.value = false
  }
}

async function retryLoad() {
  await loadPage()
}

onMounted(loadPage)

async function poll(generation = pollGeneration) {
  if (!job.value) return
  try {
    const next = await getSolveJob(job.value.job_id)
    if (generation !== pollGeneration) return
    job.value = next
    saveActiveJob(next)
  } catch (error) {
    if (generation !== pollGeneration) return
    stopPolling()
    message.error(apiErrorMessage(error, '排课进度读取失败，页面不会把任务标记为完成。'))
    return
  }
  if (!running.value) await settleTerminalJob()
}

async function onStart() {
  if (!canEdit.value || !sourceId.value || running.value || starting.value) return
  starting.value = true
  blockingIssues.value = []
  try {
    const { job_id } = await startAutoSchedule(sourceId.value, minutes.value * 60, {
      allowPartial: allowPartial.value,
      relax: allowPartial.value ? relax.value : [],
    })
    job.value = await getSolveJob(job_id)
    saveActiveJob(job.value)
    if (running.value) startPolling()
    else await settleTerminalJob()
  } catch (e) {
    const detail = (e as ApiError).detail as unknown
    if (detail && typeof detail === 'object' && 'issues' in detail) {
      blockingIssues.value = (detail as { issues: PreflightIssue[] }).issues
      message.error('数据未通过排课前置检查')
    } else {
      message.error(apiErrorMessage(e, '无法启动排课'))
    }
  } finally {
    starting.value = false
  }
}

/** 照着冲突报告的建议重试:勾好可放宽的项目,直接再排一次。 */
async function onRetryPartial() {
  if (!canEdit.value) return
  allowPartial.value = true
  relax.value = conflict.value?.relaxable_codes ?? []
  stopPolling()
  saveActiveJob(null)
  job.value = null
  await onStart()
}

async function onStop() {
  if (!canEdit.value || !job.value || !running.value) return
  try {
    await stopSolveJob(job.value.job_id)
    message.info('已请求提前结束，将保留当前最佳解')
  } catch (error) {
    message.error(apiErrorMessage(error, '提前结束请求失败，请稍后重试。'))
  }
}
async function onCancel() {
  if (!canEdit.value || !job.value || !running.value) return
  try {
    await cancelSolveJob(job.value.job_id)
    message.info('已请求取消')
  } catch (error) {
    message.error(apiErrorMessage(error, '取消请求失败，请稍后重试。'))
  }
}

function openResult() {
  router.push({ name: 'versions' })
}
</script>

<template>
  <div class="scheduling-page auto-schedule-page" data-testid="auto-schedule-page">
    <header class="scheduling-page-header">
      <div>
        <p class="scheduling-eyebrow">{{ '求解作业' }}</p>
        <h1>{{ '自动排课' }}</h1>
        <p>{{ '先核对数据准备度和约束，再启动可追踪、可取消的排课任务。' }}</p>
      </div>
      <div class="scheduling-header-actions">
        <n-select
          v-if="semesters.length"
          v-accessible-select="'选择工作学期'"
          :value="sid"
          :options="semesterOptions"
          :placeholder="'选择学期'"
          data-testid="as-semester"
          :disabled="running || starting || restoringJob"
          @update:value="onSemesterChange"
        />
      </div>
    </header>

    <section v-if="loading" class="scheduling-state" data-testid="as-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取自动排课设置' }}</strong>
      <span>{{ '前置检查、草稿和约束配置加载完成后会显示在这里。' }}</span>
    </section>
    <section v-else-if="loadError" class="scheduling-state scheduling-state-error" data-testid="as-load-error" role="alert">
      <AlertTriangle :size="23" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '当前页面没有启动任何排课任务。' }}</span>
      <n-button type="primary" data-testid="as-retry-load" @click="retryLoad">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>
    <section v-else-if="!sid" class="scheduling-state" data-testid="as-empty">
      <Clock3 :size="24" aria-hidden="true" />
      <strong>{{ '尚未创建可用学期' }}</strong>
      <span>{{ '先创建学期和作息时间表，再启动自动排课。' }}</span>
      <n-button type="primary" @click="router.push({ name: 'semesters' })">{{ '前往学期配置' }}</n-button>
    </section>

    <template v-else>
      <n-alert v-if="!canEdit" type="info" data-testid="as-restricted">
        <template #icon><ShieldCheck :size="17" aria-hidden="true" /></template>
        {{ '当前角色仅可查看排课准备度和运行结果，启动、停止和取消任务仅对排课管理员开放。' }}
      </n-alert>

      <section v-if="check" class="scheduling-panel auto-preflight-panel" data-testid="as-preflight">
        <header class="scheduling-panel-heading compact-heading">
          <div>
            <p class="scheduling-eyebrow">{{ '启动前核对' }}</p>
            <h2>{{ '排课前置检查' }}</h2>
            <p>{{ check.class_count }} {{ '班' }} · {{ check.teacher_count }} {{ '位教师' }} · {{ check.assignment_count }} {{ '条教学任务' }} · {{ '共' }} {{ check.total_periods }} {{ '节' }}</p>
          </div>
          <FileWarning :size="20" class="scheduling-heading-icon" aria-hidden="true" />
        </header>
        <n-alert v-if="check.ok && check.warning_count === 0" type="success" :bordered="false">
          <template #icon><CheckCircle2 :size="17" aria-hidden="true" /></template>
          {{ '数据检查通过，可以开始排课' }}
        </n-alert>
        <n-alert v-else :type="check.ok ? 'warning' : 'error'" :bordered="false">
          <template #icon><AlertTriangle :size="17" aria-hidden="true" /></template>
          {{ check.error_count }} {{ '项错误' }}、{{ check.warning_count }} {{ '项提醒' }}
        </n-alert>
        <div v-for="i in check.issues" :key="i.code + i.subject_id" class="auto-issue" data-testid="pf-issue">
          <n-tag size="small" :type="i.level === 'error' ? 'error' : 'warning'">
            {{ i.level === 'error' ? '错误' : '提醒' }}
          </n-tag>
          <n-text>{{ i.message }}</n-text>
        </div>
      </section>

      <section class="scheduling-panel auto-constraints-panel" data-testid="as-constraints">
        <header class="scheduling-panel-heading compact-heading">
          <div>
            <p class="scheduling-eyebrow">{{ '求解边界' }}</p>
            <h2>{{ '当前约束配置' }}</h2>
            <p>{{ '这些设置由学期配置维护，自动排课会按当前值求解。' }}</p>
          </div>
          <SlidersHorizontal :size="20" class="scheduling-heading-icon" aria-hidden="true" />
        </header>
        <div v-if="constraints" class="auto-constraint-grid">
          <div class="auto-constraint-item"><span>{{ '同科目每日上限' }}</span><strong>{{ constraints.daily_subject_cap }} {{ '节' }}</strong></div>
          <div class="auto-constraint-item"><span>{{ '教师每日上限' }}</span><strong>{{ constraints.teacher_daily_max }} {{ '节' }}</strong></div>
          <div class="auto-constraint-item"><span>{{ '教师连续上课上限' }}</span><strong>{{ constraints.teacher_consecutive_max }} {{ '节' }}</strong></div>
          <div v-for="(weight, code) in constraints.weights" :key="code" class="auto-constraint-item">
            <span>{{ constraints.weight_names[code] ?? code }}</span><strong>{{ weight === 0 ? '关闭' : weight }}</strong>
          </div>
        </div>
        <div v-else class="scheduling-inline-empty" data-testid="as-constraints-loading">
          <n-spin size="small" /><span>{{ '正在读取约束配置' }}</span>
        </div>
      </section>

      <section class="scheduling-panel auto-start-panel">
        <header class="scheduling-panel-heading compact-heading">
          <div>
            <p class="scheduling-eyebrow">{{ '任务控制' }}</p>
            <h2>{{ '开始排课' }}</h2>
            <p>{{ '结果会写成新草稿，来源草稿保持不变。' }}</p>
          </div>
          <Play :size="20" class="scheduling-heading-icon" aria-hidden="true" />
        </header>
        <div class="auto-start-fields">
          <label class="scheduling-field auto-source-field">
            <span>{{ '来源草稿' }}</span>
            <n-select
              v-model:value="sourceId" v-accessible-select="'选择来源草稿'" :options="draftOptions"
              :placeholder="'选择草稿'" data-testid="as-source" :disabled="!canEdit || running || restoringJob"
            />
          </label>
          <label class="scheduling-field auto-minutes-field">
            <span>{{ '排课时间上限' }}</span>
            <n-input-number
              v-model:value="minutes" :min="1" :max="60" :disabled="!canEdit || running || restoringJob"
              data-testid="as-minutes"
            >
              <template #suffix>{{ '分钟' }}</template>
            </n-input-number>
          </label>
          <n-button
            type="primary" :loading="starting || restoringJob" :disabled="!canEdit || !sourceId || running || restoringJob"
            data-testid="as-start" @click="onStart"
          >
            <template #icon><Play :size="16" aria-hidden="true" /></template>
            {{ '开始排课' }}
          </n-button>
        </div>
        <p class="auto-start-note">{{ '锁定的单元格会保持原位；其余已排课程作为求解起点，结果写成新草稿。' }}</p>
        <label class="auto-partial-option">
          <n-checkbox v-model:checked="allowPartial" :disabled="!canEdit || running" data-testid="as-partial" />
          <span>{{ '允许部分排课（排不下的课程列成列表，不让整个任务失败）' }}</span>
        </label>
        <div v-if="allowPartial" class="auto-relax-options">
          <span class="auto-relax-label">{{ '可放宽' }}：</span>
          <n-checkbox-group v-model:value="relax" :disabled="!canEdit || running">
            <n-checkbox
              v-for="o in relaxable" :key="o.code" :value="o.code"
              :label="o.name" :data-testid="`as-relax-${o.code}`"
            />
          </n-checkbox-group>
        </div>
        <p v-if="allowPartial" class="auto-start-note auto-relax-note">{{ '班级、教师、教室/场地的“同一时段只能有一门课”不可放宽，这是物理限制，不是政策。' }}</p>
        <n-alert v-if="blockingIssues.length" type="error" :title="'请先修正这些问题'" data-testid="as-blocking-alert">
          <div v-for="i in blockingIssues" :key="i.code + i.subject_id" data-testid="as-blocking">{{ i.message }}</div>
        </n-alert>
      </section>

      <section v-if="job" class="scheduling-panel auto-progress-panel" data-testid="as-job">
        <header class="scheduling-panel-heading compact-heading">
          <div>
            <p class="scheduling-eyebrow">{{ '实时反馈' }}</p>
            <h2>{{ '排课进度' }}</h2>
            <p>{{ running ? '任务仍在服务端运行，离开页面不会把它标记为完成。' : '任务已返回最终状态，可继续查看报告或处理未排课程。' }}</p>
          </div>
          <Clock3 :size="20" class="scheduling-heading-icon" aria-hidden="true" />
        </header>
        <div class="auto-job-summary">
          <n-tag :type="statusTagType" data-testid="as-status">{{ statusLabel }}</n-tag>
          <span>{{ '已耗时' }} {{ elapsedText }} / {{ '上限' }} {{ job.max_seconds }} {{ '秒' }}</span>
          <span v-if="running || job.solutions" data-testid="as-solutions">{{ '已找到' }} {{ job.solutions }} {{ '个解' }}</span>
          <span v-if="job.partial && !running">{{ '未排' }} {{ unplacedPeriods }} {{ '节' }}</span>
          <span v-else-if="job.objective !== null">{{ '当前目标值' }} {{ Math.round(job.objective) }}</span>
        </div>
        <n-progress
          type="line" :percentage="progressPercent"
          :status="job.status === 'failed' ? 'error' : job.status === 'cancelled' ? 'warning' : running ? 'default' : 'success'"
          :processing="running"
        />
        <div v-if="running && !explaining" class="scheduling-actions">
          <n-button
            type="primary" ghost :disabled="!canEdit || job.solutions === 0"
            data-testid="as-stop" @click="onStop"
          >
            <template #icon><Square :size="15" aria-hidden="true" /></template>
            {{ '提前结束（取当前最佳解）' }}
          </n-button>
          <n-popconfirm @positive-click="onCancel">
            <template #trigger>
              <n-button type="error" ghost :disabled="!canEdit" data-testid="as-cancel">
                <template #icon><XCircle :size="15" aria-hidden="true" /></template>{{ '取消排课' }}
              </n-button>
            </template>
            {{ '取消后不会生成结果草稿，确定吗？' }}
          </n-popconfirm>
        </div>
        <p v-if="explaining" class="auto-explaining" data-testid="as-explaining">{{ '无法排出。正在逐项试解，找出是哪几项组合造成的……' }}</p>
        <n-alert v-if="job.status === 'failed' && !conflictCauses.length" type="error" data-testid="as-error">
          <template #icon><AlertTriangle :size="17" aria-hidden="true" /></template>{{ job.error || '排课失败，请查看服务端日志或调整约束后重试。' }}
        </n-alert>
        <n-alert v-if="conflict && conflictCauses.length" type="error" :title="conflict.headline" data-testid="as-conflict">
          <div class="auto-conflict-list">
            <div v-for="(c, k) in conflictCauses" :key="k" class="auto-conflict-item" data-testid="as-cause">
              <div><n-tag size="small" :bordered="false" :type="c.relaxable ? 'warning' : 'error'">{{ c.scope_name }}</n-tag><span>{{ c.message }}</span></div>
              <p>{{ '建议' }}：{{ c.suggestion }}</p>
            </div>
          </div>
          <p v-if="!conflict.complete" class="auto-start-note">{{ incompleteNote }}</p>
          <n-button
            v-if="conflict.relaxable_codes.length" type="primary" ghost size="small"
            :disabled="!canEdit" data-testid="as-retry-partial" @click="onRetryPartial"
          >
            {{ '改用部分排课' }}（{{ '放宽' }} {{ conflict.relaxable_codes.map(codeName).join('、') }}）
          </n-button>
        </n-alert>
        <n-alert v-if="job.status === 'finished'" type="success" data-testid="as-done">
          <template #icon><CheckCircle2 :size="17" aria-hidden="true" /></template>
          {{ '已生成新草稿' }}「{{ job.result_name }}」
          <n-button text type="primary" @click="openResult">{{ '前往版本与发布' }}</n-button>
        </n-alert>
        <n-alert v-if="unscheduled.length" type="warning" :title="'以下教学任务未能排入，请人工处理'" data-testid="as-unscheduled">
          <div class="scheduling-table-scroll auto-report-scroll" tabindex="0" aria-label="未排课程列表，可横向滚动">
            <table class="scheduling-data-table">
              <thead><tr><th>{{ '科目' }}</th><th>{{ '班级' }}</th><th>{{ '未排节数' }}</th><th>{{ '原因' }}</th></tr></thead>
              <tbody>
                <tr v-for="u in unscheduled" :key="u.assignment_ids.join('-')">
                  <td>{{ u.subject_name }}</td><td>{{ u.class_names.join('、') }}</td><td>{{ u.periods }} {{ '节' }}</td><td>{{ u.reason || '排课时权衡取舍' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </n-alert>
        <div v-if="job.report" class="scheduling-table-scroll auto-report-scroll" tabindex="0" aria-label="软约束报告，可横向滚动">
          <table class="scheduling-data-table" data-testid="as-report">
            <thead><tr><th>{{ '软约束' }}</th><th>{{ '权重' }}</th><th>{{ '达成' }}</th><th>{{ '未达成明细' }}</th></tr></thead>
            <tbody>
              <tr v-for="i in job.report.items" :key="i.code">
                <td>{{ i.code }} {{ i.name }}</td><td>{{ i.weight === 0 ? '关闭' : i.weight }}</td>
                <td>{{ i.satisfied }} / {{ i.opportunities }} <n-text :depth="3">({{ Math.round(i.rate * 100) }}%)</n-text></td>
                <td><n-text v-if="!i.details.length" depth="3">—</n-text><template v-else><div v-for="(d, k) in i.details.slice(0, 3)" :key="k">{{ d }}</div></template><n-text v-if="i.details.length > 3" depth="3">…{{ '等' }} {{ i.violations }} {{ '项' }}</n-text></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.auto-schedule-page { max-width: 1440px; }
.auto-start-fields { display: grid; grid-template-columns: minmax(190px, 1fr) minmax(140px, 190px) auto; align-items: end; gap: 14px; }
.auto-start-fields > .n-button { min-height: 40px; }
.auto-start-note { margin: 12px 0 0; color: var(--app-text-muted); font-size: 13px; line-height: 1.55; }
.auto-partial-option { display: flex; align-items: flex-start; gap: 8px; margin-top: 17px; color: var(--app-text); font-size: 13px; line-height: 1.5; }
.auto-relax-options { display: flex; align-items: flex-start; flex-wrap: wrap; gap: 10px; margin: 10px 0 0 28px; }
.auto-relax-label { color: var(--app-text-muted); font-size: 13px; }
.auto-relax-note { margin-left: 28px; }
.auto-issue { display: flex; align-items: flex-start; gap: 9px; margin-top: 10px; font-size: 13px; line-height: 1.5; }
.auto-constraint-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin-top: 16px; }
.auto-constraint-item { display: grid; gap: 4px; min-width: 0; padding: 12px; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); background: var(--app-surface-muted); }
.auto-constraint-item span { overflow-wrap: anywhere; color: var(--app-text-muted); font-size: 12px; }
.auto-constraint-item strong { color: var(--app-text); font-size: 16px; }
.auto-job-summary { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin: 16px 0 12px; color: var(--app-text-muted); font-size: 13px; }
.auto-explaining { margin: 12px 0; color: var(--app-text-muted); font-size: 13px; }
.auto-conflict-list { display: grid; gap: 12px; }
.auto-conflict-item > div { display: flex; align-items: flex-start; flex-wrap: wrap; gap: 8px; }
.auto-conflict-item p { margin: 5px 0 0 8px; color: var(--app-text-muted); font-size: 13px; }
.auto-report-scroll { margin-top: 12px; }
.auto-report-scroll table { min-width: 620px; }

@media (max-width: 820px) {
  .auto-start-fields { grid-template-columns: minmax(0, 1fr) minmax(120px, 0.6fr); }
  .auto-start-fields > .n-button { grid-column: 1 / -1; justify-self: start; }
}

@media (max-width: 560px) {
  .auto-start-fields { grid-template-columns: 1fr; }
  .auto-start-fields > .n-button { width: 100%; }
  .auto-relax-options, .auto-relax-note { margin-left: 0; }
  .auto-job-summary { align-items: flex-start; flex-direction: column; gap: 7px; }
}
</style>
