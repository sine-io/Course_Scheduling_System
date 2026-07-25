<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getDailyBoard } from '@/api/substitutionLog'
import type { DailyBoard, LogEntry } from '@/api/substitutionLog'

const WEEKDAYS = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

const route = useRoute()
const board = ref<DailyBoard | null>(null)
const loading = ref(true)

// 只列已安排的处理方式(通知单是公告安排,待处理的不上榜)
const rows = computed<LogEntry[]>(() => (board.value?.entries ?? []).filter((e) => e.disposed))
const dateLabel = computed(() =>
  board.value ? `${board.value.date}（${WEEKDAYS[board.value.weekday % 7]}）` : '')
const printedAt = computed(() => new Date().toLocaleString(
  'zh-CN', { hour12: false },
))

function handlerText(e: LogEntry): string {
  if (e.handler_name) return e.handler_name
  return e.sub_type_label ?? ''   // 自习/不处理没有接手教师
}

function noteText(e: LogEntry): string {
  if (e.sub_type === 'swap' && e.swap_period_name) {
    return `${e.absent_teacher_name} 于 ${e.swap_date} ${e.swap_period_name} 补 ${e.swap_class_names}${e.swap_subject_name}`
  }
  return e.note || ''
}

function doPrint() {
  window.print()
}
function doClose() {
  window.close()
}

onMounted(async () => {
  const sid = Number(route.query.semester_id)
  const on = (route.query.date as string) || null
  try {
    board.value = await getDailyBoard(sid, on)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="sheet">
    <div class="no-print toolbar">
      <button type="button" data-testid="print-btn" @click="doPrint">{{ '打印' }}</button>
      <button type="button" @click="doClose">{{ '关闭' }}</button>
    </div>

    <template v-if="board">
      <header class="head">
        <h1 class="school">{{ board.school_name }}</h1>
        <h2 class="title">{{ '调课与代课通知单' }}</h2>
        <div class="meta">
          <span>{{ board.semester_label }}</span>
          <span>{{ '日期' }}：{{ dateLabel }}</span>
        </div>
      </header>

      <p v-if="!rows.length" class="empty" data-testid="print-empty">{{ '本日无调课与代课安排。' }}</p>

      <table v-else class="grid" data-testid="print-table">
        <thead>
          <tr>
            <th style="width: 12%">{{ '节次' }}</th>
            <th style="width: 14%">{{ '班级' }}</th>
            <th style="width: 12%">{{ '科目' }}</th>
            <th style="width: 14%">原授课教师</th>
            <th style="width: 10%">请假类型</th>
            <th style="width: 12%">处理方式</th>
            <th style="width: 14%">{{ '代课/接手' }}</th>
            <th>{{ '备注' }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in rows" :key="e.affected_period_id" data-testid="print-row">
            <td>{{ e.period_name }}</td>
            <td>{{ e.class_names }}<span v-if="e.room_name" class="room"> @{{ e.room_name }}</span></td>
            <td>{{ e.subject_name }}</td>
            <td>{{ e.absent_teacher_name }}</td>
            <td>{{ e.leave_type_label }}</td>
            <td>{{ e.sub_type_label }}</td>
            <td>{{ handlerText(e) }}</td>
            <td class="note">{{ noteText(e) }}</td>
          </tr>
        </tbody>
      </table>

      <footer class="foot">
        <span>排课管理员：____________　教务主任：____________</span>
        <span class="printed">{{ '打印时间' }}：{{ printedAt }}</span>
      </footer>
    </template>

    <p v-else-if="loading" class="empty">{{ '加载中…' }}</p>
  </div>
</template>

<style scoped>
.sheet {
  max-width: 780px;
  margin: 0 auto;
  padding: 24px;
  color: #000;
  background: #fff;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}
.toolbar { display: flex; gap: 8px; justify-content: flex-end; margin-bottom: 16px; }
.toolbar button {
  padding: 6px 16px; cursor: pointer; border: 1px solid #888; border-radius: 4px; background: #f4f4f4;
}
.head { text-align: center; margin-bottom: 16px; }
.school { font-size: 22px; margin: 0 0 4px; }
.title { font-size: 18px; font-weight: 600; letter-spacing: 4px; margin: 0 0 8px; }
.meta { display: flex; justify-content: space-between; font-size: 14px; padding: 0 4px; }
.grid { border-collapse: collapse; width: 100%; font-size: 14px; }
.grid th, .grid td { border: 1px solid #000; padding: 6px 8px; text-align: center; }
.grid th { background: #eee; }
.grid td.note { text-align: left; }
.room { color: #444; }
.empty { text-align: center; padding: 40px 0; font-size: 15px; }
.foot {
  display: flex; justify-content: space-between; margin-top: 24px; font-size: 13px;
}
.printed { color: #444; }

@media print {
  @page { size: A4; margin: 14mm; }
  .no-print { display: none !important; }
  .sheet { max-width: none; padding: 0; }
}
</style>
