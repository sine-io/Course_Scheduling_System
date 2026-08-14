<script setup lang="ts">
import {
  AlertTriangle, Building2, Download, FileImage, FileSpreadsheet, FileText, RefreshCw,
  School, Search, ShieldCheck,
} from '@lucide/vue'
import {
  NButton, NRadioButton, NRadioGroup, NSelect, NSpin, NTag, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import TimetableGrid from '@/components/timetable/TimetableGrid.vue'
import type { GridEntry, PeriodCell } from '@/components/timetable/types'
import { apiErrorMessage } from '@/api/client'
import { getMyTeacher, getPublishedTimetable, publishedSemesters } from '@/api/timetables'
import type { NamedBrief, PublicSemester, PublishedTimetable } from '@/api/timetables'
import { exportBatchZip, exportSchoolWorkbook, exportTimetable } from '@/api/exports'
import type { ExportFmt } from '@/api/exports'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import { useAuthStore } from '@/stores/auth'
import { useSemesterContextStore } from '@/stores/semesterContext'
import './scheduling/scheduling-workspace.css'

type ViewKind = 'class' | 'teacher' | 'room'
type ExportTask = ExportFmt | 'school' | 'batch'

const semesters = ref<PublicSemester[]>([])
const sid = ref<number | null>(null)
const data = ref<PublishedTimetable | null>(null)
const me = ref<NamedBrief | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)

const message = useMessage()
const auth = useAuthStore()
const semesterContext = useSemesterContextStore()
const canManage = computed(() => (
  auth.hasRole('admin') || auth.hasRole('scheduler') || auth.hasRole('director')
))

const view = ref<ViewKind>('class')
const classId = ref<number | null>(null)
const teacherId = ref<number | null>(null)
const roomId = ref<number | null>(null)
const exporting = ref<ExportTask | null>(null)

const targetId = computed(() => (
  view.value === 'class' ? classId.value
    : view.value === 'teacher' ? teacherId.value : roomId.value
))
const exportDisabled = computed(() => loading.value || exporting.value !== null || targetId.value === null)

async function onExport(format: ExportFmt) {
  if (sid.value === null || targetId.value === null || exporting.value !== null) return
  exporting.value = format
  try {
    await exportTimetable(sid.value, view.value, targetId.value, format)
    message.success('导出任务已完成')
  } catch (error) {
    message.error(apiErrorMessage(error, '导出失败'))
  } finally {
    exporting.value = null
  }
}

async function onExportAll(kind: 'school' | 'batch') {
  if (sid.value === null || exporting.value !== null) return
  exporting.value = kind
  try {
    await (kind === 'school' ? exportSchoolWorkbook(sid.value) : exportBatchZip(sid.value))
    message.success('导出任务已完成')
  } catch (error) {
    message.error(apiErrorMessage(error, '导出失败'))
  } finally {
    exporting.value = null
  }
}

const semesterOptions = computed(() => semesters.value.map((semester) => ({
  label: semester.label,
  value: semester.id,
})))
const classOptions = computed(() => (
  data.value?.classes ?? []).map((item) => ({ label: `${item.grade}年${item.name}`, value: item.id }))
)
const teacherOptions = computed(() => (
  data.value?.teachers ?? []).map((item) => ({ label: item.name, value: item.id }))
)
const roomOptions = computed(() => (
  data.value?.rooms ?? []).map((item) => ({ label: item.name, value: item.id }))
)

function resetTargets() {
  classId.value = null
  teacherId.value = null
  roomId.value = null
}

async function load(id: number) {
  loading.value = true
  loadError.value = null
  sid.value = id
  try {
    ;[data.value, me.value] = await Promise.all([getPublishedTimetable(id), getMyTeacher(id)])
    const published = data.value
    if (!published) {
      data.value = null
      me.value = null
      resetTargets()
      return
    }
    classId.value = published.classes[0]?.id ?? null
    roomId.value = published.rooms[0]?.id ?? null
    if (me.value) {
      view.value = 'teacher'
      teacherId.value = me.value.id
    } else {
      teacherId.value = published.teachers[0]?.id ?? null
      if (view.value === 'teacher' && teacherId.value === null) view.value = 'class'
    }
  } catch (error) {
    data.value = null
    me.value = null
    resetTargets()
    loadError.value = apiErrorMessage(error, '暂时无法读取已发布课表，请重试。')
  } finally {
    loading.value = false
  }
}

async function loadPage() {
  loading.value = true
  loadError.value = null
  try {
    await semesterContext.load()
    semesters.value = await publishedSemesters()
    const currentId = semesters.value.find((semester) => semester.id === semesterContext.currentSemesterId)?.id
      ?? semesterContext.currentSemesterId
      ?? semesters.value[0]?.id
    if (currentId) await load(currentId)
    else {
      sid.value = null
      data.value = null
      resetTargets()
      loading.value = false
    }
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取已发布课表，请重试。')
    loading.value = false
  }
}

