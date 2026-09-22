<script setup lang="ts">
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Download,
  FileCheck2,
  FileSpreadsheet,
  LoaderCircle,
  RefreshCw,
  Upload,
} from '@lucide/vue'
import { NAlert, NButton, NTag } from 'naive-ui'
import { computed, ref, watch } from 'vue'
import { apiErrorMessage } from '@/api/client'
import {
  confirmSemesterReadiness,
  getSemesterReadiness,
} from '@/api/calendar'
import type { SemesterReadiness } from '@/api/calendar'
import {
  commitTeacherArrangementImport,
  downloadTeacherArrangementTemplate,
  previewTeacherArrangementImport,
} from '@/api/imports'
import type {
  TeacherArrangementDecision,
  TeacherArrangementDecisionValue,
  TeacherArrangementIssue,
  TeacherArrangementCommitResult,
  TeacherArrangementMode,
  TeacherArrangementPreview,
  TeacherArrangementPreviewRow,
} from '@/api/imports'
import type { SemesterListItem } from '@/api/semesters'
import './template-import.css'

const props = defineProps<{
  semester: SemesterListItem
  canEdit: boolean
}>()
const emit = defineEmits<{ changed: [] }>()

const mode = ref<TeacherArrangementMode>('standard')
const file = ref<File | null>(null)
const preview = ref<TeacherArrangementPreview | null>(null)
const result = ref<TeacherArrangementCommitResult | null>(null)
const error = ref<string | null>(null)
const downloading = ref(false)
const previewing = ref(false)
const committing = ref(false)
const readinessLoading = ref(false)
const confirmingReadiness = ref(false)
const readiness = ref<SemesterReadiness | null>(null)
const confirmChanges = ref(false)
const confirmWarnings = ref(false)
const decisions = ref<Record<string, TeacherArrangementDecisionValue>>({})
type ReviewFilter =
  | 'blocker'
  | 'warning'
  | 'conflict'
  | 'new'
  | 'changed'
  | 'unchanged'
  | 'disappeared'
interface ReviewItem {
  key: string
  kind: 'issue' | 'row'
  sheet: string
  row: number
  field: string
  title: string
  message: string
  suggestion: string
  value: unknown
  status?: string
  changes: TeacherArrangementPreviewRow['changes']
  decision: TeacherArrangementDecision | null
}
const activeFilter = ref<ReviewFilter>('new')
const selectedReviewKey = ref<string | null>(null)
type FailedAction = 'download' | 'preview' | 'readiness' | 'confirm_readiness'
const failedAction = ref<FailedAction | null>(null)

