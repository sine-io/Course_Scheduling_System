<script setup lang="ts">
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileCheck2,
  FileSpreadsheet,
  LoaderCircle,
  Upload,
} from '@lucide/vue'
import { NAlert, NButton, NTag } from 'naive-ui'
import { computed, ref, watch } from 'vue'
import { apiErrorMessage } from '@/api/client'
import {
  commitTeacherArrangementImport,
  downloadTeacherArrangementTemplate,
  previewTeacherArrangementImport,
} from '@/api/imports'
import type {
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

const mode = ref<TeacherArrangementMode>('standard')
const file = ref<File | null>(null)
const preview = ref<TeacherArrangementPreview | null>(null)
const result = ref<TeacherArrangementCommitResult | null>(null)
const error = ref<string | null>(null)
const downloading = ref(false)
const previewing = ref(false)
const committing = ref(false)
const confirmChanges = ref(false)
const confirmWarnings = ref(false)
type ReviewFilter = 'blocker' | 'warning' | 'new' | 'changed' | 'unchanged' | 'disappeared'
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
}
const activeFilter = ref<ReviewFilter>('new')
const selectedReviewKey = ref<string | null>(null)

const allRows = computed(() => (
  preview.value?.sheets.flatMap(sheet => sheet.rows.map(row => ({ ...row, label: sheet.label }))) ?? []
))
const canCommit = computed(() => Boolean(
  props.canEdit
  && file.value
  && preview.value?.can_commit
  && (!preview.value.counts.changed || confirmChanges.value)
  && (!preview.value.counts.warning || confirmWarnings.value),
))
const completedStep = computed(() => {
  if (result.value) return 4
  if (preview.value) return 3
  if (file.value) return 2
  return 1
})
const filterDefinitions: Array<{ key: ReviewFilter, label: string }> = [
  { key: 'blocker', label: '阻断' },
  { key: 'warning', label: '警告' },
  { key: 'new', label: '新增' },
  { key: 'changed', label: '变更' },
  { key: 'unchanged', label: '不变' },
  { key: 'disappeared', label: '消失' },
]
const filterCounts = computed<Record<ReviewFilter, number>>(() => ({
  blocker: preview.value?.counts.blocker ?? 0,
  warning: preview.value?.counts.warning ?? 0,
  new: preview.value?.counts.new ?? 0,
  changed: preview.value?.counts.changed ?? 0,
  unchanged: preview.value?.counts.unchanged ?? 0,
  disappeared: 0,
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
      }))
  }
  if (activeFilter.value === 'disappeared') return []
  return allRows.value
    .filter(row => row.status === activeFilter.value)
    .map(row => ({
      key: `row-${row.label}-${row.row}-${row.source_key}`,
      kind: 'row' as const,
      sheet: row.label,
      row: row.row,
      field: '识别项',
      title: row.identity,
      message: `${statusLabel(row.status)}数据`,
      suggestion: row.status === 'changed' ? '核对字段差异后确认更新' : '无需处理',
      value: row.identity,
      status: row.status,
      changes: row.changes,
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
  confirmChanges.value = false
  confirmWarnings.value = false
})

watch(preview, (value) => {
  if (!value) return
  activeFilter.value = value.counts.blocker
    ? 'blocker'
    : value.counts.warning
      ? 'warning'
      : value.counts.new
        ? 'new'
        : value.counts.changed
          ? 'changed'
          : 'unchanged'
  selectedReviewKey.value = null
  confirmWarnings.value = false
})

function chooseFile(event: Event) {
  const input = event.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
  preview.value = null
  result.value = null
  error.value = null
  confirmChanges.value = false
  confirmWarnings.value = false
}

async function downloadTemplate() {
  downloading.value = true
  error.value = null
  try {
    await downloadTeacherArrangementTemplate(props.semester.id, mode.value)
  } catch (cause) {
    error.value = apiErrorMessage(cause, '模板下载失败，请重试。')
  } finally {
    downloading.value = false
  }
}

async function previewWorkbook() {
  if (!file.value) return
  previewing.value = true
  error.value = null
  result.value = null
  try {
    preview.value = await previewTeacherArrangementImport(
      props.semester.id,
      mode.value,
      file.value,
    )
  } catch (cause) {
    preview.value = null
    error.value = apiErrorMessage(cause, '模板预览失败，请检查文件后重试。')
  } finally {
    previewing.value = false
  }
}

async function commitWorkbook() {
  if (!canCommit.value || !file.value || !preview.value) return
  committing.value = true
  error.value = null
  try {
    result.value = await commitTeacherArrangementImport(
      props.semester.id,
      mode.value,
      file.value,
      preview.value.fingerprint,
      confirmChanges.value,
      confirmWarnings.value,
    )
  } catch (cause) {
    error.value = apiErrorMessage(cause, '模板导入失败，请重新预览后再试。')
  } finally {
    committing.value = false
  }
}

function statusLabel(status: string) {
  return { new: '新增', changed: '变更', unchanged: '不变' }[status] ?? status
}

function selectFilter(filter: ReviewFilter) {
  activeFilter.value = filter
  selectedReviewKey.value = null
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

    <ol class="template-import-steps" aria-label="导入进度">
      <li v-for="(label, index) in ['选择范围', '准备文件', '校验数据', '确认导入']" :key="label" :class="{ active: completedStep >= index + 1 }">
        <span>{{ index + 1 }}</span>
        <strong>{{ label }}</strong>
      </li>
    </ol>

    <n-alert v-if="!props.canEdit" type="info" :bordered="false">
      当前角色只能预览模板数据，提交导入需要教务主任权限。
    </n-alert>
    <n-alert v-if="error" type="error" closable :bordered="false" @close="error = null">
      {{ error }}
    </n-alert>
    <n-alert
      v-if="result"
      data-testid="template-import-success"
      type="success"
      :bordered="false"
    >
      {{ result.idempotent ? '该批次已导入，未重复写入。' : `已导入批次 #${result.batch_id}，数据仍处于排课准备草稿。` }}
    </n-alert>

    <section class="template-import-scope" aria-labelledby="template-mode-heading">
      <div>
        <h3 id="template-mode-heading">导入模式</h3>
        <p>{{ mode === 'standard' ? '教师、班级、科目与教学任务' : '同时包含场地和作息时间表' }}</p>
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

    <section v-if="previewing" class="template-import-loading" role="status">
      <LoaderCircle class="template-import-spinner" :size="20" aria-hidden="true" />
      正在校验模板
    </section>

    <section v-if="preview" class="template-import-preview" aria-labelledby="template-preview-heading">
      <div class="template-import-preview-heading">
        <div>
          <h3 id="template-preview-heading">导入预览</h3>
          <p>模板 v{{ preview.template_version }} · {{ file?.name }}</p>
        </div>
        <n-tag :type="preview.can_commit ? 'success' : 'error'" :bordered="false">
          {{ preview.can_commit ? '可提交' : '需修正' }}
        </n-tag>
      </div>

      <div class="template-import-counts">
        <div data-testid="preview-count-new"><span>新增</span><strong>{{ preview.counts.new }}</strong></div>
        <div><span>变更</span><strong>{{ preview.counts.changed }}</strong></div>
        <div><span>不变</span><strong>{{ preview.counts.unchanged }}</strong></div>
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
          <div v-if="!reviewItems.length" class="template-review-empty">
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
          <div v-if="selectedReview.changes.length" class="template-review-changes">
            <div v-for="change in selectedReview.changes" :key="change.field">
              <strong>{{ change.field }}</strong>
              <span>{{ displayValue(change.before) }} → {{ displayValue(change.after) }}</span>
            </div>
          </div>
        </aside>
      </div>

      <label v-if="preview.counts.changed" class="template-import-confirm">
        <input v-model="confirmChanges" type="checkbox">
        <span>确认使用模板中的值更新 {{ preview.counts.changed }} 条现有数据</span>
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
        <span v-else>
          <CheckCircle2 :size="16" aria-hidden="true" />
          提交不会创建排课草案或激活规则
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
  </div>
</template>
