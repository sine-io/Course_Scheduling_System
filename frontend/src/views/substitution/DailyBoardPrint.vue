<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getDailyBoard } from '@/api/substitutionLog'
import type { DailyBoard, LogEntry } from '@/api/substitutionLog'
import { useAppConfigStore } from '@/stores/appConfig'

const appConfig = useAppConfigStore()
const mainland = computed(() => appConfig.isMainland)
const tr = (tw: string, cn: string) => mainland.value ? cn : tw
const WEEKDAYS = computed(() => mainland.value
  ? ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  : ['週日', '週一', '週二', '週三', '週四', '週五', '週六'])

const route = useRoute()
const board = ref<DailyBoard | null>(null)
const loading = ref(true)

// 只列已安排的處置(通知單是公告安排,待處理的不上榜)
const rows = computed<LogEntry[]>(() => (board.value?.entries ?? []).filter((e) => e.disposed))
const dateLabel = computed(() =>
  board.value ? `${board.value.date}(${WEEKDAYS.value[board.value.weekday % 7]})` : '')
const printedAt = computed(() => new Date().toLocaleString(
  mainland.value ? 'zh-CN' : 'zh-TW', { hour12: false },
))

function handlerText(e: LogEntry): string {
  if (e.handler_name) return e.handler_name
  return e.sub_type_label ?? ''   // 自習/不處理沒有接手教師
}

function noteText(e: LogEntry): string {
  if (e.sub_type === 'swap' && e.swap_period_name) {
    return mainland.value
      ? `${e.absent_teacher_name} 于 ${e.swap_date} ${e.swap_period_name} 补 ${e.swap_class_names}${e.swap_subject_name}`
      : `${e.absent_teacher_name} 於 ${e.swap_date} ${e.swap_period_name} 補 ${e.swap_class_names}${e.swap_subject_name}`
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
  <div class="sheet" :class="{ mainland }">
    <div class="no-print toolbar">
      <button type="button" data-testid="print-btn" @click="doPrint">{{ tr('列印', '打印') }}</button>
      <button type="button" @click="doClose">{{ tr('關閉', '关闭') }}</button>
    </div>

    <template v-if="board">
      <header class="head">
        <h1 class="school">{{ board.school_name }}</h1>
        <h2 class="title">{{ tr('調代課通知單', '调代课通知单') }}</h2>
        <div class="meta">
          <span>{{ board.semester_label }}</span>
          <span>{{ tr('日期', '日期') }}：{{ dateLabel }}</span>
        </div>
      </header>

      <p v-if="!rows.length" class="empty" data-testid="print-empty">{{ tr('本日無調代課安排。', '本日无调代课安排。') }}</p>

      <table v-else class="grid" data-testid="print-table">
        <thead>
          <tr>
            <th style="width: 12%">{{ tr('節次', '节次') }}</th>
            <th style="width: 14%">{{ tr('班級', '班级') }}</th>
            <th style="width: 12%">{{ tr('科目', '科目') }}</th>
            <th style="width: 14%">{{ tr('原任教師', '原任教师') }}</th>
            <th style="width: 10%">{{ tr('假別', '假别') }}</th>
            <th style="width: 12%">{{ tr('處置', '处置') }}</th>
            <th style="width: 14%">{{ tr('代課/接手', '代课/接手') }}</th>
            <th>{{ tr('備註', '备注') }}</th>
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
        <span>{{ tr('教學組長', '教务员') }}：____________　{{ tr('教務主任', '教务主任') }}：____________</span>
        <span class="printed">{{ tr('列印時間', '打印时间') }}：{{ printedAt }}</span>
      </footer>
    </template>

    <p v-else-if="loading" class="empty">{{ tr('載入中…', '加载中…') }}</p>
  </div>
</template>

<style scoped>
.sheet {
  max-width: 780px;
  margin: 0 auto;
  padding: 24px;
  color: #000;
  background: #fff;
  font-family: "Microsoft JhengHei", "PingFang TC", sans-serif;
}
.sheet.mainland { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; }
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