const allRows = computed(() => (
  preview.value?.sheets.flatMap(sheet => sheet.rows.map(row => ({ ...row, label: sheet.label }))) ?? []
))
const decisionRows = computed(() => allRows.value.filter(row => row.decision !== null))
const unresolvedDecisionCount = computed(() => decisionRows.value.filter(row => (
  row.decision && !decisions.value[row.decision.key] && !row.decision.selected
)).length)
const pendingChangeCount = computed(() => (
  (preview.value?.counts.changed ?? 0)
  + decisionRows.value.filter(row => (
    row.decision?.kind === 'conflict'
    && (decisions.value[row.decision.key] ?? row.decision.selected) === 'incoming'
  )).length
))
const canCommit = computed(() => Boolean(
  props.canEdit
  && file.value
  && preview.value
  && !previewing.value
  && !committing.value
  && !preview.value.counts.blocker
  && !unresolvedDecisionCount.value
  && (!pendingChangeCount.value || confirmChanges.value)
  && (!preview.value.counts.warning || confirmWarnings.value),
))
const stepLabels = computed(() => (
  mode.value === 'scheduling_ready'
    ? ['选择范围', '准备文件', '校验数据', '确认导入', '确认就绪']
    : ['选择范围', '准备文件', '校验数据', '确认导入']
))
const canConfirmReadiness = computed(() => Boolean(
  props.canEdit
  && readiness.value
  && !readiness.value.ready
  && readiness.value.checks.every(check => check.ok),
))
const readinessNextHref = computed(() => (
  `/scheduling/flow?step=start&semester=${props.semester.id}`
))
const completedStep = computed(() => {
  if (result.value) return mode.value === 'scheduling_ready' ? 5 : 4
  if (preview.value) return 3
  if (file.value) return 2
  return 1
})
const retryBusy = computed(() => (
  downloading.value
  || previewing.value
  || committing.value
  || readinessLoading.value
  || confirmingReadiness.value
))
const retryLabel = computed(() => ({
  download: '重新下载',
  preview: '重新预览',
  readiness: '重新检查',
  confirm_readiness: '重新确认',
})[failedAction.value ?? 'preview'])
const filterDefinitions: Array<{ key: ReviewFilter, label: string }> = [
  { key: 'blocker', label: '阻断' },
  { key: 'warning', label: '警告' },
  { key: 'conflict', label: '冲突' },
  { key: 'new', label: '新增' },
  { key: 'changed', label: '变更' },
  { key: 'unchanged', label: '不变' },
  { key: 'disappeared', label: '消失' },
]
const filterCounts = computed<Record<ReviewFilter, number>>(() => ({
  blocker: preview.value?.counts.blocker ?? 0,
  warning: preview.value?.counts.warning ?? 0,
  conflict: preview.value?.counts.conflict ?? 0,
  new: preview.value?.counts.new ?? 0,
  changed: preview.value?.counts.changed ?? 0,
  unchanged: preview.value?.counts.unchanged ?? 0,
  disappeared: preview.value?.counts.disappeared ?? 0,
}))
const reviewItems = computed<ReviewItem[]>(() => {
  if (!preview.value) return []
  if (activeFilter.value === 'blocker' || activeFilter.value === 'warning') {
    return preview.value.issues
      .filter(issue => issue.severity === activeFilter.value)
      .map((issue: TeacherArrangementIssue, index) => ({
        key: `issue-${issue.severity}-${issue.sheet}-${issue.row}-${issue.field}-${index}`,
        kind: 'issue' as const,
        sheet: issue.sheet,
        row: issue.row,
        field: issue.field,
        title: issue.field,
        message: issue.message,
        suggestion: issue.suggestion,
        value: issue.value,
        changes: [],
        decision: null,
      }))
  }
  return allRows.value
    .filter(row => row.status === activeFilter.value)
    .map(row => ({
      key: `row-${row.label}-${row.row}-${row.source_key}`,
      kind: 'row' as const,
      sheet: row.label,
      row: row.row,
      field: '识别项',
      title: row.identity,
      message: rowMessage(row.status),
      suggestion: rowSuggestion(row.status),
      value: row.identity,
      status: row.status,
      changes: row.changes,
      decision: row.decision,
    }))
})
const selectedReview = computed(() => (
  reviewItems.value.find(item => item.key === selectedReviewKey.value)
  ?? reviewItems.value[0]
  ?? null
))

watch(mode, () => {
  file.value = null
  preview.value = null
  result.value = null
  error.value = null
  failedAction.value = null
  confirmChanges.value = false
  confirmWarnings.value = false
  decisions.value = {}
  readiness.value = null
})

watch(preview, (value) => {
  if (!value) return
  activeFilter.value = value.counts.blocker
    ? 'blocker'
    : value.counts.warning
      ? 'warning'
      : value.counts.conflict
        ? 'conflict'
        : value.counts.disappeared
          ? 'disappeared'
          : value.counts.new
            ? 'new'
            : value.counts.changed
              ? 'changed'
              : 'unchanged'
  selectedReviewKey.value = null
  confirmWarnings.value = false
  confirmChanges.value = false
  decisions.value = Object.fromEntries(
    value.sheets
      .flatMap(sheet => sheet.rows)
      .filter(row => row.decision?.selected)
      .map(row => [row.decision!.key, row.decision!.selected!]),
  )
})

function chooseFile(event: Event) {
  const input = event.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
  preview.value = null
  result.value = null
  error.value = null
  failedAction.value = null
  confirmChanges.value = false
  confirmWarnings.value = false
  decisions.value = {}
  readiness.value = null
}

async function downloadTemplate() {
  downloading.value = true
  error.value = null
  failedAction.value = null
  try {
    await downloadTeacherArrangementTemplate(props.semester.id, mode.value)
  } catch (cause) {
    error.value = apiErrorMessage(cause, '模板下载失败，请重试。')
    failedAction.value = 'download'
  } finally {
    downloading.value = false
  }
}

async function requestPreview(
  selectedDecisions: Record<string, TeacherArrangementDecisionValue>,
) {
  if (!file.value) return
  previewing.value = true
  error.value = null
  failedAction.value = null
  result.value = null
  readiness.value = null
  try {
    preview.value = await previewTeacherArrangementImport(
      props.semester.id,
      mode.value,
      file.value,
      selectedDecisions,
    )
  } catch (cause) {
    preview.value = null
    error.value = apiErrorMessage(cause, '模板预览失败，请检查文件后重试。')
    failedAction.value = 'preview'
  } finally {
    previewing.value = false
  }
}

