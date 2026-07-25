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

const message = useMessage()

const semesters = ref<SemesterListItem[]>([])
const sid = ref<number | null>(null)
const items = ref<TimetableBrief[]>([])
const semesterOptions = computed(() => semesters.value.map((s) => ({ label: s.label, value: s.id })))

const statusType: Record<string, 'default' | 'success' | 'warning'> = {
  draft: 'warning', published: 'success', archived: 'default',
}
const timetableStatusLabels = computed<Record<string, string>>(() => ({
  draft: '草稿',
  published: '已发布',
  archived: '已归档',
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
  await createTimetable(sid.value, `${'草稿'}${String.fromCharCode(65 + items.value.length)}`)
  message.success('已创建草稿')
  await reload()
}
async function onDuplicate(t: TimetableBrief) {
  await duplicateTimetable(t.id, `${t.name} ${'副本'}`)
  message.success('已复制为新草稿')
  await reload()
}
async function onDelete(id: number) {
  await deleteTimetable(id)
  message.success('已删除')
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
  message.success('已改名')
  await reload()
}

// 发布(未排完 → 警告列表 → 可强制发布)
const warnShow = ref(false)
const report = ref<Completeness | null>(null)
const publishTarget = ref<TimetableBrief | null>(null)

function warnStale(n?: number) {
  if (n && n > 0) {
    message.warning(
      `有 ${n} 条今日之后的调课与代课按先前课表安排，请到今日看板/调课与代课记录重新检查`,
      { duration: 8000 })
  }
}

async function onPublish(t: TimetableBrief) {
  publishTarget.value = t
  try {
    const r = await publishTimetable(t.id)
    message.success(`已发布“${t.name}”`)
    warnStale(r.stale_affected)
    await reload()
  } catch (e) {
    const r = publishReport((e as ApiError).detail)
    if (r) {
      report.value = r
      warnShow.value = true
    } else {
      message.error((e as ApiError).detail as string || '发布失败')
    }
  }
}
async function onForcePublish() {
  if (!publishTarget.value) return
  try {
    const r = await publishTimetable(publishTarget.value.id, true)
    warnShow.value = false
    message.success('已强制发布（仍有未排完教学任务）')
    warnStale(r.stale_affected)
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail as string || '发布失败')
  }
}

/** 发布前预览完整性(不改状态)。 */
const checkText = ref('')
async function onCheck(t: TimetableBrief) {
  const r = await getCompleteness(t.id)
  checkText.value = r.complete
    ? `“${t.name}”教学任务已排完（${r.placed}/${r.required} 节）`
    : `“${t.name}”尚有 ${r.remaining} 节未排（${r.placed}/${r.required}）`
}
</script>

<template>
  <n-space vertical size="large">
    <n-space align="center">
      <h1 style="margin: 0">{{ '版本与发布' }}</h1>
      <n-select
        :value="sid" :options="semesterOptions" :placeholder="'选择学期'"
        style="width: 220px" @update:value="onSemesterChange"
      />
      <n-button type="primary" size="small" data-testid="v-new" @click="onCreate">{{ '新增草稿' }}</n-button>
    </n-space>

    <n-alert type="info" :show-icon="true">
      {{ '同学期可有多份草稿并存，但至多一份“已发布”。发布新版本时，旧的已发布课表会自动转为已归档。已发布/已归档的课表为快照，不可再编辑；要修改请先复制为新草稿。' }}
    </n-alert>

    <n-alert v-if="checkText" type="default" closable @close="checkText = ''">{{ checkText }}</n-alert>

    <n-card size="small">
      <n-empty v-if="items.length === 0" :description="'暂无课表版本'" />
      <table v-else class="data-table">
        <thead>
          <tr><th>{{ '名称' }}</th><th>{{ '状态' }}</th><th>{{ '已排单元格' }}</th><th>{{ '操作' }}</th></tr>
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
                <n-button size="tiny" data-testid="v-check" @click="onCheck(t)">{{ '完整性检查' }}</n-button>
                <n-button
                  v-if="t.status === 'draft'" size="tiny" type="primary"
                  data-testid="v-publish" @click="onPublish(t)"
                >
                  {{ '发布' }}
                </n-button>
                <n-button size="tiny" data-testid="v-duplicate" @click="onDuplicate(t)">{{ '复制' }}</n-button>
                <n-button size="tiny" @click="openRename(t)">{{ '改名' }}</n-button>
                <n-popconfirm @positive-click="onDelete(t.id)">
                  <template #trigger><n-button size="tiny" type="error" ghost>{{ '删除' }}</n-button></template>
                  {{ '确定删除此课表版本吗？其单元格将一并移除。' }}
                </n-popconfirm>
              </n-space>
            </td>
          </tr>
        </tbody>
      </table>
    </n-card>

    <n-modal v-model:show="renameShow" preset="card" :title="'课表改名'" style="max-width: 400px">
      <n-space vertical>
        <n-input v-model:value="renameValue" data-testid="v-rename-input" />
        <n-button type="primary" data-testid="v-rename-save" @click="onRename">{{ '保存' }}</n-button>
      </n-space>
    </n-modal>

    <n-modal
      v-model:show="warnShow" preset="card" :title="'尚有教学任务未排完'"
      style="max-width: 620px"
    >
      <n-space vertical>
        <n-alert type="warning" :show-icon="true">
          {{ '共' }} {{ report?.remaining }} {{ '节未排入（已排' }} {{ report?.placed }} / {{ '应排' }} {{ report?.required }} {{ '节）。仍可强制发布，未排教学任务将不出现在课表上。' }}
        </n-alert>
        <table class="data-table" data-testid="v-unplaced">
          <thead>
            <tr><th>{{ '班级' }}</th><th>{{ '科目' }}</th><th>{{ '教师' }}</th><th>{{ '未排节数' }}</th><th>{{ '原因' }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="u in report?.unplaced ?? []" :key="u.course_assignment_id">
              <td>{{ u.classes.join('、') }}</td>
              <td>{{ u.subject }}</td>
              <td>{{ u.teachers.join('、') }}</td>
              <td><n-text type="error">{{ u.remaining }}</n-text> / {{ u.required }}</td>
              <!-- 自动排课留下的原因(手动未排完则无);草稿发布后仍查得到 -->
              <td>{{ u.reason || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <n-space justify="end">
          <n-button @click="warnShow = false">{{ '取消' }}</n-button>
          <n-button type="warning" data-testid="v-force-publish" @click="onForcePublish">
            {{ '仍要发布' }}
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
