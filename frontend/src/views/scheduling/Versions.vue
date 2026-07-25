<script setup lang="ts">
import {
  NAlert, NButton, NCard, NEmpty, NInput, NModal, NPopconfirm, NSelect, NSpace, NTag, NText,
  useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import type { ApiError } from '@/api/client'
import { listSemesters } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'
import {
  createTimetable, deleteTimetable, duplicateTimetable, getCompleteness,
  listTimetables, publishReport, publishTimetable, renameTimetable,
} from '@/api/timetables'
import type { Completeness, TimetableBrief } from '@/api/timetables'
import { useAppConfigStore } from '@/stores/appConfig'

const message = useMessage()
const appConfig = useAppConfigStore()
const mainland = computed(() => appConfig.isMainland)
const tr = (tw: string, cn: string) => mainland.value ? cn : tw

const semesters = ref<SemesterListItem[]>([])
const sid = ref<number | null>(null)
const items = ref<TimetableBrief[]>([])
const semesterOptions = computed(() => semesters.value.map((s) => ({ label: s.label, value: s.id })))

const statusType: Record<string, 'default' | 'success' | 'warning'> = {
  draft: 'warning', published: 'success', archived: 'default',
}
const timetableStatusLabels = computed<Record<string, string>>(() => ({
  draft: tr('草稿', '草稿'),
  published: tr('已發布', '已发布'),
  archived: tr('已封存', '已归档'),
}))

async function reload() {
  if (sid.value) items.value = await listTimetables(sid.value)
}
async function onSemesterChange(id: number) {
  sid.value = id
  await reload()
}
onMounted(async () => {
  semesters.value = await listSemesters()
  if (semesters.value.length) await onSemesterChange(semesters.value[0].id)
})

async function onCreate() {
  if (!sid.value) return
  await createTimetable(sid.value, `${tr('草稿', '草稿')}${String.fromCharCode(65 + items.value.length)}`)
  message.success(tr('已建立草稿', '已建立草稿'))
  await reload()
}
async function onDuplicate(t: TimetableBrief) {
  await duplicateTimetable(t.id, `${t.name} ${tr('複本', '副本')}`)
  message.success(tr('已複製為新草稿', '已复制为新草稿'))
  await reload()
}
async function onDelete(id: number) {
  await deleteTimetable(id)
  message.success(tr('已刪除', '已删除'))
  await reload()
}

// 改名
const renameShow = ref(false)
const renameTarget = ref<TimetableBrief | null>(null)
const renameValue = ref('')
function openRename(t: TimetableBrief) {
  renameTarget.value = t
  renameValue.value = t.name
  renameShow.value = true
}
async function onRename() {
  if (!renameTarget.value || !renameValue.value) return
  await renameTimetable(renameTarget.value.id, renameValue.value)
  renameShow.value = false
  message.success(tr('已改名', '已改名'))
  await reload()
}

// 發布(未排完 → 警告清單 → 可強制發布)
const warnShow = ref(false)
const report = ref<Completeness | null>(null)
const publishTarget = ref<TimetableBrief | null>(null)

function warnStale(n?: number) {
  if (n && n > 0) {
    message.warning(
      tr(
        `有 ${n} 筆今日之後的調代課是依先前課表安排的,請至今日看板/調代課紀錄重新檢視`,
        `有 ${n} 条今日之后的调代课按先前课表安排，请到今日看板/调代课记录重新检查`,
      ),
      { duration: 8000 })
  }
}

async function onPublish(t: TimetableBrief) {
  publishTarget.value = t
  try {
    const r = await publishTimetable(t.id)
    message.success(tr(`已發布「${t.name}」`, `已发布“${t.name}”`))
    warnStale(r.stale_affected)
    await reload()
  } catch (e) {
    const r = publishReport((e as ApiError).detail)
    if (r) {
      report.value = r
      warnShow.value = true
    } else {
      message.error((e as ApiError).detail as string || tr('發布失敗', '发布失败'))
    }
  }
}
async function onForcePublish() {
  if (!publishTarget.value) return
  try {
    const r = await publishTimetable(publishTarget.value.id, true)
    warnShow.value = false
    message.success(tr('已強制發布(仍有未排完課務)', '已强制发布（仍有未排完课务）'))
    warnStale(r.stale_affected)
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail as string || tr('發布失敗', '发布失败'))
  }
}

/** 發布前預覽完整性(不改狀態)。 */
const checkText = ref('')
async function onCheck(t: TimetableBrief) {
  const r = await getCompleteness(t.id)
  checkText.value = r.complete
    ? tr(`「${t.name}」課務已排完(${r.placed}/${r.required} 節)`, `“${t.name}”课务已排完（${r.placed}/${r.required} 节）`)
    : tr(`「${t.name}」尚有 ${r.remaining} 節未排(${r.placed}/${r.required})`, `“${t.name}”尚有 ${r.remaining} 节未排（${r.placed}/${r.required}）`)
}
</script>

