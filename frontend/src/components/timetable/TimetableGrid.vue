<script setup lang="ts">
import { Check, LockKeyhole, MoveHorizontal, Plus, Trash2 } from '@lucide/vue'
import { computed } from 'vue'
import type { DragData, DropFeedback, GridEntry, PeriodCell } from './types'

const props = withDefaults(defineProps<{
  periods: PeriodCell[]
  entries?: GridEntry[]
  numWeekdays?: number
  readonly?: boolean
  dragging?: DragData | null // 父层告知目前拖拽中的内容(供 check feedback)
  feedback?: DropFeedback | null // 父层回填的可放/冲突判定
  placementLabel?: string // 键盘排入模式下用于构造单元格操作名称
}>(), {
  entries: () => [],
  numWeekdays: undefined,
  readonly: false,
  dragging: null,
  feedback: null,
  placementLabel: '所选课程',
})

const emit = defineEmits<{
  dragstart: [data: DragData]
  dragend: []
  check: [payload: { weekday: number; period_no: number; data: DragData | null }]
  drop: [payload: { weekday: number; period_no: number; data: DragData | null }]
  activate: [payload: { weekday: number; period_no: number; data: DragData | null }]
  select: [entry: GridEntry]
  move: [entry: GridEntry]
  remove: [entry: GridEntry]
}>()

const WEEKDAY_LABELS = ['一', '二', '三', '四', '五', '六', '日']

const weekdays = computed(() => {
  const max = props.numWeekdays ?? Math.max(5, ...props.periods.map((p) => p.weekday))
  return Array.from({ length: max }, (_, i) => i + 1)
})
const periodNos = computed(() =>
  [...new Set(props.periods.map((p) => p.period_no))].sort((a, b) => a - b))

const periodMap = computed(() => {
  const m = new Map<string, PeriodCell>()
  for (const p of props.periods) m.set(`${p.weekday}-${p.period_no}`, p)
  return m
})
// 各节次的代表信息(取任一天),用于左栏的节次名称与时间
const periodInfo = computed(() => {
  const m = new Map<number, PeriodCell>()
  for (const p of props.periods) if (!m.has(p.period_no)) m.set(p.period_no, p)
  return m
})
const entryMap = computed(() => {
  const m = new Map<string, GridEntry>()
  for (const e of props.entries) m.set(`${e.weekday}-${e.period_no}`, e)
  return m
})
// 连堂占用的下方单元格(跳过不渲染)
const coveredSet = computed(() => {
  const s = new Set<string>()
  const nos = periodNos.value
  for (const e of props.entries) {
    const span = e.span ?? 1
    if (span <= 1) continue
    const idx = nos.indexOf(e.period_no)
    for (let k = 1; k < span; k++) {
      const pp = nos[idx + k]
      if (pp !== undefined) s.add(`${e.weekday}-${pp}`)
    }
  }
  return s
})

