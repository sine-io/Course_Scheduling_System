<script setup lang="ts">
import {
  Check, CopyPlus, Merge, Plus, RefreshCw, Save, Trash2,
} from '@lucide/vue'
import {
  NAlert, NButton, NCheckbox, NEmpty, NInput, NInputNumber, NRadioButton,
  NRadioGroup, NSelect, NSpin, NTag, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref, watch } from 'vue'
import { apiErrorMessage } from '@/api/client'
import {
  applyPeriodSetup,
  getPeriodSetup,
  PERIOD_TYPE_LABELS,
} from '@/api/semesters'
import type {
  PeriodSetupDraft,
  PeriodSetupGroup,
  PeriodSetupPattern,
  PeriodType,
} from '@/api/semesters'

const props = withDefaults(
  defineProps<{ semesterId: number, canEdit?: boolean }>(),
  { canEdit: true },
)
const emit = defineEmits<{ applied: [draft: PeriodSetupDraft] }>()
const message = useMessage()

const loading = ref(true)
const applying = ref(false)
const errorMessage = ref<string | null>(null)
const draft = ref<PeriodSetupDraft | null>(null)
const groups = ref<PeriodSetupGroup[]>([])
const mergeSelection = ref<string[]>([])
let nextDraftKey = 1

const weekdayLabels = ['周一', '周二', '周三', '周四', '周五', '周六']
const typeOptions = (Object.keys(PERIOD_TYPE_LABELS) as PeriodType[]).map((value) => ({
  value,
  label: PERIOD_TYPE_LABELS[value],
}))
const classOptions = computed(() => (draft.value?.classes ?? []).map((item) => ({
  value: item.id,
  label: `${item.name} · ${item.track_label}`,
})))
const selectedMergeGroups = computed(() => (
  groups.value.filter((group) => mergeSelection.value.includes(group.key))
))

function cloneGroups(value: PeriodSetupGroup[]): PeriodSetupGroup[] {
  return value.map((group) => ({
    ...group,
    class_ids: [...group.class_ids],
    periods: group.periods.map((period) => ({
      ...period,
      weekdays: [...period.weekdays],
    })),
  }))
}

