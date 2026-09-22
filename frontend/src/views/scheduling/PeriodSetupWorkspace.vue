<script setup lang="ts">
import {
  AlertTriangle, CheckCircle2, Clock3, Plus, RefreshCw, Save, Trash2,
} from '@lucide/vue'
import {
  NAlert, NButton, NCheckbox, NEmpty, NInput, NInputNumber, NPopconfirm, NPopselect, NSpin, NTag, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref, watch } from 'vue'
import { apiErrorMessage } from '@/api/client'
import type { Assignment, ClassLoad } from '@/api/assignments'
import { applyPeriodSetup, getPeriodSetup, PERIOD_TYPE_LABELS } from '@/api/semesters'
import type { PeriodSetupClass, PeriodSetupDraft, PeriodSetupGroup, PeriodSetupPattern, PeriodType } from '@/api/semesters'

const props = withDefaults(defineProps<{
  semesterId: number
  assignments?: Assignment[]
  classLoads?: ClassLoad[]
  canEdit?: boolean
}>(), {
  assignments: () => [],
  classLoads: () => [],
  canEdit: true,
})

const emit = defineEmits<{
  changed: []
  editPeriodTable: [id: number]
}>()

type PeriodSection = 'morning' | 'afternoon' | 'evening' | 'break'

interface PeriodRow {
  period_no: number
  name: string
  start_time: string | null
  end_time: string | null
  cells: Record<number, PeriodType>
  section: PeriodSection
}

interface EditableGroup {
  key: string
  table_id: number | null
  name: string
  num_weekdays: number
  weekdays: number[]
  morning_count: number
  afternoon_count: number
  evening_count: number
  is_default: boolean
  class_ids: number[]
  rows: PeriodRow[]
}

interface NormalizedTime {
  value: string | null
  seconds: number | null
}

const message = useMessage()
const loading = ref(true)
const saving = ref(false)
const refreshing = ref(false)
const loadError = ref<string | null>(null)
const draft = ref<PeriodSetupDraft | null>(null)
const groups = ref<EditableGroup[]>([])
const activeGroupKey = ref('')

const WEEKDAY_NAMES = ['一', '二', '三', '四', '五', '六', '日']
const typeLabels: Record<PeriodType, string> = {
  regular: '常规课',
  morning: '早自习',
  lunch: '午休',
  homeroom: '班会时间',
  reserved: '固定用途',
}
const sectionLabels: Record<PeriodSection, string> = {
  morning: '上午',
  afternoon: '下午',
  evening: '晚上',
  break: '休息',
}
const typeOptions = (Object.keys(PERIOD_TYPE_LABELS) as PeriodType[]).map((type) => ({
  label: typeLabels[type],
  value: type,
}))

const activeGroup = computed(() => groups.value.find((group) => group.key === activeGroupKey.value) ?? groups.value[0] ?? null)
const activeWeekdays = computed(() => activeGroup.value?.weekdays ?? [])
const gradeGroups = computed(() => {
  const byGrade = new Map<number, PeriodSetupClass[]>()
  for (const item of draft.value?.classes ?? []) {
    const items = byGrade.get(item.grade) ?? []
    items.push(item)
    byGrade.set(item.grade, items)
  }
  return [...byGrade.entries()].sort(([left], [right]) => left - right).map(([grade, classes]) => ({ grade, classes }))
})
const assignedClassCounts = computed(() => {
  const counts = new Map<number, number>()
  for (const group of groups.value) {
    for (const classId of group.class_ids) counts.set(classId, (counts.get(classId) ?? 0) + 1)
  }
  return counts
})
const unassignedClasses = computed(() => (draft.value?.classes ?? []).filter((item) => !assignedClassCounts.value.has(item.id)))
const duplicateClasses = computed(() => [...assignedClassCounts.value.entries()].filter(([, count]) => count > 1).map(([id]) => id))
const duplicateGroupNames = computed(() => {
  const counts = new Map<string, number>()
  for (const group of groups.value) {
    const name = group.name.trim()
    if (name) counts.set(name, (counts.get(name) ?? 0) + 1)
  }
  return [...counts.entries()].filter(([, count]) => count > 1).map(([name]) => name)
})
const groupsWithoutRegular = computed(() => groups.value.filter((group) => group.class_ids.length > 0 && regularCapacity(group) === 0))
const localBlockers = computed(() => {
  const blockers: string[] = []
  if (!groups.value.length) blockers.push('至少需要一套作息分组')
  if (unassignedClasses.value.length) blockers.push(`仍有 ${unassignedClasses.value.length} 个班级没有分配作息分组`)
  if (duplicateClasses.value.length) blockers.push('同一个班级被分配到了多个作息分组')
  if (duplicateGroupNames.value.length) blockers.push(`作息分组名称重复：「${duplicateGroupNames.value[0]}」`)
  if (!groups.value.some((group) => group.is_default)) blockers.push('请指定一套学期默认作息')
  if (groups.value.filter((group) => group.is_default).length > 1) blockers.push('只能指定一套学期默认作息')
  if (groupsWithoutRegular.value.length) blockers.push(`「${groupsWithoutRegular.value[0].name}」至少需要一个常规课节次`)
  if (!groups.value.some((group) => regularCapacity(group) > 0)) blockers.push('至少需要一个常规课节次')
  return blockers
})