function fmt(t?: string | null): string {
  return t ? t.slice(0, 5) : ''
}
function weekdayLabel(w: number): string {
  return `星期${WEEKDAY_LABELS[w - 1] ?? w}`
}
function periodLabelName(p: number): string {
  return periodInfo.value.get(p)?.name ?? `第${p}节`
}
function periodTime(p: number): string {
  const info = periodInfo.value.get(p)
  if (!info?.start_time) return ''
  return `${fmt(info.start_time)}-${fmt(info.end_time)}`
}
function key(w: number, p: number): string {
  return `${w}-${p}`
}
function periodAt(w: number, p: number): PeriodCell | undefined {
  return periodMap.value.get(key(w, p))
}
function entryAt(w: number, p: number): GridEntry | undefined {
  return entryMap.value.get(key(w, p))
}
function isCovered(w: number, p: number): boolean {
  return coveredSet.value.has(key(w, p))
}
function isRegular(w: number, p: number): boolean {
  return periodAt(w, p)?.type === 'regular'
}
function cardDraggable(e: GridEntry): boolean {
  return !props.readonly && !e.locked
}
function cellStyle(w: number, p: number, rowIdx: number) {
  const e = entryAt(w, p)
  const span = e?.span ?? 1
  return {
    gridColumn: `${w + 1}`,
    gridRow: span > 1 ? `${rowIdx + 2} / span ${span}` : `${rowIdx + 2}`,
  }
}
function cellClass(w: number, p: number) {
  const period = periodAt(w, p)
  const fb = props.feedback
  const isFbCell = fb && fb.weekday === w && fb.period_no === p
  return {
    'is-nodef': !period,
    'is-blocked': !!period && period.type !== 'regular',
    'is-regular': !!period && period.type === 'regular',
    'has-entry': !!entryAt(w, p),
    'is-droppable': !!isFbCell && fb!.ok,
    'is-conflict': !!isFbCell && !fb!.ok,
  }
}
function feedbackReason(w: number, p: number): string | null {
  const fb = props.feedback
  if (fb && !fb.ok && fb.weekday === w && fb.period_no === p) return fb.reason ?? '冲突'
  return null
}
function cellAriaLabel(w: number, p: number): string {
  const day = weekdayLabel(w)
  const period = periodAt(w, p)
  const periodName = period?.name ?? periodLabelName(p)
  const entry = entryAt(w, p)
  if (entry) {
    const details = [day, periodName, entry.subject]
    if (entry.teacher) details.push(entry.teacher)
    if (entry.room) details.push(entry.room)
    if (entry.locked) details.push('已锁定')
    details.push(props.readonly ? '只读' : entry.locked ? '可解锁' : '可编辑')
    return details.join('，')
  }
  if (!period) return `${day}，${periodName}，无节次定义`
  if (period.type !== 'regular') return `${day}，${periodName}，不可排课`
  const reason = feedbackReason(w, p)
  if (reason) return `${day}，${periodName}，冲突：${reason}`
  if (props.feedback?.weekday === w && props.feedback.period_no === p && props.feedback.ok) {
    return `${day}，${periodName}，可以排入`
  }
  return `${day}，${periodName}，空闲`
}
function cardAriaLabel(entry: GridEntry): string {
  const action = props.readonly ? '只读' : entry.locked ? '按回车解锁' : '按回车锁定'
  return [entry.subject, entry.teacher, entry.room, entry.locked ? '已锁定' : '', action]
    .filter(Boolean)
    .join('，')
}
function placementAriaLabel(w: number, p: number): string {
  const action = props.dragging?.source === 'grid' ? '移到' : '排入'
  return `将${props.placementLabel}${action}${weekdayLabel(w)}${periodLabelName(p)}`
}
function canActivate(w: number, p: number): boolean {
  return !props.readonly
    && !!props.dragging
    && isRegular(w, p)
    && !entryAt(w, p)
    && !feedbackReason(w, p)
}
function isMoveSelected(entry: GridEntry): boolean {
  return props.dragging?.source === 'grid' && props.dragging.entryId === entry.id
}

function onCardDragStart(e: GridEntry, ev: DragEvent) {
  if (!cardDraggable(e)) {
    ev.preventDefault()
    return
  }
  const data: DragData = { source: 'grid', entryId: e.id }
  ev.dataTransfer?.setData('application/json', JSON.stringify(data))
  if (ev.dataTransfer) ev.dataTransfer.effectAllowed = 'move'
  emit('dragstart', data)
}
function onCellCheck(w: number, p: number, ev: DragEvent) {
  if (props.readonly || !isRegular(w, p) || entryAt(w, p)) return
  ev.preventDefault() // 允许放下
  emit('check', { weekday: w, period_no: p, data: props.dragging })
}
function onCellDrop(w: number, p: number, ev: DragEvent) {
  if (props.readonly || !isRegular(w, p) || entryAt(w, p)) return
  ev.preventDefault()
  let data: DragData | null = props.dragging
  const raw = ev.dataTransfer?.getData('application/json')
  if (raw) {
    try {
      data = JSON.parse(raw) as DragData
    } catch {
      /* 保留 props.dragging */
    }
  }
  emit('drop', { weekday: w, period_no: p, data })
  emit('dragend')
}
function onCellActivate(w: number, p: number) {
  if (!canActivate(w, p)) return
  emit('activate', { weekday: w, period_no: p, data: props.dragging })
}
</script>

