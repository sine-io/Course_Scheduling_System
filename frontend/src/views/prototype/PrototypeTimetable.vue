<script setup lang="ts">
import { AlertTriangle, Check, Inbox, LoaderCircle, LockKeyhole } from '@lucide/vue'
import type { CourseCell, ScheduleRow, StatusMode } from './prototypeData'
import { scheduleRows, weekdays } from './prototypeData'

withDefaults(defineProps<{
  statusMode: StatusMode
  selectedCourseKey: string | null
  rows?: ScheduleRow[]
  days?: string[]
  compact?: boolean
}>(), {
  rows: () => scheduleRows,
  days: () => weekdays,
  compact: false,
})

const emit = defineEmits<{
  select: [course: CourseCell]
}>()
</script>

<template>
  <div class="prototype-timetable-region" :class="{ 'is-compact': compact }">
    <div v-if="statusMode === 'loading'" class="prototype-timetable-state is-loading" aria-live="polite">
      <LoaderCircle class="state-spin" :size="22" aria-hidden="true" />
      <span>正在读取课表…</span>
      <div class="timetable-loading-lines" aria-hidden="true">
        <i v-for="line in 4" :key="line" />
      </div>
    </div>
    <div v-else-if="statusMode === 'empty'" class="prototype-timetable-state" aria-live="polite">
      <Inbox :size="24" aria-hidden="true" />
      <strong>尚无可展示的作息时间表</strong>
      <span>完成学期设置后，这里会出现可编辑课表。</span>
    </div>
    <div v-else-if="statusMode === 'restricted'" class="prototype-timetable-state is-restricted" role="status">
      <LockKeyhole :size="24" aria-hidden="true" />
      <strong>当前角色无法打开排课草稿</strong>
      <span>可在课表查询中查看已发布课表；编辑、移动和发布仅对排课管理员开放。</span>
    </div>
    <div v-else-if="statusMode === 'error'" class="prototype-timetable-state is-error" role="alert">
      <AlertTriangle :size="24" aria-hidden="true" />
      <strong>课表加载失败</strong>
      <span>排课服务暂时没有响应，当前页面保留筛选条件。</span>
    </div>
    <div v-else class="prototype-timetable-scroll">
      <div class="prototype-timetable" role="grid" aria-label="八年级 2 班课表">
        <div class="timetable-corner" role="columnheader">节次</div>
        <div v-for="day in days" :key="day" class="timetable-day" role="columnheader">{{ day }}</div>
        <template v-for="row in rows" :key="row.period">
          <div class="timetable-period" role="rowheader">
            <strong>{{ row.period }}</strong>
            <span>{{ row.time }}</span>
          </div>
          <div v-for="(cell, cellIndex) in row.cells" :key="cell?.id ?? `${row.period}-empty-${cellIndex}`" class="timetable-slot" role="gridcell">
            <button
              v-if="cell"
              class="prototype-course"
              :class="[`tone-${cell.tone}`, { 'is-selected': selectedCourseKey === cell.id, 'is-conflict': cell.conflict }]"
              type="button"
              :aria-pressed="selectedCourseKey === cell.id"
              :title="`${cell.subject} · ${cell.teacher} · ${cell.room}`"
              @click="emit('select', cell)"
            >
              <span class="course-title-row">
                <strong>{{ cell.subject }}</strong>
                <LockKeyhole v-if="cell.locked" :size="12" aria-label="已锁定" />
                <AlertTriangle v-if="cell.conflict" :size="12" aria-label="存在冲突" />
              </span>
              <small>{{ cell.teacher }} · {{ cell.room }}</small>
              <Check v-if="cell.locked" class="course-check" :size="12" aria-hidden="true" />
            </button>
            <span v-else class="empty-slot" aria-label="空课位">—</span>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.prototype-timetable-region { min-width: 0; min-height: 310px; }
