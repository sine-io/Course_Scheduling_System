<script setup lang="ts">
import { AlertTriangle, RefreshCw, Save } from '@lucide/vue'
import { NButton, NSpin, useMessage } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import type { ApiError } from '@/api/client'
import { getTimeRules, replaceTimeRules } from '@/api/basedata'
import type { TeacherRuleType } from '@/api/basedata'
import { getAvailableSlots, getSemester } from '@/api/semesters'
import type { AvailableSlot } from '@/api/semesters'
import './basedata-workspace.css'

const props = defineProps<{ teacherId: number; semesterId: number }>()
const emit = defineEmits<{ saved: [] }>()
const message = useMessage()

const loading = ref(true)
const saving = ref(false)
const loadError = ref<string | null>(null)
const slots = ref<AvailableSlot[]>([])
const noTable = ref(false)
const ruleMap = ref<Record<string, TeacherRuleType>>({})

const WEEKDAY_NAMES = ['一', '二', '三', '四', '五', '六', '日']
const CYCLE: (TeacherRuleType | null)[] = ['unavailable', 'avoid', 'prefer', null]
const ruleLabels: Record<TeacherRuleType, string> = {
  unavailable: '不可排',
  avoid: '尽量避开',
  prefer: '偏好',
}
function ruleLabel(type: TeacherRuleType) {
  return ruleLabels[type]
}

const weekdays = computed(() => [...new Set(slots.value.map((slot) => slot.weekday))].sort((a, b) => a - b))
const rows = computed(() => {
  const rowNames = new Map<number, string>()
  for (const slot of slots.value) {
    if (!rowNames.has(slot.period_no)) rowNames.set(slot.period_no, slot.name)
  }
  return [...rowNames.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([period_no, name]) => ({ period_no, name }))
})

function key(weekday: number, periodNo: number) {
  return `${weekday}_${periodNo}`
}
function cellExists(weekday: number, periodNo: number) {
  return slots.value.some((slot) => slot.weekday === weekday && slot.period_no === periodNo)
}
function cycle(weekday: number, periodNo: number) {
  if (!cellExists(weekday, periodNo)) return
  const ruleKey = key(weekday, periodNo)
  const current = ruleMap.value[ruleKey] ?? null
  const next = CYCLE[(CYCLE.indexOf(current) + 1) % CYCLE.length]
  if (next === null) delete ruleMap.value[ruleKey]
  else ruleMap.value[ruleKey] = next
}
function cellLabel(weekday: number, periodNo: number) {
  if (!cellExists(weekday, periodNo)) return `周${WEEKDAY_NAMES[weekday - 1]}，第 ${periodNo} 节，不可用时段`
  const rule = ruleMap.value[key(weekday, periodNo)]
  return `周${WEEKDAY_NAMES[weekday - 1]}，第 ${periodNo} 节，当前${rule ? ruleLabel(rule) : '无规则'}，按下切换`
}
function errorMessage(error: unknown, fallback: string) {
  return (error as Partial<ApiError> | null)?.detail || fallback
}

async function loadData() {
  loading.value = true
  loadError.value = null
  noTable.value = false
  slots.value = []
  ruleMap.value = {}
  try {
    const semester = await getSemester(props.semesterId)
    const table = semester.period_tables.find((candidate) => candidate.is_default) ?? semester.period_tables[0]
    if (!table) {
      noTable.value = true
      return
    }
    const [availableSlots, rules] = await Promise.all([
      getAvailableSlots(table.id),
      getTimeRules(props.teacherId),
    ])
    slots.value = availableSlots
    for (const rule of rules) {
      ruleMap.value[key(rule.weekday, rule.period_no)] = rule.rule_type
    }
  } catch (error) {
    loadError.value = errorMessage(error, '暂时无法读取时段规则，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

async function save() {
  if (saving.value) return
  saving.value = true
  try {
    const rules = Object.entries(ruleMap.value).map(([ruleKey, rule_type]) => {
      const [weekday, period_no] = ruleKey.split('_').map(Number)
      return { weekday, period_no, rule_type }
    })
    await replaceTimeRules(props.teacherId, rules)
    message.success('时段规则已保存')
    emit('saved')
  } catch (error) {
    message.error(errorMessage(error, '保存失败'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="basedata-form" data-testid="teacher-time-rules" :aria-busy="loading">
    <section v-if="loading" class="basedata-state basedata-state--compact" data-testid="time-rules-loading" role="status">
      <n-spin size="small" />
      <strong>{{ '正在读取时段规则' }}</strong>
    </section>
    <section v-else-if="loadError" class="basedata-state basedata-state-error basedata-state--compact" data-testid="time-rules-error" role="alert">
      <AlertTriangle :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <n-button type="primary" data-testid="time-rules-retry" @click="loadData">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>
    <section v-else-if="noTable" class="basedata-state basedata-state--compact" data-testid="time-rules-no-table">
      <strong>{{ '尚未创建作息时间表' }}</strong>
      <span>
        {{ '此学期尚未创建作息时间表，请先在“学期与作息时间表”中创建默认作息时间表，再设置时段规则。' }}
      </span>
    </section>
    <template v-else>
      <div class="basedata-rule-legend" aria-label="时段规则图例">
        <span>{{ '按单元格依次切换：' }}</span>
        <span data-rule="unavailable">{{ ruleLabel('unavailable') }}</span>
        <span data-rule="avoid">{{ ruleLabel('avoid') }}</span>
        <span data-rule="prefer">{{ ruleLabel('prefer') }}</span>
      </div>
      <div class="basedata-rule-scroll" tabindex="0" aria-label="教师时段规则表，可横向滚动">
        <table class="basedata-rule-grid">
          <thead>
            <tr>
              <th>{{ '节次' }}</th>
              <th v-for="weekday in weekdays" :key="weekday">{{ '周' }}{{ WEEKDAY_NAMES[weekday - 1] }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.period_no">
              <td class="rowhead">{{ row.name }}</td>
              <td v-for="weekday in weekdays" :key="weekday">
                <button
                  type="button"
                  class="basedata-rule-cell"
                  :data-rule="ruleMap[key(weekday, row.period_no)] || undefined"
                  :disabled="!cellExists(weekday, row.period_no)"
                  :aria-label="cellLabel(weekday, row.period_no)"
                  @click="cycle(weekday, row.period_no)"
                >
                  {{ ruleMap[key(weekday, row.period_no)] ? ruleLabel(ruleMap[key(weekday, row.period_no)]) : '' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="basedata-modal-actions">
        <n-button type="primary" data-testid="time-rules-save" :loading="saving" :disabled="saving" @click="save">
          <template #icon><Save :size="15" aria-hidden="true" /></template>
          {{ '保存规则' }}
        </n-button>
      </div>
    </template>
  </div>
</template>
