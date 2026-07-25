<script setup lang="ts">
import {
  NButton, NCard, NInput, NPopconfirm, NPopselect, NSpace, NSpin, NText, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import { PERIOD_TYPE_LABELS, getPeriodTable, replacePeriods } from '@/api/semesters'
import type { Period, PeriodType } from '@/api/semesters'
import { useProfileText } from '@/composables/useProfileText'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const { isMainland, tr } = useProfileText()
const tableId = Number(route.params.id)

interface Row {
  period_no: number
  name: string
  start_time: string | null
  end_time: string | null
  cells: Record<number, PeriodType> // weekday → type
}

const loading = ref(true)
const saving = ref(false)
const tableName = ref('')
const numWeekdays = ref(5)
const rows = ref<Row[]>([])

const WEEKDAY_NAMES = ['一', '二', '三', '四', '五', '六', '日']
const weekdays = computed(() => Array.from({ length: numWeekdays.value }, (_, i) => i + 1))

const mainlandPeriodTypeLabels: Record<PeriodType, string> = {
  regular: '常规课', morning: '早自习', lunch: '午休', homeroom: '班会时间', reserved: '固定用途',
}
function periodTypeLabel(type: PeriodType) {
  return isMainland.value ? mainlandPeriodTypeLabels[type] : PERIOD_TYPE_LABELS[type]
}
const typeOptions = computed(() => (Object.keys(PERIOD_TYPE_LABELS) as PeriodType[]).map((type) => ({
  label: periodTypeLabel(type),
  value: type,
})))

const TYPE_COLORS: Record<PeriodType, string> = {
  regular: '#e8f5e9',
  morning: '#e3f2fd',
  lunch: '#f5f5f5',
  homeroom: '#fff3e0',
  reserved: '#ffebee',
}

function buildRows(periods: Period[], nWeekdays: number) {
  const byNo = new Map<number, Row>()
  for (const p of periods) {
    let row = byNo.get(p.period_no)
    if (!row) {
      row = { period_no: p.period_no, name: p.name, start_time: p.start_time, end_time: p.end_time, cells: {} }
      byNo.set(p.period_no, row)
    }
    row.cells[p.weekday] = p.type
    // 以最早出現的名稱/時間為該列代表值
  }
  const result = [...byNo.values()].sort((a, b) => a.period_no - b.period_no)
  // 補齊缺漏格位為 regular
  for (const row of result) {
    for (let wd = 1; wd <= nWeekdays; wd++) {
      if (!(wd in row.cells)) row.cells[wd] = 'regular'
    }
  }
  return result
}

async function load() {
  loading.value = true
  try {
    const table = await getPeriodTable(tableId)
    tableName.value = table.name
    numWeekdays.value = table.num_weekdays
    rows.value = buildRows(table.periods, table.num_weekdays)
  } finally {
    loading.value = false
  }
}
onMounted(load)

function addRow() {
  const nextNo = rows.value.length ? Math.max(...rows.value.map((r) => r.period_no)) + 1 : 1
  const cells: Record<number, PeriodType> = {}
  for (const wd of weekdays.value) cells[wd] = 'regular'
  rows.value.push({
    period_no: nextNo,
    name: tr(`第 ${nextNo} 列`, `第 ${nextNo} 节`),
    start_time: null,
    end_time: null,
    cells,
  })
}

function removeRow(period_no: number) {
  rows.value = rows.value.filter((r) => r.period_no !== period_no)
}

// 將整列套用同一類型(方便一鍵設定午休等)
function applyRowType(row: Row, type: PeriodType) {
  for (const wd of weekdays.value) row.cells[wd] = type
}

async function save() {
  saving.value = true
  try {
    const periods: Period[] = []
    for (const row of rows.value) {
      for (const wd of weekdays.value) {
        periods.push({
          weekday: wd,
          period_no: row.period_no,
          name: row.name,
          start_time: row.start_time || null,
          end_time: row.end_time || null,
          type: row.cells[wd],
        })
      }
    }
    await replacePeriods(tableId, periods)
    message.success(tr('節次表已儲存', '节次表已保存'))
  } catch (e) {
    message.error((e as ApiError).detail || tr('儲存失敗', '保存失败'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <n-space vertical size="large">
    <n-space align="center" justify="space-between">
      <h1 style="margin: 0">{{ tr('節次表', '节次表') }}:{{ tableName }}</h1>
      <n-space>
        <n-button @click="router.back()">{{ tr('返回', '返回') }}</n-button>
        <n-button type="primary" :loading="saving" @click="save">{{ tr('儲存', '保存') }}</n-button>
      </n-space>
    </n-space>

    <n-text depth="3">
      {{ tr('點選格子可變更節次類型。只有「一般課」的格位會參與排課;週三下午等不排課時段請設為「固定用途」。', '点击单元格可更改节次类型。只有“常规课”单元格会参与排课；不排课时段请设为“固定用途”。') }}
    </n-text>

    <n-spin :show="loading">
      <n-card>
        <div style="overflow-x: auto">
          <table class="period-grid">
            <thead>
              <tr>
                <th style="min-width: 200px">{{ tr('節次 / 時間', '节次 / 时间') }}</th>
                <th v-for="wd in weekdays" :key="wd">{{ tr('週', '周') }}{{ WEEKDAY_NAMES[wd - 1] }}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.period_no">
                <td>
                  <n-space vertical size="small">
                    <n-input v-model:value="row.name" size="small" :placeholder="tr('名稱', '名称')" />
                    <n-space size="small" :wrap="false">
                      <n-input v-model:value="row.start_time" size="small" placeholder="08:00" style="width: 78px" />
                      <n-text depth="3">~</n-text>
                      <n-input v-model:value="row.end_time" size="small" placeholder="08:40" style="width: 78px" />
                    </n-space>
                    <n-space size="small">
                      <n-button text size="tiny" @click="applyRowType(row, 'regular')">{{ tr('整列設一般', '整行设为常规课') }}</n-button>
                      <n-button text size="tiny" @click="applyRowType(row, 'reserved')">{{ tr('整列設固定', '整行设为固定用途') }}</n-button>
                    </n-space>
                  </n-space>
                </td>
                <td v-for="wd in weekdays" :key="wd" style="text-align: center">
                  <n-popselect v-model:value="row.cells[wd]" :options="typeOptions" trigger="click">
                    <div class="cell" :style="{ background: TYPE_COLORS[row.cells[wd]] }">
                      {{ periodTypeLabel(row.cells[wd]) }}
                    </div>
                  </n-popselect>
                </td>
                <td>
                  <n-popconfirm @positive-click="removeRow(row.period_no)">
                    <template #trigger>
                      <n-button size="tiny" type="error" ghost>{{ tr('刪列', '删除行') }}</n-button>
                    </template>
                    {{ tr('刪除此節次列?', '删除此节次行吗？') }}
                  </n-popconfirm>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <n-button size="small" dashed style="margin-top: 12px" @click="addRow">+ {{ tr('新增節次列', '新增节次行') }}</n-button>
      </n-card>
    </n-spin>
  </n-space>
</template>

<style scoped>
.period-grid {
  border-collapse: collapse;
  width: 100%;
}
.period-grid th,
.period-grid td {
  border: 1px solid var(--n-border-color, #e0e0e0);
  padding: 6px 8px;
  vertical-align: middle;
}
.period-grid th {
  background: rgba(128, 128, 128, 0.08);
  font-weight: 600;
}
.cell {
  cursor: pointer;
  border-radius: 4px;
  padding: 8px 4px;
  min-width: 72px;
  color: #333;
  user-select: none;
}
</style>
