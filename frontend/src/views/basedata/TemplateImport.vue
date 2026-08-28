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
  TeacherArrangementCommitResult,
  TeacherArrangementMode,
  TeacherArrangementPreview,
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

const allRows = computed(() => (
  preview.value?.sheets.flatMap(sheet => sheet.rows.map(row => ({ ...row, label: sheet.label }))) ?? []
))
const canCommit = computed(() => Boolean(
  props.canEdit
  && file.value
  && preview.value?.can_commit
  && (!preview.value.counts.changed || confirmChanges.value),
))
const completedStep = computed(() => {
  if (result.value) return 4
  if (preview.value) return 3
  if (file.value) return 2
  return 1
})

watch(mode, () => {
  file.value = null
  preview.value = null
  result.value = null
  error.value = null
  confirmChanges.value = false
})

function chooseFile(event: Event) {
  const input = event.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
  preview.value = null
  result.value = null
  error.value = null
  confirmChanges.value = false
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

      <div v-if="preview.issues.length" class="template-import-issues">
        <div v-for="issue in preview.issues" :key="`${issue.sheet}-${issue.row}-${issue.field}-${issue.code}`">
          <AlertTriangle :size="16" aria-hidden="true" />
          <span>{{ issue.sheet }} · 第 {{ issue.row }} 行 · {{ issue.field }}</span>
          <strong>{{ issue.message }}</strong>
        </div>
      </div>

      <div v-if="allRows.length" class="template-import-table-wrap">
        <table>
          <thead><tr><th>工作表</th><th>行</th><th>识别项</th><th>结果</th></tr></thead>
          <tbody>
            <tr v-for="row in allRows.slice(0, 80)" :key="`${row.label}-${row.row}-${row.source_key}`">
              <td>{{ row.label }}</td>
              <td>{{ row.row }}</td>
              <td>{{ row.identity }}</td>
              <td><span :class="`row-status ${row.status}`">{{ statusLabel(row.status) }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <label v-if="preview.counts.changed" class="template-import-confirm">
        <input v-model="confirmChanges" type="checkbox">
        <span>确认使用模板中的值更新 {{ preview.counts.changed }} 条现有数据</span>
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