async function load() {
  loading.value = true
  errorMessage.value = null
  try {
    const value = await getPeriodSetup(props.semesterId)
    draft.value = value
    groups.value = cloneGroups(value.groups)
    mergeSelection.value = []
  } catch (error) {
    errorMessage.value = apiErrorMessage(error, '无法读取作息分组，请稍后重试。')
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.semesterId, load)

function weekdays(group: PeriodSetupGroup) {
  return Array.from({ length: group.num_weekdays }, (_, index) => index + 1)
}

function weekdayOptions(group: PeriodSetupGroup) {
  return weekdays(group).map((value) => ({ value, label: weekdayLabels[value - 1] }))
}

function setNumWeekdays(group: PeriodSetupGroup, value: number) {
  const oldValue = group.num_weekdays
  group.num_weekdays = value
  for (const period of group.periods) {
    const coveredAllOldDays = period.weekdays.length === oldValue
      && period.weekdays.every((weekday) => weekday <= oldValue)
    period.weekdays = period.weekdays.filter((weekday) => weekday <= value)
    if (value > oldValue && coveredAllOldDays) {
      period.weekdays.push(...Array.from(
        { length: value - oldValue },
        (_, index) => oldValue + index + 1,
      ))
    }
  }
}

function setDefault(target: PeriodSetupGroup) {
  if (!props.canEdit) return
  for (const group of groups.value) group.is_default = group.key === target.key
}

function assignClasses(target: PeriodSetupGroup, classIds: number[]) {
  if (!props.canEdit) return
  const selected = new Set(classIds)
  for (const group of groups.value) {
    if (group.key !== target.key) {
      group.class_ids = group.class_ids.filter((classId) => !selected.has(classId))
    }
  }
  target.class_ids = [...classIds]
}

function newPattern(group: PeriodSetupGroup, periodNo?: number): PeriodSetupPattern {
  const nextNumber = periodNo ?? (
    group.periods.length ? Math.max(...group.periods.map((item) => item.period_no)) + 1 : 1
  )
  return {
    period_no: nextNumber,
    weekdays: weekdays(group),
    name: `第 ${nextNumber} 节`,
    type: 'regular',
    start_time: null,
    end_time: null,
  }
}

function splitGroup(source: PeriodSetupGroup) {
  if (!props.canEdit) return
  const key = `draft-${nextDraftKey}`
  nextDraftKey += 1
  groups.value.push({
    key,
    table_id: null,
    name: `${source.name}（新分组）`,
    num_weekdays: source.num_weekdays,
    is_default: false,
    class_ids: [],
    periods: source.periods.map((period) => ({
      ...period,
      weekdays: [...period.weekdays],
    })),
  })
}

function addGroup() {
  if (!props.canEdit) return
  const key = `draft-${nextDraftKey}`
  nextDraftKey += 1
  const group: PeriodSetupGroup = {
    key,
    table_id: null,
    name: `新作息分组 ${nextDraftKey - 1}`,
    num_weekdays: 5,
    is_default: groups.value.length === 0,
    class_ids: [],
    periods: [],
  }
  group.periods.push(newPattern(group))
  groups.value.push(group)
}

function toggleMerge(key: string, checked: boolean) {
  mergeSelection.value = checked
    ? [...mergeSelection.value, key]
    : mergeSelection.value.filter((item) => item !== key)
}

function mergeSelected() {
  if (!props.canEdit || selectedMergeGroups.value.length < 2) return
  const [target, ...sources] = selectedMergeGroups.value
  const mergedClassIds = new Set(target.class_ids)
  for (const source of sources) {
    for (const classId of source.class_ids) mergedClassIds.add(classId)
    if (source.is_default) target.is_default = true
  }
  target.class_ids = [...mergedClassIds]
  const removed = new Set(sources.map((group) => group.key))
  groups.value = groups.value.filter((group) => !removed.has(group.key))
  mergeSelection.value = []
}

function removeGroup(target: PeriodSetupGroup) {
  if (!props.canEdit || target.class_ids.length || groups.value.length <= 1) return
  groups.value = groups.value.filter((group) => group.key !== target.key)
}

function addPeriod(group: PeriodSetupGroup) {
  if (!props.canEdit) return
  group.periods.push(newPattern(group))
}

function removePeriod(group: PeriodSetupGroup, index: number) {
  if (!props.canEdit) return
  group.periods.splice(index, 1)
}

function previewRows(group: PeriodSetupGroup): number[] {
  return [...new Set(group.periods.map((period) => period.period_no))].sort((a, b) => a - b)
}

function previewCell(group: PeriodSetupGroup, periodNo: number, weekday: number) {
  return group.periods.find((period) => (
    period.period_no === periodNo && period.weekdays.includes(weekday)
  ))
}

function shortTime(value: string | null): string {
  return value?.slice(0, 5) ?? ''
}

const localBlockers = computed(() => {
  const blockers: string[] = []
  if (!groups.value.length) blockers.push('至少需要一个作息分组')
  if (groups.value.filter((group) => group.is_default).length !== 1) {
    blockers.push('必须且只能有一套学期默认作息')
  }
  const names = groups.value.map((group) => group.name.trim())
  if (names.some((name) => !name)) blockers.push('请填写每个分组的名称')
  if (new Set(names).size !== names.length) blockers.push('作息分组名称不可重复')
  const assigned = groups.value.flatMap((group) => group.class_ids)
  const expected = (draft.value?.classes ?? []).map((item) => item.id)
  const missing = expected.filter((classId) => !assigned.includes(classId))
  if (missing.length) {
    blockers.push(`还有 ${missing.length} 个班级未分配作息`)
  }
  if (new Set(assigned).size !== assigned.length) blockers.push('同一个班级被分配到多个分组')
  if (!groups.value.some((group) => group.periods.some((period) => period.type === 'regular'))) {
    blockers.push('至少需要一个常规课节次')
  }
  for (const group of groups.value) {
    if (group.class_ids.length && !group.periods.some((period) => period.type === 'regular')) {
      blockers.push(`「${group.name || '未命名分组'}」至少需要一个常规课节次`)
    }
    const cells = new Set<string>()
    for (const period of group.periods) {
      if (!period.name.trim()) blockers.push(`「${group.name || '未命名分组'}」有未命名节次`)
      if (!period.weekdays.length) blockers.push(`「${group.name || '未命名分组'}」有节次未选择工作日`)
      if ((period.start_time === null) !== (period.end_time === null)) {
        blockers.push(`「${group.name || '未命名分组'}」的开始和结束时间需要成对填写`)
      }
      for (const weekday of period.weekdays) {
        const cell = `${weekday}-${period.period_no}`
        if (cells.has(cell)) blockers.push(`「${group.name || '未命名分组'}」有重复节次格`)
        cells.add(cell)
      }
    }
  }
  return [...new Set(blockers)]
})

const localWarnings = computed(() => {
  if (groups.value.some((group) => group.periods.some((period) => (
    period.start_time === null || period.end_time === null
  )))) {
    return ['有节次尚未填写完整的开始和结束时间']
  }
  return []
})

async function apply() {
  if (!props.canEdit || applying.value || !draft.value) return
  errorMessage.value = null
  if (localBlockers.value.length) {
    errorMessage.value = localBlockers.value[0]
    return
  }
  applying.value = true
  try {
    const payload = cloneGroups(groups.value).map((group) => ({
      ...group,
      name: group.name.trim(),
      periods: group.periods.map((period) => ({ ...period, name: period.name.trim() })),
    }))
    const value = await applyPeriodSetup(props.semesterId, draft.value.fingerprint, payload)
    draft.value = value
    groups.value = cloneGroups(value.groups)
    mergeSelection.value = []
    message.success('作息分组已应用')
    emit('applied', value)
  } catch (error) {
    errorMessage.value = apiErrorMessage(error, '应用作息失败，请重新读取后重试。')
  } finally {
    applying.value = false
  }
}
</script>

<template>
  <section class="period-setup" data-testid="period-setup">
    <div v-if="loading" class="period-setup-state" role="status">
      <n-spin size="small" />
      <span>{{ '正在读取作息分组' }}</span>
    </div>
    <div v-else-if="!draft" class="period-setup-state">
      <n-alert type="error" :show-icon="true">{{ errorMessage }}</n-alert>
      <n-button data-testid="period-setup-retry" @click="load">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </div>
    <template v-else>
      <n-alert
        v-if="draft.source === 'suggested'"
        type="info"
        data-testid="period-setup-source"
      >
        {{ '以下分组根据班级学制生成，目前只是可编辑建议，尚未写入系统。' }}
      </n-alert>
      <n-alert v-else type="success" data-testid="period-setup-source">
        {{ '正在编辑当前学期已经应用的作息分组。' }}
      </n-alert>
      <n-alert v-if="!canEdit" type="info" data-testid="period-setup-readonly">
        {{ '当前角色只能查看作息分组和周视图。' }}
      </n-alert>
      <n-alert v-if="errorMessage" type="error" data-testid="period-setup-error" role="alert">
        {{ errorMessage }}
      </n-alert>

      <div v-if="canEdit" class="period-setup-toolbar">
        <n-button data-testid="period-add-group" @click="addGroup">
          <template #icon><Plus :size="15" aria-hidden="true" /></template>
          {{ '新增分组' }}
        </n-button>
        <n-button
          data-testid="period-merge"
          :disabled="selectedMergeGroups.length < 2"
          @click="mergeSelected"
        >
          <template #icon><Merge :size="15" aria-hidden="true" /></template>
          {{ `合并所选${selectedMergeGroups.length ? `（${selectedMergeGroups.length}）` : ''}` }}
        </n-button>
        <span v-if="selectedMergeGroups.length > 1" class="period-toolbar-note">
          {{ `将保留“${selectedMergeGroups[0].name}”的节次设置` }}
        </span>
      </div>

      <n-empty v-if="!groups.length" :description="'尚无作息分组'" />
      <section
        v-for="group in groups"
        :key="group.key"
        class="period-setup-group"
        data-period-group="true"
        :data-testid="`period-group-${group.key}`"
      >
        <header class="period-group-header">
          <div class="period-group-title">
            <n-checkbox
              v-if="canEdit"
              :checked="mergeSelection.includes(group.key)"
              :data-testid="`period-merge-select-${group.key}`"
              :aria-label="`选择合并${group.name}`"
              @update:checked="toggleMerge(group.key, $event)"
            />
            <n-input
              v-model:value="group.name"
              :data-testid="`period-group-name-${group.key}`"
              :aria-label="`${group.name}分组名称`"
              :disabled="!canEdit"
              maxlength="64"
            />
            <n-tag v-if="group.is_default" type="success" size="small">{{ '默认作息' }}</n-tag>
          </div>
          <div v-if="canEdit" class="period-group-actions">
            <n-button
              v-if="!group.is_default"
              size="small"
              @click="setDefault(group)"
            >
              <template #icon><Check :size="14" aria-hidden="true" /></template>
              {{ '设为默认' }}
            </n-button>
            <n-button
              size="small"
              :data-testid="`period-split-${group.key}`"
              @click="splitGroup(group)"
            >
              <template #icon><CopyPlus :size="14" aria-hidden="true" /></template>
              {{ '拆出新分组' }}
            </n-button>
            <n-button
              v-if="groups.length > 1"
              size="small"
              quaternary
              type="error"
              :disabled="group.class_ids.length > 0"
              :title="group.class_ids.length ? '先移动此组班级后才能删除' : '删除空分组'"
              :aria-label="`删除${group.name}`"
              @click="removeGroup(group)"
            >
              <template #icon><Trash2 :size="14" aria-hidden="true" /></template>
            </n-button>
          </div>
        </header>

        <div class="period-group-settings">
          <label>
            <span>{{ '每周上课日' }}</span>
            <n-radio-group
              :value="group.num_weekdays"
              size="small"
              :disabled="!canEdit"
              @update:value="setNumWeekdays(group, $event)"
            >
              <n-radio-button :value="5">{{ '周一至周五' }}</n-radio-button>
              <n-radio-button :value="6">{{ '周一至周六' }}</n-radio-button>
            </n-radio-group>
          </label>
          <label>
            <span>{{ '使用此作息的班级' }}</span>
            <n-select
              :value="group.class_ids"
              multiple
              filterable
              :options="classOptions"
              :disabled="!canEdit"
              :aria-label="`${group.name}的班级`"
              :placeholder="'选择班级'"
              @update:value="assignClasses(group, $event)"
            />
          </label>
        </div>

        <div class="period-pattern-heading">
          <h3>{{ '节次设置' }}</h3>
          <n-button v-if="canEdit" size="small" dashed @click="addPeriod(group)">
            <template #icon><Plus :size="14" aria-hidden="true" /></template>
            {{ '新增节次' }}
          </n-button>
        </div>
        <div class="period-pattern-scroll">
          <table class="period-pattern-table">
            <thead>
              <tr>
                <th>{{ '序号' }}</th>
                <th>{{ '名称' }}</th>
                <th>{{ '类型' }}</th>
                <th>{{ '工作日' }}</th>
                <th>{{ '开始' }}</th>
                <th>{{ '结束' }}</th>
                <th v-if="canEdit"><span class="sr-only">{{ '操作' }}</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!group.periods.length">
                <td :colspan="canEdit ? 7 : 6" class="period-table-empty">{{ '尚未添加节次' }}</td>
              </tr>
              <tr v-for="(period, index) in group.periods" :key="`${group.key}-${index}`">
                <td>
                  <n-input-number
                    v-model:value="period.period_no"
                    :min="1"
                    size="small"
                    :disabled="!canEdit"
                    :aria-label="`${group.name}第${index + 1}行序号`"
                  />
                </td>
                <td>
                  <n-input
                    v-model:value="period.name"
                    size="small"
                    :disabled="!canEdit"
                    :data-testid="`period-name-${group.key}-${index}`"
                    :aria-label="`${group.name}第${index + 1}行名称`"
                  />
                </td>
                <td>
                  <n-select
                    v-model:value="period.type"
                    size="small"
                    :options="typeOptions"
                    :disabled="!canEdit"
                    :aria-label="`${period.name}类型`"
                  />
                </td>
                <td>
                  <n-select
                    v-model:value="period.weekdays"
                    multiple
                    size="small"
                    :options="weekdayOptions(group)"
                    :disabled="!canEdit"
                    :aria-label="`${period.name}工作日`"
                  />
                </td>
                <td>
                  <n-input
                    v-model:value="period.start_time"
                    size="small"
                    :disabled="!canEdit"
                    placeholder="08:00"
                    :aria-label="`${period.name}开始时间`"
                  />
                </td>
                <td>
                  <n-input
                    v-model:value="period.end_time"
                    size="small"
                    :disabled="!canEdit"
                    placeholder="08:40"
                    :aria-label="`${period.name}结束时间`"
                  />
                </td>
                <td v-if="canEdit">
                  <n-button
                    quaternary
                    type="error"
                    size="small"
                    :data-testid="`period-remove-${group.key}-${index}`"
                    :aria-label="`删除${period.name}`"
                    :title="`删除${period.name}`"
                    @click="removePeriod(group, index)"
                  >
                    <template #icon><Trash2 :size="14" aria-hidden="true" /></template>
                  </n-button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="period-preview-heading">
          <h3>{{ '周视图预览' }}</h3>
          <span>{{ `${group.num_weekdays} 天 · ${group.periods.length} 条节次设置` }}</span>
        </div>
        <div class="period-week-scroll">
          <table class="period-week-table">
            <thead>
              <tr>
                <th>{{ '节次' }}</th>
                <th v-for="weekday in weekdays(group)" :key="weekday">
                  {{ weekdayLabels[weekday - 1] }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!previewRows(group).length">
                <td :colspan="group.num_weekdays + 1" class="period-table-empty">{{ '暂无预览' }}</td>
              </tr>
              <tr v-for="periodNo in previewRows(group)" :key="periodNo">
                <th>{{ periodNo }}</th>
                <td
                  v-for="weekday in weekdays(group)"
                  :key="weekday"
                  :data-testid="`period-preview-${group.key}-${weekday}-${periodNo}`"
                >
                  <template v-if="previewCell(group, periodNo, weekday)">
                    <span
                      class="period-preview-cell"
                      :data-type="previewCell(group, periodNo, weekday)?.type"
                    >
                      <strong>{{ previewCell(group, periodNo, weekday)?.name }}</strong>
                      <small>{{ PERIOD_TYPE_LABELS[previewCell(group, periodNo, weekday)?.type as PeriodType] }}</small>
                      <small v-if="previewCell(group, periodNo, weekday)?.start_time">
                        {{ `${shortTime(previewCell(group, periodNo, weekday)?.start_time ?? null)}-${shortTime(previewCell(group, periodNo, weekday)?.end_time ?? null)}` }}
                      </small>
                    </span>
                  </template>
                  <span v-else class="period-preview-none">{{ '—' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div class="period-setup-review">
        <n-alert v-if="localBlockers.length" type="error" :title="'应用前需要处理'">
          <ul><li v-for="item in localBlockers" :key="item">{{ item }}</li></ul>
        </n-alert>
        <n-alert v-else-if="localWarnings.length" type="warning" :title="'可以应用，仍有提醒'">
          <ul><li v-for="item in localWarnings" :key="item">{{ item }}</li></ul>
        </n-alert>
        <n-alert v-else type="success">{{ '分组和节次配置完整，可以应用。' }}</n-alert>
        <n-button
          v-if="canEdit"
          type="primary"
          data-testid="period-setup-apply"
          :loading="applying"
          :disabled="applying || localBlockers.length > 0"
          @click="apply"
        >
          <template #icon><Save :size="15" aria-hidden="true" /></template>
          {{ '应用全部作息分组' }}
        </n-button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.period-setup { display: grid; min-width: 0; gap: 18px; }
.period-setup-state { display: grid; min-height: 180px; place-items: center; align-content: center; gap: 10px; }
.period-setup-toolbar,
.period-group-header,
.period-group-title,
.period-group-actions,
.period-pattern-heading,
.period-preview-heading,
.period-setup-review {
  display: flex;
  min-width: 0;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}
.period-setup-toolbar { padding: 2px 0; }
.period-toolbar-note { color: var(--app-text-faint); font-size: 12px; }
.period-setup-group { min-width: 0; padding: 22px 0 4px; border-top: 1px solid var(--app-border); }
.period-group-header { justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.period-group-title { flex: 1 1 360px; }
.period-group-title :deep(.n-input) { width: min(300px, 100%); font-weight: 650; }
.period-group-actions { justify-content: flex-end; }
.period-group-settings { display: grid; grid-template-columns: minmax(220px, .8fr) minmax(280px, 1.2fr); gap: 14px; margin-bottom: 20px; }
.period-group-settings label { display: grid; min-width: 0; gap: 7px; }
.period-group-settings label > span { color: var(--app-text-muted); font-size: 12px; font-weight: 650; }
.period-pattern-heading,
.period-preview-heading { justify-content: space-between; margin: 14px 0 8px; }
.period-pattern-heading h3,
.period-preview-heading h3 { margin: 0; font-size: 14px; }
.period-preview-heading span { color: var(--app-text-faint); font-size: 12px; }
.period-pattern-scroll,
.period-week-scroll { width: 100%; min-width: 0; overflow-x: auto; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); }
.period-pattern-table,
.period-week-table { width: 100%; min-width: 820px; border-collapse: collapse; table-layout: fixed; }
.period-pattern-table { min-width: 980px; }
.period-pattern-table th,
.period-pattern-table td,
.period-week-table th,
.period-week-table td { padding: 8px; border-right: 1px solid var(--app-border); border-bottom: 1px solid var(--app-border); text-align: left; vertical-align: middle; }
.period-pattern-table th:last-child,
.period-pattern-table td:last-child,
.period-week-table th:last-child,
.period-week-table td:last-child { border-right: 0; }
.period-pattern-table tbody tr:last-child td,
.period-week-table tbody tr:last-child td,
.period-week-table tbody tr:last-child th { border-bottom: 0; }
.period-pattern-table thead th,
.period-week-table thead th { background: var(--app-surface-muted); color: var(--app-text-muted); font-size: 11px; font-weight: 650; }
.period-pattern-table th:nth-child(1) { width: 82px; }
.period-pattern-table th:nth-child(2) { width: 150px; }
.period-pattern-table th:nth-child(3) { width: 125px; }
.period-pattern-table th:nth-child(4) { width: 220px; }
.period-pattern-table th:nth-child(5),
.period-pattern-table th:nth-child(6) { width: 105px; }
.period-pattern-table th:nth-child(7) { width: 52px; }
.period-week-table th,
.period-week-table td { text-align: center; }
.period-week-table tbody th { width: 54px; background: var(--app-surface-muted); color: var(--app-text-muted); }
.period-preview-cell { display: grid; min-height: 62px; align-content: center; gap: 3px; padding: 7px; border-radius: var(--app-radius-xs); background: var(--app-surface-muted); }
.period-preview-cell strong { font-size: 12px; }
.period-preview-cell small { color: var(--app-text-muted); font-size: 10px; }
.period-preview-cell[data-type='regular'] { background: var(--app-success-soft); }
.period-preview-cell[data-type='morning'] { background: var(--app-primary-soft); }
.period-preview-cell[data-type='lunch'] { background: var(--app-surface-pressed); }
.period-preview-cell[data-type='homeroom'] { background: var(--app-warning-soft); }
.period-preview-cell[data-type='reserved'] { background: var(--app-danger-soft); }
.period-preview-none,
.period-table-empty { color: var(--app-text-faint); font-size: 12px; text-align: center !important; }
.period-setup-review { align-items: flex-start; justify-content: space-between; padding-top: 4px; }
.period-setup-review :deep(.n-alert) { flex: 1 1 520px; }
.period-setup-review ul { margin: 4px 0; padding-left: 18px; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
@media (max-width: 720px) {
  .period-group-settings { grid-template-columns: 1fr; }
  .period-group-header { flex-direction: column; }
  .period-group-actions { justify-content: flex-start; }
}
</style>
