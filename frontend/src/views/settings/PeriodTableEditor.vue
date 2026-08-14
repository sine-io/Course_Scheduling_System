<script setup lang="ts">
import { AlertTriangle, ArrowLeft, Clock3, Plus, RefreshCw, Save, Trash2 } from '@lucide/vue'
import {
  NAlert, NButton, NEmpty, NInput, NPopconfirm, NPopselect, NSpin, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import { PERIOD_TYPE_LABELS, getPeriodTable, replacePeriods } from '@/api/semesters'
import { useAuthStore } from '@/stores/auth'
import type { Period, PeriodType } from '@/api/semesters'
import { useSemesterContextStore } from '@/stores/semesterContext'
import './settings-workspace.css'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const message = useMessage()
const semesterContext = useSemesterContextStore()
const tableId = Number(route.params.id)

interface Row {
  period_no: number
  name: string
  start_time: string | null
  end_time: string | null
  cells: Record<number, PeriodType>
}

const loading = ref(true)
const saving = ref(false)
const loadError = ref<string | null>(null)
const tableName = ref('')
const tableSemesterId = ref<number | null>(null)
const numWeekdays = ref(5)
const rows = ref<Row[]>([])

const canManageSemesters = computed(() => (
  !auth.user || auth.hasRole('admin') || auth.hasRole('scheduler')
))
const canEdit = computed(() => (
  canManageSemesters.value
  && (!semesterContext.authoritative || semesterContext.isCurrent(tableSemesterId.value))
))

const WEEKDAY_NAMES = ['一', '二', '三', '四', '五', '六', '日']
const weekdays = computed(() => Array.from({ length: numWeekdays.value }, (_, index) => index + 1))
const gridMinWidth = computed(() => `${300 + weekdays.value.length * 108 + 92}px`)

const periodTypeLabels: Record<PeriodType, string> = {
  regular: '常规课',
  morning: '早自习',
  lunch: '午休',
  homeroom: '班会时间',
  reserved: '固定用途',
}
const typeOptions = computed(() => (Object.keys(PERIOD_TYPE_LABELS) as PeriodType[]).map((type) => ({
  label: periodTypeLabels[type],
  value: type,
})))

function buildRows(periods: Period[], nWeekdays: number) {
  const byNumber = new Map<number, Row>()
  for (const period of periods) {
    let row = byNumber.get(period.period_no)
    if (!row) {
      row = {
        period_no: period.period_no,
        name: period.name,
        start_time: period.start_time,
        end_time: period.end_time,
        cells: {},
      }
      byNumber.set(period.period_no, row)
    }
    row.cells[period.weekday] = period.type
  }
  const result = [...byNumber.values()].sort((left, right) => left.period_no - right.period_no)
  for (const row of result) {
    for (let weekday = 1; weekday <= nWeekdays; weekday += 1) {
      if (!(weekday in row.cells)) row.cells[weekday] = 'regular'
    }
  }
  return result
}

async function load() {
  loading.value = true
  loadError.value = null
  try {
    if (!Number.isInteger(tableId) || tableId <= 0) throw new Error('invalid-period-table-id')
    await semesterContext.load()
    const table = await getPeriodTable(tableId)
    tableSemesterId.value = table.semester_id ?? null
    tableName.value = table.name
    numWeekdays.value = table.num_weekdays
    rows.value = buildRows(table.periods, table.num_weekdays)
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取作息时间表，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(load)

function addRow() {
  if (!canEdit.value) return
  const nextNumber = rows.value.length
    ? Math.max(...rows.value.map((row) => row.period_no)) + 1
    : 1
  const cells: Record<number, PeriodType> = {}
  for (const weekday of weekdays.value) cells[weekday] = 'regular'
  rows.value.push({
    period_no: nextNumber,
    name: `第 ${nextNumber} 节`,
    start_time: null,
    end_time: null,
    cells,
  })
}

function removeRow(periodNumber: number) {
  if (!canEdit.value) return
  rows.value = rows.value.filter((row) => row.period_no !== periodNumber)
}

function applyRowType(row: Row, type: PeriodType) {
  if (!canEdit.value) return
  for (const weekday of weekdays.value) row.cells[weekday] = type
}

async function save() {
  if (!canEdit.value || saving.value) return
  if (rows.value.some((row) => !row.name.trim())) {
    message.warning('请填写每个节次的名称')
    return
  }
  saving.value = true
  try {
    const periods: Period[] = []
    for (const row of rows.value) {
      for (const weekday of weekdays.value) {
        periods.push({
          weekday,
          period_no: row.period_no,
          name: row.name.trim(),
          start_time: row.start_time || null,
          end_time: row.end_time || null,
          type: row.cells[weekday],
        })
      }
    }
    await replacePeriods(tableId, periods)
    message.success('作息时间表已保存')
  } catch (error) {
    message.error(apiErrorMessage(error, '保存失败，请重试。'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="settings-page period-editor-page">
    <header class="settings-page-header">
      <div>
        <p class="settings-eyebrow">{{ '作息配置' }}</p>
        <h1>{{ '作息时间表' }}</h1>
        <p>{{ tableName ? `正在编辑“${tableName}”。只有常规课单元格会参与排课。` : '维护每天的节次、时间和用途。' }}</p>
      </div>
      <div class="settings-command-group">
        <n-button data-testid="period-table-back" @click="router.back()">
          <template #icon><ArrowLeft :size="16" aria-hidden="true" /></template>
          {{ '返回' }}
        </n-button>
        <n-button v-if="!loading && !loadError" type="primary" data-testid="period-table-save" :loading="saving" :disabled="saving || !canEdit" @click="save">
          <template #icon><Save :size="16" aria-hidden="true" /></template>
          {{ '保存作息表' }}
        </n-button>
      </div>
    </header>

    <section v-if="loading" class="settings-state" data-testid="period-table-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取作息时间表' }}</strong>
      <span>{{ '节次和工作日加载完成后会显示在编辑区。' }}</span>
    </section>

    <section v-else-if="loadError" class="settings-state settings-error" data-testid="period-table-error" role="alert">
      <AlertTriangle :size="21" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '没有修改当前作息时间表。' }}</span>
      <n-button type="primary" data-testid="period-table-retry" @click="load">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>

    <section v-else class="settings-panel period-editor-panel" data-testid="period-table-workspace">
      <div class="settings-panel-heading">
        <div>
          <p class="settings-eyebrow">{{ '编辑工作面' }}</p>
          <h2>{{ tableName }}</h2>
          <p>{{ '点击类型按钮切换单元格用途；时间和名称会应用到这一节的所有工作日。' }}</p>
        </div>
        <Clock3 :size="20" class="settings-heading-icon" aria-hidden="true" />
      </div>
      <n-alert v-if="!canEdit" type="info" data-testid="period-table-readonly">
        所选作息时间表属于历史学期，历史学期只允许查询，不能保存修改。
      </n-alert>

      <div class="settings-table-scroll period-grid-scroll" data-testid="period-grid-scroll" tabindex="0" aria-label="作息时间表，可横向滚动">
        <table class="settings-data-table period-grid" :style="{ minWidth: gridMinWidth }">
          <thead>
            <tr>
              <th class="period-details-column">{{ '节次 / 时间' }}</th>
              <th v-for="weekday in weekdays" :key="weekday">{{ '周' }}{{ WEEKDAY_NAMES[weekday - 1] }}</th>
              <th class="period-actions-column">{{ '操作' }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!rows.length">
              <td :colspan="weekdays.length + 2">
                <div class="period-empty"><n-empty size="small" :description="'尚未添加任何节次'" /></div>
              </td>
            </tr>
            <tr v-for="row in rows" v-else :key="row.period_no">
              <td class="period-details-column">
                <div class="period-details">
                  <n-input v-model:value="row.name" size="small" :aria-label="`第 ${row.period_no} 行名称`" placeholder="节次名称" :disabled="!canEdit" />
                  <div class="period-time-range">
                    <n-input v-model:value="row.start_time" size="small" :aria-label="`${row.name}开始时间`" placeholder="08:00" :disabled="!canEdit" />
                    <span aria-hidden="true">-</span>
                    <n-input v-model:value="row.end_time" size="small" :aria-label="`${row.name}结束时间`" placeholder="08:40" :disabled="!canEdit" />
                  </div>
                  <div class="period-row-presets">
                    <n-button text size="tiny" :disabled="!canEdit" @click="applyRowType(row, 'regular')">{{ '整行常规课' }}</n-button>
                    <n-button text size="tiny" :disabled="!canEdit" @click="applyRowType(row, 'reserved')">{{ '整行固定用途' }}</n-button>
                  </div>
                </div>
              </td>
              <td v-for="weekday in weekdays" :key="weekday" class="period-type-column">
                <n-popselect v-model:value="row.cells[weekday]" :options="typeOptions" trigger="click" :disabled="!canEdit">
                  <n-button
                    size="small" block
                    class="period-type-cell"
                    :class="`period-type-${row.cells[weekday]}`"
                    :aria-label="`${row.name}，周${WEEKDAY_NAMES[weekday - 1]}，${periodTypeLabels[row.cells[weekday]]}`"
                    :disabled="!canEdit"
                  >
                    {{ periodTypeLabels[row.cells[weekday]] }}
                  </n-button>
                </n-popselect>
              </td>
              <td class="period-actions-column">
                <n-popconfirm :disabled="!canEdit" @positive-click="removeRow(row.period_no)">
                  <template #trigger>
                    <n-button size="small" type="error" quaternary :disabled="!canEdit" :aria-label="`删除${row.name}`" :title="`删除${row.name}`">
                      <template #icon><Trash2 :size="15" aria-hidden="true" /></template>
                    </n-button>
                  </template>
                  {{ `确定删除“${row.name}”这一行吗？保存后才会写入系统。` }}
                </n-popconfirm>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="settings-actions">
        <n-button dashed data-testid="period-add-row" :disabled="!canEdit" @click="addRow">
          <template #icon><Plus :size="15" aria-hidden="true" /></template>
          {{ '新增节次行' }}
        </n-button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.period-editor-page,
.period-editor-panel { min-width: 0; }
.period-grid-scroll { max-width: 100%; }
.period-grid { table-layout: fixed; }
.period-grid th,
.period-grid td { text-align: center; }
.period-grid .period-details-column {
  position: sticky;
  left: 0;
  z-index: 1;
  width: 300px;
  background: var(--app-surface);
  text-align: left;
}
.period-grid thead .period-details-column {
  z-index: 2;
  background: var(--app-surface-muted);
}
.period-type-column { width: 108px; }
.period-actions-column { width: 92px; }
.period-details { display: grid; min-width: 0; gap: 8px; }
.period-time-range { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 6px; }
.period-row-presets { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.period-type-cell { min-width: 84px; border-color: transparent; font-size: 12px; font-weight: 650; }
.period-type-cell.period-type-regular { background: var(--app-success-soft); color: var(--app-success); }
.period-type-cell.period-type-morning { background: var(--app-primary-soft); color: var(--app-primary-strong); }
.period-type-cell.period-type-lunch { background: var(--app-surface-pressed); color: var(--app-text-muted); }
.period-type-cell.period-type-homeroom { background: var(--app-warning-soft); color: var(--app-warning); }
.period-type-cell.period-type-reserved { background: var(--app-danger-soft); color: var(--app-danger); }
.period-empty { display: grid; min-height: 130px; place-items: center; }

@media (max-width: 560px) {
  .period-grid .period-details-column { width: 250px; }
  .period-grid { min-width: 990px !important; }
}
</style>
