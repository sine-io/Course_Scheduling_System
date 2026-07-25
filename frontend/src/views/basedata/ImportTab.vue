<script setup lang="ts">
import {
  NAlert, NButton, NCheckbox, NList, NListItem, NRadioButton, NRadioGroup, NSpace, NText, NUpload,
  useMessage,
} from 'naive-ui'
import type { UploadFileInfo } from 'naive-ui'
import { computed, ref } from 'vue'
import { downloadTemplate, entityLabels, uploadImport } from '@/api/imports'
import type { ImportEntity, ImportResult } from '@/api/imports'
import { useAppConfigStore } from '@/stores/appConfig'

const props = defineProps<{ semesterId: number }>()
const emit = defineEmits<{ imported: [] }>()
const message = useMessage()
const appConfig = useAppConfigStore()
const mainland = computed(() => appConfig.isMainland)
const tr = (tw: string, cn: string) => mainland.value ? cn : tw
const labels = computed(() => entityLabels(mainland.value))

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
    message.error(tr('範本下載失敗', '模板下载失败'))
  }
}

function onFileChange(data: { fileList: UploadFileInfo[] }) {
  selectedFile.value = data.fileList[0]?.file ?? null
  result.value = null
}

async function onUpload() {
  if (!selectedFile.value) {
    message.warning(tr('請先選擇檔案', '请先选择文件'))
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
      message.success(tr(`成功匯入 ${r.imported} 筆`, `成功导入 ${r.imported} 条`))
      emit('imported')
    } else {
      message.error(tr('匯入未完成,請修正錯誤後重試', '导入未完成，请修正错误后重试'))
    }
  } catch (e) {
    message.error((e as Error).message || tr('匯入失敗', '导入失败'))
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <n-space vertical size="large" style="max-width: 640px">
    <n-alert type="info" :show-icon="true">
      {{ tr('匯入步驟:① 選擇資料類型 → ② 下載範本並填寫(第 4 列起填,說明/範例列會自動略過)→ ③ 上傳。任一列有誤將全部不匯入,並列出錯誤列號。', '导入步骤：① 选择资料类型 → ② 下载模板并填写（从第 4 行开始，说明/示例行会自动略过）→ ③ 上传。任一行有误将全部不导入，并列出错误行号。') }}
    </n-alert>

    <n-space vertical>
      <n-text strong>{{ tr('① 資料類型', '① 资料类型') }}</n-text>
      <n-radio-group v-model:value="entity">
        <n-radio-button v-for="(label, key) in labels" :key="key" :value="key">
          {{ label }}
        </n-radio-button>
      </n-radio-group>
    </n-space>

    <n-space vertical>
      <n-text strong>{{ tr('② 下載範本', '② 下载模板') }}</n-text>
      <n-button @click="onDownload">{{ tr('下載', '下载') }}「{{ labels[entity] }}」{{ tr('範本', '模板') }}</n-button>
    </n-space>

    <n-space vertical>
      <n-text strong>{{ tr('③ 上傳填好的檔案', '③ 上传填写完成的文件') }}</n-text>
      <n-checkbox v-if="isTeacher" v-model:checked="createAccounts">
        {{ tr('同時建立教師登入帳號(預設密碼,首次登入需更改)', '同时建立教师登录账号（默认密码，首次登录需修改）') }}
      </n-checkbox>
      <n-upload :max="1" :default-upload="false" accept=".xlsx" @change="onFileChange">
        <n-button>{{ tr('選擇檔案', '选择文件') }}</n-button>
      </n-upload>
      <n-button type="primary" :loading="uploading" :disabled="!selectedFile" @click="onUpload">
        {{ tr('開始匯入', '开始导入') }}
      </n-button>
    </n-space>

    <n-alert v-if="result && result.errors.length === 0" type="success">
      {{ tr(`成功匯入 ${result.imported} 筆資料。`, `成功导入 ${result.imported} 条资料。`) }}
    </n-alert>
    <n-alert v-if="result && result.errors.length > 0" type="error" :title="tr('匯入失敗(資料庫未寫入)', '导入失败（数据库未写入）')">
      <n-list>
        <n-list-item v-for="(err, i) in result.errors" :key="i">
          <n-text>{{ err }}</n-text>
        </n-list-item>
      </n-list>
    </n-alert>
  </n-space>
</template>
