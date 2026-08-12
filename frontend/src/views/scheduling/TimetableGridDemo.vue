<script setup lang="ts">
import { Clock3, Layers3 } from '@lucide/vue'
import { NEmpty, NRadioButton, NRadioGroup, NTag, useMessage } from 'naive-ui'
import { computed, reactive, ref } from 'vue'
import TimetableGrid from '@/components/timetable/TimetableGrid.vue'
import type { DragData, DropFeedback, GridEntry, PeriodCell } from '@/components/timetable/types'
import './scheduling-workspace.css'

const message = useMessage()

// ── 两套示例作息时间表(小学 40 分、中职 50 分)──
function pad(n: number) { return String(n).padStart(2, '0') }
function slot(start: number, len: number) {
  const s = `${pad(Math.floor(start / 60))}:${pad(start % 60)}`
  const e = start + len
  return { start: s, end: `${pad(Math.floor(e / 60))}:${pad(e % 60)}` }
}

function buildElementary(): PeriodCell[] {
  const cells: PeriodCell[] = []
  const starts = [480, 530, 580, 630, 680, 720, 790, 840] // 分钟
  for (let w = 1; w <= 5; w++) {
    starts.forEach((st, i) => {
      const p = i + 1
      const t = slot(st, p === 6 ? 60 : 40)
      let type = 'regular'
      let name = `第${p}节`
      if (p === 6) { type = 'lunch'; name = '午休' }
      // 周三下午不排课(第 7、8 节)
      if (w === 3 && p >= 7) { type = 'reserved'; name = '周三不排' }
      cells.push({ weekday: w, period_no: p, name, type, start_time: t.start, end_time: t.end })
    })
  }
  return cells
}
function buildVocational(): PeriodCell[] {
  const cells: PeriodCell[] = []
  const starts = [480, 540, 600, 660, 720, 790, 850, 910]
  for (let w = 1; w <= 5; w++) {
    starts.forEach((st, i) => {
      const p = i + 1
      const t = slot(st, p === 5 ? 60 : 50)
      let type = 'regular'
      let name = `第${p}节`
      if (p === 5) { type = 'lunch'; name = '午休' }
      cells.push({ weekday: w, period_no: p, name, type, start_time: t.start, end_time: t.end })
    })
  }
  return cells
}

const sample = ref<'elementary' | 'vocational'>('elementary')
const periods = computed(() => (sample.value === 'elementary' ? buildElementary() : buildVocational()))

// 各示例独立的已排单元格与未排列表
interface TrayItem { assignmentId: number; subject: string; teacher: string; room?: string; span?: number }
const state = reactive<Record<string, { entries: GridEntry[]; tray: TrayItem[] }>>({
  elementary: {
    entries: [
      { id: 1, weekday: 1, period_no: 1, subject: '班会时间', teacher: '王老师', locked: true },
      { id: 2, weekday: 2, period_no: 2, subject: '数学', teacher: '李老师' },
    ],
    tray: [
      { assignmentId: 11, subject: '语文', teacher: '王老师' },
      { assignmentId: 12, subject: '英语', teacher: '陈老师' },
      { assignmentId: 13, subject: '生物', teacher: '林老师', room: '生物实验室' },
    ],
  },
  vocational: {
    entries: [
      { id: 21, weekday: 1, period_no: 1, subject: '语文', teacher: '张老师', locked: true },
      { id: 22, weekday: 1, period_no: 6, subject: '综合实践活动', teacher: '陈老师', room: '综合实践教室', span: 2 },
    ],
    tray: [
      { assignmentId: 31, subject: '数学', teacher: '李老师' },
      { assignmentId: 32, subject: '美术', teacher: '陈老师', room: '美术教室', span: 2 },
    ],
  },
})
const current = computed(() => state[sample.value])

// 冲突模拟:某些教师在特定时段「已在他处有课」,拖入即红框
const busy: Record<string, Set<string>> = {
  ['王老师']: new Set(['1-2']),
  ['张老师']: new Set(['2-3']),
}

const dragging = ref<DragData | null>(null)
const feedback = ref<DropFeedback | null>(null)

