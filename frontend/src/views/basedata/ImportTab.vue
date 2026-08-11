<script setup lang="ts">
import { Download, FileSpreadsheet, RotateCcw, Upload } from '@lucide/vue'
import {
  NAlert, NButton, NCheckbox, NList, NListItem, NRadioButton, NRadioGroup, NUpload, useMessage,
} from 'naive-ui'
import type { UploadFileInfo } from 'naive-ui'
import { computed, ref, watch } from 'vue'
import { downloadTemplate, ENTITY_LABELS, uploadImport } from '@/api/imports'
import type { ImportEntity, ImportResult } from '@/api/imports'
import './basedata-workspace.css'

const props = withDefaults(defineProps<{ semesterId: number; canEdit?: boolean }>(), { canEdit: true })
const emit = defineEmits<{ imported: [] }>()
const message = useMessage()
const labels = ENTITY_LABELS

const entity = ref<ImportEntity>('subjects')
const createAccounts = ref(false)
const fileList = ref<UploadFileInfo[]>([])
const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const downloading = ref(false)
const result = ref<ImportResult | null>(null)
const errorMessage = ref<string | null>(null)

const isTeacher = computed(() => entity.value === 'teachers')

watch(entity, () => {
  fileList.value = []
  selectedFile.value = null
  result.value = null
  errorMessage.value = null
  createAccounts.value = false
})

async function onDownload() {
  if (downloading.value) return
  errorMessage.value = null
  downloading.value = true
  try {
    await downloadTemplate(entity.value)
  } catch (error) {
    errorMessage.value = (error as Error).message || '模板下载失败，请稍后重试。'
  } finally {
    downloading.value = false
  }
}

function onFileChange(data: { fileList: UploadFileInfo[] }) {
  fileList.value = data.fileList
  selectedFile.value = data.fileList[0]?.file ?? null
  result.value = null
  errorMessage.value = null
}

async function onUpload() {
  if (uploading.value) return
  if (!selectedFile.value) {
    errorMessage.value = '请先选择文件'
    return
  }
  errorMessage.value = null
  uploading.value = true
  result.value = null
  try {
    const importResult = await uploadImport(
      entity.value,
      props.semesterId,
      selectedFile.value,
      isTeacher.value && createAccounts.value,
    )
    result.value = importResult
    if (importResult.errors.length === 0) {
      message.success(`成功导入 ${importResult.imported} 条`)
      emit('imported')
    } else {
      message.error('导入未完成，请修正错误后重试')
    }
  } catch (error) {
    errorMessage.value = (error as Error).message || '导入失败，请稍后重试。'
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="basedata-tab-content basedata-import" data-testid="import-workspace">
    <n-alert v-if="!canEdit" type="info" data-testid="import-readonly">
      {{ '当前角色没有批量导入权限。' }}
    </n-alert>
    <template v-else>
      <n-alert type="info" :show-icon="true">
        {{ '导入步骤：① 选择数据类型 → ② 下载模板并填写（从第 4 行开始，说明/示例行会自动跳过）→ ③ 上传。任一行有误将全部不导入，并列出错误行号。' }}
      </n-alert>

      <section class="basedata-import-step">
        <div class="basedata-import-step-heading">
          <FileSpreadsheet :size="18" aria-hidden="true" />
          <strong>{{ '① 数据类型' }}</strong>
        </div>
        <n-radio-group v-model:value="entity" class="basedata-import-entities" aria-label="选择导入数据类型">
          <n-radio-button v-for="(label, key) in labels" :key="key" :value="key">
            {{ label }}
          </n-radio-button>
        </n-radio-group>
      </section>

      <section class="basedata-import-step">
        <div class="basedata-import-step-heading">
          <Download :size="18" aria-hidden="true" />
          <strong>{{ '② 下载模板' }}</strong>
        </div>
        <div>
          <n-button
            data-testid="import-download"
            :loading="downloading"
            :disabled="uploading"
            @click="onDownload"
          >
            <template #icon><Download :size="15" aria-hidden="true" /></template>
            {{ '下载' }}「{{ labels[entity] }}」{{ '模板' }}
          </n-button>
        </div>
      </section>

      <section class="basedata-import-step">
        <div class="basedata-import-step-heading">
          <Upload :size="18" aria-hidden="true" />
          <strong>{{ '③ 上传填写完成的文件' }}</strong>
        </div>
        <n-checkbox v-if="isTeacher" v-model:checked="createAccounts">
          {{ '同时创建教师登录账号（默认密码，首次登录需修改）' }}
        </n-checkbox>
        <n-upload
          v-model:file-list="fileList"
          :max="1"
          :default-upload="false"
          accept=".xlsx"
          @change="onFileChange"
        >
          <n-button data-testid="import-file">
            <template #icon><FileSpreadsheet :size="15" aria-hidden="true" /></template>
            {{ '选择文件' }}
          </n-button>
        </n-upload>
        <div>
          <n-button
            type="primary"
            data-testid="import-upload"
            :loading="uploading"
            :disabled="!selectedFile || uploading"
            @click="onUpload"
          >
            <template #icon>
              <RotateCcw v-if="result?.errors.length" :size="15" aria-hidden="true" />
              <Upload v-else :size="15" aria-hidden="true" />
            </template>
            {{ result?.errors.length ? '修正文件后重试' : '开始导入' }}
          </n-button>
        </div>
      </section>

      <n-alert
        v-if="errorMessage"
        type="error"
        data-testid="import-error"
        role="alert"
        aria-live="assertive"
      >
        {{ errorMessage }}
      </n-alert>

      <n-alert
        v-if="result && result.errors.length === 0"
        type="success"
        data-testid="import-success"
        role="status"
      >
        {{ `成功导入 ${result.imported} 条数据。` }}
      </n-alert>
      <n-alert
        v-if="result && result.errors.length > 0"
        type="error"
        :title="'导入失败（数据库未写入）'"
        data-testid="import-result-errors"
        role="alert"
      >
        <n-list>
          <n-list-item v-for="(error, index) in result.errors" :key="index">
            {{ error }}
          </n-list-item>
        </n-list>
      </n-alert>
    </template>
  </div>
</template>
