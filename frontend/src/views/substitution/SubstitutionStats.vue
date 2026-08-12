<script setup lang="ts">
import { BarChart3, CalendarRange, Download, FileSpreadsheet, RefreshCw } from '@lucide/vue'
import { NButton, NDatePicker, NEmpty, NSelect, NSpin, NTag } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import { listTeachers } from '@/api/basedata'
import { listSemesters } from '@/api/semesters'
import { publishedSemesters } from '@/api/timetables'
import { getMyStats, getStats, statsExportUrl } from '@/api/substitutionStats'
import type { MonthlyReport } from '@/api/substitutionStats'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import { useAuthStore } from '@/stores/auth'
import { formatDateWithWeekday } from './reportDate'
import './operations-workspace.css'

const auth = useAuthStore()
const route = useRoute()
const canManage = computed(() =>
  auth.hasRole('admin') || auth.hasRole('scheduler') || auth.hasRole('director'))

function monthTs(): number {
  const date = new Date()
  return new Date(date.getFullYear(), date.getMonth(), 1).getTime()
}

function initialMonthTs(): number {
  const year = Number(route.query.year)
  const month = Number(route.query.month)
  if (year && month) return new Date(year, month - 1, 1).getTime()
  return monthTs()
}

const semesters = ref<{ id: number; label: string }[]>([])
const sid = ref<number | null>(null)
const monthValue = ref<number>(initialMonthTs())
const teacherOptions = ref<{ label: string; value: number }[]>([])
const teacherId = ref<number | null>(null)
const report = ref<MonthlyReport | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)

const semesterOptions = computed(() => semesters.value.map((semester) => ({
  label: semester.label,
  value: semester.id,
})))

function yearMonth(): { year: number; month: number } {
  const date = new Date(monthValue.value)
  return { year: date.getFullYear(), month: date.getMonth() + 1 }
}

const periodLabel = computed(() => {
  const { year, month } = yearMonth()
  return `${year} 年 ${month} 月`
})
const totalHandled = computed(() =>
  (report.value?.summaries ?? []).reduce((total, summary) => total + summary.handled_count, 0))
const totalBillable = computed(() =>
  (report.value?.summaries ?? []).reduce((total, summary) => total + summary.billable_count, 0))

async function reload() {
  if (sid.value === null) return
  loading.value = true
  loadError.value = null
  const { year, month } = yearMonth()
  try {
    report.value = canManage.value
      ? await getStats(sid.value, year, month, teacherId.value)
      : await getMyStats(sid.value, year, month)
  } catch (error) {
    report.value = null
    loadError.value = apiErrorMessage(error, '暂时无法读取代课课时统计，请重试。')
  } finally {
    loading.value = false
  }
}

async function onSemesterChange(id: number) {
  sid.value = id
  teacherId.value = null
  report.value = null
  loading.value = true
  loadError.value = null
  try {
    teacherOptions.value = canManage.value
      ? (await listTeachers(id)).map((teacher) => ({
        label: teacher.name,
        value: teacher.id,
      }))
      : []
  } catch (error) {
    teacherOptions.value = []
    loadError.value = apiErrorMessage(error, '暂时无法读取该学期的教师与代课统计，请重试。')
    loading.value = false
    return
  }
  await reload()
}

function onExport() {
  if (sid.value === null) return
  const { year, month } = yearMonth()
  window.open(statsExportUrl(sid.value, year, month, teacherId.value), '_blank')
}