onMounted(loadPage)

const defaultTable = computed(() => {
  const tables = data.value?.period_tables ?? []
  return tables.find((table) => table.is_default) ?? tables[0] ?? null
})

const activeTable = computed(() => {
  if (view.value === 'class' && classId.value) {
    const classUnit = data.value?.classes.find((item) => item.id === classId.value)
    if (classUnit?.period_table_id) {
      return data.value?.period_tables.find((table) => table.id === classUnit.period_table_id)
        ?? defaultTable.value
    }
  }
  return defaultTable.value
})
const periods = computed<PeriodCell[]>(() => (activeTable.value?.periods ?? []) as PeriodCell[])
const numWeekdays = computed(() => activeTable.value?.num_weekdays ?? 5)

const entries = computed<GridEntry[]>(() => {
  const all = data.value?.entries ?? []
  let filtered = all
  if (view.value === 'class') {
    filtered = classId.value ? all.filter((entry) => entry.class_ids.includes(classId.value!)) : []
  } else if (view.value === 'teacher') {
    filtered = teacherId.value ? all.filter((entry) => entry.teacher_ids.includes(teacherId.value!)) : []
  } else {
    filtered = roomId.value ? all.filter((entry) => entry.room_id === roomId.value) : []
  }
  return filtered.map((entry) => ({
    id: entry.id,
    weekday: entry.weekday,
    period_no: entry.period_no,
    span: entry.span,
    locked: false,
    subject: entry.subject,
    teacher: view.value === 'class' ? entry.teachers.join('、') : entry.classes.join('、'),
    room: entry.room ?? undefined,
  }))
})
</script>

