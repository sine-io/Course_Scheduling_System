<script setup lang="ts">
import {
  AlertTriangle, CheckCircle2, Download, Eye, FileSpreadsheet, RotateCcw, Upload,
} from '@lucide/vue'
import {
  NAlert, NButton, NCheckbox, NList, NListItem, NRadioButton, NRadioGroup, NTag,
  NUpload, useDialog, useMessage,
} from 'naive-ui'
import type { UploadFileInfo } from 'naive-ui'
import { computed, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import {
  commitSetupImport,
  downloadSetupTemplate,
  downloadTemplate,
  ENTITY_LABELS,
  previewSetupImport,
  uploadImport,
} from '@/api/imports'
import type {
  CombinedImportCommitResult,
  CombinedImportPreview,
  CombinedImportStatus,
  ImportEntity,
  ImportResult,
} from '@/api/imports'
import { highRiskConfirmation } from '@/api/highRisk'
import './basedata-workspace.css'

const props = withDefaults(
  defineProps<{
    semesterId: number
    canEdit?: boolean
    canManageAccounts?: boolean
  }>(),
  { canEdit: true, canManageAccounts: false },
)
const emit = defineEmits<{ imported: [] }>()
const message = useMessage()
const dialog = useDialog()
const labels = ENTITY_LABELS

const mode = ref<'combined' | 'single'>('combined')

const combinedFileList = ref<UploadFileInfo[]>([])
const combinedFile = ref<File | null>(null)
const combinedPreview = ref<CombinedImportPreview | null>(null)
const combinedResult = ref<CombinedImportCommitResult | null>(null)
const combinedBusy = ref(false)
const combinedDownloading = ref(false)
const combinedError = ref<string | null>(null)
const confirmChanges = ref(false)

const entity = ref<ImportEntity>('subjects')
const createAccounts = ref(false)
const singleFileList = ref<UploadFileInfo[]>([])
const singleFile = ref<File | null>(null)
const singleUploading = ref(false)
const singleDownloading = ref(false)
const singleResult = ref<ImportResult | null>(null)
const singleError = ref<string | null>(null)

const isTeacher = computed(() => entity.value === 'teachers')
const canCommitCombined = computed(() => (
  !!combinedPreview.value?.can_commit
  && !!combinedFile.value
  && (!combinedPreview.value.has_changes || confirmChanges.value)
  && !combinedBusy.value
))

const statusMeta: Record<CombinedImportStatus, { label: string, type: string }> = {
  new: { label: '新增', type: 'success' },
  unchanged: { label: '未变化', type: 'default' },
  changed: { label: '将修改', type: 'warning' },
  conflict: { label: '冲突', type: 'error' },
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '空'
  if (Array.isArray(value)) return value.length ? value.join('、') : '空'
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}

async function onCombinedDownload() {
  if (combinedDownloading.value) return
  combinedError.value = null
  combinedDownloading.value = true
  try {
    await downloadSetupTemplate()
  } catch (error) {
    combinedError.value = apiErrorMessage(error, '组合模板下载失败，请稍后重试。')
  } finally {
    combinedDownloading.value = false
  }
}

function onCombinedFileChange(data: { fileList: UploadFileInfo[] }) {
  combinedFileList.value = data.fileList
  combinedFile.value = data.fileList[0]?.file ?? null
  combinedPreview.value = null
  combinedResult.value = null
  combinedError.value = null
  confirmChanges.value = false
}

async function onCombinedPreview() {
  if (!props.canEdit || combinedBusy.value || !combinedFile.value) return
  combinedBusy.value = true
  combinedError.value = null
  combinedPreview.value = null
  combinedResult.value = null
  confirmChanges.value = false
  try {
    combinedPreview.value = await previewSetupImport(props.semesterId, combinedFile.value)
  } catch (error) {
    combinedError.value = apiErrorMessage(error, '无法预览工作簿，请检查文件后重试。')
  } finally {
    combinedBusy.value = false
  }
}

async function onCombinedCommit() {
  if (!canCommitCombined.value || !combinedFile.value || !combinedPreview.value) return
  combinedBusy.value = true
  combinedError.value = null
  try {
    combinedResult.value = await commitSetupImport(
      props.semesterId,
      combinedFile.value,
      combinedPreview.value.fingerprint,
      confirmChanges.value,
    )
    message.success('基础数据已导入')
    emit('imported')
  } catch (error) {
    combinedError.value = apiErrorMessage(error, '提交失败，请重新预览后重试。')
  } finally {
    combinedBusy.value = false
  }
}

async function onSingleDownload() {
  if (singleDownloading.value) return
  singleError.value = null
  singleDownloading.value = true
  try {
    await downloadTemplate(entity.value)
  } catch (error) {
    singleError.value = apiErrorMessage(error, '模板下载失败，请稍后重试。')
  } finally {
    singleDownloading.value = false
  }
}

function onSingleFileChange(data: { fileList: UploadFileInfo[] }) {
  singleFileList.value = data.fileList
  singleFile.value = data.fileList[0]?.file ?? null
  singleResult.value = null
  singleError.value = null
}

async function performSingleUpload() {
  if (!props.canEdit || singleUploading.value) return
  if (!singleFile.value) {
    singleError.value = '请先选择文件'
    return
  }
  singleError.value = null
  singleUploading.value = true
  singleResult.value = null
  try {
    const confirmation = isTeacher.value && createAccounts.value
      ? highRiskConfirmation(`semester:${props.semesterId}:teacher-accounts`)
      : undefined
    const importResult = await uploadImport(
      entity.value,
      props.semesterId,
      singleFile.value,
      isTeacher.value && createAccounts.value,
      confirmation,
    )
    singleResult.value = importResult
    if (importResult.errors.length === 0) {
      message.success(`成功导入 ${importResult.imported} 条`)
      emit('imported')
    } else {
      message.error('导入未完成，请修正错误后重试')
    }
  } catch (error) {
    singleError.value = apiErrorMessage(error, '导入失败，请稍后重试。')
  } finally {
    singleUploading.value = false
  }
}

function onSingleUpload() {
  if (!isTeacher.value || !createAccounts.value) {
    void performSingleUpload()
    return
  }
  dialog.warning({
    title: '确认批量创建教师账号',
    content: `目标：学期 #${props.semesterId} 的教师导入。影响：导入成功的每位教师都会新增登录账号，默认密码须由本人首次登录修改。`,
    positiveText: '确认导入并建号',
    negativeText: '取消',
    maskClosable: false,
    onPositiveClick: () => performSingleUpload(),
  })
}
</script>

<template>
  <div class="basedata-tab-content basedata-import" data-testid="import-workspace">
    <n-alert v-if="!canEdit" type="info" data-testid="import-readonly">
      {{ '当前角色没有批量导入权限；仍可选择导入方式并下载模板。' }}
    </n-alert>

    <div role="radiogroup" aria-label="选择导入方式">
      <n-radio-group v-model:value="mode" class="basedata-import-entities">
        <n-radio-button value="combined">{{ '组合工作簿' }}</n-radio-button>
        <n-radio-button value="single">{{ '按表导入' }}</n-radio-button>
      </n-radio-group>
    </div>

    <div v-if="mode === 'combined'" data-testid="combined-import-panel">
      <div class="combined-import-heading">
        <div>
          <strong>{{ '组合工作簿' }}</strong>
          <p>{{ '一次核对科目、教师、班级和教室，确认后统一写入。' }}</p>
        </div>
        <div class="combined-sheet-tags" aria-label="工作表内容">
          <n-tag size="small">{{ '科目' }}</n-tag>
          <n-tag size="small">{{ '教师' }}</n-tag>
          <n-tag size="small">{{ '班级' }}</n-tag>
          <n-tag size="small">{{ '教室' }}</n-tag>
        </div>
      </div>

      <section class="basedata-import-step">
        <div class="basedata-import-step-heading">
          <Download :size="18" aria-hidden="true" />
          <strong>{{ '工作簿' }}</strong>
        </div>
        <n-button
          data-testid="combined-download"
          :loading="combinedDownloading"
          :disabled="combinedBusy"
          @click="onCombinedDownload"
        >
          <template #icon><Download :size="15" aria-hidden="true" /></template>
          {{ '下载组合模板' }}
        </n-button>
      </section>

      <section v-if="canEdit" class="basedata-import-step">
        <div class="basedata-import-step-heading">
          <Eye :size="18" aria-hidden="true" />
          <strong>{{ '导入预览' }}</strong>
        </div>
        <n-upload
          v-model:file-list="combinedFileList"
          :max="1"
          :default-upload="false"
          accept=".xlsx"
          @change="onCombinedFileChange"
        >
          <n-button data-testid="combined-file">
            <template #icon><FileSpreadsheet :size="15" aria-hidden="true" /></template>
            {{ '选择已填写的工作簿' }}
          </n-button>
        </n-upload>
        <div>
          <n-button
            type="primary"
            data-testid="combined-preview"
            :loading="combinedBusy && !combinedPreview"
            :disabled="!combinedFile || combinedBusy"
            @click="onCombinedPreview"
          >
            <template #icon><Eye :size="15" aria-hidden="true" /></template>
            {{ combinedPreview ? '重新预览' : '预览导入结果' }}
          </n-button>
        </div>
      </section>

      <n-alert v-if="combinedError" type="error" data-testid="combined-import-error" role="alert">
        {{ combinedError }}
      </n-alert>

      <section
        v-if="combinedPreview"
        class="combined-preview"
        data-testid="combined-preview-results"
        aria-live="polite"
      >
        <div class="combined-counts" aria-label="导入预览统计">
          <span data-status="new"><strong>{{ `新增 ${combinedPreview.counts.new}` }}</strong></span>
          <span data-status="unchanged">{{ `未变化 ${combinedPreview.counts.unchanged}` }}</span>
          <span data-status="changed"><strong>{{ `将修改 ${combinedPreview.counts.changed}` }}</strong></span>
          <span data-status="conflict"><strong>{{ `冲突 ${combinedPreview.counts.conflict}` }}</strong></span>
        </div>

        <n-alert
          v-if="combinedPreview.errors.length"
          type="error"
          :title="'存在冲突，当前不会写入任何数据'"
          data-testid="combined-conflicts"
        >
          <n-list>
            <n-list-item v-for="error in combinedPreview.errors" :key="`${error.sheet}-${error.row}-${error.field}-${error.message}`">
              <strong>{{ `${error.sheet} · 第 ${error.row} 行 · ${error.field}` }}</strong>
              <span>{{ error.message }}</span>
            </n-list-item>
          </n-list>
        </n-alert>

        <section v-for="sheet in combinedPreview.sheets" :key="sheet.key" class="combined-sheet-preview">
          <div class="combined-sheet-title">
            <h3>{{ sheet.label }}</h3>
            <span>{{ `${sheet.rows.length} 行` }}</span>
          </div>
          <div v-if="sheet.rows.length" class="combined-table-scroll">
            <table class="combined-preview-table">
              <thead>
                <tr><th>{{ '行' }}</th><th>{{ '记录' }}</th><th>{{ '状态' }}</th><th>{{ '具体变化或冲突' }}</th></tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in sheet.rows"
                  :key="`${sheet.key}-${row.row}`"
                  :data-testid="`combined-row-${sheet.key}-${row.row}`"
                >
                  <td>{{ row.row }}</td>
                  <td>{{ row.identity }}</td>
                  <td>
                    <n-tag size="small" :type="statusMeta[row.status].type as never">
                      {{ statusMeta[row.status].label }}
                    </n-tag>
                  </td>
                  <td>
                    <span v-if="row.changes.length" class="combined-change-list">
                      <span v-for="change in row.changes" :key="change.field">
                        {{ `${change.field}：${formatValue(change.before)} → ${formatValue(change.after)}` }}
                      </span>
                    </span>
                    <span v-else-if="row.errors.length" class="combined-error-list">
                      <span v-for="error in row.errors" :key="`${error.field}-${error.message}`">
                        {{ `${error.field}：${error.message}` }}
                      </span>
                    </span>
                    <span v-else class="combined-muted">{{ row.status === 'new' ? '将创建' : '无需处理' }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="combined-empty">{{ '此工作表没有待处理行' }}</p>
        </section>

        <div v-if="combinedPreview.can_commit" class="combined-commit-area">
          <n-checkbox
            v-if="combinedPreview.has_changes"
            v-model:checked="confirmChanges"
            data-testid="combined-confirm-changes"
          >
            {{ `我已核对并确认修改 ${combinedPreview.counts.changed} 条现有数据` }}
          </n-checkbox>
          <n-alert v-else type="success" :show-icon="true">
            {{ '没有冲突，也不会修改现有记录。' }}
          </n-alert>
          <n-button
            type="primary"
            data-testid="combined-commit"
            :loading="combinedBusy"
            :disabled="!canCommitCombined"
            @click="onCombinedCommit"
          >
            <template #icon><CheckCircle2 :size="15" aria-hidden="true" /></template>
            {{ '确认并导入全部工作表' }}
          </n-button>
        </div>
      </section>

      <n-alert
        v-if="combinedResult"
        type="success"
        data-testid="combined-import-success"
        role="status"
      >
        {{ `导入完成：新增 ${combinedResult.total_created} 条，更新 ${combinedResult.total_updated} 条，${combinedResult.total_unchanged} 条未变化。` }}
      </n-alert>
    </div>

    <div v-else class="single-import-panel" data-testid="single-import-panel">
      <n-alert type="info" :show-icon="true">
        {{ '按表导入适合补录单类数据；跨表引用必须已经存在。' }}
      </n-alert>

      <section class="basedata-import-step">
        <div class="basedata-import-step-heading">
          <FileSpreadsheet :size="18" aria-hidden="true" />
          <strong>{{ '数据类型' }}</strong>
        </div>
        <div role="radiogroup" aria-label="选择导入数据类型">
          <n-radio-group v-model:value="entity" class="basedata-import-entities">
            <n-radio-button v-for="(label, key) in labels" :key="key" :value="key">
              {{ label }}
            </n-radio-button>
          </n-radio-group>
        </div>
      </section>

      <section class="basedata-import-step">
        <div class="basedata-import-step-heading">
          <Download :size="18" aria-hidden="true" />
          <strong>{{ '模板' }}</strong>
        </div>
        <n-button
          data-testid="import-download"
          :loading="singleDownloading"
          :disabled="singleUploading"
          @click="onSingleDownload"
        >
          <template #icon><Download :size="15" aria-hidden="true" /></template>
          {{ '下载' }}「{{ labels[entity] }}」{{ '模板' }}
        </n-button>
      </section>

      <section v-if="canEdit" class="basedata-import-step">
        <div class="basedata-import-step-heading">
          <Upload :size="18" aria-hidden="true" />
          <strong>{{ '上传文件' }}</strong>
        </div>
        <n-checkbox v-if="isTeacher && canManageAccounts" v-model:checked="createAccounts">
          {{ '同时创建教师登录账号（默认密码，首次登录需修改）' }}
        </n-checkbox>
        <n-upload
          v-model:file-list="singleFileList"
          :max="1"
          :default-upload="false"
          accept=".xlsx"
          @change="onSingleFileChange"
        >
          <n-button data-testid="import-file">
            <template #icon><FileSpreadsheet :size="15" aria-hidden="true" /></template>
            {{ '选择文件' }}
          </n-button>
        </n-upload>
        <n-button
          type="primary"
          data-testid="import-upload"
          :loading="singleUploading"
          :disabled="!singleFile || singleUploading"
          @click="onSingleUpload"
        >
          <template #icon>
            <RotateCcw v-if="singleResult?.errors.length" :size="15" aria-hidden="true" />
            <Upload v-else :size="15" aria-hidden="true" />
          </template>
          {{ singleResult?.errors.length ? '修正文件后重试' : '开始导入' }}
        </n-button>
      </section>

      <n-alert v-if="singleError" type="error" data-testid="import-error" role="alert">
        {{ singleError }}
      </n-alert>
      <n-alert
        v-if="singleResult && singleResult.errors.length === 0"
        type="success"
        data-testid="import-success"
        role="status"
      >
        {{ `成功导入 ${singleResult.imported} 条数据。` }}
      </n-alert>
      <n-alert
        v-if="singleResult && singleResult.errors.length > 0"
        type="error"
        :title="'导入失败（数据库未写入）'"
        data-testid="import-result-errors"
        role="alert"
      >
        <template #icon><AlertTriangle :size="17" aria-hidden="true" /></template>
        <n-list>
          <n-list-item v-for="(error, index) in singleResult.errors" :key="index">
            {{ error }}
          </n-list-item>
        </n-list>
      </n-alert>
    </div>
  </div>
</template>

<style scoped>
.basedata-import { max-width: 920px; }
.combined-import-heading,
.combined-sheet-title,
.combined-counts,
.combined-sheet-tags,
.combined-commit-area {
  display: flex;
  min-width: 0;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}
.combined-import-heading { justify-content: space-between; padding: 16px 0; }
.combined-import-heading strong { font-size: 16px; }
.combined-import-heading p { margin: 4px 0 0; color: var(--app-text-muted); font-size: 13px; }
.combined-preview { display: grid; gap: 20px; padding-top: 20px; border-top: 1px solid var(--app-border); }
.combined-counts { gap: 8px; }
.combined-counts > span {
  min-width: 104px;
  padding: 9px 12px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
  color: var(--app-text-muted);
  font-size: 13px;
}
.combined-counts [data-status='new'] { color: var(--app-success); }
.combined-counts [data-status='changed'] { color: var(--app-warning-pressed); }
.combined-counts [data-status='conflict'] { color: var(--app-danger); }
.combined-sheet-preview { min-width: 0; }
.combined-sheet-title { justify-content: space-between; margin-bottom: 8px; }
.combined-sheet-title h3 { margin: 0; font-size: 14px; }
.combined-sheet-title span,
.combined-empty,
.combined-muted { color: var(--app-text-faint); font-size: 12px; }
.combined-table-scroll { width: 100%; overflow-x: auto; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); }
.combined-preview-table { width: 100%; min-width: 660px; border-collapse: collapse; font-size: 12px; }
.combined-preview-table th,
.combined-preview-table td { padding: 9px 10px; border-bottom: 1px solid var(--app-border); text-align: left; vertical-align: top; }
.combined-preview-table th { background: var(--app-surface-muted); color: var(--app-text-muted); font-weight: 650; }
.combined-preview-table tr:last-child td { border-bottom: 0; }
.combined-preview-table td:first-child { width: 48px; color: var(--app-text-faint); }
.combined-preview-table td:nth-child(2) { width: 170px; font-weight: 650; }
.combined-preview-table td:nth-child(3) { width: 90px; }
.combined-change-list,
.combined-error-list { display: grid; gap: 4px; }
.combined-error-list { color: var(--app-danger); }
.combined-commit-area { align-items: flex-start; flex-direction: column; padding-top: 2px; }
.combined-commit-area :deep(.n-alert) { width: 100%; }
.combined-commit-area :deep(.n-checkbox__label) { white-space: normal; }
.single-import-panel { display: grid; gap: var(--app-space-4); }
@media (max-width: 560px) {
  .combined-import-heading { align-items: flex-start; flex-direction: column; }
  .combined-counts > span { flex: 1 1 42%; min-width: 0; }
}
</style>