async function previewWorkbook() {
  await requestPreview(decisions.value)
}

async function loadReadiness() {
  readinessLoading.value = true
  error.value = null
  failedAction.value = null
  try {
    readiness.value = await getSemesterReadiness(props.semester.id)
  } catch (cause) {
    error.value = apiErrorMessage(cause, '数据已导入，但就绪检查加载失败，请重试。')
    failedAction.value = 'readiness'
  } finally {
    readinessLoading.value = false
  }
}

async function commitWorkbook() {
  if (!canCommit.value || !file.value || !preview.value) return
  committing.value = true
  error.value = null
  failedAction.value = null
  try {
    result.value = await commitTeacherArrangementImport(
      props.semester.id,
      mode.value,
      file.value,
      preview.value.fingerprint,
      confirmChanges.value,
      confirmWarnings.value,
      decisions.value,
    )
    emit('changed')
    if (mode.value === 'scheduling_ready') {
      await loadReadiness()
    }
  } catch (cause) {
    error.value = apiErrorMessage(cause, '模板导入失败，请重新预览后再试。')
    failedAction.value = 'preview'
  } finally {
    committing.value = false
  }
}

async function confirmReadiness() {
  if (!canConfirmReadiness.value) return
  confirmingReadiness.value = true
  error.value = null
  failedAction.value = null
  try {
    readiness.value = await confirmSemesterReadiness(props.semester.id)
  } catch (cause) {
    error.value = apiErrorMessage(cause, '排课就绪确认失败，请重新检查后再试。')
    failedAction.value = 'confirm_readiness'
  } finally {
    confirmingReadiness.value = false
  }
}

function clearFailure() {
  error.value = null
  failedAction.value = null
}

async function retryFailure() {
  if (failedAction.value === 'download') await downloadTemplate()
  else if (failedAction.value === 'readiness') await loadReadiness()
  else if (failedAction.value === 'confirm_readiness') await confirmReadiness()
  else await previewWorkbook()
}

function statusLabel(status: string) {
  return {
    new: '新增',
    changed: '变更',
    unchanged: '不变',
    conflict: '冲突',
    disappeared: '来源中消失',
  }[status] ?? status
}

function rowMessage(status: string) {
  if (status === 'conflict') return '系统值与模板值存在冲突'
  if (status === 'disappeared') return '该来源行已不在本次模板中'
  return `${statusLabel(status)}数据`
}

function rowSuggestion(status: string) {
  if (status === 'conflict') return '选择使用模板值或保留系统值'
  if (status === 'disappeared') return '选择保留为手工数据或安全移除'
  return status === 'changed' ? '核对字段差异后确认更新' : '无需处理'
}

function selectFilter(filter: ReviewFilter) {
  activeFilter.value = filter
  selectedReviewKey.value = null
}

async function chooseDecision(key: string, value: TeacherArrangementDecisionValue) {
  const selectedDecisions = { ...decisions.value, [key]: value }
  decisions.value = selectedDecisions
  await requestPreview(selectedDecisions)
}

function selectedDecision(decision: TeacherArrangementDecision) {
  return decisions.value[decision.key] ?? decision.selected
}

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '空'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

function csvCell(value: unknown) {
  return `"${String(value ?? '').replaceAll('"', '""')}"`
}

