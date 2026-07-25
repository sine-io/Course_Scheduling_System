<script setup lang="ts">
import { NButton, NDatePicker, NEmpty, NSelect, NSpace, NTag, NText } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { listTeachers } from '@/api/basedata'
import { listSemesters } from '@/api/semesters'
import { publishedSemesters } from '@/api/timetables'
import { getMyStats, getStats, statsExportUrl } from '@/api/substitutionStats'
import type { MonthlyReport } from '@/api/substitutionStats'
import { useAuthStore } from '@/stores/auth'
import { useAppConfigStore } from '@/stores/appConfig'

const auth = useAuthStore()
const appConfig = useAppConfigStore()
const mainland = computed(() => appConfig.isMainland)
const tr = (tw: string, cn: string) => mainland.value ? cn : tw
const canManage = computed(() =>
  auth.hasRole('admin') || auth.hasRole('scheduler') || auth.hasRole('director'))

const WEEKDAYS = computed(() => mainland.value
  ? ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  : ['週日', '週一', '週二', '週三', '週四', '週五', '週六'])
function withWeekday(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return `${iso}(${WEEKDAYS.value[new Date(y, m - 1, d).getDay()]})`
}

function monthTs(): number {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth(), 1).getTime()
}

const route = useRoute()

function initialMonthTs(): number {
  const y = Number(route.query.year)
  const m = Number(route.query.month)
  if (y && m) return new Date(y, m - 1, 1).getTime()
  return monthTs()
}

const semesters = ref<{ id: number; label: string }[]>([])
const sid = ref<number | null>(null)
const monthValue = ref<number>(initialMonthTs())
const teacherOptions = ref<{ label: string; value: number }[]>([])
const teacherId = ref<number | null>(null)
const report = ref<MonthlyReport | null>(null)
const loading = ref(false)

const semesterOptions = computed(() => semesters.value.map((s) => ({ label: s.label, value: s.id })))

function ym(): { year: number; month: number } {
  const d = new Date(monthValue.value)
  return { year: d.getFullYear(), month: d.getMonth() + 1 }
}
const periodLabel = computed(() => {
  const { year, month } = ym()
  return `${year} ${tr('年', '年')} ${month} ${tr('月', '月')}`
})
const totalBillable = computed(() =>
  (report.value?.summaries ?? []).reduce((n, s) => n + s.billable_count, 0))

async function reload() {
  if (sid.value === null) return
  loading.value = true
  const { year, month } = ym()
  try {
    report.value = canManage.value
      ? await getStats(sid.value, year, month, teacherId.value)
      : await getMyStats(sid.value, year, month)
  } finally {
    loading.value = false
  }
}

async function onSemesterChange(id: number) {
  sid.value = id
  if (canManage.value) {
    teacherOptions.value = (await listTeachers(id)).map((t) => ({ label: t.name, value: t.id }))
  }
  await reload()
}

function onExport() {
  if (sid.value === null) return
  const { year, month } = ym()
  window.open(statsExportUrl(sid.value, year, month, teacherId.value), '_blank')
}

onMounted(async () => {
  // 教師看不到 /semesters(管理權限),改用已發布學期清單
  semesters.value = canManage.value ? await listSemesters() : await publishedSemesters()
  if (!semesters.value.length) return
  const qsid = Number(route.query.semester_id)
  const initial = semesters.value.find((s) => s.id === qsid)?.id ?? semesters.value[0].id
  await onSemesterChange(initial)
})
</script>

<template>
  <n-space vertical size="large">
    <h2 style="margin: 0">{{ canManage ? tr('代課鐘點統計', '代课课时统计') : tr('我的代課鐘點', '我的代课课时') }}</h2>

    <n-space align="center" :wrap="true">
      <n-select
        :value="sid" :options="semesterOptions" style="width: 200px"
        :placeholder="tr('選擇學期', '选择学期')" @update:value="onSemesterChange"
      />
      <n-date-picker
        v-model:value="monthValue" type="month" style="width: 160px"
        data-testid="stats-month" @update:value="reload"
      />
      <n-select
        v-if="canManage" v-model:value="teacherId" :options="teacherOptions" clearable filterable
        :placeholder="tr('全部教師', '全部教师')" style="width: 180px"
        data-testid="stats-teacher" @update:value="reload"
      />
      <n-button
        v-if="canManage && report?.details.length" type="primary"
        data-testid="stats-export" @click="onExport"
      >
        {{ tr('匯出', '导出') }} Excel
      </n-button>
    </n-space>

    <n-space align="center">
      <n-text depth="3">{{ periodLabel }}</n-text>
      <n-tag v-if="report" type="info" data-testid="stats-total">
        {{ tr('計費合計', '计费合计') }} {{ totalBillable }} {{ tr('節', '节') }}
      </n-tag>
    </n-space>

    <n-empty
      v-if="report && !report.details.length && !loading"
      :description="tr('本月無代課紀錄', '本月无代课记录')" data-testid="stats-empty"
    />

    <template v-else-if="report?.details.length">
      <!-- 彙總:每位教師 -->
      <table v-if="canManage" class="data-table" data-testid="stats-summary">
        <thead>
          <tr><th>{{ tr('教師', '教师') }}</th><th>{{ tr('代課節數', '代课节数') }}</th><th>{{ tr('計費節數', '计费节数') }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="s in report.summaries" :key="s.teacher_id" data-testid="stats-summary-row">
            <td>{{ s.teacher_name }}</td>
            <td>{{ s.handled_count }}</td>
            <td>{{ s.billable_count }}</td>
          </tr>
        </tbody>
      </table>

      <!-- 明細:逐節 -->
      <table class="data-table" data-testid="stats-detail">
        <thead>
          <tr>
            <th v-if="canManage">{{ tr('教師', '教师') }}</th>
            <th>{{ tr('日期', '日期') }}</th><th>{{ tr('節次', '节次') }}</th><th>{{ tr('班級', '班级') }}</th><th>{{ tr('科目', '科目') }}</th>
            <th>{{ tr('原任教師', '原任教师') }}</th><th>{{ tr('假別', '假别') }}</th><th>{{ tr('處置', '处置') }}</th><th>{{ tr('計費', '计费') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(d, i) in report.details" :key="i" data-testid="stats-detail-row">
            <td v-if="canManage">{{ d.handler_name }}</td>
            <td>{{ withWeekday(d.date) }}</td>
            <td>{{ d.period_name }}</td>
            <td>{{ d.class_names }}</td>
            <td>{{ d.subject_name }}</td>
            <td>{{ d.absent_teacher_name }}</td>
            <td>{{ d.leave_type_label }}</td>
            <td>{{ d.sub_type_label }}</td>
            <td>
              <n-tag size="tiny" :type="d.counts_toward_hours ? 'success' : 'default'">
                {{ d.counts_toward_hours ? tr('計費', '计费') : tr('不計', '不计') }}
              </n-tag>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </n-space>
</template>

<style scoped>
.data-table { border-collapse: collapse; width: 100%; }
.data-table th, .data-table td {
  border: 1px solid var(--n-border-color, #e0e0e0); padding: 6px 10px; text-align: left;
  white-space: nowrap;
}
.data-table th { background: rgba(128, 128, 128, 0.08); font-weight: 600; }
</style>