function weekdayRange(count: number): number[] {
  return Array.from({ length: Math.max(0, Math.min(7, Math.trunc(count || 0))) }, (_, index) => index + 1)
}

function normalizeWeekdays(input: number[] | undefined, fallbackCount: number): number[] {
  const selected = [...new Set((input ?? []).map(Number).filter((day) => Number.isInteger(day) && day >= 1 && day <= 7))]
  const fallback = Math.max(5, Math.min(7, Math.trunc(fallbackCount || 5)))
  if (!selected.length) selected.push(...weekdayRange(fallback))
  while (selected.length < 5) {
    const next = weekdayRange(7).find((day) => !selected.includes(day))
    if (next === undefined) break
    selected.push(next)
  }
  return selected.sort((left, right) => left - right)
}

function cellsFor(days: number[] | number, type: PeriodType = 'regular'): Record<number, PeriodType> {
  const weekdays = Array.isArray(days) ? days : weekdayRange(days)
  return Object.fromEntries(weekdays.map((day) => [day, type])) as Record<number, PeriodType>
}

function formatClock(totalMinutes: number): string {
  const safe = Math.max(0, Math.min(23 * 60 + 59, totalMinutes))
  return `${String(Math.floor(safe / 60)).padStart(2, '0')}:${String(safe % 60).padStart(2, '0')}`
}

function defaultTime(section: PeriodSection, index: number): { start_time: string; end_time: string } {
  const base = section === 'morning' ? 8 * 60 : section === 'afternoon' ? 14 * 60 : section === 'evening' ? 19 * 60 : 12 * 60
  const duration = section === 'break' ? 90 : 45
  const gap = section === 'break' ? 0 : 10
  const start = base + index * (duration + gap)
  return { start_time: formatClock(start), end_time: formatClock(start + duration) }
}

function emptyRow(
  periodNo: number,
  name: string,
  section: PeriodSection,
  weekdays: number[],
  type: PeriodType = 'regular',
  sectionIndex = 0,
): PeriodRow {
  const time = defaultTime(section, Math.max(0, sectionIndex))
  return {
    period_no: periodNo,
    name,
    start_time: time.start_time,
    end_time: time.end_time,
    cells: cellsFor(weekdays, type),
    section,
  }
}

function sectionFromPattern(pattern: PeriodSetupPattern): PeriodSection {
  const name = pattern.name.toLowerCase()
  if (pattern.type === 'lunch' || name.includes('午休') || name.includes('午餐')) return 'break'
  if (pattern.type === 'morning' || name.includes('早自习') || name.includes('早读')) return 'morning'
  const hour = pattern.start_time ? Number(pattern.start_time.slice(0, 2)) : NaN
  if (Number.isFinite(hour) && hour >= 18) return 'evening'
  return 'afternoon'
}

function rowsFromPatterns(periods: PeriodSetupPattern[], weekdays: number[]): PeriodRow[] {
  const byNumber = new Map<number, PeriodRow>()
  for (const period of periods) {
    const row = byNumber.get(period.period_no) ?? {
      period_no: period.period_no,
      name: period.name,
      start_time: period.start_time,
      end_time: period.end_time,
      cells: {},
      section: sectionFromPattern(period),
    }
    row.name ||= period.name
    row.start_time ??= period.start_time
    row.end_time ??= period.end_time
    for (const weekday of period.weekdays) row.cells[weekday] = period.type
    byNumber.set(period.period_no, row)
  }
  const rows = [...byNumber.values()].sort((left, right) => left.period_no - right.period_no)
  let regularIndex = 0
  for (const row of rows) {
    for (const weekday of weekdays) row.cells[weekday] ??= 'regular'
    if (row.section === 'afternoon' && Object.values(row.cells).every((type) => type === 'regular')) {
      // Existing tables usually have no explicit section marker. Use the first
      // four regular rows as morning rows and the rest as afternoon rows.
      row.section = regularIndex < 4 ? 'morning' : 'afternoon'
      regularIndex += 1
    } else if (row.section !== 'break' && Object.values(row.cells).some((type) => type === 'regular')) {
      regularIndex += 1
    }
  }
  return rows
}

function countSections(rows: PeriodRow[]): { morning: number; afternoon: number; evening: number } {
  return {
    morning: rows.filter((row) => row.section === 'morning').length,
    afternoon: rows.filter((row) => row.section === 'afternoon').length,
    evening: rows.filter((row) => row.section === 'evening').length,
  }
}

