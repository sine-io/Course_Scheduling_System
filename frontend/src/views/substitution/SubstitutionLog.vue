<script setup lang="ts">
import { ClipboardList, Filter, RefreshCw, RotateCcw } from '@lucide/vue'
import { NAlert, NButton, NDatePicker, NEmpty, NSelect, NSpin, NTag } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import { listTeachers } from '@/api/basedata'
import { listLeaveTypes } from '@/api/leaves'
import { listSemesters } from '@/api/semesters'
import { getSubstitutionLog } from '@/api/substitutionLog'
import type { LogEntry } from '@/api/substitutionLog'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import './operations-workspace.css'

const WEEKDAYS = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
const MAX_ROWS = 1000

function toISODate(ts: number): string {
  const date = new Date(ts)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

function withWeekday(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number)
  return `${iso}（${WEEKDAYS[new Date(year, month - 1, day).getDay()]}）`
}

const semesters = ref<{ id: number; label: string }[]>([])
const sid = ref<number | null>(null)
const teacherOptions = ref<{ label: string; value: number }[]>([])
const leaveTypes = ref<Record<string, string>>({})
const teacherId = ref<number | null>(null)
const range = ref<[number, number] | null>(null)
const leaveType = ref<string | null>(null)
const entries = ref<LogEntry[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)

const truncated = computed(() => entries.value.length >= MAX_ROWS)
const semesterOptions = computed(() => semesters.value.map((semester) => ({
  label: semester.label,
  value: semester.id,
})))
const leaveTypeOptions = computed(() => Object.entries(leaveTypes.value).map(([value, label]) => ({
  label,
  value,
})))

async function reload() {
  if (sid.value === null) return
  loading.value = true
  loadError.value = null
  try {
    entries.value = await getSubstitutionLog(sid.value, {
      teacherId: teacherId.value,
      dateFrom: range.value ? toISODate(range.value[0]) : null,
      dateTo: range.value ? toISODate(range.value[1]) : null,
      leaveType: leaveType.value,
    })
  } catch (error) {
    entries.value = []
    loadError.value = apiErrorMessage(error, '暂时无法读取调课与代课记录，请重试。')
  } finally {
    loading.value = false
  }
}

async function onSemesterChange(id: number) {
  sid.value = id
  teacherId.value = null
  entries.value = []
  loading.value = true
  loadError.value = null
  try {
    teacherOptions.value = (await listTeachers(id)).map((teacher) => ({
      label: teacher.name,
      value: teacher.id,
    }))
  } catch (error) {
    teacherOptions.value = []
    loadError.value = apiErrorMessage(error, '暂时无法读取该学期的教师与调课记录，请重试。')
    loading.value = false
    return
  }
  await reload()
}

function resetFilters() {
  teacherId.value = null
  range.value = null
  leaveType.value = null
  void reload()
}

