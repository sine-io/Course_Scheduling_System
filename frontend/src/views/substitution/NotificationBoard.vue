<script setup lang="ts">
import { NButton, NCheckbox, NEmpty, NSelect, NSpace, NTag, NText, useMessage } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { notificationBoard, remind } from '@/api/notifications'
import type { BoardEntry } from '@/api/notifications'
import { listSemesters } from '@/api/semesters'
import { useAppConfigStore } from '@/stores/appConfig'

const message = useMessage()
const appConfig = useAppConfigStore()
const mainland = computed(() => appConfig.isMainland)
const tr = (tw: string, cn: string) => mainland.value ? cn : tw

const semesters = ref<{ id: number; label: string }[]>([])
const sid = ref<number | null>(null)
const entries = ref<BoardEntry[]>([])
const unackOnly = ref(true) // 預設只看未確認——那才是組長要追的

const semesterOptions = computed(() => semesters.value.map((s) => ({ label: s.label, value: s.id })))

const TYPE_LABEL = computed<Record<string, string>>(() => ({
  substitution_assigned: tr('代課通知', '代课通知'),
  substitution_cancelled: tr('代課取消', '代课取消'),
  leave_registered: tr('請假登記', '请假登记'),
  leave_cancelled: tr('銷假', '销假'),
  timetable_published: tr('課表發布', '课表发布'),
}))

async function reload() {
  if (sid.value === null) return
  entries.value = await notificationBoard(sid.value, { unacknowledgedOnly: unackOnly.value })
}

async function onSemesterChange(id: number) {
  sid.value = id
  await reload()
}

onMounted(async () => {
  semesters.value = await listSemesters()
  if (semesters.value.length) await onSemesterChange(semesters.value[0].id)
})

async function onRemind(e: BoardEntry) {
  try {
    await remind(e.id)
    message.success(tr(`已再次提醒 ${e.teacher_name}`, `已再次提醒 ${e.teacher_name}`))
    await reload()
  } catch (err) {
    message.error((err as { message?: string }).message || tr('提醒失敗', '提醒失败'))
  }
}

function ackTag(e: BoardEntry): { type: string; label: string } {
  if (e.acknowledged_at) return { type: 'success', label: tr('已確認', '已确认') }
  if (e.read_at) return { type: 'info', label: tr('已讀未確認', '已读未确认') }
  return { type: 'warning', label: tr('未讀', '未读') }
}
</script>

<template>
  <n-space vertical size="large">
    <n-space align="center">
      <h2 style="margin: 0">{{ tr('通知確認看板', '通知确认看板') }}</h2>
      <n-select
        :value="sid" :options="semesterOptions" style="width: 220px"
        :placeholder="tr('選擇學期', '选择学期')" @update:value="onSemesterChange"
      />
      <n-checkbox v-model:checked="unackOnly" data-testid="board-unackonly" @update:checked="reload">
        {{ tr('只看未確認', '只看未确认') }}
      </n-checkbox>
    </n-space>

    <n-empty v-if="!entries.length" :description="tr('沒有符合條件的通知', '没有符合条件的通知')" />
    <table v-else class="data-table" data-testid="board-table">
      <thead>
        <tr><th>{{ tr('教師', '教师') }}</th><th>{{ tr('類型', '类型') }}</th><th>{{ tr('內容', '内容') }}</th><th>{{ tr('狀態', '状态') }}</th><th>{{ tr('操作', '操作') }}</th></tr>
      </thead>
      <tbody>
        <tr v-for="e in entries" :key="e.id" data-testid="board-row">
          <td>{{ e.teacher_name }}</td>
          <td>{{ TYPE_LABEL[e.type] ?? e.type }}</td>
          <td>{{ e.title }}</td>
          <td>
            <n-tag size="small" :type="ackTag(e).type as never">{{ ackTag(e).label }}</n-tag>
          </td>
          <td>
            <n-button
              v-if="!e.acknowledged_at" size="tiny" data-testid="board-remind"
              @click="onRemind(e)"
            >
              {{ tr('再次提醒', '再次提醒') }}
            </n-button>
            <n-text v-else depth="3">—</n-text>
          </td>
        </tr>
      </tbody>
    </table>
  </n-space>
</template>

<style scoped>
.data-table { border-collapse: collapse; width: 100%; }
.data-table th, .data-table td {
  border: 1px solid var(--n-border-color, #e0e0e0); padding: 6px 10px; text-align: left;
}
.data-table th { background: rgba(128, 128, 128, 0.08); font-weight: 600; }
</style>