async function loadPage() {
  loading.value = true
  loadError.value = null
  try {
    semesters.value = canManage.value ? await listSemesters() : await publishedSemesters()
    if (!semesters.value.length) {
      sid.value = null
      report.value = null
      teacherOptions.value = []
      return
    }
    const querySemesterId = Number(route.query.semester_id)
    const initialSemesterId = semesters.value.find((semester) => semester.id === querySemesterId)?.id
      ?? semesters.value[0].id
    await onSemesterChange(initialSemesterId)
  } catch (error) {
    report.value = null
    loadError.value = apiErrorMessage(error, '暂时无法读取代课课时统计，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(loadPage)
</script>

<template>
  <main class="operations-page report-page" data-testid="substitution-stats-page">
    <header class="operations-page-header">
      <div>
        <p class="operations-eyebrow">{{ '调课与代课' }}</p>
        <h1>{{ canManage ? '代课课时统计' : '我的代课课时' }}</h1>
      </div>
      <div class="operations-header-actions">
        <n-select
          v-if="semesters.length"
          v-accessible-select="'选择工作学期'"
          :value="sid"
          :options="semesterOptions"
          :placeholder="'选择学期'"
          data-testid="stats-semester"
          @update:value="onSemesterChange"
        />
      </div>
    </header>

    <section v-if="loading && !report" class="operations-state" data-testid="stats-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取代课课时统计' }}</strong>
    </section>

    <section v-else-if="loadError" class="operations-state operations-state-error" data-testid="stats-error" role="alert">
      <RefreshCw :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <n-button type="primary" data-testid="stats-retry" @click="loadPage">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>

    <section v-else-if="sid === null" class="operations-state" data-testid="stats-no-semester">
      <BarChart3 :size="24" aria-hidden="true" />
      <strong>{{ '暂无可查看的学期' }}</strong>
    </section>

    <template v-else>
      <section class="operations-panel report-filter-panel" data-testid="stats-filters">
        <header class="operations-panel-heading">
          <div>
            <p class="operations-eyebrow">{{ '统计范围' }}</p>
            <h2>{{ periodLabel }}</h2>
            <p>{{ canManage ? '按月份与教师核对代课和计费课时。' : '按月份查看我的代课明细与计费课时。' }}</p>
          </div>
          <CalendarRange :size="20" class="operations-heading-icon" aria-hidden="true" />
        </header>

        <div class="report-filter-row stats-filter-row">
          <div class="operations-field">
            <label>{{ '月份' }}</label>
            <n-date-picker
              v-model:value="monthValue"
              type="month"
              :input-props="{ 'aria-label': '统计月份' }"
              data-testid="stats-month"
              @update:value="reload"
            />
          </div>
          <div v-if="canManage" class="operations-field stats-teacher-field">
            <label>{{ '教师' }}</label>
            <n-select
              v-model:value="teacherId"
              v-accessible-select="'统计教师'"
              :options="teacherOptions"
              clearable
              filterable
              :placeholder="'全部教师'"
              data-testid="stats-teacher"
              @update:value="reload"
            />
          </div>
          <n-button
            v-if="canManage && report?.details.length"
            type="primary"
            class="report-primary-action"
            data-testid="stats-export"
            @click="onExport"
          >
            <template #icon><Download :size="15" aria-hidden="true" /></template>
            {{ '导出 Excel' }}
          </n-button>
        </div>

        <div v-if="report" class="stats-metrics" aria-label="课时统计概览">
          <div>
            <span>{{ '代课记录' }}</span>
            <strong>{{ report.details.length }}</strong>
            <small>{{ '条明细' }}</small>
          </div>
          <div>
            <span>{{ '处理课时' }}</span>
            <strong>{{ totalHandled }}</strong>
            <small>{{ '节' }}</small>
          </div>
          <div data-testid="stats-total">
            <span>{{ '计费合计' }}</span>
            <strong>{{ totalBillable }}</strong>
            <small>{{ '节' }}</small>
          </div>
        </div>
      </section>

      <section class="operations-panel report-results-panel" data-testid="stats-results">
        <header class="operations-panel-heading">
          <div>
            <p class="operations-eyebrow">{{ '月度报告' }}</p>
            <h2>{{ canManage ? '汇总与明细' : '我的代课明细' }}</h2>
            <p>{{ report?.details.length ? `当前显示 ${report.details.length} 条代课明细` : '本月没有代课记录' }}</p>
          </div>
          <FileSpreadsheet :size="20" class="operations-heading-icon" aria-hidden="true" />
        </header>

        <div v-if="report && !report.details.length" class="operations-inline-empty">
          <n-empty :description="'本月无代课记录'" data-testid="stats-empty" />
        </div>

        <template v-else-if="report?.details.length">
          <div v-if="canManage" class="stats-report-block">
            <h3>{{ '教师汇总' }}</h3>
            <div
              class="operations-table-scroll report-table-scroll"
              data-testid="stats-summary-scroll"
              tabindex="0"
              aria-label="教师代课课时汇总，可横向滚动"
            >
              <table class="operations-data-table stats-summary-table" data-testid="stats-summary">
                <thead>
                  <tr><th>{{ '教师' }}</th><th>{{ '代课课时' }}</th><th>{{ '计费课时' }}</th></tr>
                </thead>
                <tbody>
                  <tr v-for="summary in report.summaries" :key="summary.teacher_id" data-testid="stats-summary-row">
                    <td data-label="教师"><strong>{{ summary.teacher_name }}</strong></td>
                    <td data-label="代课课时">{{ summary.handled_count }}</td>
                    <td data-label="计费课时">{{ summary.billable_count }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="stats-report-block">
            <h3>{{ '逐节明细' }}</h3>
            <div
              class="operations-table-scroll report-table-scroll"
              data-testid="stats-detail-scroll"
              tabindex="0"
              aria-label="代课课时逐节明细，可横向滚动"
            >
              <table class="operations-data-table report-data-table stats-detail-table" data-testid="stats-detail">
                <thead>
                  <tr>
                    <th v-if="canManage">{{ '教师' }}</th>
                    <th>{{ '日期' }}</th>
                    <th>{{ '节次' }}</th>
                    <th>{{ '班级' }}</th>
                    <th>{{ '科目' }}</th>
                    <th>{{ '原授课教师' }}</th>
                    <th>{{ '请假类型' }}</th>
                    <th>{{ '处理方式' }}</th>
                    <th>{{ '计费' }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(detail, index) in report.details" :key="index" data-testid="stats-detail-row">
                    <td v-if="canManage" data-label="教师"><strong>{{ detail.handler_name }}</strong></td>
                    <td data-label="日期">{{ formatDateWithWeekday(detail.date) }}</td>
                    <td data-label="节次">{{ detail.period_name }}</td>
                    <td data-label="班级">{{ detail.class_names }}</td>
                    <td data-label="科目">{{ detail.subject_name }}</td>
                    <td data-label="原授课教师">{{ detail.absent_teacher_name }}</td>
                    <td data-label="请假类型">{{ detail.leave_type_label }}</td>
                    <td data-label="处理方式">{{ detail.sub_type_label }}</td>
                    <td data-label="计费">
                      <n-tag size="tiny" :type="detail.counts_toward_hours ? 'success' : 'default'">
                        {{ detail.counts_toward_hours ? '计费' : '不计' }}
                      </n-tag>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>
      </section>
    </template>
  </main>
</template>