function cloneCells(source: Record<number, PeriodType>, weekdays: number[], fallback: PeriodType = 'regular') {
  const cells = cellsFor(weekdays, fallback)
  for (const day of weekdays) cells[day] = source[day] ?? fallback
  return cells
}

function rowsForCounts(
  weekdays: number[],
  morningCount: number,
  afternoonCount: number,
  eveningCount: number,
  previousRows: PeriodRow[] = [],
): PeriodRow[] {
  const counts = {
    morning: Math.max(0, Math.min(10, Math.trunc(morningCount || 0))),
    afternoon: Math.max(0, Math.min(10, Math.trunc(afternoonCount || 0))),
    evening: Math.max(0, Math.min(10, Math.trunc(eveningCount || 0))),
  }
  const used = new Set<number>()
  const takePrevious = (section: PeriodSection, type: PeriodType = 'regular') => {
    const candidates = previousRows.filter((row) => row.section === section && !used.has(row.period_no))
    const existing = candidates[0]
    if (!existing) return null
    used.add(existing.period_no)
    return {
      ...existing,
      cells: cloneCells(existing.cells, weekdays, type),
      section,
    }
  }
  const rows: PeriodRow[] = []
  let periodNo = 1
  const append = (section: PeriodSection, index: number, name: string, type: PeriodType = 'regular') => {
    const previous = takePrevious(section, type)
    rows.push(previous
      ? { ...previous, period_no: periodNo }
      : emptyRow(periodNo, name, section, weekdays, type, index))
    periodNo += 1
  }
  for (let index = 0; index < counts.morning; index += 1) append('morning', index, `上午第 ${index + 1} 节`)
  if (counts.morning > 0 && (counts.afternoon > 0 || counts.evening > 0)) append('break', 0, '午休', 'lunch')
  for (let index = 0; index < counts.afternoon; index += 1) append('afternoon', index, `下午第 ${index + 1} 节`)
  for (let index = 0; index < counts.evening; index += 1) append('evening', index, `晚上第 ${index + 1} 节`)
  return rows
}

function inferredWeekdays(group: PeriodSetupGroup): number[] {
  const fromPatterns = [...new Set(group.periods.flatMap((period) => period.weekdays))]
  return normalizeWeekdays(fromPatterns, group.num_weekdays)
}

function cloneGroup(group: PeriodSetupGroup): EditableGroup {
  const weekdays = inferredWeekdays(group)
  const rows = rowsFromPatterns(group.periods, weekdays)
  const counts = countSections(rows)
  return {
    key: group.key,
    table_id: group.table_id,
    name: group.name,
    num_weekdays: Math.max(5, ...weekdays),
    weekdays,
    morning_count: counts.morning,
    afternoon_count: counts.afternoon,
    evening_count: counts.evening,
    is_default: group.is_default,
    class_ids: [...group.class_ids],
    rows,
  }
}

function setDraft(next: PeriodSetupDraft) {
  draft.value = next
  groups.value = next.groups.map(cloneGroup)
  activeGroupKey.value = groups.value.find((group) => group.key === activeGroupKey.value)?.key
    ?? groups.value[0]?.key
    ?? ''
}

