<script setup lang="ts">
import { NButton, NCard, NEmpty, NSpace, NStatistic, NTag } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listSemesters } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'
import { getDailyBoard } from '@/api/substitutionLog'
import type { DailyBoard } from '@/api/substitutionLog'
import { getSemesterSummary } from '@/api/wizard'
import type { SemesterSummary } from '@/api/wizard'
import { useProfileText } from '@/composables/useProfileText'

const router = useRouter()
const { isMainland, tr } = useProfileText()
const semester = ref<SemesterListItem | null>(null)
const summary = ref<SemesterSummary | null>(null)
const board = ref<DailyBoard | null>(null)
const loading = ref(true)
const weekdays = computed(() => isMainland.value
  ? ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  : ['週日', '週一', '週二', '週三', '週四', '週五', '週六'])

const boardDateLabel = computed(() =>
  board.value ? `${board.value.date}(${weekdays.value[board.value.weekday % 7]})` : '')
const pendingCount = computed(() =>
  board.value ? board.value.entries.filter((e) => !e.disposed).length : 0)

onMounted(async () => {
  try {
    const semesters = await listSemesters()
    if (semesters.length) {
      semester.value = semesters[0]
      ;[summary.value, board.value] = await Promise.all([
        getSemesterSummary(semesters[0].id),
        getDailyBoard(semesters[0].id).catch(() => null),
      ])
    }
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <n-space vertical size="large">
    <h1 style="margin: 0">{{ tr('儀表板', '仪表盘') }}</h1>

    <n-card v-if="semester" :title="`${semester.label} · ${tr('資料摘要', '资料摘要')}`">
      <n-space size="large">
        <n-statistic :label="tr('科目', '科目')" :value="summary?.subjects ?? 0" />
        <n-statistic :label="tr('教師', '教师')" :value="summary?.teachers ?? 0" />
        <n-statistic :label="tr('班級', '班级')" :value="summary?.classes ?? 0" />
        <n-statistic :label="tr('場地', '场地')" :value="summary?.rooms ?? 0" />
      </n-space>
    </n-card>

    <n-card v-else-if="!loading">
      <n-empty :description="tr('尚未建立任何學期資料', '尚未建立任何学期资料')">
        <template #extra>
          <n-button type="primary" @click="router.push({ name: 'wizard' })">
            {{ tr('前往設定精靈', '前往设置向导') }}
          </n-button>
        </template>
      </n-empty>
    </n-card>

    <n-card
      v-if="semester && board"
      data-testid="dash-today"
      :title="`${tr('今日調代課', '今日调代课')} · ${boardDateLabel}`"
    >
      <n-space v-if="board.entries.length" vertical>
        <n-space align="center">
          <n-statistic :label="tr('今日異動', '今日变动')" :value="board.entries.length" />
          <n-tag v-if="pendingCount" type="warning" data-testid="dash-pending">
            {{ tr('尚有', '尚有') }} {{ pendingCount }} {{ tr('節待安排', '节待安排') }}
          </n-tag>
          <n-tag v-else type="success">{{ tr('今日皆已安排', '今日均已安排') }}</n-tag>
        </n-space>
        <div>
          <n-button type="primary" @click="router.push({ name: 'daily-board' })">
            {{ tr('查看今日看板', '查看今日看板') }}
          </n-button>
        </div>
      </n-space>
      <n-empty v-else :description="tr('今日無調代課', '今日无调代课')" data-testid="dash-noboard" />
    </n-card>
  </n-space>
</template>