function teacherOf(data: DragData | null): string | undefined {
  if (!data) return undefined
  if (data.source === 'tray') return data.teacher as string
  const e = current.value.entries.find((x) => x.id === data.entryId)
  return e?.teacher
}

function onTrayDragStart(item: TrayItem, ev: DragEvent) {
  const data: DragData = { source: 'tray', ...item }
  dragging.value = data
  ev.dataTransfer?.setData('application/json', JSON.stringify(data))
  if (ev.dataTransfer) ev.dataTransfer.effectAllowed = 'move'
}
function onGridDragStart(data: DragData) {
  dragging.value = data
}
function onCheck(payload: { weekday: number; period_no: number; data: DragData | null }) {
  const teacher = teacherOf(payload.data ?? dragging.value)
  const k = `${payload.weekday}-${payload.period_no}`
  const conflict = teacher ? busy[teacher]?.has(k) : false
  feedback.value = {
    weekday: payload.weekday, period_no: payload.period_no,
    ok: !conflict,
    reason: conflict ? `${teacher} 此时段已有课` : undefined,
  }
}
function onDrop(payload: { weekday: number; period_no: number; data: DragData | null }) {
  const data = payload.data ?? dragging.value
  const teacher = teacherOf(data)
  const k = `${payload.weekday}-${payload.period_no}`
  if (teacher && busy[teacher]?.has(k)) {
    message.error(`无法放入：${teacher} 此时段已有课`)
    clearDrag()
    return
  }
  if (data?.source === 'tray') {
    const idx = current.value.tray.findIndex((t) => t.assignmentId === data.assignmentId)
    if (idx >= 0) {
      const item = current.value.tray[idx]
      current.value.tray.splice(idx, 1)
      current.value.entries.push({
        id: `e${item.assignmentId}`, weekday: payload.weekday, period_no: payload.period_no,
        subject: item.subject, teacher: item.teacher, room: item.room, span: item.span,
      })
    }
  } else if (data?.source === 'grid') {
    const e = current.value.entries.find((x) => x.id === data.entryId)
    if (e) { e.weekday = payload.weekday; e.period_no = payload.period_no }
  }
  clearDrag()
}
function onTrayDrop(ev: DragEvent) {
  ev.preventDefault()
  const raw = ev.dataTransfer?.getData('application/json')
  const data: DragData | null = raw ? JSON.parse(raw) : dragging.value
  if (data?.source === 'grid') {
    const idx = current.value.entries.findIndex((x) => x.id === data.entryId)
    if (idx >= 0) {
      const e = current.value.entries[idx]
      if (e.locked) { message.warning('锁定单元格不可移除'); clearDrag(); return }
      current.value.entries.splice(idx, 1)
      current.value.tray.push({
        assignmentId: Number(String(e.id).replace('e', '')) || Date.now(),
        subject: e.subject, teacher: e.teacher ?? '', room: e.room, span: e.span,
      })
    }
  }
  clearDrag()
}
function onSelect(entry: GridEntry) {
  const e = current.value.entries.find((x) => x.id === entry.id)
  if (e) {
    e.locked = !e.locked
    message.info(e.locked
      ? `已锁定“${e.subject}”`
      : `已解锁“${e.subject}”`)
  }
}
function clearDrag() {
  dragging.value = null
  feedback.value = null
}
</script>