async function load() {
  if (!Number.isInteger(props.semesterId) || props.semesterId <= 0) return
  loading.value = true
  loadError.value = null
  try {
    setDraft(await getPeriodSetup(props.semesterId))
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取作息分组，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.semesterId, () => void load())

function regularCapacity(group: EditableGroup): number {
  return group.rows.reduce((total, row) => total + group.weekdays.filter((weekday) => row.cells[weekday] === 'regular').length, 0)
}

function configuredCells(group: EditableGroup): number {
  return group.rows.length * group.weekdays.length
}

function addGroup() {
  if (!props.canEdit) return
  const index = groups.value.length + 1
  const key = `new-${Date.now()}-${index}`
  const weekdays = weekdayRange(5)
  groups.value.push({
    key,
    table_id: null,
    name: `作息分组 ${index}`,
    num_weekdays: 5,
    weekdays,
    morning_count: 4,
    afternoon_count: 3,
    evening_count: 0,
    is_default: groups.value.length === 0,
    class_ids: [],
    rows: rowsForCounts(weekdays, 4, 3, 0),
  })
  activeGroupKey.value = key
}

function removeGroup(key: string) {
  if (!props.canEdit || groups.value.length <= 1) return
  const removedIndex = groups.value.findIndex((group) => group.key === key)
  const wasDefault = groups.value[removedIndex]?.is_default
  groups.value = groups.value.filter((group) => group.key !== key)
  if (wasDefault && groups.value[0]) groups.value[0].is_default = true
  if (activeGroupKey.value === key) activeGroupKey.value = groups.value[Math.max(0, removedIndex - 1)]?.key ?? groups.value[0]?.key ?? ''
}

function setDefault(key: string) {
  if (!props.canEdit) return
  for (const group of groups.value) group.is_default = group.key === key
}

function toggleClass(group: EditableGroup, classId: number, checked: boolean) {
  toggleClassRange(group, [classId], checked)
}

function toggleClassRange(group: EditableGroup, classIds: number[], checked: boolean) {
  if (!props.canEdit) return
  const ids = new Set(classIds)
  for (const item of groups.value) item.class_ids = item.class_ids.filter((id) => !ids.has(id))
  if (checked) group.class_ids.push(...classIds.filter((id) => !group.class_ids.includes(id)))
}

function rangeChecked(group: EditableGroup, classIds: number[]): boolean {
  return classIds.length > 0 && classIds.every((id) => group.class_ids.includes(id))
}

function rangeIndeterminate(group: EditableGroup, classIds: number[]): boolean {
  const selected = classIds.filter((id) => group.class_ids.includes(id)).length
  return selected > 0 && selected < classIds.length
}

function toggleWeekday(group: EditableGroup, weekday: number, checked: boolean) {
  if (!props.canEdit) return
  const selected = new Set(group.weekdays)
  if (checked) selected.add(weekday)
  else if (selected.size <= 5) {
    message.warning('至少保留五个上课日；如需调整请先勾选其他日期')
    return
  } else selected.delete(weekday)
  setWeekdays(group, [...selected])
}

function setWeekdays(group: EditableGroup, nextWeekdays: number[]) {
  const weekdays = normalizeWeekdays(nextWeekdays, Math.max(5, ...nextWeekdays, 5))
  group.weekdays = weekdays
  group.num_weekdays = Math.max(5, ...weekdays)
  for (const row of group.rows) {
    for (const day of Object.keys(row.cells).map(Number)) if (!weekdays.includes(day)) delete row.cells[day]
    for (const day of weekdays) row.cells[day] ??= row.section === 'break' ? 'lunch' : 'regular'
  }
}

function setDailyCount(group: EditableGroup, section: 'morning' | 'afternoon' | 'evening', value: number | null) {
  if (!props.canEdit) return
  const count = Math.max(0, Math.min(10, Math.trunc(value ?? 0)))
  if (section === 'morning') group.morning_count = count
  else if (section === 'afternoon') group.afternoon_count = count
  else group.evening_count = count
  group.rows = rowsForCounts(group.weekdays, group.morning_count, group.afternoon_count, group.evening_count, group.rows)
}

function addRow(group: EditableGroup) {
  if (!props.canEdit) return
  const next = group.rows.length ? Math.max(...group.rows.map((row) => row.period_no)) + 1 : 1
  group.rows.push(emptyRow(next, `第 ${next} 节`, 'afternoon', group.weekdays, 'regular', group.afternoon_count))
  group.afternoon_count += 1
}

function removeRow(group: EditableGroup, periodNumber: number) {
  if (!props.canEdit) return
  const row = group.rows.find((candidate) => candidate.period_no === periodNumber)
  group.rows = group.rows.filter((candidate) => candidate.period_no !== periodNumber)
  if (row?.section === 'morning') group.morning_count = Math.max(0, group.morning_count - 1)
  if (row?.section === 'afternoon') group.afternoon_count = Math.max(0, group.afternoon_count - 1)
  if (row?.section === 'evening') group.evening_count = Math.max(0, group.evening_count - 1)
}

function applyRowType(row: PeriodRow, group: EditableGroup, type: PeriodType) {
  if (!props.canEdit) return
  for (const weekday of group.weekdays) row.cells[weekday] = type
  if (type === 'lunch') row.section = 'break'
}

function patternsFromRows(group: EditableGroup): PeriodSetupPattern[] {
  const grouped = new Map<string, PeriodSetupPattern>()
  for (const row of group.rows) {
    for (const weekday of group.weekdays) {
      const type = row.cells[weekday] ?? (row.section === 'break' ? 'lunch' : 'regular')
      const key = [row.period_no, row.name.trim(), row.start_time ?? '', row.end_time ?? '', type].join('|')
      const pattern = grouped.get(key) ?? {
        period_no: row.period_no,
        weekdays: [],
        name: row.name.trim(),
        type,
        start_time: row.start_time?.trim() || null,
        end_time: row.end_time?.trim() || null,
      }
      pattern.weekdays.push(weekday)
      grouped.set(key, pattern)
    }
  }
  return [...grouped.values()].sort((left, right) => left.period_no - right.period_no || left.weekdays[0] - right.weekdays[0])
}

function normalizeTime(value: string | null): NormalizedTime | null {
  const input = value?.trim().replaceAll('：', ':') ?? ''
  if (!input) return { value: null, seconds: null }
  const match = /^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$/.exec(input)
  if (!match) return null
  const hour = Number(match[1])
  const minute = Number(match[2])
  const second = match[3] === undefined ? 0 : Number(match[3])
  if (hour > 23 || minute > 59 || second > 59) return null
  const normalized = `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
  return {
    value: match[3] === undefined ? normalized : `${normalized}:${String(second).padStart(2, '0')}`,
    seconds: hour * 3600 + minute * 60 + second,
  }
}

function normalizeRows(): boolean {
  for (const group of groups.value) {
    for (const row of group.rows) {
      if (!row.name.trim()) {
        message.warning(`${group.name || '当前作息'}存在未命名节次，请先填写节次名称`)
        return false
      }
      const start = normalizeTime(row.start_time)
      const end = normalizeTime(row.end_time)
      if (!start) {
        message.warning(`${group.name || '当前作息'}的${row.name || '节次'}开始时间格式不正确，请使用 24 小时制，例如 08:00`)
        return false
      }
      if (!end) {
        message.warning(`${group.name || '当前作息'}的${row.name || '节次'}结束时间格式不正确，请使用 24 小时制，例如 08:40`)
        return false
      }
      if ((start.value === null) !== (end.value === null)) {
        message.warning(`${group.name || '当前作息'}的${row.name || '节次'}需要同时填写开始和结束时间`)
        return false
      }
      if (start.seconds !== null && end.seconds !== null && end.seconds <= start.seconds) {
        message.warning(`${group.name || '当前作息'}的${row.name || '节次'}结束时间必须晚于开始时间`)
        return false
      }
      row.start_time = start.value
      row.end_time = end.value
    }
  }
  return true
}

function serializeGroups(): PeriodSetupGroup[] {
  return groups.value.map((group) => ({
    key: group.key,
    table_id: group.table_id,
    name: group.name.trim(),
    num_weekdays: group.num_weekdays,
    is_default: group.is_default,
    class_ids: [...group.class_ids],
    periods: patternsFromRows(group),
  }))
}

async function save() {
  if (!props.canEdit || saving.value || !draft.value) return
  if (localBlockers.value.length) {
    message.warning(localBlockers.value[0])
    return
  }
  if (groups.value.some((group) => !group.name.trim())) {
    message.warning('请填写每个作息分组的名称')
    return
  }
  if (!normalizeRows()) return
  saving.value = true
  try {
    setDraft(await applyPeriodSetup(props.semesterId, draft.value.fingerprint, serializeGroups()))
    message.success('课时设置已保存')
    emit('changed')
  } catch (error) {
    message.error(apiErrorMessage(error, '暂时无法保存课时设置，请刷新后重试。'))
  } finally {
    saving.value = false
  }
}

const assignmentPeriodsByClass = computed(() => {
  const usage = new Map<number, number>()
  const units = new Map<number, { type: 'single' | 'group'; classIds: number[]; total: number; max: number }>()
  for (const assignment of props.assignments) {
    const unit = assignment.scheduling_unit
    const entry = units.get(unit.id) ?? { type: unit.unit_type, classIds: unit.classes.map((item) => item.id), total: 0, max: 0 }
    entry.total += assignment.periods_per_week
    entry.max = Math.max(entry.max, assignment.periods_per_week)
    units.set(unit.id, entry)
  }
  for (const entry of units.values()) {
    const periods = entry.type === 'group' ? entry.max : entry.total
    for (const classId of entry.classIds) usage.set(classId, (usage.get(classId) ?? 0) + periods)
  }
  return usage
})

const capacityRows = computed(() => (draft.value?.classes ?? []).map((item) => {
  const group = groups.value.find((candidate) => candidate.class_ids.includes(item.id))
  const assigned = assignmentPeriodsByClass.value.get(item.id) ?? props.classLoads.find((load) => load.class_id === item.id)?.assigned ?? 0
  const capacity = group ? regularCapacity(group) : 0
  return { item, group, assigned, capacity, over: assigned > capacity }
}))
const capacityIssues = computed(() => capacityRows.value.filter((row) => row.over))
const allClassIds = computed(() => (draft.value?.classes ?? []).map((item) => item.id))
const allClassesChecked = computed(() => !!activeGroup.value && rangeChecked(activeGroup.value, allClassIds.value))
const allClassesIndeterminate = computed(() => !!activeGroup.value && rangeIndeterminate(activeGroup.value, allClassIds.value))

async function refresh() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await load()
    message.info('作息设置已刷新')
  } finally {
    refreshing.value = false
  }
}

</script>

<template>
  <section class="period-setup-workspace" data-testid="period-setup-workspace">
    <section v-if="loading" class="period-setup-state" data-testid="period-setup-loading" role="status">
      <n-spin size="small" />
      <strong>正在读取作息分组</strong>
    </section>
    <section v-else-if="loadError" class="period-setup-state period-setup-state-error" data-testid="period-setup-error" role="alert">
      <AlertTriangle :size="20" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <n-button type="primary" data-testid="period-setup-retry" @click="load">重新读取</n-button>
    </section>
    <template v-else-if="draft">
      <header class="period-setup-header">
        <div>
          <p class="scheduling-eyebrow">设置课时</p>
          <h2>按水晶排课布局设置上课日与节次</h2>
          <p>左侧选择班级范围、上课日和每天节数；右侧即时展示对应节次，可继续逐格调整用途和时间。</p>
        </div>
        <div class="period-setup-header-actions">
          <n-button quaternary :loading="refreshing" data-testid="period-setup-refresh" @click="refresh">
            <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
            刷新
          </n-button>
          <n-button type="primary" :loading="saving" :disabled="!canEdit || saving" data-testid="period-setup-save" @click="save">
            <template #icon><Save :size="15" aria-hidden="true" /></template>
            保存设置课时
          </n-button>
        </div>
      </header>

      <n-alert v-if="draft.source === 'suggested'" type="info" data-testid="period-setup-suggested">
        这是根据班级学段生成的建议草稿；保存后才会创建作息时间表并用于排课。
      </n-alert>
      <n-alert v-if="!canEdit" type="info" data-testid="period-setup-readonly">
        当前角色只能查看课时设置，历史学期不能保存修改。
      </n-alert>

      <div class="period-group-switcher" aria-label="作息分组">
        <div class="period-group-switcher-heading">
          <span class="period-section-label">作息分组</span>
          <strong>{{ groups.length }} 组</strong>
        </div>
        <div class="period-group-switcher-items">
          <button
            v-for="group in groups"
            :key="group.key"
            class="period-group-item"
            :class="{ 'is-active': activeGroup?.key === group.key }"
            type="button"
            :data-testid="`period-group-${group.key}`"
            @click="activeGroupKey = group.key"
          >
            <span class="period-group-item-main">
              <strong>{{ group.name || '未命名作息' }}</strong>
              <small>{{ group.class_ids.length }} 个班级 · {{ regularCapacity(group) }} 节/周</small>
            </span>
            <NTag v-if="group.is_default" size="small" type="success">默认</NTag>
          </button>
          <n-empty v-if="!groups.length" description="尚未建立作息分组" size="small" />
        </div>
        <n-button text :disabled="!canEdit" data-testid="period-group-add" aria-label="新增作息分组" title="新增作息分组" @click="addGroup">
          <template #icon><Plus :size="17" aria-hidden="true" /></template>
          新增分组
        </n-button>
      </div>

      <div v-if="activeGroup" class="period-setup-layout">
        <aside class="period-control-panel" aria-label="课时设置控制面板">
          <section class="period-control-section period-control-group-meta">
            <div class="period-control-heading">
              <div>
                <span class="period-section-label">当前分组</span>
                <strong>{{ activeGroup.name || '未命名作息' }}</strong>
              </div>
              <NTag v-if="activeGroup.is_default" type="success" size="small">学期默认</NTag>
            </div>
            <n-input v-model:value="activeGroup.name" :disabled="!canEdit" data-testid="period-group-name" aria-label="作息分组名称" placeholder="作息分组名称" />
            <div class="period-control-actions">
              <n-button v-if="!activeGroup.is_default" dashed size="small" :disabled="!canEdit" data-testid="period-group-set-default" @click="setDefault(activeGroup.key)">设为学期默认</n-button>
              <n-button v-if="activeGroup.table_id" text size="small" :disabled="!canEdit" data-testid="period-group-open-detail" @click="emit('editPeriodTable', activeGroup.table_id)">独立宽表</n-button>
              <n-popconfirm v-if="groups.length > 1" :disabled="!canEdit" @positive-click="removeGroup(activeGroup.key)">
                <template #trigger>
                  <n-button text type="error" size="small" :disabled="!canEdit" data-testid="period-group-delete" aria-label="删除当前作息分组" title="删除当前作息分组">
                    <template #icon><Trash2 :size="15" aria-hidden="true" /></template>
                    删除
                  </n-button>
                </template>
                保存后将移除这套作息时间表，确定继续吗？
              </n-popconfirm>
            </div>
          </section>

          <section class="period-control-section period-class-range" data-testid="period-class-range">
            <div class="period-control-heading">
              <div>
                <span class="period-section-label">班级范围</span>
                <strong>选择使用这套作息的班级</strong>
              </div>
              <span class="period-control-count">{{ activeGroup.class_ids.length }} / {{ draft.classes.length }}</span>
            </div>
            <n-checkbox
              :checked="allClassesChecked"
              :indeterminate="allClassesIndeterminate"
              :disabled="!canEdit || !allClassIds.length"
              data-testid="period-class-all"
              @update:checked="toggleClassRange(activeGroup, allClassIds, $event)"
            >
              全校（全部班级）
            </n-checkbox>
            <div class="period-grade-list">
              <div v-for="grade in gradeGroups" :key="grade.grade" class="period-grade-group">
                <n-checkbox
                  :checked="rangeChecked(activeGroup, grade.classes.map((item) => item.id))"
                  :indeterminate="rangeIndeterminate(activeGroup, grade.classes.map((item) => item.id))"
                  :disabled="!canEdit"
                  :data-testid="`period-grade-${grade.grade}`"
                  @update:checked="toggleClassRange(activeGroup, grade.classes.map((item) => item.id), $event)"
                >
                  {{ grade.grade }} 年级（{{ grade.classes.length }} 个班）
                </n-checkbox>
                <div class="period-class-options">
                  <n-checkbox
                    v-for="item in grade.classes"
                    :key="item.id"
                    :checked="activeGroup.class_ids.includes(item.id)"
                    :data-testid="`period-class-${item.id}`"
                    :disabled="!canEdit"
                    @update:checked="toggleClass(activeGroup, item.id, $event)"
                  >
                    <span>{{ item.name }}</span>
                    <small>{{ item.track_label }}</small>
                  </n-checkbox>
                </div>
              </div>
            </div>
          </section>

          <section class="period-control-section period-weekday-section" data-testid="period-group-weekdays">
            <div class="period-control-heading">
              <div>
                <span class="period-section-label">上课天数</span>
                <strong>选择每周上课日</strong>
              </div>
              <span class="period-control-count">{{ activeGroup.weekdays.length }} 天</span>
            </div>
            <div class="period-weekday-options" data-testid="period-weekdays">
              <n-checkbox
                v-for="(name, index) in WEEKDAY_NAMES"
                :key="name"
                :checked="activeGroup.weekdays.includes(index + 1)"
                :disabled="!canEdit"
                :data-testid="`period-weekday-${index + 1}`"
                @update:checked="toggleWeekday(activeGroup, index + 1, $event)"
              >
                周{{ name }}
              </n-checkbox>
            </div>
            <small class="period-control-hint">至少选择五天；周日可单独作为第七个上课日。</small>
          </section>

          <section class="period-control-section period-daily-count-section" data-testid="period-daily-counts">
            <div class="period-control-heading">
              <div>
                <span class="period-section-label">每天节数</span>
                <strong>调整后右侧立即渲染</strong>
              </div>
            </div>
            <div class="period-count-controls">
              <label class="period-count-field">
                <span>上午节数</span>
                <n-input-number :value="activeGroup.morning_count" :min="0" :max="10" :disabled="!canEdit" data-testid="period-template-morning" @update:value="setDailyCount(activeGroup, 'morning', $event)" />
              </label>
              <label class="period-count-field">
                <span>下午节数</span>
                <n-input-number :value="activeGroup.afternoon_count" :min="0" :max="10" :disabled="!canEdit" data-testid="period-template-afternoon" @update:value="setDailyCount(activeGroup, 'afternoon', $event)" />
              </label>
              <label class="period-count-field">
                <span>晚上节数</span>
                <n-input-number :value="activeGroup.evening_count" :min="0" :max="10" :disabled="!canEdit" data-testid="period-template-evening" @update:value="setDailyCount(activeGroup, 'evening', $event)" />
              </label>
            </div>
            <small class="period-control-hint">午休会在上午与下午（或晚上）之间自动加入，可在右侧逐格修改。</small>
          </section>
        </aside>

        <section class="period-group-editor" data-testid="period-group-editor">
          <div class="period-preview" data-testid="period-preview">
            <header class="period-preview-heading">
              <div>
                <span class="period-section-label">节次预览</span>
                <h3>{{ activeGroup.name || '未命名作息' }}</h3>
                <p>周{{ activeGroup.weekdays.map((day) => WEEKDAY_NAMES[day - 1]).join('、周') }} · {{ configuredCells(activeGroup) }} 格 · 常规容量 {{ regularCapacity(activeGroup) }} 节/周</p>
              </div>
              <Clock3 :size="20" aria-hidden="true" />
            </header>

            <div class="period-grid-scroll" data-testid="period-setup-grid-scroll" tabindex="0" aria-label="作息节次编辑表，可横向滚动">
              <table class="period-setup-grid">
                <thead>
                  <tr>
                    <th class="period-grid-details">节次 / 时间</th>
                    <th v-for="day in activeWeekdays" :key="day">周{{ WEEKDAY_NAMES[day - 1] }}</th>
                    <th class="period-grid-actions">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!activeGroup.rows.length"><td :colspan="activeWeekdays.length + 2"><n-empty description="尚未添加节次" size="small" /></td></tr>
                  <tr v-for="row in activeGroup.rows" v-else :key="row.period_no">
                    <td class="period-grid-details">
                      <div class="period-row-details">
                        <div class="period-row-heading">
                          <n-tag size="small" :type="row.section === 'break' ? 'default' : row.section === 'evening' ? 'warning' : 'info'">{{ sectionLabels[row.section] }}</n-tag>
                          <span>第 {{ row.period_no }} 行</span>
                        </div>
                        <n-input v-model:value="row.name" size="small" :disabled="!canEdit" :aria-label="`${row.period_no}节名称`" placeholder="节次名称" />
                        <div class="period-time-range">
                          <n-input v-model:value="row.start_time" size="small" :disabled="!canEdit" placeholder="08:00" :aria-label="`${row.name}开始时间`" />
                          <span>-</span>
                          <n-input v-model:value="row.end_time" size="small" :disabled="!canEdit" placeholder="08:40" :aria-label="`${row.name}结束时间`" />
                        </div>
                        <div class="period-row-presets">
                          <n-button text size="tiny" :disabled="!canEdit" @click="applyRowType(row, activeGroup, 'regular')">整行常规课</n-button>
                          <n-button text size="tiny" :disabled="!canEdit" @click="applyRowType(row, activeGroup, 'reserved')">整行固定用途</n-button>
                        </div>
                      </div>
                    </td>
                    <td v-for="day in activeWeekdays" :key="day" class="period-grid-cell">
                      <n-popselect v-model:value="row.cells[day]" :options="typeOptions" trigger="click" :disabled="!canEdit">
                        <n-button block size="small" class="period-type-cell" :class="`period-type-${row.cells[day] || 'regular'}`" :disabled="!canEdit" :aria-label="`${row.name}，周${WEEKDAY_NAMES[day - 1]}，${typeLabels[row.cells[day] || 'regular']}`">
                          {{ typeLabels[row.cells[day] || 'regular'] }}
                        </n-button>
                      </n-popselect>
                    </td>
                    <td class="period-grid-actions">
                      <n-popconfirm :disabled="!canEdit" @positive-click="removeRow(activeGroup, row.period_no)">
                        <template #trigger>
                          <n-button text type="error" :disabled="!canEdit" :aria-label="`删除${row.name}`" title="删除节次">
                            <template #icon><Trash2 :size="15" aria-hidden="true" /></template>
                          </n-button>
                        </template>
                        确定删除这一行吗？保存后才会写入系统。
                      </n-popconfirm>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="period-grid-footer">
              <n-button dashed :disabled="!canEdit" data-testid="period-setup-add-row" @click="addRow(activeGroup)">
                <template #icon><Plus :size="15" aria-hidden="true" /></template>
                新增节次行
              </n-button>
              <span>早自习、午休、班会和固定用途可逐格设置为非任课时段。</span>
            </div>
          </div>

          <section class="period-capacity-preview" data-testid="period-capacity-preview">
            <div class="period-subsection-heading">
              <div><span class="period-section-label">排课容量预览</span><strong>课程总量与常规课节次</strong></div>
              <Clock3 :size="18" aria-hidden="true" />
            </div>
            <div v-if="!capacityRows.length" class="period-capacity-empty">暂无班级，保存作息后会在这里显示每个班级的容量。</div>
            <div v-else class="period-capacity-list">
              <div v-for="row in capacityRows" :key="row.item.id" class="period-capacity-row">
                <div><strong>{{ row.item.name }}</strong><small>{{ row.group?.name ?? '未分配作息' }}</small></div>
                <span>{{ row.assigned }} / {{ row.capacity }} 节</span>
                <n-tag size="small" :type="row.over ? 'error' : 'success'">{{ row.over ? `超出 ${row.assigned - row.capacity} 节` : '容量足够' }}</n-tag>
              </div>
            </div>
            <n-alert v-if="capacityIssues.length" type="error" data-testid="period-capacity-warning"><template #icon><AlertTriangle :size="17" aria-hidden="true" /></template>有 {{ capacityIssues.length }} 个班级的课程总量超过常规课容量。可以先保存作息草稿，但“科目节数”和后续排课会保持阻塞，请增加常规节次或减少课程节数。</n-alert>
            <n-alert v-else-if="!localBlockers.length" type="success" data-testid="period-capacity-ready"><template #icon><CheckCircle2 :size="17" aria-hidden="true" /></template>当前作息分组和课程总量具备进入下一步的容量。</n-alert>
          </section>
        </section>
      </div>

      <n-alert v-if="localBlockers.length" type="warning" data-testid="period-setup-blockers">{{ localBlockers[0] }}，完成后才能保存设置课时。</n-alert>
      <div v-if="draft.warnings.length" class="period-setup-warnings"><n-alert v-for="warning in draft.warnings" :key="warning" type="warning">{{ warning }}</n-alert></div>
    </template>
  </section>
</template>

<style scoped src="./period-setup-workspace.css"></style>