<template>
  <div
    class="tg-wrap"
    data-testid="timetable-scroll"
    tabindex="0"
    aria-label="课表工作面，可横向滚动"
  >
    <div
      class="tg-grid"
      role="grid"
      aria-label="课表"
      :style="{ gridTemplateColumns: `96px repeat(${weekdays.length}, minmax(92px, 1fr))` }"
    >
      <div class="tg-row" role="row">
        <div class="tg-corner" role="columnheader" :style="{ gridColumn: '1', gridRow: '1' }">
          <span>节次</span>
        </div>
        <div
          v-for="w in weekdays" :key="`h${w}`" class="tg-head" role="columnheader"
          :style="{ gridColumn: `${w + 1}`, gridRow: '1' }"
        >
          {{ weekdayLabel(w) }}
        </div>
      </div>

      <div v-for="(p, i) in periodNos" :key="`p${p}`" class="tg-row" role="row">
        <div class="tg-period" role="rowheader" :style="{ gridColumn: '1', gridRow: `${i + 2}` }">
          <div class="tg-period-name">{{ periodLabelName(p) }}</div>
          <div class="tg-period-time">{{ periodTime(p) }}</div>
        </div>

        <template v-for="w in weekdays" :key="`${w}-${p}`">
          <div
            v-if="!isCovered(w, p)"
            class="tg-cell" :class="cellClass(w, p)" :style="cellStyle(w, p, i)"
            role="gridcell"
            :aria-label="cellAriaLabel(w, p)"
            :aria-rowspan="(entryAt(w, p)?.span ?? 1) > 1 ? entryAt(w, p)!.span : undefined"
            :data-weekday="w" :data-period="p"
            @dragenter="onCellCheck(w, p, $event)"
            @dragover="onCellCheck(w, p, $event)"
            @drop="onCellDrop(w, p, $event)"
          >
            <div
              v-if="entryAt(w, p)"
              class="tg-card"
              :class="{
                'is-locked': entryAt(w, p)!.locked,
                'is-selected': isMoveSelected(entryAt(w, p)!),
              }"
              :draggable="cardDraggable(entryAt(w, p)!)"
              @dragstart="onCardDragStart(entryAt(w, p)!, $event)"
              @dragend="emit('dragend')"
              @click="emit('select', entryAt(w, p)!)"
            >
              <button
                type="button"
                class="tg-card-main"
                :disabled="readonly"
                :aria-label="cardAriaLabel(entryAt(w, p)!)"
                :title="cardAriaLabel(entryAt(w, p)!)"
              >
                <span v-if="entryAt(w, p)!.locked" class="tg-lock" aria-hidden="true">
                  <LockKeyhole :size="12" />
                </span>
                <span class="tg-subject">{{ entryAt(w, p)!.subject }}</span>
                <span v-if="entryAt(w, p)!.teacher" class="tg-teacher">{{ entryAt(w, p)!.teacher }}</span>
                <span v-if="entryAt(w, p)!.room" class="tg-room">{{ entryAt(w, p)!.room }}</span>
              </button>
              <div v-if="!readonly" class="tg-card-actions">
                <button
                  type="button"
                  class="tg-entry-action"
                  :class="{ 'is-selected': isMoveSelected(entryAt(w, p)!) }"
                  :disabled="entryAt(w, p)!.locked"
                  :aria-label="`移动${entryAt(w, p)!.subject}`"
                  :title="entryAt(w, p)!.locked ? '请先解锁课程' : `移动${entryAt(w, p)!.subject}`"
                  :aria-pressed="isMoveSelected(entryAt(w, p)!)"
                  @click.stop="emit('move', entryAt(w, p)!)"
                >
                  <MoveHorizontal :size="13" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  class="tg-entry-action is-danger"
                  :disabled="entryAt(w, p)!.locked"
                  :aria-label="`移除${entryAt(w, p)!.subject}`"
                  :title="entryAt(w, p)!.locked ? '请先解锁课程' : `移除${entryAt(w, p)!.subject}`"
                  @click.stop="emit('remove', entryAt(w, p)!)"
                >
                  <Trash2 :size="13" aria-hidden="true" />
                </button>
              </div>
            </div>
            <div v-else-if="!isRegular(w, p)" class="tg-blocked-label">
              {{ periodAt(w, p)?.name ?? '—' }}
            </div>
            <div v-else-if="feedbackReason(w, p)" class="tg-reason" :title="feedbackReason(w, p)!">
              {{ feedbackReason(w, p) }}
            </div>
            <div
              v-else-if="feedback?.weekday === w && feedback.period_no === p && feedback.ok"
              class="tg-available"
            >
              <Check :size="14" aria-hidden="true" />
              <span>{{ '可放' }}</span>
            </div>
            <button
              v-else-if="canActivate(w, p)"
              type="button"
              class="tg-place-action"
              :aria-label="placementAriaLabel(w, p)"
              :title="placementAriaLabel(w, p)"
              @click="onCellActivate(w, p)"
            >
              <Plus :size="16" aria-hidden="true" />
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tg-wrap {
  width: 100%;
  min-width: 0;
  overflow-x: auto;
  overscroll-behavior-inline: contain;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  -webkit-overflow-scrolling: touch;
}
.tg-grid {
  display: grid;
  min-width: max-content;
  gap: 1px;
  background: var(--app-border);
  grid-auto-rows: minmax(62px, auto);
}
.tg-row { display: contents; }
.tg-corner,
.tg-head,
.tg-period,
.tg-cell {
  min-width: 0;
  background: var(--app-surface);
}
.tg-corner,
.tg-period {
  position: sticky;
  z-index: 2;
  left: 0;
  border-right: 1px solid var(--app-border-strong);
}
.tg-corner {
  z-index: 3;
  display: grid;
  place-items: center;
  color: var(--app-text-faint);
  font-size: 11px;
  font-weight: 700;
}
.tg-head {
  display: grid;
  place-items: center;
  padding: 8px 5px;
  background: var(--app-surface-muted);
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 700;
  text-align: center;
}
.tg-period {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 6px 8px;
  background: var(--app-surface-muted);
}
.tg-period-name { color: var(--app-text); font-size: 12px; font-weight: 700; }
.tg-period-time { color: var(--app-text-faint); font-size: 10px; }
.tg-cell {
  position: relative;
  min-height: 62px;
  padding: 3px;
  box-shadow: inset 0 0 0 1px transparent;
  transition:
    background-color var(--app-motion-duration) var(--app-motion-ease),
    box-shadow var(--app-motion-duration) var(--app-motion-ease);
}
.tg-cell.is-blocked,
.tg-cell.is-nodef {
  background: var(--app-surface-pressed);
  box-shadow: inset 0 0 0 1px var(--app-border);
}
.tg-cell.is-droppable {
  background: var(--app-success-soft);
  box-shadow: inset 0 0 0 2px var(--app-success);
}
.tg-cell.is-conflict {
  background: var(--app-danger-soft);
  box-shadow: inset 0 0 0 2px var(--app-danger);
}
.tg-blocked-label,
.tg-reason,
.tg-available {
  display: flex;
  height: 100%;
  min-height: 54px;
  align-items: center;
  justify-content: center;
  padding: 6px;
  color: var(--app-text-faint);
  font-size: 11px;
  line-height: 1.35;
  text-align: center;
}
.tg-reason { color: var(--app-danger-pressed); }
.tg-available { gap: 4px; color: var(--app-success-pressed); font-weight: 700; }
.tg-card,
.tg-place-action {
  width: 100%;
  height: 100%;
  min-height: 54px;
  border-radius: var(--app-radius-xs);
  font: inherit;
}
.tg-card {
  position: relative;
  border: 1px solid var(--app-primary-border);
  background: var(--app-primary-soft);
  color: var(--app-text);
  cursor: grab;
}
.tg-card:hover { border-color: var(--app-primary); }
.tg-card.is-selected {
  border-color: var(--app-primary);
  box-shadow: var(--app-shadow-focus);
}
.tg-card.is-locked {
  border-color: var(--app-border-strong);
  background: var(--app-surface-pressed);
  cursor: pointer;
}
.tg-card-main {
  display: flex;
  width: 100%;
  min-height: 100%;
  flex-direction: column;
  align-items: flex-start;
  padding: 6px 7px 28px;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  text-align: left;
}
.tg-card-main:disabled { cursor: default; opacity: 1; }
.tg-lock {
  position: absolute;
  top: 5px;
  right: 5px;
  display: inline-flex;
  color: var(--app-text-muted);
}
.tg-subject {
  padding-right: 15px;
  overflow-wrap: anywhere;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
}
.tg-teacher { margin-top: 2px; color: var(--app-text-muted); font-size: 11px; line-height: 1.35; }
.tg-room { margin-top: 2px; color: var(--app-text-faint); font-size: 10px; line-height: 1.35; }
.tg-card-actions {
  position: absolute;
  right: 4px;
  bottom: 4px;
  display: flex;
  gap: 3px;
}
.tg-entry-action {
  display: grid;
  width: 21px;
  height: 21px;
  place-items: center;
  padding: 0;
  border: 1px solid var(--app-border-strong);
  border-radius: var(--app-radius-xs);
  background: var(--app-surface);
  color: var(--app-text-muted);
  cursor: pointer;
}
.tg-entry-action:hover:not(:disabled),
.tg-entry-action:focus-visible,
.tg-entry-action.is-selected {
  border-color: var(--app-primary);
  color: var(--app-primary-strong);
}
.tg-entry-action.is-danger:hover:not(:disabled),
.tg-entry-action.is-danger:focus-visible {
  border-color: var(--app-danger);
  color: var(--app-danger-pressed);
}
.tg-entry-action:disabled { cursor: not-allowed; opacity: 0.45; }
.tg-place-action {
  display: grid;
  place-items: center;
  border: 1px dashed var(--app-primary-border);
  background: transparent;
  color: var(--app-primary-strong);
  cursor: pointer;
}
.tg-place-action:hover,
.tg-place-action:focus-visible {
  border-color: var(--app-primary);
  background: var(--app-primary-soft);
}

@media (max-width: 560px) {
  .tg-grid { grid-auto-rows: minmax(58px, auto); }
  .tg-cell { min-height: 58px; }
  .tg-card,
  .tg-place-action { min-height: 50px; }
}
</style>