<template>
  <n-space vertical size="large">
    <n-space align="center">
      <h1 style="margin: 0">{{ tr('版本與發布', '版本与发布') }}</h1>
      <n-select
        :value="sid" :options="semesterOptions" :placeholder="tr('選擇學期', '选择学期')"
        style="width: 220px" @update:value="onSemesterChange"
      />
      <n-button type="primary" size="small" data-testid="v-new" @click="onCreate">{{ tr('新增草稿', '新增草稿') }}</n-button>
    </n-space>

    <n-alert type="info" :show-icon="true">
      {{ tr('同學期可有多份草稿並存,但至多一份「已發布」。發布新版本時,舊的已發布課表會自動轉為已封存。已發布/已封存的課表為快照,不可再編輯;要修改請先複製為新草稿。', '同学期可有多份草稿并存，但至多一份“已发布”。发布新版本时，旧的已发布课表会自动转为已归档。已发布/已归档的课表为快照，不可再编辑；要修改请先复制为新草稿。') }}
    </n-alert>

    <n-alert v-if="checkText" type="default" closable @close="checkText = ''">{{ checkText }}</n-alert>

    <n-card size="small">
      <n-empty v-if="items.length === 0" :description="tr('尚無課表版本', '暂无课表版本')" />
      <table v-else class="data-table">
        <thead>
          <tr><th>{{ tr('名稱', '名称') }}</th><th>{{ tr('狀態', '状态') }}</th><th>{{ tr('已排格位', '已排格位') }}</th><th>{{ tr('操作', '操作') }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="t in items" :key="t.id" :data-testid="`v-row-${t.name}`">
            <td>{{ t.name }}</td>
            <td>
              <n-tag :type="statusType[t.status]" size="small" :data-testid="`v-status-${t.name}`">
                {{ timetableStatusLabels[t.status] ?? t.status }}
              </n-tag>
            </td>
            <td>{{ t.entry_count }}</td>
            <td>
              <n-space>
                <n-button size="tiny" data-testid="v-check" @click="onCheck(t)">{{ tr('完整性檢查', '完整性检查') }}</n-button>
                <n-button
                  v-if="t.status === 'draft'" size="tiny" type="primary"
                  data-testid="v-publish" @click="onPublish(t)"
                >
                  {{ tr('發布', '发布') }}
                </n-button>
                <n-button size="tiny" data-testid="v-duplicate" @click="onDuplicate(t)">{{ tr('複製', '复制') }}</n-button>
                <n-button size="tiny" @click="openRename(t)">{{ tr('改名', '改名') }}</n-button>
                <n-popconfirm @positive-click="onDelete(t.id)">
                  <template #trigger><n-button size="tiny" type="error" ghost>{{ tr('刪除', '删除') }}</n-button></template>
                  {{ tr('確定刪除此課表版本?其格位將一併移除。', '确定删除此课表版本吗？其格位将一并移除。') }}
                </n-popconfirm>
              </n-space>
            </td>
          </tr>
        </tbody>
      </table>
    </n-card>

    <n-modal v-model:show="renameShow" preset="card" :title="tr('課表改名', '课表改名')" style="max-width: 400px">
      <n-space vertical>
        <n-input v-model:value="renameValue" data-testid="v-rename-input" />
        <n-button type="primary" data-testid="v-rename-save" @click="onRename">{{ tr('儲存', '保存') }}</n-button>
      </n-space>
    </n-modal>

    <n-modal
      v-model:show="warnShow" preset="card" :title="tr('尚有課務未排完', '尚有课务未排完')"
      style="max-width: 620px"
    >
      <n-space vertical>
        <n-alert type="warning" :show-icon="true">
          {{ tr('共', '共') }} {{ report?.remaining }} {{ tr('節未排入(已排', '节未排入（已排') }} {{ report?.placed }} / {{ tr('應排', '应排') }} {{ report?.required }} {{ tr('節)。仍可強制發布,未排課務將不出現在課表上。', '节）。仍可强制发布，未排课务将不出现在课表上。') }}
        </n-alert>
        <table class="data-table" data-testid="v-unplaced">
          <thead>
            <tr><th>{{ tr('班級', '班级') }}</th><th>{{ tr('科目', '科目') }}</th><th>{{ tr('教師', '教师') }}</th><th>{{ tr('未排節數', '未排节数') }}</th><th>{{ tr('原因', '原因') }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="u in report?.unplaced ?? []" :key="u.course_assignment_id">
              <td>{{ u.classes.join('、') }}</td>
              <td>{{ u.subject }}</td>
              <td>{{ u.teachers.join('、') }}</td>
              <td><n-text type="error">{{ u.remaining }}</n-text> / {{ u.required }}</td>
              <!-- 自動排課留下的原因(手動未排完則無);草稿發布後仍查得到 -->
              <td>{{ u.reason || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <n-space justify="end">
          <n-button @click="warnShow = false">{{ tr('取消', '取消') }}</n-button>
          <n-button type="warning" data-testid="v-force-publish" @click="onForcePublish">
            {{ tr('仍要發布', '仍要发布') }}
          </n-button>
        </n-space>
      </n-space>
    </n-modal>
  </n-space>
</template>

<style scoped>
.data-table { border-collapse: collapse; width: 100%; }
.data-table th, .data-table td { border: 1px solid var(--n-border-color, #e0e0e0); padding: 8px 10px; text-align: left; }
.data-table th { background: rgba(128,128,128,0.08); font-weight: 600; }
</style>
