<script setup lang="ts">
import {
  NButton, NCard, NDatePicker, NEmpty, NInput, NSelect, NSpace, NSpin, NTag, NText, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import type { ApiError } from '@/api/client'
import { listSemesters } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'
import {
  confirmSemesterReadiness, createCalendarException, deleteCalendarException,
  getSemesterReadiness, listCalendarExceptions, updateCalendarException,
} from '@/api/calendar'
import type { CalendarException, CalendarExceptionKind, SemesterReadiness } from '@/api/calendar'
import { useAppConfigStore } from '@/stores/appConfig'

const message = useMessage()
const appConfig = useAppConfigStore()
const semesters = ref<SemesterListItem[]>([])
const selectedSemesterId = ref<number | null>(null)
const exceptions = ref<CalendarException[]>([])
const readiness = ref<SemesterReadiness | null>(null)
const loading = ref(false)
const editingExceptionId = ref<number | null>(null)
const form = ref({
  date: null as string | null,
  kind: 'no_instruction' as CalendarExceptionKind,
  makeup_weekday: null as number | null,
  note: '',
})
const isMainland = computed(() => appConfig.isMainland)
const weekdayOptions = computed(() => ['一', '二', '三', '四', '五', '六'].map((name, i) => ({
  label: `${isMainland.value ? '周' : '週'}${name}`, value: i + 1,
})))
const kindOptions = computed(() => [
  { label: isMainland.value ? '停课' : '停課', value: 'no_instruction' },
  { label: isMainland.value ? '补课' : '補課', value: 'makeup_instruction' },
])

async function loadSemesterData() {
  if (!selectedSemesterId.value) return
  loading.value = true
  try {
    const [rows, state] = await Promise.all([
      listCalendarExceptions(selectedSemesterId.value), getSemesterReadiness(selectedSemesterId.value),
    ])
    exceptions.value = rows
    readiness.value = state
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  semesters.value = await listSemesters()
  selectedSemesterId.value = semesters.value[0]?.id ?? null
  await loadSemesterData()
})

function resetForm() {
  editingExceptionId.value = null
  form.value = { date: null, kind: 'no_instruction', makeup_weekday: null, note: '' }
}

function beginEdit(item: CalendarException) {
  editingExceptionId.value = item.id
  form.value = {
    date: item.date,
    kind: item.kind,
    makeup_weekday: item.makeup_weekday,
    note: item.note,
  }
}

async function saveException() {
  if (!selectedSemesterId.value || !form.value.date) {
    message.warning(isMainland.value ? '请选择日期' : '請選擇日期')
    return
  }
  try {
    const wasEditing = editingExceptionId.value !== null
    const body = {
      date: form.value.date,
      kind: form.value.kind,
      makeup_weekday: form.value.kind === 'makeup_instruction' ? form.value.makeup_weekday : null,
      note: form.value.note,
    }
    if (!wasEditing) {
      await createCalendarException(selectedSemesterId.value, body)
    } else {
      await updateCalendarException(editingExceptionId.value!, body)
    }
    resetForm()
    await loadSemesterData()
    message.success(isMainland.value
      ? (wasEditing ? '校历例外已更新' : '校历例外已保存')
      : (wasEditing ? '校曆例外已更新' : '校曆例外已儲存'))
  } catch (e) {
    message.error((e as ApiError).detail || (isMainland.value ? '保存失败' : '儲存失敗'))
  }
}

async function removeException(id: number) {
  await deleteCalendarException(id)
  await loadSemesterData()
}

async function confirmReady() {
  if (!selectedSemesterId.value) return
  try {
    readiness.value = await confirmSemesterReadiness(selectedSemesterId.value)
    message.success(isMainland.value ? '学期已确认就绪' : '學期已確認就緒')
  } catch (e) {
    message.error((e as ApiError).detail || (isMainland.value ? '尚未满足就绪条件' : '尚未符合就緒條件'))
    await loadSemesterData()
  }
}
</script>

<template>
  <n-space vertical size="large">
    <h1 style="margin: 0">{{ isMainland ? '校历与学期就绪' : '校曆與學期就緒' }}</h1>
    <n-card :title="isMainland ? '选择学期' : '選擇學期'">
      <n-select
        v-model:value="selectedSemesterId"
        :options="semesters.map(s => ({ label: s.label, value: s.id }))"
        style="max-width: 360px"
        @update:value="loadSemesterData"
      />
    </n-card>
    <n-empty v-if="!selectedSemesterId" :description="isMainland ? '尚未建立学期' : '尚未建立學期'" />
    <template v-else>
      <n-card :title="isMainland ? '校历例外日期' : '校曆例外日期'">
        <n-space align="center" :wrap="true">
          <n-date-picker v-model:formatted-value="form.date" value-format="yyyy-MM-dd" type="date" />
          <n-select v-model:value="form.kind" :options="kindOptions" style="width: 120px" />
          <n-select
            v-if="form.kind === 'makeup_instruction'"
            v-model:value="form.makeup_weekday"
            :options="weekdayOptions"
            :placeholder="isMainland ? '使用哪天课表' : '使用哪天課表'"
            style="width: 160px"
          />
          <n-input v-model:value="form.note" :placeholder="isMainland ? '备注（可选）' : '備註（選填）'" style="width: 220px" />
          <n-button type="primary" @click="saveException">
            {{ editingExceptionId === null ? (isMainland ? '添加' : '新增') : (isMainland ? '保存修改' : '儲存修改') }}
          </n-button>
          <n-button v-if="editingExceptionId !== null" @click="resetForm">
            {{ isMainland ? '取消编辑' : '取消編輯' }}
          </n-button>
        </n-space>
        <n-spin :show="loading">
          <n-space vertical style="margin-top: 16px">
            <n-empty v-if="exceptions.length === 0" :description="isMainland ? '暂无例外日期' : '尚無例外日期'" />
            <n-space v-for="item in exceptions" v-else :key="item.id" align="center" justify="space-between">
              <n-text>{{ item.date }}</n-text>
              <n-tag :type="item.kind === 'no_instruction' ? 'error' : 'success'">
                {{ item.kind === 'no_instruction' ? (isMainland ? '停课' : '停課') : `${isMainland ? '补课' : '補課'}（${isMainland ? '周' : '週'}${item.makeup_weekday}${isMainland ? '课表' : '課表'}）` }}
              </n-tag>
              <n-text depth="3">{{ item.note }}</n-text>
              <n-button size="small" tertiary @click="beginEdit(item)">{{ isMainland ? '编辑' : '編輯' }}</n-button>
              <n-button size="small" tertiary type="error" @click="removeException(item.id)">{{ isMainland ? '删除' : '刪除' }}</n-button>
            </n-space>
          </n-space>
        </n-spin>
      </n-card>
      <n-card :title="isMainland ? '学期就绪检查' : '學期就緒檢查'">
        <n-space vertical>
          <n-space align="center">
            <n-tag :type="readiness?.ready ? 'success' : 'warning'">{{ readiness?.ready ? (isMainland ? '已就绪' : '已就緒') : '草稿' }}</n-tag>
            <n-text depth="3">{{ isMainland ? `已维护 ${readiness?.calendar_exception_count ?? 0} 个校历例外` : `已維護 ${readiness?.calendar_exception_count ?? 0} 個校曆例外` }}</n-text>
            <n-button v-if="!readiness?.ready" type="primary" @click="confirmReady">{{ isMainland ? '确认就绪' : '確認就緒' }}</n-button>
          </n-space>
          <n-text v-for="issue in readiness?.issues ?? []" :key="issue.code" type="error">{{ issue.message }}</n-text>
        </n-space>
      </n-card>
    </template>
  </n-space>
</template>