<template>
  <div class="scheduling-page timetable-demo-page" data-testid="timetable-demo-page">
    <header class="scheduling-page-header">
      <div>
        <p class="scheduling-eyebrow">{{ '交互样例' }}</p>
        <h1>{{ '课表组件演示（TimetableGrid）' }}</h1>
        <p>{{ '小学与中职两套作息样例，包含锁定、连堂和冲突状态。' }}</p>
      </div>
    </header>

    <section class="scheduling-panel demo-toolbar" aria-label="演示设置">
      <div>
        <p class="scheduling-eyebrow">{{ '样例作息' }}</p>
        <div role="radiogroup" aria-label="演示学段">
          <n-radio-group v-model:value="sample">
            <n-radio-button value="elementary" data-testid="demo-elementary">{{ '小学（40 分钟/节）' }}</n-radio-button>
            <n-radio-button value="vocational" data-testid="demo-vocational">{{ '中职（50 分钟/节）' }}</n-radio-button>
          </n-radio-group>
        </div>
      </div>
      <div class="demo-summary" aria-label="当前样例概况">
        <n-tag size="small">{{ current.entries.length }} {{ '格已排' }}</n-tag>
        <n-tag size="small" type="warning">{{ current.tray.length }} {{ '项待排' }}</n-tag>
      </div>
    </section>

    <div class="demo-layout">
      <section class="scheduling-panel demo-grid-panel">
        <header class="scheduling-panel-heading compact-heading">
          <div>
            <p class="scheduling-eyebrow">{{ '课表工作面' }}</p>
            <h2>{{ sample === 'elementary' ? '小学周课表' : '中职周课表' }}</h2>
            <p>{{ sample === 'elementary' ? '40 分钟标准节次' : '50 分钟标准节次' }}</p>
          </div>
          <Clock3 :size="20" class="scheduling-heading-icon" aria-hidden="true" />
        </header>
        <TimetableGrid
          :key="sample"
          :periods="periods" :entries="current.entries"
          :dragging="dragging" :feedback="feedback"
          @dragstart="onGridDragStart" @dragend="clearDrag"
          @check="onCheck" @drop="onDrop" @select="onSelect"
        />
      </section>

      <aside
        class="scheduling-panel demo-tray"
        aria-label="未排课程"
        @dragover.prevent @drop="onTrayDrop"
      >
        <header class="scheduling-panel-heading compact-heading">
          <div>
            <p class="scheduling-eyebrow">{{ '待排托盘' }}</p>
            <h2>{{ '未排课程' }}</h2>
          </div>
          <Layers3 :size="20" class="scheduling-heading-icon" aria-hidden="true" />
        </header>
        <div class="demo-tray-content">
          <n-empty v-if="current.tray.length === 0" size="small" :description="'已全部排入'" />
          <div
            v-for="item in current.tray" :key="item.assignmentId"
            class="tray-item" :data-testid="`tray-${item.subject}`" draggable="true"
            :aria-label="`${item.subject}，${item.teacher}${item.room ? `，${item.room}` : ''}`"
            @dragstart="onTrayDragStart(item, $event)" @dragend="clearDrag"
          >
            <div class="tray-subject">
              {{ item.subject }}
              <n-tag v-if="item.span && item.span > 1" size="tiny" type="warning">{{ item.span }}{{ '连堂' }}</n-tag>
            </div>
            <div class="tray-teacher">{{ item.teacher }}<span v-if="item.room"> · {{ item.room }}</span></div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.timetable-demo-page { max-width: 1600px; }
.demo-toolbar { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; }
.demo-toolbar .scheduling-eyebrow { margin-bottom: 8px; }
.demo-summary { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.demo-layout { display: grid; min-width: 0; grid-template-columns: minmax(0, 1fr) 250px; align-items: start; gap: 20px; }
.demo-grid-panel { display: grid; min-width: 0; gap: 16px; overflow: hidden; }
.demo-tray { display: grid; min-width: 0; gap: 14px; }
.demo-tray-content { display: grid; gap: 9px; min-height: 160px; align-content: start; }
.tray-item {
  min-width: 0;
  padding: 10px 11px;
  border: 1px solid var(--app-primary-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-primary-soft);
  cursor: grab;
}
.tray-subject { font-weight: 600; display: flex; align-items: center; gap: 6px; }
.tray-teacher { margin-top: 3px; color: var(--app-text-muted); font-size: 12px; overflow-wrap: anywhere; }
@media (max-width: 1100px) {
  .demo-layout { grid-template-columns: 1fr; }
  .demo-tray-content { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); min-height: 0; }
}

@media (max-width: 560px) {
  .demo-toolbar { align-items: stretch; flex-direction: column; }
  .demo-toolbar :deep(.n-radio-group) { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); width: 100%; }
  .demo-toolbar :deep(.n-radio-button) { justify-content: center; min-width: 0; }
  .demo-tray-content { grid-template-columns: 1fr; }
}
</style>
