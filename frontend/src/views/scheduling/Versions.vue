<script setup lang="ts">
import {
  AlertTriangle, CheckCircle2, Copy, FileCheck2, History, Pencil, Plus, RefreshCw,
  Rocket, ShieldCheck, Trash2,
} from '@lucide/vue'
import {
  NAlert, NButton, NEmpty, NInput, NModal, NPopconfirm, NSelect, NSpin, NTag,
  useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import { listSemesters } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'
import {
  checkPublication, createTimetable, deleteTimetable, duplicateTimetable, getCompleteness,
  listTimetables, publishTimetable, renameTimetable,
} from '@/api/timetables'
import type { PublicationCheck, TimetableBrief } from '@/api/timetables'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import { useAuthStore } from '@/stores/auth'
import { useSemesterContextStore } from '@/stores/semesterContext'
import './scheduling-workspace.css'

type ActionKind = 'create' | 'check' | 'publish' | 'duplicate' | 'rename' | 'delete' | 'confirm-publish'

const message = useMessage()
const auth = useAuthStore()
const semesterContext = useSemesterContextStore()

const semesters = ref<SemesterListItem[]>([])
const sid = ref<number | null>(null)
const canEdit = computed(() => (
  (auth.hasRole('admin') || auth.hasRole('scheduler'))
  && (!semesterContext.authoritative || semesterContext.isCurrent(sid.value))
))
const items = ref<TimetableBrief[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
const actionError = ref<string | null>(null)
const pending = ref<{ kind: ActionKind; id: number | null } | null>(null)
const semesterOptions = computed(() => semesters.value.map((s) => ({ label: s.label, value: s.id })))

const statusType: Record<string, 'default' | 'success' | 'warning' | 'info'> = {
  draft: 'warning', checked: 'info', published: 'success', archived: 'default',
}
const timetableStatusLabels: Record<string, string> = {
  draft: '草稿', checked: '检查通过', published: '已发布', archived: '已归档',
}

function publicationState(timetable: TimetableBrief): string {
  return timetable.publication_state || timetable.status
}

function isPending(kind: ActionKind, id: number | null = null) {
  return pending.value?.kind === kind && pending.value.id === id
}

async function reload() {
  if (!sid.value) {
    items.value = []
    return
  }
  items.value = await listTimetables(sid.value)
}

async function loadPage() {
  loading.value = true
  loadError.value = null
  try {
    await semesterContext.load()
    semesters.value = await listSemesters()
    sid.value = semesters.value.find((semester) => semester.is_current)?.id
      ?? semesterContext.currentSemesterId
      ?? semesters.value[0]?.id
      ?? null
    await reload()
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取课表版本，请重试。')
  } finally {
    loading.value = false
  }
}

async function onSemesterChange(id: number) {
  if (pending.value) return
  loading.value = true
  loadError.value = null
  actionError.value = null
  sid.value = id
  checkText.value = ''
  try {
    await reload()
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取课表版本，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(loadPage)

async function runAction(
  kind: ActionKind,
  id: number | null,
  action: () => Promise<void>,
  fallback: string,
) {
  if (pending.value) return
  pending.value = { kind, id }
  actionError.value = null
  try {
    await action()
  } catch (error) {
    actionError.value = apiErrorMessage(error, fallback)
    message.error(actionError.value)
  } finally {
    pending.value = null
  }
}

async function onCreate() {
  if (!canEdit.value || !sid.value) return
  await runAction('create', null, async () => {
    await createTimetable(sid.value!, `草稿${String.fromCharCode(65 + items.value.length)}`)
    message.success('已创建草稿')
    await reload()
  }, '创建草稿失败，请稍后重试。')
}

async function onDuplicate(timetable: TimetableBrief) {
  if (!canEdit.value) return
  await runAction('duplicate', timetable.id, async () => {
    await duplicateTimetable(timetable.id, `${timetable.name} 副本`)
    message.success('已复制为新草稿')
    await reload()
  }, '复制课表失败，请稍后重试。')
}

async function onDelete(timetable: TimetableBrief) {
  if (!canEdit.value) return
  await runAction('delete', timetable.id, async () => {
    await deleteTimetable(timetable.id)
    message.success(`已删除“${timetable.name}”`)
    await reload()
  }, '删除课表版本失败，请稍后重试。')
}

const renameShow = ref(false)
const renameTarget = ref<TimetableBrief | null>(null)
const renameValue = ref('')

function openRename(timetable: TimetableBrief) {
  if (!canEdit.value) return
  renameTarget.value = timetable
  renameValue.value = timetable.name
  renameShow.value = true
}

async function onRename() {
  const target = renameTarget.value
  const nextName = renameValue.value.trim()
  if (!canEdit.value || !target || !nextName) return
  await runAction('rename', target.id, async () => {
    await renameTimetable(target.id, nextName)
    renameShow.value = false
    message.success('已改名')
    await reload()
  }, '课表改名失败，请稍后重试。')
}

const confirmShow = ref(false)
const checkedPublication = ref<PublicationCheck | null>(null)
const publishTarget = ref<TimetableBrief | null>(null)

function warnStale(count?: number) {
  if (count && count > 0) {
    message.warning(
      `有 ${count} 条今日之后的调课与代课按先前课表安排，请到今日看板/调课与代课记录重新检查`,
      { duration: 8000 },
    )
  }
}

async function onPublish(timetable: TimetableBrief) {
  if (!canEdit.value) return
  if (pending.value) return
  pending.value = { kind: 'publish', id: timetable.id }
  actionError.value = null
  try {
    checkedPublication.value = await checkPublication(timetable.id)
    publishTarget.value = timetable
    confirmShow.value = true
    await reload()
  } catch (error) {
    actionError.value = apiErrorMessage(error, '发布检查失败，请稍后重试。')
    message.error(actionError.value)
  } finally {
    pending.value = null
  }
}

function closePublishConfirmation() {
  if (pending.value) return
  confirmShow.value = false
}

async function onConfirmPublish() {
  const target = publishTarget.value
  const checked = checkedPublication.value
  if (!canEdit.value || !target || !checked) return
  await runAction('confirm-publish', target.id, async () => {
    const result = await publishTimetable(target.id, {
      fingerprint: checked.fingerprint,
      force: checked.requires_force,
    })
    confirmShow.value = false
    message.success(checked.requires_force
      ? '已发布（仍有未排完教学任务）'
      : `已发布“${target.name}”`)
    warnStale(result.stale_affected)
    await reload()
  }, '发布失败，请稍后重试。')
}

const checkText = ref('')
async function onCheck(timetable: TimetableBrief) {
  await runAction('check', timetable.id, async () => {
    const currentDraft = canEdit.value && timetable.status === 'draft'
      && (!semesterContext.authoritative || semesterContext.isCurrent(timetable.semester_id))
    const publication = currentDraft ? await checkPublication(timetable.id) : null
    const completeness = publication?.completeness ?? await getCompleteness(timetable.id)
    checkText.value = completeness.complete
      ? `“${timetable.name}”教学任务已排完（${completeness.placed}/${completeness.required} 节）`
      : `“${timetable.name}”尚有 ${completeness.remaining} 节未排（${completeness.placed}/${completeness.required}）`
    if (publication) await reload()
  }, '完整性检查失败，请稍后重试。')
}
</script>

<template>
  <div class="scheduling-page versions-page" data-testid="versions-page">
    <header class="scheduling-page-header">
      <div>
        <p class="scheduling-eyebrow">{{ '版本控制' }}</p>
        <h1>{{ '版本与发布' }}</h1>
        <p>{{ '核对草稿完整性，发布正式课表，并保留历史版本供追溯。' }}</p>
      </div>
      <div class="scheduling-header-actions">
        <n-select
          v-if="semesters.length"
          v-accessible-select="'选择工作学期'"
          :value="sid"
          :options="semesterOptions"
          :placeholder="'选择学期'"
          data-testid="versions-semester"
          :disabled="loading || pending !== null"
          @update:value="onSemesterChange"
        />
        <n-button
          v-if="canEdit"
          type="primary"
          data-testid="v-new"
          :loading="isPending('create')"
          :disabled="pending !== null"
          @click="onCreate"
        >
          <template #icon><Plus :size="16" aria-hidden="true" /></template>
          {{ '新增草稿' }}
        </n-button>
      </div>
    </header>

    <section v-if="loading" class="scheduling-state" data-testid="versions-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取课表版本' }}</strong>
      <span>{{ '草稿、已发布版本和归档记录加载完成后会显示在这里。' }}</span>
    </section>
    <section v-else-if="loadError" class="scheduling-state scheduling-state-error" data-testid="versions-error" role="alert">
      <AlertTriangle :size="23" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '当前页面没有修改任何课表版本。' }}</span>
      <n-button type="primary" data-testid="versions-retry" @click="loadPage">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>
    <section v-else-if="!sid" class="scheduling-state" data-testid="versions-empty-semester">
      <History :size="24" aria-hidden="true" />
      <strong>{{ '尚未创建可用学期' }}</strong>
      <span>{{ '创建学期后，可在此维护草稿、发布版本和归档记录。' }}</span>
    </section>

    <template v-else>
      <n-alert v-if="!canEdit" type="info" data-testid="versions-restricted">
        <template #icon><ShieldCheck :size="17" aria-hidden="true" /></template>
        {{ '当前角色可查看版本并执行完整性检查，新增、复制、改名、发布和删除仅对排课管理员开放。' }}
      </n-alert>
      <n-alert type="info" data-testid="versions-policy">
        {{ '同学期可有多份草稿并存，但至多一份“已发布”。发布新版本时，旧的已发布课表会自动转为已归档。已发布/已归档的课表为快照；要修改请先复制为新草稿。' }}
      </n-alert>
      <n-alert
        v-if="actionError"
        type="error"
        closable
        data-testid="versions-action-error"
        role="alert"
        @close="actionError = null"
      >
        {{ actionError }}
      </n-alert>
      <n-alert v-if="checkText" type="default" closable data-testid="versions-check-result" @close="checkText = ''">
        <template #icon><CheckCircle2 :size="17" aria-hidden="true" /></template>
        {{ checkText }}
      </n-alert>

      <section class="scheduling-panel versions-list-panel">
        <header class="scheduling-panel-heading compact-heading">
          <div>
            <p class="scheduling-eyebrow">{{ '学期版本' }}</p>
            <h2>{{ '课表版本列表' }}</h2>
            <p>{{ items.length ? `当前共有 ${items.length} 个版本` : '当前学期还没有课表版本' }}</p>
          </div>
          <History :size="20" class="scheduling-heading-icon" aria-hidden="true" />
        </header>
        <div v-if="items.length === 0" class="scheduling-inline-empty" data-testid="versions-empty">
          <n-empty :description="'暂无课表版本'" />
        </div>
        <div
          v-else
          class="scheduling-table-scroll versions-table-scroll"
          data-testid="versions-table-scroll"
          tabindex="0"
          aria-label="课表版本列表，可横向滚动"
        >
          <table class="scheduling-data-table versions-data-table">
            <thead><tr><th>{{ '名称' }}</th><th>{{ '发布状态' }}</th><th>{{ '已排单元格' }}</th><th>{{ '操作' }}</th></tr></thead>
            <tbody>
              <tr v-for="timetable in items" :key="timetable.id" :data-testid="`v-row-${timetable.name}`">
                <td><strong>{{ timetable.name }}</strong></td>
                <td>
                  <n-tag :type="statusType[publicationState(timetable)]" size="small" :data-testid="`v-status-${timetable.name}`">
                    {{ timetableStatusLabels[publicationState(timetable)] ?? publicationState(timetable) }}
                  </n-tag>
                </td>
                <td>{{ timetable.entry_count }}</td>
                <td>
                  <div class="scheduling-row-actions versions-row-actions">
                    <n-button
                      size="tiny"
                      data-testid="v-check"
                      :loading="isPending('check', timetable.id)"
                      :disabled="pending !== null"
                      @click="onCheck(timetable)"
                    >
                      <template #icon><FileCheck2 :size="13" aria-hidden="true" /></template>
                      {{ '完整性检查' }}
                    </n-button>
                    <n-button
                      v-if="canEdit && timetable.status === 'draft'"
                      size="tiny"
                      type="primary"
                      data-testid="v-publish"
                      :loading="isPending('publish', timetable.id)"
                      :disabled="pending !== null"
                      @click="onPublish(timetable)"
                    >
                      <template #icon><Rocket :size="13" aria-hidden="true" /></template>
                      {{ '发布' }}
                    </n-button>
                    <n-button
                      v-if="canEdit"
                      size="tiny"
                      data-testid="v-duplicate"
                      :loading="isPending('duplicate', timetable.id)"
                      :disabled="pending !== null"
                      @click="onDuplicate(timetable)"
                    >
                      <template #icon><Copy :size="13" aria-hidden="true" /></template>
                      {{ '复制' }}
                    </n-button>
                    <n-button v-if="canEdit" size="tiny" :disabled="pending !== null" @click="openRename(timetable)">
                      <template #icon><Pencil :size="13" aria-hidden="true" /></template>
                      {{ '改名' }}
                    </n-button>
                    <n-popconfirm v-if="canEdit" @positive-click="onDelete(timetable)">
                      <template #trigger>
                        <n-button
                          size="tiny"
                          type="error"
                          ghost
                          :loading="isPending('delete', timetable.id)"
                          :disabled="pending !== null"
                        >
                          <template #icon><Trash2 :size="13" aria-hidden="true" /></template>
                          {{ '删除' }}
                        </n-button>
                      </template>
                      {{ `确定删除“${timetable.name}”吗？其单元格将一并移除。` }}
                    </n-popconfirm>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <n-modal v-if="canEdit" v-model:show="renameShow" preset="card" :title="'课表改名'" class="versions-modal">
      <div class="scheduling-form">
        <label class="scheduling-field">
          <span>{{ '课表名称' }}</span>
          <n-input v-model:value="renameValue" data-testid="v-rename-input" maxlength="80" />
        </label>
        <div class="scheduling-modal-actions">
          <n-button @click="renameShow = false">{{ '取消' }}</n-button>
          <n-button
            type="primary"
            data-testid="v-rename-save"
            :loading="isPending('rename', renameTarget?.id ?? null)"
            :disabled="!canEdit || !renameValue.trim() || pending !== null"
            @click="onRename"
          >
            {{ '保存' }}
          </n-button>
        </div>
      </div>
    </n-modal>

    <n-modal
      v-if="canEdit"
      v-model:show="confirmShow"
      preset="card"
      :title="checkedPublication?.requires_force ? '确认发布未完整课表' : '确认发布课表'"
      class="versions-publish-modal"
    >
      <div class="versions-warning-content" data-testid="v-publish-confirmation">
        <n-alert :type="checkedPublication?.passed ? 'success' : 'warning'">
          {{ checkedPublication?.passed
            ? '发布检查已通过。确认后，此版本将成为当前正式课表。'
            : '发布检查未通过。确认后仍会发布，未排教学任务不会出现在正式课表中。' }}
        </n-alert>
        <dl class="versions-confirmation-summary">
          <div><dt>{{ '目标学期' }}</dt><dd>{{ checkedPublication?.semester.label }}</dd></div>
          <div><dt>{{ '目标版本' }}</dt><dd>{{ checkedPublication?.version.name }}（#{{ checkedPublication?.version.id }}）</dd></div>
          <div>
            <dt>{{ '完整性结果' }}</dt>
            <dd>
              {{ checkedPublication?.completeness.placed }} / {{ checkedPublication?.completeness.required }} {{ '节已排' }}
              <span v-if="checkedPublication?.completeness.remaining">
                {{ `，剩余 ${checkedPublication.completeness.remaining} 节` }}
              </span>
            </dd>
          </div>
        </dl>
        <div
          v-if="checkedPublication?.completeness.unplaced.length"
          class="scheduling-table-scroll"
          tabindex="0"
          aria-label="未排教学任务，可横向滚动"
        >
          <table class="scheduling-data-table versions-unplaced-table" data-testid="v-unplaced">
            <thead><tr><th>{{ '班级' }}</th><th>{{ '科目' }}</th><th>{{ '教师' }}</th><th>{{ '未排节数' }}</th><th>{{ '原因' }}</th></tr></thead>
            <tbody>
              <tr v-for="unplaced in checkedPublication?.completeness.unplaced ?? []" :key="unplaced.course_assignment_id">
                <td>{{ unplaced.classes.join('、') }}</td><td>{{ unplaced.subject }}</td><td>{{ unplaced.teachers.join('、') }}</td>
                <td><strong class="versions-danger-text">{{ unplaced.remaining }}</strong> / {{ unplaced.required }}</td>
                <td>{{ unplaced.reason || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="scheduling-modal-actions">
          <n-button
            data-testid="v-publish-cancel"
            :disabled="!canEdit || pending !== null"
            @click="closePublishConfirmation"
          >
            {{ '取消' }}
          </n-button>
          <n-button
            :type="checkedPublication?.requires_force ? 'warning' : 'primary'"
            data-testid="v-confirm-publish"
            :loading="isPending('confirm-publish', publishTarget?.id ?? null)"
            :disabled="!canEdit || pending !== null"
            @click="onConfirmPublish"
          >
            {{ checkedPublication?.requires_force ? '仍要发布' : '确认发布' }}
          </n-button>
        </div>
      </div>
    </n-modal>
  </div>
</template>

<style scoped>
.versions-page { max-width: 1440px; }
.versions-list-panel { display: grid; gap: 16px; }
.versions-data-table { min-width: 760px; }
.versions-data-table th:nth-child(1) { min-width: 180px; }
.versions-data-table th:nth-child(4) { min-width: 390px; }
.versions-row-actions { flex-wrap: nowrap; }
.versions-warning-content { display: grid; gap: 16px; }
.versions-confirmation-summary { display: grid; gap: 1px; margin: 0; overflow: hidden; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); background: var(--app-border); }
.versions-confirmation-summary > div { display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 12px; padding: 10px 12px; background: var(--app-surface); }
.versions-confirmation-summary dt { color: var(--app-text-muted); font-size: 12px; font-weight: 650; }
.versions-confirmation-summary dd { min-width: 0; margin: 0; overflow-wrap: anywhere; font-size: 13px; font-weight: 600; }
.versions-unplaced-table { min-width: 680px; }
.versions-danger-text { color: var(--app-danger); }
:global(.versions-modal) { width: min(420px, calc(100vw - 32px)); }
:global(.versions-publish-modal) { width: min(700px, calc(100vw - 32px)); }

@media (max-width: 560px) {
  .versions-data-table { min-width: 720px; }
}
</style>
