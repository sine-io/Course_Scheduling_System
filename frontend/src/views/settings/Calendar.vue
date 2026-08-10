<script setup lang="ts">
import {
  AlertTriangle, CalendarCheck2, CheckCircle2, Pencil, Plus, RefreshCw, Trash2,
} from '@lucide/vue'
import {
  NButton, NDatePicker, NEmpty, NInput, NPopconfirm, NSelect, NSpin, NTag, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import { listSemesters } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'
import {
  confirmSemesterReadiness, createCalendarException, deleteCalendarException,
  getSemesterReadiness, listCalendarExceptions, updateCalendarException,
} from '@/api/calendar'
import type { CalendarException, CalendarExceptionKind, SemesterReadiness } from '@/api/calendar'
import './settings-workspace.css'

const message = useMessage()
const route = useRoute()
const router = useRouter()
const semesters = ref<SemesterListItem[]>([])
const selectedSemesterId = ref<number | null>(null)
const exceptions = ref<CalendarException[]>([])
const readiness = ref<SemesterReadiness | null>(null)
const initialLoading = ref(true)
const dataLoading = ref(false)
const loadError = ref<string | null>(null)
const dataError = ref<string | null>(null)
const saving = ref(false)
const deletingExceptionId = ref<number | null>(null)
const confirmingReady = ref(false)
let loadSequence = 0

const form = ref({
  date: null as string | null,
  kind: 'no_instruction' as CalendarExceptionKind,
  makeup_weekday: null as number | null,
  note: '',
})
const weekdayOptions = computed(() => ['一', '二', '三', '四', '五', '六'].map((name, index) => ({
  label: `星期${name}`,
  value: index + 1,
})))
const kindOptions = [
  { label: '停课', value: 'no_instruction' },
  { label: '补课', value: 'makeup_instruction' },
]
const semesterOptions = computed(() => semesters.value.map((semester) => ({
  label: semester.label,
  value: semester.id,
})))

function errorMessage(error: unknown, fallback = '暂时无法读取校历数据，请重试。'): string {
  const detail = (error as Partial<ApiError> | null)?.detail
  return detail || fallback
}

function resetForm() {
  editingExceptionId.value = null
  form.value = { date: null, kind: 'no_instruction', makeup_weekday: null, note: '' }
}

const editingExceptionId = ref<number | null>(null)

async function loadSemesterData(id = selectedSemesterId.value) {
  if (!id) {
    exceptions.value = []
    readiness.value = null
    return
  }
  const sequence = ++loadSequence
  dataLoading.value = true
  dataError.value = null
  try {
    const [rows, state] = await Promise.all([
      listCalendarExceptions(id),
      getSemesterReadiness(id),
    ])
    if (sequence !== loadSequence) return
    exceptions.value = rows
    readiness.value = state
  } catch (error) {
    if (sequence === loadSequence) {
      dataError.value = errorMessage(error)
      exceptions.value = []
      readiness.value = null
    }
  } finally {
    if (sequence === loadSequence) dataLoading.value = false
  }
}

async function loadPage() {
  initialLoading.value = true
  loadError.value = null
  dataError.value = null
  try {
    semesters.value = await listSemesters()
    const queryId = Number(route.query.semester)
    selectedSemesterId.value = semesters.value.some((semester) => semester.id === queryId)
      ? queryId
      : (semesters.value[0]?.id ?? null)
    await loadSemesterData()
  } catch (error) {
    loadError.value = errorMessage(error)
    semesters.value = []
    selectedSemesterId.value = null
  } finally {
    initialLoading.value = false
  }
}

onMounted(loadPage)

async function selectSemester(value: number | null) {
  selectedSemesterId.value = value
  resetForm()
  if (value) {
    await router.replace({ query: { ...route.query, semester: String(value) } })
  }
  await loadSemesterData(value)
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
  if (saving.value) return
  if (!selectedSemesterId.value || !form.value.date) {
    message.warning('请选择日期')
    return
  }
  if (form.value.kind === 'makeup_instruction' && !form.value.makeup_weekday) {
    message.warning('补课日期需要选择按星期几的课表上课')
    return
  }
  saving.value = true
  try {
    const wasEditing = editingExceptionId.value !== null
    const body = {
      date: form.value.date,
      kind: form.value.kind,
      makeup_weekday: form.value.kind === 'makeup_instruction' ? form.value.makeup_weekday : null,
      note: form.value.note.trim(),
    }
    if (wasEditing) {
      await updateCalendarException(editingExceptionId.value!, body)
    } else {
      await createCalendarException(selectedSemesterId.value, body)
    }
    resetForm()
    await loadSemesterData()
    message.success(wasEditing ? '特殊日期已更新' : '特殊日期已保存')
  } catch (error) {
    message.error(errorMessage(error, '特殊日期保存失败，请重试。'))
  } finally {
    saving.value = false
  }
}

async function removeException(id: number) {
  if (deletingExceptionId.value !== null) return
  deletingExceptionId.value = id
  try {
    await deleteCalendarException(id)
    await loadSemesterData()
    message.success('特殊日期已删除')
  } catch (error) {
    message.error(errorMessage(error, '特殊日期删除失败，请重试。'))
  } finally {
    deletingExceptionId.value = null
  }
}

async function confirmReady() {
  if (!selectedSemesterId.value || confirmingReady.value) return
  confirmingReady.value = true
  try {
    readiness.value = await confirmSemesterReadiness(selectedSemesterId.value)
    message.success('排课准备已确认完成')
  } catch (error) {
    message.error(errorMessage(error, '尚未满足排课准备条件'))
    await loadSemesterData()
  } finally {
    confirmingReady.value = false
  }
}
</script>

<template>
  <div class="settings-page">
    <header class="settings-page-header">
      <div>
        <p class="settings-eyebrow">{{ '学期运行准备' }}</p>
        <h1>{{ '校历与排课准备' }}</h1>
        <p>{{ '维护停课与补课日期，检查当前学期是否具备开始排课的必要条件。' }}</p>
      </div>
      <n-button text type="primary" @click="router.push({ name: 'semesters' })">
        <template #icon><CalendarCheck2 :size="16" aria-hidden="true" /></template>
        {{ '管理学期与作息表' }}
      </n-button>
    </header>

    <section v-if="initialLoading" class="settings-state" data-testid="calendar-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取校历设置' }}</strong>
      <span>{{ '学期列表和排课准备状态加载完成后会显示在这里。' }}</span>
    </section>

    <section v-else-if="loadError" class="settings-state settings-error" data-testid="calendar-error" role="alert">
      <AlertTriangle :size="21" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '没有修改现有校历数据。' }}</span>
      <n-button type="primary" data-testid="calendar-retry" @click="loadPage">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>

    <template v-else>
      <section class="settings-panel" data-testid="calendar-semester-panel">
        <div class="settings-panel-heading">
          <div>
            <p class="settings-eyebrow">{{ '工作范围' }}</p>
            <h2>{{ '选择学期' }}</h2>
            <p>{{ '切换学期后，特殊日期和排课准备检查会同步更新。' }}</p>
          </div>
        </div>
        <n-select
          :value="selectedSemesterId"
          :options="semesterOptions"
          :disabled="!semesters.length || dataLoading"
          data-testid="calendar-semester-select"
          @update:value="selectSemester"
        />
      </section>

      <section v-if="!semesters.length" class="settings-panel settings-empty" data-testid="calendar-empty">
        <n-empty :description="'尚未创建任何学期'" />
      </section>

      <template v-else-if="selectedSemesterId">
        <section v-if="dataLoading" class="settings-state settings-inline-state" data-testid="calendar-data-loading" role="status" aria-live="polite">
          <n-spin size="small" />
          <strong>{{ '正在读取当前学期的校历' }}</strong>
        </section>

        <section v-else-if="dataError" class="settings-state settings-error settings-inline-state" data-testid="calendar-data-error" role="alert">
          <AlertTriangle :size="21" aria-hidden="true" />
          <strong>{{ dataError }}</strong>
          <n-button type="primary" data-testid="calendar-data-retry" @click="loadSemesterData()">
            <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
            {{ '重新读取当前学期' }}
          </n-button>
        </section>

        <template v-else>
          <section class="settings-panel" data-testid="calendar-exceptions-panel">
            <div class="settings-panel-heading">
              <div>
                <p class="settings-eyebrow">{{ '日期例外' }}</p>
                <h2>{{ '特殊日期' }}</h2>
                <p>{{ '停课日不会生成常规课表，补课日会按选定工作日的课表运行。' }}</p>
              </div>
              <n-tag :type="exceptions.length ? 'warning' : 'default'">{{ `${exceptions.length} 个例外` }}</n-tag>
            </div>
            <div class="settings-form-grid">
              <div class="settings-field">
                <label for="calendar-date">{{ '日期' }}</label>
                <n-date-picker id="calendar-date" v-model:formatted-value="form.date" value-format="yyyy-MM-dd" type="date" />
              </div>
              <div class="settings-field">
                <span class="settings-field-label">{{ '类型' }}</span>
                <n-select v-model:value="form.kind" :options="kindOptions" />
              </div>
              <div v-if="form.kind === 'makeup_instruction'" class="settings-field">
                <span class="settings-field-label">{{ '按哪天课表上课' }}</span>
                <n-select v-model:value="form.makeup_weekday" :options="weekdayOptions" placeholder="选择星期" />
              </div>
              <div class="settings-field">
                <label for="calendar-note">{{ '备注' }}</label>
                <n-input id="calendar-note" v-model:value="form.note" placeholder="可选" />
              </div>
            </div>
            <div class="settings-actions">
              <n-button type="primary" data-testid="calendar-save" :loading="saving" :disabled="saving" @click="saveException">
                <template #icon><Plus v-if="editingExceptionId === null" :size="15" aria-hidden="true" /><Pencil v-else :size="15" aria-hidden="true" /></template>
                {{ editingExceptionId === null ? '添加特殊日期' : '保存修改' }}
              </n-button>
              <n-button v-if="editingExceptionId !== null" data-testid="calendar-cancel-edit" :disabled="saving" @click="resetForm">{{ '取消编辑' }}</n-button>
            </div>

            <div v-if="!exceptions.length" class="settings-empty" data-testid="calendar-exceptions-empty">
              <n-empty size="small" :description="'暂无特殊日期'" />
            </div>
            <div v-else class="settings-rows" data-testid="calendar-exception-list">
              <div v-for="item in exceptions" :key="item.id" class="settings-row" :data-testid="`calendar-exception-${item.id}`">
                <div class="settings-row-main">
                  <strong>{{ item.date }}</strong>
                  <span>{{ item.note || '未填写备注' }}</span>
                </div>
                <div class="settings-command-group">
                  <n-tag :type="item.kind === 'no_instruction' ? 'error' : 'success'" size="small">
                    {{ item.kind === 'no_instruction' ? '停课' : `补课（按星期${item.makeup_weekday}课表）` }}
                  </n-tag>
                  <n-button size="small" @click="beginEdit(item)">
                    <template #icon><Pencil :size="14" aria-hidden="true" /></template>
                    {{ '编辑' }}
                  </n-button>
                  <n-popconfirm :disabled="deletingExceptionId !== null" @positive-click="removeException(item.id)">
                    <template #trigger>
                      <n-button
                        :data-testid="`calendar-delete-${item.id}`"
                        size="small" type="error" ghost
                        :loading="deletingExceptionId === item.id"
                        :disabled="deletingExceptionId !== null"
                      >
                        <template #icon><Trash2 :size="14" aria-hidden="true" /></template>
                        {{ '删除' }}
                      </n-button>
                    </template>
                    {{ `确定删除 ${item.date} 的特殊日期吗？` }}
                  </n-popconfirm>
                </div>
              </div>
            </div>
          </section>

          <section class="settings-panel" data-testid="calendar-readiness-panel">
            <div class="settings-panel-heading">
              <div>
                <p class="settings-eyebrow">{{ '排课门槛' }}</p>
                <h2>{{ '排课准备检查' }}</h2>
                <p>{{ '确认后，排课工作台会将这个学期视为已准备完成。' }}</p>
              </div>
              <CheckCircle2 :size="20" class="settings-heading-icon" aria-hidden="true" />
            </div>
            <div class="settings-actions">
              <n-tag :type="readiness?.ready ? 'success' : 'warning'" size="small">
                {{ readiness?.ready ? '已确认' : '待完善' }}
              </n-tag>
              <span class="settings-field-hint">{{ `已维护 ${readiness?.calendar_exception_count ?? 0} 个特殊日期` }}</span>
              <n-button v-if="!readiness?.ready" type="primary" data-testid="calendar-ready" :loading="confirmingReady" :disabled="confirmingReady" @click="confirmReady">
                <template #icon><CheckCircle2 :size="15" aria-hidden="true" /></template>
                {{ '确认排课准备完成' }}
              </n-button>
            </div>
            <div v-if="readiness?.issues?.length" class="settings-rows" data-testid="calendar-readiness-issues">
              <div v-for="issue in readiness.issues" :key="issue.code" class="settings-row">
                <div class="settings-row-main">
                  <strong>{{ issue.message }}</strong>
                  <span>{{ issue.code }}</span>
                </div>
                <AlertTriangle :size="17" color="var(--app-warning)" aria-hidden="true" />
              </div>
            </div>
            <div v-else class="settings-field-hint" data-testid="calendar-ready-feedback">
              {{ readiness?.ready ? '当前学期已满足排课准备条件。' : '当前没有额外问题。' }}
            </div>
          </section>
        </template>
      </template>
    </template>
  </div>
</template>
