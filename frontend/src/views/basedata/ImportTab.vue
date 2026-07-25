<script setup lang="ts">
import {
  NAlert, NButton, NCheckbox, NList, NListItem, NRadioButton, NRadioGroup, NSpace, NText, NUpload,
  useMessage,
} from 'naive-ui'
import type { UploadFileInfo } from 'naive-ui'
import { computed, ref } from 'vue'
import { downloadTemplate, ENTITY_LABELS, uploadImport } from '@/api/imports'
import type { ImportEntity, ImportResult } from '@/api/imports'

const props = defineProps<{ semesterId: number }>()
const emit = defineEmits<{ imported: [] }>()
const message = useMessage()
const labels = ENTITY_LABELS

const entity = ref<ImportEntity>('subjects')
const createAccounts = ref(false)
const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const result = ref<ImportResult | null>(null)

const isTeacher = computed(() => entity.value === 'teachers')

async function onDownload() {
  try {
    await downloadTemplate(entity.value)
  } catch {
    message.error('模板下载失败')
  }
}

function onFileChange(data: { fileList: UploadFileInfo[] }) {
  selectedFile.value = data.fileList[0]?.file ?? null
  result.value = null
}

async function onUpload() {
  if (!selectedFile.value) {
    message.warning('请先选择文件')
    return
  }
  uploading.value = true
  result.value = null
  try {
    const r = await uploadImport(
      entity.value, props.semesterId, selectedFile.value, isTeacher.value && createAccounts.value,
    )
    result.value = r
    if (r.errors.length === 0) {
      message.success(`成功导入 ${r.imported} 条`)
      emit('imported')
    } else {
      message.error('导入未完成，请修正错误后重试')
    }
  } catch (e) {
    message.error((e as Error).message || '导入失败')
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <n-space vertical size="large" style="max-width: 640px">
    <n-alert type="info" :show-icon="true">
      {{ '导入步骤：① 选择数据类型 → ② 下载模板并填写（从第 4 行开始，说明/示例行会自动跳过）→ ③ 上传。任一行有误将全部不导入，并列出错误行号。' }}
    </n-alert>

    <n-space vertical>
      <n-text strong>{{ '① 数据类型' }}</n-text>
      <n-radio-group v-model:value="entity">
        <n-radio-button v-for="(label, key) in labels" :key="key" :value="key">
          {{ label }}
        </n-radio-button>
      </n-radio-group>
    </n-space>

    <n-space vertical>
      <n-text strong>{{ '② 下载模板' }}</n-text>
      <n-button @click="onDownload">{{ '下载' }}「{{ labels[entity] }}」{{ '模板' }}</n-button>
    </n-space>

    <n-space vertical>
      <n-text strong>{{ '③ 上传填写完成的文件' }}</n-text>
      <n-checkbox v-if="isTeacher" v-model:checked="createAccounts">
        {{ '同时创建教师登录账号（默认密码，首次登录需修改）' }}
      </n-checkbox>
      <n-upload :max="1" :default-upload="false" accept=".xlsx" @change="onFileChange">
        <n-button>{{ '选择文件' }}</n-button>
      </n-upload>
      <n-button type="primary" :loading="uploading" :disabled="!selectedFile" @click="onUpload">
        {{ '开始导入' }}
      </n-button>
    </n-space>

    <n-alert v-if="result && result.errors.length === 0" type="success">
      {{ `成功导入 ${result.imported} 条数据。` }}
    </n-alert>
    <n-alert v-if="result && result.errors.length > 0" type="error" :title="'导入失败（数据库未写入）'">
      <n-list>
        <n-list-item v-for="(err, i) in result.errors" :key="i">
          <n-text>{{ err }}</n-text>
        </n-list-item>
      </n-list>
    </n-alert>
  </n-space>
</template>