async function loadPage() {
  loading.value = true
  loadError.value = null
  try {
    ;[semesters.value, leaveTypes.value] = await Promise.all([listSemesters(), listLeaveTypes()])
    if (!semesters.value.length) {
      sid.value = null
      entries.value = []
      teacherOptions.value = []
      return
    }
    await onSemesterChange(semesters.value[0].id)
  } catch (error) {
    entries.value = []
    loadError.value = apiErrorMessage(error, '暂时无法读取调课与代课记录，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(loadPage)

function dispositionText(entry: LogEntry): string {
  if (!entry.disposed) return '待安排'
  if (entry.handler_name) return `${entry.sub_type_label} · ${entry.handler_name}`
  return entry.sub_type_label ?? ''
}

function statusType(entry: LogEntry): string {
  if (entry.status === 'pending') return 'warning'
  if (entry.status === 'cancelled') return 'default'
  if (entry.status === 'completed') return 'info'
  return 'success'
}
</script>

<template>
  <main class="operations-page report-page" data-testid="substitution-log-page">
    <header class="operations-page-header">
      <div>
        <p class="operations-eyebrow">{{ '调课与代课' }}</p>
        <h1>{{ '调课与代课记录' }}</h1>
      </div>
      <div class="operations-header-actions">
        <n-select
          v-if="semesters.length"
          v-accessible-select="'选择工作学期'"
          :value="sid"
          :options="semesterOptions"
          :placeholder="'选择学期'"
          data-testid="log-semester"
          @update:value="onSemesterChange"
        />
      </div>
    </header>

    <section v-if="loading && !entries.length" class="operations-state" data-testid="log-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取调课与代课记录' }}</strong>
    </section>

    <section v-else-if="loadError" class="operations-state operations-state-error" data-testid="log-error" role="alert">
      <RefreshCw :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <n-button type="primary" data-testid="log-retry" @click="loadPage">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>

    <section v-else-if="sid === null" class="operations-state" data-testid="log-no-semester">
      <ClipboardList :size="24" aria-hidden="true" />
      <strong>{{ '暂无可查看的学期' }}</strong>
    </section>

    <template v-else>
      <section class="operations-panel report-filter-panel" data-testid="log-filters">
        <header class="operations-panel-heading">
          <div>
            <p class="operations-eyebrow">{{ '记录范围' }}</p>
            <h2>{{ '筛选调课与代课记录' }}</h2>
            <p>{{ '按教师、日期范围和请假类型缩小查询结果。' }}</p>
          </div>
          <Filter :size="20" class="operations-heading-icon" aria-hidden="true" />
        </header>

        <div class="report-filter-grid">
          <div class="operations-field">
            <label>{{ '教师（缺课或代课）' }}</label>
            <n-select
              v-model:value="teacherId"
              v-accessible-select="'教师（缺课或代课）'"
              :options="teacherOptions"
              clearable
              filterable
              :placeholder="'全部教师'"
              data-testid="log-teacher"
              @update:value="reload"
            />
          </div>
          <div class="operations-field report-date-range-field">
            <label>{{ '日期范围' }}</label>
            <n-date-picker
              v-model:value="range"
              type="daterange"
              clearable
              :input-props="{ 'aria-label': '记录日期范围' }"
              data-testid="log-range"
              @update:value="reload"
            />
          </div>
          <div class="operations-field">
            <label>{{ '请假类型' }}</label>
            <n-select
              v-model:value="leaveType"
              v-accessible-select="'请假类型'"
              :options="leaveTypeOptions"
              clearable
              :placeholder="'全部类型'"
              data-testid="log-leavetype"
              @update:value="reload"
            />
          </div>
          <n-button quaternary class="report-reset-action" data-testid="log-reset" @click="resetFilters">
            <template #icon><RotateCcw :size="14" aria-hidden="true" /></template>
            {{ '清除筛选' }}
          </n-button>
        </div>
      </section>

      <section class="operations-panel report-results-panel" data-testid="log-results">
        <header class="operations-panel-heading">
          <div>
            <p class="operations-eyebrow">{{ '历史记录' }}</p>
            <h2>{{ '调课与代课明细' }}</h2>
            <p data-testid="log-count">{{ '共' }} {{ entries.length }} {{ '条' }}</p>
          </div>
          <ClipboardList :size="20" class="operations-heading-icon" aria-hidden="true" />
        </header>

        <n-alert v-if="truncated" type="warning" :bordered="false" data-testid="log-truncated">
          {{ `只显示最新的 ${MAX_ROWS} 条，更早记录未列出。请缩小日期范围，或添加教师、请假类型筛选。` }}
        </n-alert>

        <div v-if="!entries.length && !loading" class="operations-inline-empty">
          <n-empty :description="'没有符合条件的记录'" data-testid="log-empty" />
        </div>

        <div
          v-else-if="entries.length"
          class="operations-table-scroll report-table-scroll"
          data-testid="log-table-scroll"
          tabindex="0"
          aria-label="调课与代课历史记录，可横向滚动"
        >
          <table class="operations-data-table report-data-table substitution-log-table" data-testid="log-table">
            <thead>
              <tr>
                <th>{{ '日期' }}</th>
                <th>{{ '节次' }}</th>
                <th>{{ '班级' }}</th>
                <th>{{ '科目' }}</th>
                <th>{{ '原授课教师' }}</th>
                <th>{{ '请假类型' }}</th>
                <th>{{ '处理方式' }}</th>
                <th>{{ '状态' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in entries" :key="entry.affected_period_id" data-testid="log-row">
                <td data-label="日期"><strong>{{ withWeekday(entry.date) }}</strong></td>
                <td data-label="节次">{{ entry.period_name }}</td>
                <td data-label="班级">{{ entry.class_names }}</td>
                <td data-label="科目">{{ entry.subject_name }}</td>
                <td data-label="原授课教师">{{ entry.absent_teacher_name }}</td>
                <td data-label="请假类型">{{ entry.leave_type_label }}</td>
                <td data-label="处理方式" :class="{ 'report-pending-text': !entry.disposed }">{{ dispositionText(entry) }}</td>
                <td data-label="状态">
                  <n-tag size="small" :type="statusType(entry) as never">{{ entry.status_label }}</n-tag>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </main>
</template>
