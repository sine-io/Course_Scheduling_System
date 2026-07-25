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

const message = useMessage()
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
const weekdayOptions = computed(() => ['一', '二', '三', '四', '五', '六'].map((name, i) => ({
  label: `星期${name}`, value: i + 1,
})))
const kindOptions = computed(() => [
  { label: '停课', value: 'no_instruction' },
  { label: '补课', value: 'makeup_instruction' },
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
    message.warning('请选择日期')
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
    message.success(wasEditing ? '特殊日期已更新' : '特殊日期已保存')
  } catch (e) {
    message.error((e as ApiError).detail || ('保存失败'))
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
    message.success('排课准备已确认完成')
  } catch (e) {
    message.error((e as ApiError).detail || ('尚未满足排课准备条件'))
    await loadSemesterData()
  }
}
</script>

<template>
  <n-space vertical size="large">
    <h1 style="margin: 0">校历与排课准备</h1>
    <n-card :title="'选择学期'">
      <n-select
        v-model:value="selectedSemesterId"
        :options="semesters.map(s => ({ label: s.label, value: s.id }))"
        style="max-width: 360px"
        @update:value="loadSemesterData"
      />
    </n-card>
    <n-empty v-if="!selectedSemesterId" :description="'尚未创建学期'" />
    <template v-else>
      <n-card title="特殊日期">
        <n-space align="center" :wrap="true">
          <n-date-picker v-model:formatted-value="form.date" value-format="yyyy-MM-dd" type="date" />
          <n-select v-model:value="form.kind" :options="kindOptions" style="width: 120px" />
          <n-select
            v-if="form.kind === 'makeup_instruction'"
            v-model:value="form.makeup_weekday"
            :options="weekdayOptions"
            placeholder="选择按星期几的课表上课"
            style="width: 160px"
          />
          <n-input v-model:value="form.note" :placeholder="'备注（可选）'" style="width: 220px" />
          <n-button type="primary" @click="saveException">
            {{ editingExceptionId === null ? ('添加') : ('保存修改') }}
          </n-button>
          <n-button v-if="editingExceptionId !== null" @click="resetForm">
            {{ '取消编辑' }}
          </n-button>
        </n-space>
        <n-spin :show="loading">
          <n-space vertical style="margin-top: 16px">
            <n-empty v-if="exceptions.length === 0" :description="'暂无特殊日期'" />
            <n-space v-for="item in exceptions" v-else :key="item.id" align="center" justify="space-between">
              <n-text>{{ item.date }}</n-text>
              <n-tag :type="item.kind === 'no_instruction' ? 'error' : 'success'">
                {{ item.kind === 'no_instruction' ? '停课' : `补课（按星期${item.makeup_weekday}课表）` }}
              </n-tag>
              <n-text depth="3">{{ item.note }}</n-text>
              <n-button size="small" tertiary @click="beginEdit(item)">{{ '编辑' }}</n-button>
              <n-button size="small" tertiary type="error" @click="removeException(item.id)">{{ '删除' }}</n-button>
            </n-space>
          </n-space>
        </n-spin>
      </n-card>
      <n-card title="排课准备检查">
        <n-space vertical>
          <n-space align="center">
            <n-tag :type="readiness?.ready ? 'success' : 'warning'">{{ readiness?.ready ? '已确认' : '待完善' }}</n-tag>
            <n-text depth="3">{{ `已维护 ${readiness?.calendar_exception_count ?? 0} 个特殊日期` }}</n-text>
            <n-button v-if="!readiness?.ready" type="primary" @click="confirmReady">确认排课准备完成</n-button>
          </n-space>
          <n-text v-for="issue in readiness?.issues ?? []" :key="issue.code" type="error">{{ issue.message }}</n-text>
        </n-space>
      </n-card>
    </template>
  </n-space>
</template>