<template>
  <div class="scheduling-page timetable-query-page" data-testid="timetable-query-page">
    <header class="scheduling-page-header">
      <div>
        <p class="scheduling-eyebrow">{{ '只读查询' }}</p>
        <h1>{{ '课表查询' }}</h1>
        <p>{{ '按班级、教师或教室/场地查看已发布课表，并导出当前视图。' }}</p>
      </div>
      <div class="scheduling-header-actions query-header-actions">
        <n-select
          v-if="semesters.length"
          v-accessible-select="'选择已发布学期'"
          :value="sid"
          :options="semesterOptions"
          :placeholder="'选择已发布学期'"
          data-testid="tq-semester"
          @update:value="load"
        />
        <n-tag v-if="data" size="small" type="success">
          {{ data.semester_label }} · {{ data.name }}{{ '（已发布）' }}
        </n-tag>
      </div>
    </header>

    <section v-if="loading" class="scheduling-state" data-testid="tq-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取已发布课表' }}</strong>
      <span>{{ '课表和作息时间加载完成后会显示在这里。' }}</span>
    </section>
    <section v-else-if="loadError" class="scheduling-state scheduling-state-error" data-testid="tq-error" role="alert">
      <AlertTriangle :size="23" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '未能确认发布状态，请重新读取。' }}</span>
      <n-button type="primary" data-testid="tq-retry" @click="loadPage">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>
    <section v-else-if="!data" class="scheduling-state" data-testid="tq-none">
      <Search :size="24" aria-hidden="true" />
      <strong>{{ '当前暂无已发布的课表' }}</strong>
      <span>{{ '排课管理员发布课表后，可在此按班级、教师或教室/场地查询。' }}</span>
    </section>

    <template v-else>
      <section class="scheduling-panel query-toolbar" aria-label="课表筛选与导出">
        <div class="query-view-controls">
          <div role="radiogroup" aria-label="课表视角">
            <n-radio-group v-model:value="view">
              <n-radio-button value="class" data-testid="tq-view-class">{{ '班级' }}</n-radio-button>
              <n-radio-button value="teacher" data-testid="tq-view-teacher">{{ '教师' }}</n-radio-button>
              <n-radio-button value="room" data-testid="tq-view-room">{{ '教室/场地' }}</n-radio-button>
            </n-radio-group>
          </div>
          <n-select
            v-if="view === 'class'"
            v-model:value="classId"
            v-accessible-select="'选择班级'"
            data-testid="tq-class"
            :options="classOptions"
            :placeholder="'选择班级'"
            filterable
          />
          <n-select
            v-else-if="view === 'teacher'"
            v-model:value="teacherId"
            v-accessible-select="'选择教师'"
            data-testid="tq-teacher"
            :options="teacherOptions"
            :placeholder="'选择教师'"
            filterable
          />
          <n-select
            v-else
            v-model:value="roomId"
            v-accessible-select="'选择教室/场地'"
            data-testid="tq-room"
            :options="roomOptions"
            :placeholder="'选择教室/场地'"
            filterable
          />
          <n-tag v-if="me && view === 'teacher' && teacherId === me.id" size="small" type="info">
            {{ '本人课表' }}
          </n-tag>
        </div>

        <div class="query-export-bar" aria-label="课表导出">
          <span class="query-export-label"><Download :size="15" aria-hidden="true" />{{ '导出当前课表' }}</span>
          <div class="query-export-actions">
            <n-button
              size="small"
              :loading="exporting === 'xlsx'"
              :disabled="exportDisabled"
              data-testid="export-xlsx"
              @click="onExport('xlsx')"
            >
              <template #icon><FileSpreadsheet :size="14" aria-hidden="true" /></template>Excel
            </n-button>
            <n-button
              size="small"
              :loading="exporting === 'pdf'"
              :disabled="exportDisabled"
              data-testid="export-pdf"
              @click="onExport('pdf')"
            >
              <template #icon><FileText :size="14" aria-hidden="true" /></template>PDF
            </n-button>
            <n-button
              size="small"
              :loading="exporting === 'png'"
              :disabled="exportDisabled"
              data-testid="export-png"
              @click="onExport('png')"
            >
              <template #icon><FileImage :size="14" aria-hidden="true" /></template>PNG
            </n-button>
            <template v-if="canManage">
              <span class="query-export-separator" aria-hidden="true" />
              <n-button
                size="small"
                :loading="exporting === 'school'"
                :disabled="loading || exporting !== null"
                data-testid="export-school"
                @click="onExportAll('school')"
              >
                <template #icon><School :size="14" aria-hidden="true" /></template>{{ '全校总表 Excel' }}
              </n-button>
              <n-button
                size="small"
                :loading="exporting === 'batch'"
                :disabled="loading || exporting !== null"
                data-testid="export-batch"
                @click="onExportAll('batch')"
              >
                <template #icon><Building2 :size="14" aria-hidden="true" /></template>{{ '批量 ZIP' }}
              </n-button>
            </template>
          </div>
        </div>
      </section>

      <section class="scheduling-panel query-grid-panel" data-testid="tq-grid">
        <header class="scheduling-panel-heading compact-heading">
          <div>
            <p class="scheduling-eyebrow">{{ '当前视图' }}</p>
            <h2>{{ view === 'class' ? '班级课表' : view === 'teacher' ? '教师课表' : '教室/场地课表' }}</h2>
            <p>{{ '以下内容来自当前已发布版本，只读展示。' }}</p>
          </div>
          <ShieldCheck :size="20" class="scheduling-heading-icon" aria-hidden="true" />
        </header>
        <div v-if="periods.length === 0" class="scheduling-state query-inline-state" data-testid="tq-no-periods">
          <Search :size="22" aria-hidden="true" />
          <strong>{{ '本学期暂无作息时间表' }}</strong>
          <span>{{ '作息时间表配置完成后，课表网格会显示在这里。' }}</span>
        </div>
        <TimetableGrid
          v-else
          :periods="periods"
          :num-weekdays="numWeekdays"
          :entries="entries"
          readonly
        />
      </section>
      <p class="query-readonly-note"><ShieldCheck :size="14" aria-hidden="true" />{{ '课表为只读查看；如有变动请联系排课管理员。' }}</p>
    </template>
  </div>
</template>

<style scoped>
.timetable-query-page { max-width: 1600px; }
.query-header-actions { max-width: min(680px, 58vw); }
.query-toolbar { display: grid; gap: 16px; }
.query-view-controls, .query-export-bar, .query-export-actions { display: flex; min-width: 0; align-items: center; flex-wrap: wrap; gap: 8px; }
.query-view-controls .n-select { width: 210px; max-width: 100%; }
.query-export-bar { justify-content: space-between; padding-top: 14px; border-top: 1px solid var(--app-border); }
.query-export-label { display: inline-flex; align-items: center; gap: 6px; color: var(--app-text-muted); font-size: 12px; font-weight: 700; }
.query-export-separator { width: 1px; height: 22px; margin: 0 3px; background: var(--app-border); }
.query-grid-panel { display: grid; min-width: 0; gap: 16px; overflow: hidden; }
.query-inline-state { min-height: 200px; }
.query-readonly-note { display: flex; align-items: center; gap: 6px; margin: -4px 0 0; color: var(--app-text-muted); font-size: 12px; }

@media (max-width: 820px) {
  .query-header-actions { max-width: 100%; }
  .query-export-bar { align-items: flex-start; flex-direction: column; }
}

@media (max-width: 560px) {
  .query-view-controls { align-items: stretch; flex-direction: column; }
  .query-view-controls > div, .query-view-controls .n-select { width: 100%; }
  .query-view-controls :deep(.n-radio-group) { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); width: 100%; }
  .query-view-controls :deep(.n-radio-button) { justify-content: center; min-width: 0; }
  .query-export-actions { width: 100%; }
  .query-export-separator { display: none; }
}
</style>