function exportIssues() {
  if (!preview.value?.issues.length) return
  const header = ['严重级别', '工作表', '行号', '字段', '原值', '问题', '修复建议']
  const rows = preview.value.issues.map(issue => [
    issue.severity === 'blocker' ? '阻断' : '警告',
    issue.sheet,
    issue.row,
    issue.field,
    displayValue(issue.value),
    issue.message,
    issue.suggestion,
  ])
  const csv = [header, ...rows].map(row => row.map(csvCell).join(',')).join('\r\n')
  const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = '教师安排模板问题.csv'
  anchor.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="template-import-workspace">
    <header class="template-import-header">
      <div>
        <p class="basedata-eyebrow">标准化导入</p>
        <h2>教师安排模板</h2>
      </div>
      <n-tag data-testid="template-semester" type="info" :bordered="false">
        {{ props.semester.label }}
      </n-tag>
    </header>

    <ol
      class="template-import-steps"
      :class="{ 'has-five': stepLabels.length === 5 }"
      aria-label="导入进度"
    >
      <li v-for="(label, index) in stepLabels" :key="label" :class="{ active: completedStep >= index + 1 }">
        <span>{{ index + 1 }}</span>
        <strong>{{ label }}</strong>
      </li>
    </ol>

    <n-alert v-if="!props.canEdit" type="info" :bordered="false">
      当前角色只能预览模板数据，提交导入需要教务主任权限。
    </n-alert>
    <div v-if="error" class="template-import-error" data-testid="template-import-error">
      <n-alert type="error" closable :bordered="false" @close="clearFailure">
        {{ error }}
      </n-alert>
      <n-button
        v-if="failedAction"
        data-testid="template-error-retry"
        secondary
        :loading="retryBusy"
        @click="retryFailure"
      >
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ retryLabel }}
      </n-button>
    </div>
    <n-alert
      v-if="result"
      data-testid="template-import-success"
      type="success"
      :bordered="false"
    >
      {{ result.idempotent ? '该导入记录已完成，未重复写入。' : `已导入记录 #${result.batch_id}，排课就绪状态已回到待确认。` }}
    </n-alert>

    <section class="template-import-scope" aria-labelledby="template-mode-heading">
      <div>
        <h3 id="template-mode-heading">导入模式</h3>
        <p>{{ mode === 'standard' ? '教师、班级、科目与教学任务' : '同时包含教室/场地和作息时间表' }}</p>
      </div>
      <div class="template-mode-segment" role="group" aria-label="选择导入模式">
        <button
          type="button"
          data-testid="template-mode-standard"
          :aria-pressed="mode === 'standard'"
          @click="mode = 'standard'"
        >
          教师安排标准
        </button>
        <button
          type="button"
          data-testid="template-mode-ready"
          :aria-pressed="mode === 'scheduling_ready'"
          @click="mode = 'scheduling_ready'"
        >
          自动排课准备
        </button>
      </div>
    </section>

    <section class="template-import-file-flow">
      <div class="template-import-action">
        <FileSpreadsheet :size="22" aria-hidden="true" />
        <div>
          <strong>下载 v1.0 模板</strong>
          <span>模板已绑定当前目标学期</span>
        </div>
        <n-button
          data-testid="template-download"
          secondary
          :loading="downloading"
          @click="downloadTemplate"
        >
          <template #icon><Download :size="16" aria-hidden="true" /></template>
          下载
        </n-button>
      </div>

      <label class="template-import-dropzone">
        <Upload :size="24" aria-hidden="true" />
        <span>{{ file?.name ?? '选择已填写的 XLSX 模板' }}</span>
        <small v-if="file">{{ (file.size / 1024).toFixed(1) }} KB</small>
        <input
          data-testid="template-file"
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          @change="chooseFile"
        >
      </label>

      <n-button
        data-testid="template-preview"
        type="primary"
        :loading="previewing"
        :disabled="!file"
        @click="previewWorkbook"
      >
        <template #icon><FileCheck2 :size="16" aria-hidden="true" /></template>
        校验并预览
      </n-button>
    </section>

    <section
      v-if="previewing"
      class="template-import-loading"
      data-testid="template-preview-loading"
      role="status"
      aria-live="polite"
    >
      <LoaderCircle class="template-import-spinner" :size="20" aria-hidden="true" />
      正在校验模板
    </section>

    <section v-if="preview" class="template-import-preview" aria-labelledby="template-preview-heading">
      <div class="template-import-preview-heading">
        <div>
          <h3 id="template-preview-heading">导入预览</h3>
          <p>模板 v{{ preview.template_version }} · {{ file?.name }}</p>
        </div>
        <n-tag
          :type="preview.counts.blocker ? 'error' : unresolvedDecisionCount ? 'warning' : 'success'"
          :bordered="false"
        >
          {{ preview.counts.blocker ? '需修正' : unresolvedDecisionCount ? '待决策' : '可提交' }}
        </n-tag>
      </div>

      <div class="template-import-counts">
        <div data-testid="preview-count-new"><span>新增</span><strong>{{ preview.counts.new }}</strong></div>
        <div><span>变更</span><strong>{{ preview.counts.changed }}</strong></div>
        <div><span>不变</span><strong>{{ preview.counts.unchanged }}</strong></div>
        <div class="danger"><span>冲突</span><strong>{{ preview.counts.conflict }}</strong></div>
        <div class="warning"><span>消失</span><strong>{{ preview.counts.disappeared }}</strong></div>
        <div class="danger"><span>阻断</span><strong>{{ preview.counts.blocker }}</strong></div>
        <div class="warning"><span>警告</span><strong>{{ preview.counts.warning }}</strong></div>
      </div>

      <div class="template-review-toolbar">
        <div class="template-review-filters" role="group" aria-label="筛选预览结果">
          <button
            v-for="filter in filterDefinitions"
            :key="filter.key"
            type="button"
            :data-testid="`review-filter-${filter.key}`"
            :aria-pressed="activeFilter === filter.key"
            @click="selectFilter(filter.key)"
          >
            <span>{{ filter.label }}</span>
            <strong>{{ filterCounts[filter.key] }}</strong>
          </button>
        </div>
        <n-button
          v-if="preview.issues.length"
          data-testid="export-issues"
          quaternary
          size="small"
          @click="exportIssues"
        >
          <template #icon><Download :size="15" aria-hidden="true" /></template>
          导出问题
        </n-button>
      </div>

      <div class="template-review-workbench">
        <div class="template-review-queue" aria-label="审查队列">
          <button
            v-for="(item, index) in reviewItems"
            :key="item.key"
            type="button"
            :data-testid="`review-queue-item-${index}`"
            :aria-current="selectedReview?.key === item.key ? 'true' : undefined"
            @click="selectedReviewKey = item.key"
          >
            <span>{{ item.sheet }} · 第 {{ item.row }} 行</span>
            <strong>{{ item.title }}</strong>
            <small>{{ item.message }}</small>
          </button>
          <div v-if="!reviewItems.length" class="template-review-empty" data-testid="review-empty">
            当前分类没有记录
          </div>
        </div>
        <aside v-if="selectedReview" data-testid="review-detail" class="template-review-detail">
          <div class="template-review-location">
            <span>{{ selectedReview.sheet }}</span>
            <strong>第 {{ selectedReview.row }} 行 · {{ selectedReview.field }}</strong>
          </div>
          <dl>
            <div><dt>原值</dt><dd>{{ displayValue(selectedReview.value) }}</dd></div>
            <div><dt>结果</dt><dd>{{ selectedReview.message }}</dd></div>
            <div><dt>处理建议</dt><dd>{{ selectedReview.suggestion }}</dd></div>
          </dl>
          <div
            v-if="selectedReview.decision"
            class="template-review-decision"
            :data-kind="selectedReview.decision.kind"
          >
            <strong>{{ selectedReview.decision.kind === 'conflict' ? '选择采用值' : '处理消失项' }}</strong>
            <div role="group" aria-label="选择导入决策">
              <template v-if="selectedReview.decision.kind === 'conflict'">
                <button
                  type="button"
                  data-testid="decision-incoming"
                  :aria-pressed="selectedDecision(selectedReview.decision) === 'incoming'"
                  :disabled="previewing"
                  @click="chooseDecision(selectedReview.decision.key, 'incoming')"
                >
                  使用模板值
                </button>
                <button
                  type="button"
                  data-testid="decision-current"
                  :aria-pressed="selectedDecision(selectedReview.decision) === 'current'"
                  :disabled="previewing"
                  @click="chooseDecision(selectedReview.decision.key, 'current')"
                >
                  保留系统值
                </button>
              </template>
              <template v-else>
                <button
                  type="button"
                  data-testid="decision-keep"
                  :aria-pressed="selectedDecision(selectedReview.decision) === 'keep'"
                  :disabled="previewing"
                  @click="chooseDecision(selectedReview.decision.key, 'keep')"
                >
                  保留为手工数据
                </button>
                <button
                  type="button"
                  data-testid="decision-remove"
                  :disabled="previewing || !selectedReview.decision.removal_allowed"
                  :aria-pressed="selectedDecision(selectedReview.decision) === 'remove'"
                  :title="selectedReview.decision.reason ?? undefined"
                  @click="chooseDecision(selectedReview.decision.key, 'remove')"
                >
                  安全移除
                </button>
              </template>
            </div>
            <small v-if="selectedReview.decision.reason">
              {{ selectedReview.decision.reason }}
            </small>
          </div>
          <div v-if="selectedReview.changes.length" class="template-review-changes">
            <div v-for="change in selectedReview.changes" :key="change.field">
              <strong>{{ change.field }}</strong>
              <span v-if="change.baseline !== undefined">
                上次 {{ displayValue(change.baseline) }} · 系统 {{ displayValue(change.current) }} · 模板 {{ displayValue(change.incoming) }}
              </span>
              <span v-else>{{ displayValue(change.before) }} → {{ displayValue(change.after) }}</span>
            </div>
          </div>
        </aside>
      </div>

      <label v-if="pendingChangeCount" class="template-import-confirm">
        <input v-model="confirmChanges" data-testid="confirm-changes" type="checkbox">
        <span>确认使用模板中的值更新 {{ pendingChangeCount }} 条现有数据</span>
      </label>
      <label v-if="preview.counts.warning" class="template-import-confirm warning-confirm">
        <input v-model="confirmWarnings" data-testid="confirm-warnings" type="checkbox">
        <span>已逐条审查 {{ preview.counts.warning }} 项警告，确认按预览结果导入</span>
      </label>

      <footer class="template-import-submit">
        <span v-if="preview.counts.blocker">
          <AlertTriangle :size="16" aria-hidden="true" />
          修正阻断项后重新上传
        </span>
        <span v-else-if="unresolvedDecisionCount">
          <AlertTriangle :size="16" aria-hidden="true" />
          还有 {{ unresolvedDecisionCount }} 项需要选择处理方式
        </span>
        <span v-else>
          <CheckCircle2 :size="16" aria-hidden="true" />
          提交不会创建课表草稿或激活规则
        </span>
        <n-button
          data-testid="template-commit"
          type="primary"
          :loading="committing"
          :disabled="!canCommit"
          @click="commitWorkbook"
        >
          确认导入
        </n-button>
      </footer>
    </section>

    <section
      v-if="mode === 'scheduling_ready' && result"
      data-testid="template-readiness"
      class="template-readiness"
      aria-labelledby="template-readiness-heading"
    >
      <div class="template-readiness-heading">
        <div>
          <h3 id="template-readiness-heading">排课就绪确认</h3>
          <p>导入记录 #{{ result.batch_id }}</p>
        </div>
        <n-tag v-if="readiness" :type="readiness.ready ? 'success' : 'warning'" :bordered="false">
          {{ readiness.ready ? '已确认' : '待确认' }}
        </n-tag>
      </div>

      <div v-if="readinessLoading" class="template-import-loading" role="status">
        <LoaderCircle class="template-import-spinner" :size="20" aria-hidden="true" />
        正在执行就绪检查
      </div>
      <template v-else-if="readiness">
        <div class="template-readiness-checks">
          <div
            v-for="check in readiness.checks"
            :key="check.key"
            class="template-readiness-check"
            :class="{ failed: !check.ok }"
          >
            <CheckCircle2 v-if="check.ok" :size="20" aria-hidden="true" />
            <AlertTriangle v-else :size="20" aria-hidden="true" />
            <div>
              <strong>{{ check.label }}</strong>
              <span v-if="check.ok">
                通过<span v-if="check.warning_count">，{{ check.warning_count }} 项提醒</span>
              </span>
              <span v-else>{{ check.error_count }} 项未通过</span>
            </div>
          </div>
        </div>

        <div v-if="readiness.issues.length" class="template-readiness-issues" role="alert">
          <div v-for="issue in readiness.issues" :key="`${issue.code}-${issue.subject_type}-${issue.subject_id}`">
            <AlertTriangle :size="16" aria-hidden="true" />
            <span>{{ issue.message }}</span>
          </div>
        </div>

        <footer class="template-readiness-actions">
          <span v-if="readiness.ready">
            <CheckCircle2 :size="16" aria-hidden="true" />
            已由教务主任确认
          </span>
          <span v-else-if="canConfirmReadiness">
            <CheckCircle2 :size="16" aria-hidden="true" />
            两项检查均已通过
          </span>
          <span v-else>
            <AlertTriangle :size="16" aria-hidden="true" />
            处理未通过项后再确认
          </span>
          <a
            v-if="readiness.ready"
            data-testid="readiness-next"
            class="template-readiness-next"
            :href="readinessNextHref"
          >
            继续排课工作台
            <ArrowRight :size="16" aria-hidden="true" />
          </a>
          <n-button
            v-else
            data-testid="readiness-confirm"
            type="primary"
            :loading="confirmingReadiness"
            :disabled="!canConfirmReadiness"
            @click="confirmReadiness"
          >
            确认排课就绪
          </n-button>
        </footer>
      </template>
    </section>
  </div>
</template>