.prototype-timetable-scroll { max-width: 100%; overflow-x: auto; overscroll-behavior-x: contain; padding-bottom: 4px; }
.prototype-timetable { display: grid; grid-template-columns: 88px repeat(6, minmax(112px, 1fr)); gap: 5px; min-width: 790px; }
.timetable-corner, .timetable-day, .timetable-period, .timetable-slot { border: 1px solid var(--proto-line); }
.timetable-corner, .timetable-day { min-height: 36px; display: grid; place-items: center; background: var(--proto-surface-muted); color: var(--proto-text-muted); font-size: 12px; font-weight: 700; }
.timetable-corner { position: sticky; left: 0; z-index: 4; }
.timetable-day { color: var(--proto-text); }
.timetable-period { position: sticky; left: 0; z-index: 3; display: flex; flex-direction: column; justify-content: center; gap: 3px; min-height: 64px; padding: 8px; background: #fbfcfe; }
.timetable-period strong { color: var(--proto-text); font-size: 12px; }
.timetable-period span { color: var(--proto-text-muted); font-size: 10px; white-space: nowrap; }
.timetable-slot { min-height: 64px; padding: 4px; background: var(--proto-surface); }
.prototype-course { position: relative; display: flex; width: 100%; min-height: 54px; flex-direction: column; align-items: flex-start; gap: 4px; padding: 8px 8px 7px; border: 1px solid transparent; border-radius: 6px; color: var(--proto-text); cursor: pointer; text-align: left; transition: border-color 150ms ease, background-color 150ms ease; }
.prototype-course:hover, .prototype-course:focus-visible { border-color: var(--proto-primary); outline: none; }
.prototype-course.is-selected { border-color: var(--proto-primary); box-shadow: inset 3px 0 var(--proto-primary); }
.prototype-course.is-conflict { border-color: var(--proto-danger); }
.course-title-row { display: flex; align-items: center; gap: 5px; width: 100%; font-size: 12px; }
.prototype-course small { max-width: 100%; overflow: hidden; color: var(--proto-text-muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.course-check { position: absolute; right: 7px; bottom: 7px; color: var(--proto-success); }
.tone-blue { background: var(--proto-blue-soft); color: #194da9; }
.tone-teal { background: var(--proto-teal-soft); color: #087d79; }
.tone-purple { background: var(--proto-purple-soft); color: #5d47b8; }
.tone-orange { background: var(--proto-orange-soft); color: #a75708; }
.tone-green { background: var(--proto-green-soft); color: #167649; }
.tone-red { background: var(--proto-red-soft); color: #b42318; }
.empty-slot { display: grid; min-height: 54px; place-items: center; color: #c1c8d2; font-size: 13px; }
.prototype-timetable-state { display: grid; min-height: 310px; place-items: center; align-content: center; gap: 9px; padding: 24px; color: var(--proto-text-muted); text-align: center; }
.prototype-timetable-state strong { color: var(--proto-text); font-size: 13px; }
.prototype-timetable-state span { font-size: 11px; }
.prototype-timetable-state.is-restricted { color: var(--proto-warning); }
.prototype-timetable-state.is-restricted strong { color: var(--proto-text); }
.prototype-timetable-state.is-error { color: var(--proto-danger); }
.prototype-timetable-state.is-error strong { color: var(--proto-danger); }
.state-spin { animation: prototype-spin 1s linear infinite; color: var(--proto-primary); }
.timetable-loading-lines { display: grid; width: min(420px, 90%); gap: 8px; margin-top: 8px; }
.timetable-loading-lines i { display: block; height: 28px; border-radius: 5px; background: linear-gradient(90deg, #eef1f5 20%, #f8fafc 45%, #eef1f5 70%); background-size: 220% 100%; animation: prototype-shimmer 1.3s ease-in-out infinite; }
@keyframes prototype-spin { to { transform: rotate(360deg); } }
@keyframes prototype-shimmer { to { background-position: -120% 0; } }
@media (prefers-reduced-motion: reduce) {
  .prototype-course, .state-spin, .timetable-loading-lines i { transition: none; animation: none; }
}
</style>
