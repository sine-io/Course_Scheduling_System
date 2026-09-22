<script setup lang="ts">
import { FileCheck2, FileUp, RefreshCw } from '@lucide/vue'
import { NAlert, NButton, NCard, NDataTable, NEmpty, NTag } from 'naive-ui'
import { computed, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import {
  commitReferenceImport,
  previewReferenceImport,
} from '@/api/imports'
import type { ReferenceImportAssignment, ReferenceImportPreview } from '@/api/imports'

const props = defineProps<{
  semesterId: number
  canEdit: boolean
}>()
const emit = defineEmits<{ changed: [] }>()

const wordFile = ref<File | null>(null)
const xlsxFile = ref<File | null>(null)
const preview = ref<ReferenceImportPreview | null>(null)
const loading = ref(false)
const committing = ref(false)
const error = ref<string | null>(null)
const resultMessage = ref<string | null>(null)

const tableRows = computed(() => (preview.value?.assignments ?? []).slice(0, 80))
const tableColumns = [
  { title: '班级', key: 'class_name', width: 75 },
  { title: '科目', key: 'subject', width: 100 },
  { title: '拆分', key: 'component', width: 150 },
  { title: '周节数', key: 'periods', width: 70 },
  { title: '教师', key: 'teacher', width: 100, render: (row: ReferenceImportAssignment) => row.teacher || '待指定' },
]

function chooseFile(event: Event, target: 'word' | 'xlsx') {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  if (target === 'word') wordFile.value = file
  else xlsxFile.value = file
  preview.value = null
  error.value = null
  resultMessage.value = null
}

async function previewFiles() {
  if (!wordFile.value || !xlsxFile.value) return
  loading.value = true
  error.value = null
  resultMessage.value = null
  try {
    preview.value = await previewReferenceImport(props.semesterId, wordFile.value, xlsxFile.value)
  } catch (cause) {
    error.value = apiErrorMessage(cause, '参考文件预览失败')
  } finally {
    loading.value = false
  }
}

async function commitFiles() {
  if (!preview.value || !wordFile.value || !xlsxFile.value || !props.canEdit) return
  committing.value = true
  error.value = null
  try {
    const result = await commitReferenceImport(
      props.semesterId,
      wordFile.value,
      xlsxFile.value,
      preview.value.fingerprint,
      true,
    )
    resultMessage.value = result.idempotent
      ? '这批参考文件已经导入过，系统保持幂等，未重复创建数据。'
      : `已创建 ${result.created.assignments ?? 0} 个教学任务，草稿课表已生成。`
    emit('changed')
  } catch (cause) {
    error.value = apiErrorMessage(cause, '参考文件提交失败')
  } finally {
    committing.value = false
  }
}
</script>

<template>
  <div class="reference-import-workspace">
    <div class="reference-import-heading">
      <div>
        <p class="basedata-eyebrow">参考文件</p>
        <h2>导入排课规则与教师安排</h2>
        <p>先预览归一化结果，确认后写入基础数据、教学任务和草稿固定课位。</p>
      </div>
      <NTag type="info" size="small">2026-2027 第1学期</NTag>
    </div>

    <NAlert v-if="!props.canEdit" type="info">当前角色只能预览，提交需要教务主任权限。</NAlert>
    <NAlert v-if="error" type="error" closable @close="error = null">{{ error }}</NAlert>
    <NAlert v-if="resultMessage" type="success">{{ resultMessage }}</NAlert>

    <div class="reference-import-files">
      <label>
        <span>排课规则 Word</span>
        <input type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" @change="chooseFile($event, 'word')">
        <small>{{ wordFile?.name ?? '请选择排课规则.docx' }}</small>
      </label>
      <label>
        <span>教师安排 Excel</span>
        <input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" @change="chooseFile($event, 'xlsx')">
        <small>{{ xlsxFile?.name ?? '请选择教师安排8.24.xlsx' }}</small>
      </label>
    </div>

    <div class="basedata-modal-actions">
      <NButton type="primary" :loading="loading" :disabled="!wordFile || !xlsxFile" @click="previewFiles">
        <template #icon><FileUp :size="16" aria-hidden="true" /></template>
        预览归一化结果
      </NButton>
      <NButton type="success" :loading="committing" :disabled="!preview?.can_commit || !props.canEdit" @click="commitFiles">
        <template #icon><FileCheck2 :size="16" aria-hidden="true" /></template>
        确认并生成草稿
      </NButton>
      <NButton quaternary :disabled="loading || committing" @click="previewFiles">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        刷新预览
      </NButton>
    </div>

    <template v-if="preview">
      <div class="reference-import-counts">
        <NTag v-for="(value, key) in preview.counts" :key="key" size="small">{{ key }}：{{ value }}</NTag>
      </div>
      <NAlert v-if="preview.errors.length" type="error">
        <div v-for="item in preview.errors" :key="`${item.code}-${item.source}`">{{ item.message }}{{ item.source ? `（${item.source}）` : '' }}</div>
      </NAlert>
      <NAlert v-if="preview.warnings.length" type="warning">
        <div v-for="item in preview.warnings" :key="item">{{ item }}</div>
      </NAlert>
      <NCard title="教学任务预览" size="small" :bordered="false">
        <NDataTable v-if="tableRows.length" :columns="tableColumns" :data="tableRows" :pagination="{ pageSize: 16 }" :bordered="false" />
        <NEmpty v-else description="没有可显示的教学任务" />
      </NCard>
    </template>
  </div>
</template>
