<script setup lang="ts">
import { AlertTriangle, Pencil, Plus, RefreshCw, Save, Trash2, X } from '@lucide/vue'
import {
  NAlert, NButton, NEmpty, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSpin, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref, watch } from 'vue'
import { apiErrorMessage } from '@/api/client'
import {
  TRACK_LABELS, commitClassBatch, createClassUnit, deleteClassUnit, listClassUnits, listTeachers,
  previewClassBatch, updateClassUnit,
} from '@/api/basedata'
import type { ClassBatchCandidate, ClassTrack, ClassUnit, Teacher } from '@/api/basedata'
import { highRiskConfirmation } from '@/api/highRisk'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import './basedata-workspace.css'

const props = withDefaults(
  defineProps<{ semesterId: number; canEdit?: boolean; canDelete?: boolean }>(),
  { canEdit: true, canDelete: false },
)
const emit = defineEmits<{ changed: [] }>()
const message = useMessage()

const items = ref<ClassUnit[]>([])
const teachers = ref<Teacher[]>([])
const search = ref('')
const loading = ref(true)
const loadError = ref<string | null>(null)
const saving = ref(false)
const deletingId = ref<number | null>(null)

const trackLabels: Record<ClassTrack, string> = {
  elementary: '小学',
  junior_high: '初中',
  senior_high: '普通高中',
  comprehensive: '综合高中',
  vocational: '中等职业学校',
}
function trackLabel(track: ClassTrack) {
  return trackLabels[track]
}
const trackOptions = computed(() => (Object.keys(TRACK_LABELS) as ClassTrack[]).map((track) => ({
  label: trackLabel(track),
  value: track,
})))
const teacherOptions = computed(() => teachers.value.map((teacher) => ({ label: teacher.name, value: teacher.id })))
async function reload() {
  loading.value = true
  loadError.value = null
  try {
    items.value = await listClassUnits(props.semesterId, search.value || undefined)
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取班级，请重试。')
  } finally {
    loading.value = false
  }
}

async function loadInitialData() {
  loading.value = true
  loadError.value = null
  try {
    const [classItems, teacherItems] = await Promise.all([
      listClassUnits(props.semesterId, search.value || undefined),
      listTeachers(props.semesterId),
    ])
    items.value = classItems
    teachers.value = teacherItems
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取班级，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(loadInitialData)

const show = ref(false)
const editingId = ref<number | null>(null)
const form = ref<{
  grade: number
  name: string
  track: ClassTrack
  department: string
  student_count: number | null
  homeroom_teacher_id: number | null
  period_table_id: number | null
}>({
  grade: 1,
  name: '',
  track: 'elementary',
  department: '',
  student_count: null,
  homeroom_teacher_id: null,
  period_table_id: null,
})

const showDepartment = computed(() => form.value.track === 'vocational')

const gradeLabels: Record<ClassTrack, Record<number, string>> = {
  elementary: { 1: '一年级', 2: '二年级', 3: '三年级', 4: '四年级', 5: '五年级', 6: '六年级' },
  junior_high: { 7: '七年级', 8: '八年级', 9: '九年级' },
  senior_high: { 10: '高一', 11: '高二', 12: '高三' },
  comprehensive: { 10: '高一', 11: '高二', 12: '高三' },
  vocational: { 1: '中职一年级', 2: '中职二年级', 3: '中职三年级' },
}
const batchGradeOptions = computed(() => Object.entries(gradeLabels[batchForm.value.track]).map(([value, label]) => ({
  label,
  value: Number(value),
})))

const batchForm = ref<{
  grade: number
  track: ClassTrack
  start_number: number
  end_number: number
}>({
  grade: 1,
  track: 'elementary',
  start_number: 1,
  end_number: 3,
})
const batchShow = ref(false)
const batchLoading = ref(false)
const batchSaving = ref(false)
const batchError = ref<string | null>(null)
const batchPreviewFingerprint = ref<string | null>(null)
const batchRows = ref<ClassBatchCandidate[]>([])
const batchExistingNames = computed(() => new Set(items.value.map((item) => item.name)))
const batchRowConflict = (row: ClassBatchCandidate) => {
  const sameName = batchRows.value.some((other) => other.row_id !== row.row_id && other.name.trim() === row.name.trim())
  if (sameName) return `批次内班级名称重复：${row.name}`
  if (batchExistingNames.value.has(row.name.trim())) return `本学期已有班级「${row.name.trim()}」`
  if (row.name === row.default_name) return row.conflict
  return null
}
const batchReady = computed(() => (
  Boolean(batchPreviewFingerprint.value)
  && batchRows.value.length > 0
  && batchRows.value.every((row) => row.name.trim() && !batchRowConflict(row))
))

watch(() => batchForm.value.track, (track) => {
  const firstGrade = Number(Object.keys(gradeLabels[track])[0])
  if (!gradeLabels[track][batchForm.value.grade]) batchForm.value.grade = firstGrade
  batchPreviewFingerprint.value = null
  batchRows.value = []
})
watch(() => batchForm.value.grade, () => {
  batchPreviewFingerprint.value = null
  batchRows.value = []
})
watch(() => [batchForm.value.start_number, batchForm.value.end_number], () => {
  batchPreviewFingerprint.value = null
  batchRows.value = []
})

function openBatch() {
  if (!props.canEdit) return
  batchForm.value = { grade: 1, track: 'elementary', start_number: 1, end_number: 3 }
  batchError.value = null
  batchPreviewFingerprint.value = null
  batchRows.value = []
  batchShow.value = true
}
function closeBatch() {
  if (!batchSaving.value && !batchLoading.value) batchShow.value = false
}
async function previewBatch() {
  if (!props.canEdit || batchLoading.value || batchSaving.value) return
  batchError.value = null
  if (batchForm.value.end_number < batchForm.value.start_number) {
    batchError.value = '结束班号不能小于起始班号'
    return
  }
  if (batchForm.value.end_number - batchForm.value.start_number + 1 > 100) {
    batchError.value = '一次最多生成 100 个班级'
    return
  }
  batchLoading.value = true
  try {
    const preview = await previewClassBatch(props.semesterId, batchForm.value)
    batchPreviewFingerprint.value = preview.fingerprint
    batchRows.value = preview.candidates.map((row) => ({ ...row }))
  } catch (error) {
    batchError.value = apiErrorMessage(error, '暂时无法生成班级候选，请重试。')
  } finally {
    batchLoading.value = false
  }
}
function addBatchRow() {
  const rowId = Math.max(0, ...batchRows.value.map((row) => row.row_id)) + 1
  batchRows.value.push({
    row_id: rowId,
    name: '',
    default_name: '',
    department: null,
    student_count: null,
    homeroom_teacher_id: null,
    conflict: null,
  })
}
function removeBatchRow(rowId: number) {
  batchRows.value = batchRows.value.filter((row) => row.row_id !== rowId)
}
async function saveBatch() {
  if (!props.canEdit || !batchReady.value || batchSaving.value || !batchPreviewFingerprint.value) return
  batchSaving.value = true
  batchError.value = null
  try {
    const result = await commitClassBatch(props.semesterId, {
      grade: batchForm.value.grade,
      track: batchForm.value.track,
      preview_fingerprint: batchPreviewFingerprint.value,
      candidates: batchRows.value.map((row) => ({
        row_id: row.row_id,
        name: row.name.trim(),
        department: batchForm.value.track === 'vocational' ? row.department || null : null,
        student_count: row.student_count,
        homeroom_teacher_id: row.homeroom_teacher_id,
      })),
    })
    batchShow.value = false
    message.success(result.idempotent ? '班级已存在，未重复创建' : `已保存 ${result.classes.length} 个班级`)
    await reload()
    emit('changed')
  } catch (error) {
    batchError.value = apiErrorMessage(error, '批量保存失败，未写入任何班级。')
  } finally {
    batchSaving.value = false
  }
}

function openCreate() {
  if (!props.canEdit) return
  editingId.value = null
  form.value = {
    grade: 1,
    name: '',
    track: 'elementary',
    department: '',
    student_count: null,
    homeroom_teacher_id: null,
    period_table_id: null,
  }
  show.value = true
}
function openEdit(classUnit: ClassUnit) {
  if (!props.canEdit) return
  editingId.value = classUnit.id
  form.value = {
    grade: classUnit.grade,
    name: classUnit.name,
    track: classUnit.track,
    department: classUnit.department ?? '',
    student_count: classUnit.student_count,
    homeroom_teacher_id: classUnit.homeroom_teacher_id,
    period_table_id: classUnit.period_table_id,
  }
  show.value = true
}
function closeModal() {
  if (!saving.value) show.value = false
}

async function save() {
  if (!props.canEdit || saving.value) return
  if (!form.value.name) {
    message.warning('请输入班级名称')
    return
  }
  saving.value = true
  const body = {
    grade: form.value.grade,
    name: form.value.name,
    track: form.value.track,
    department: showDepartment.value ? form.value.department || null : null,
    student_count: form.value.student_count,
    homeroom_teacher_id: form.value.homeroom_teacher_id,
    period_table_id: form.value.period_table_id,
  }
  try {
    if (editingId.value) await updateClassUnit(editingId.value, body)
    else await createClassUnit(props.semesterId, body)
    show.value = false
    message.success('已保存')
    await reload()
    emit('changed')
  } catch (error) {
    message.error(apiErrorMessage(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function remove(classUnit: ClassUnit) {
  if (!props.canDelete || deletingId.value !== null) return
  deletingId.value = classUnit.id
  try {
    await deleteClassUnit(classUnit.id, highRiskConfirmation(`class-unit:${classUnit.id}`))
    message.success('已删除')
    await reload()
    emit('changed')
  } catch (error) {
    message.error(apiErrorMessage(error, '删除失败'))
  } finally {
    deletingId.value = null
  }
}
</script>

<template>
  <div class="basedata-tab-content" :aria-busy="loading">
    <div class="basedata-toolbar">
      <div class="basedata-toolbar-main">
        <n-input
          v-model:value="search"
          class="basedata-search"
          :placeholder="'搜索班级名称'"
          clearable
          aria-label="搜索班级名称"
          @input="reload"
        />
      </div>
      <div v-if="canEdit" class="basedata-toolbar-actions">
        <n-button secondary data-testid="class-add-batch" @click="openBatch">
          <template #icon><Plus :size="16" aria-hidden="true" /></template>
          {{ '批量设置班级' }}
        </n-button>
        <n-button type="primary" data-testid="class-add" @click="openCreate">
          <template #icon><Plus :size="16" aria-hidden="true" /></template>
          {{ '新增班级' }}
        </n-button>
      </div>
    </div>

    <n-alert v-if="!canEdit" class="basedata-readonly" type="info" data-testid="classes-readonly">
      {{ '仅可查看班级，当前角色没有新增、编辑或删除权限。' }}
    </n-alert>

    <section v-if="loading && !items.length" class="basedata-state" data-testid="classes-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取班级' }}</strong>
      <span>{{ '班级列表加载完成后会显示在这里。' }}</span>
    </section>
    <section v-else-if="loadError" class="basedata-state basedata-state-error" data-testid="classes-error" role="alert">
      <AlertTriangle :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '当前列表未更新。' }}</span>
      <n-button type="primary" data-testid="classes-retry" @click="loadInitialData">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>
    <section v-else-if="!items.length" class="basedata-state" data-testid="classes-empty" role="status">
      <n-empty :description="'暂无班级'" />
    </section>
    <div v-else class="basedata-table-scroll" data-testid="classes-table-scroll" tabindex="0" aria-label="班级列表，可横向滚动">
      <table class="basedata-data-table basedata-data-table--classes" data-testid="classes-table">
        <thead>
          <tr>
            <th>{{ '年级' }}</th>
            <th>{{ '班级名称' }}</th>
            <th>{{ '学段' }}</th>
            <th>{{ '专业' }}</th>
            <th>{{ '班主任' }}</th>
            <th>{{ '人数' }}</th>
            <th v-if="canEdit">{{ '操作' }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="classUnit in items" :key="classUnit.id">
            <td>{{ classUnit.grade }}</td>
            <td>{{ classUnit.name }}</td>
            <td>{{ trackLabel(classUnit.track) }}</td>
            <td>{{ classUnit.department || '—' }}</td>
            <td>{{ classUnit.homeroom_teacher?.name || '—' }}</td>
            <td>{{ classUnit.student_count ?? '—' }}</td>
            <td v-if="canEdit">
              <div class="basedata-command-group">
                <n-button size="small" :data-testid="`class-edit-${classUnit.id}`" @click="openEdit(classUnit)">
                  <template #icon><Pencil :size="14" aria-hidden="true" /></template>
                  {{ '编辑' }}
                </n-button>
                <n-popconfirm v-if="canDelete" :disabled="deletingId !== null" @positive-click="remove(classUnit)">
                  <template #trigger>
                    <n-button
                      size="small"
                      type="error"
                      ghost
                      :data-testid="`class-delete-${classUnit.id}`"
                      :loading="deletingId === classUnit.id"
                      :disabled="deletingId !== null"
                    >
                      <template #icon><Trash2 :size="14" aria-hidden="true" /></template>
                      {{ '删除' }}
                    </n-button>
                  </template>
                  {{ `将永久删除班级“${classUnit.name}”及其排课单位关联。确定继续吗？` }}
                </n-popconfirm>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <n-modal v-if="canEdit" v-model:show="show" preset="card" class="basedata-modal" :title="editingId ? '编辑班级' : '新增班级'">
      <div class="basedata-form">
        <div class="basedata-form-row">
          <div class="basedata-field">
            <span class="basedata-field-label">{{ '年级' }}</span>
            <n-input-number
              v-model:value="form.grade"
              :min="1"
              :max="12"
              :input-props="{ 'aria-label': '年级' }"
            />
          </div>
          <div class="basedata-field">
            <label for="class-name">{{ '班级名称' }}</label>
            <n-input
              id="class-name"
              v-model:value="form.name"
              data-testid="class-name"
              :placeholder="'如：1班、七年级1班'"
              :input-props="{ 'aria-label': '班级名称' }"
            />
          </div>
        </div>
        <div class="basedata-field">
          <span class="basedata-field-label">{{ '学段' }}</span>
          <n-select v-model:value="form.track" v-accessible-select="'学段'" :options="trackOptions" />
        </div>
        <div v-if="showDepartment" class="basedata-field">
          <label for="class-department">{{ '专业（中职）' }}</label>
          <n-input
            id="class-department"
            v-model:value="form.department"
            :placeholder="'如：机械专业'"
            :input-props="{ 'aria-label': '专业（中职）' }"
          />
        </div>
        <div class="basedata-field">
          <span class="basedata-field-label">{{ '班主任（可选）' }}</span>
          <n-select
            v-model:value="form.homeroom_teacher_id"
            v-accessible-select="'班主任'"
            :options="teacherOptions"
            clearable
            :placeholder="'（未指定）'"
          />
        </div>
        <div class="basedata-field">
          <span class="basedata-field-label">{{ '人数（可选）' }}</span>
          <n-input-number
            v-model:value="form.student_count"
            :min="0"
            :input-props="{ 'aria-label': '人数' }"
          />
        </div>
        <div class="basedata-modal-actions">
          <n-button quaternary :disabled="!canEdit || saving" @click="closeModal">
            <template #icon><X :size="15" aria-hidden="true" /></template>
            {{ '取消' }}
          </n-button>
          <n-button type="primary" data-testid="class-save" :loading="saving" :disabled="!canEdit || saving" @click="save">
            <template #icon><Save :size="15" aria-hidden="true" /></template>
            {{ '保存' }}
          </n-button>
        </div>
      </div>
    </n-modal>

    <n-modal v-if="canEdit" v-model:show="batchShow" preset="card" class="basedata-modal basedata-modal--wide" :title="'批量设置班级'">
      <div class="basedata-form">
        <p class="basedata-batch-intro">{{ '按同一学段和年级生成候选，确认前可逐行修改或删除。' }}</p>
        <div class="basedata-form-row">
          <div class="basedata-field">
            <span class="basedata-field-label">{{ '学段' }}</span>
            <n-select v-model:value="batchForm.track" v-accessible-select="'批量学段'" :options="trackOptions" data-testid="class-batch-track" />
          </div>
          <div class="basedata-field">
            <span class="basedata-field-label">{{ '年级' }}</span>
            <n-select v-model:value="batchForm.grade" v-accessible-select="'批量年级'" :options="batchGradeOptions" data-testid="class-batch-grade" />
          </div>
        </div>
        <div class="basedata-form-row">
          <div class="basedata-field">
            <span class="basedata-field-label">{{ '起始班号' }}</span>
            <n-input-number v-model:value="batchForm.start_number" :min="1" :max="1000" data-testid="class-batch-start" :input-props="{ 'aria-label': '起始班号' }" />
          </div>
          <div class="basedata-field">
            <span class="basedata-field-label">{{ '结束班号' }}</span>
            <n-input-number v-model:value="batchForm.end_number" :min="1" :max="1000" data-testid="class-batch-end" :input-props="{ 'aria-label': '结束班号' }" />
          </div>
        </div>
        <n-alert v-if="batchError" type="error" data-testid="class-batch-error">{{ batchError }}</n-alert>
        <div class="basedata-modal-actions">
          <n-button type="primary" :loading="batchLoading" data-testid="class-batch-preview" @click="previewBatch">
            <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
            {{ '生成候选' }}
          </n-button>
        </div>

        <template v-if="batchPreviewFingerprint">
          <div class="basedata-batch-preview-heading">
            <div>
              <strong>{{ `${gradeLabels[batchForm.track][batchForm.grade]}候选班级` }}</strong>
              <span>{{ `共 ${batchRows.length} 个，可编辑后一次保存` }}</span>
            </div>
            <n-button size="small" secondary data-testid="class-batch-add-row" @click="addBatchRow">
              <template #icon><Plus :size="14" aria-hidden="true" /></template>
              {{ '添加一行' }}
            </n-button>
          </div>
          <div class="basedata-batch-table-scroll" data-testid="class-batch-table-scroll" tabindex="0" aria-label="班级候选列表，可横向滚动">
            <table class="basedata-data-table basedata-batch-table" data-testid="class-batch-table">
              <thead>
                <tr>
                  <th>{{ '班级名称' }}</th>
                  <th>{{ '人数' }}</th>
                  <th>{{ '班主任' }}</th>
                  <th v-if="batchForm.track === 'vocational'">{{ '专业' }}</th>
                  <th>{{ '状态' }}</th>
                  <th>{{ '操作' }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in batchRows" :key="row.row_id">
                  <td>
                    <n-input v-model:value="row.name" size="small" :data-testid="`class-batch-name-${row.row_id}`" :status="batchRowConflict(row) ? 'error' : undefined" :input-props="{ 'aria-label': '班级名称' }" />
                    <span v-if="batchRowConflict(row)" class="basedata-batch-row-error">{{ batchRowConflict(row) }}</span>
                  </td>
                  <td><n-input-number v-model:value="row.student_count" size="small" :min="0" :input-props="{ 'aria-label': '人数' }" /></td>
                  <td><n-select v-model:value="row.homeroom_teacher_id" v-accessible-select="'班主任'" size="small" clearable :options="teacherOptions" :placeholder="'未指定'" /></td>
                  <td v-if="batchForm.track === 'vocational'"><n-input v-model:value="row.department" size="small" :placeholder="'可选'" :input-props="{ 'aria-label': '专业' }" /></td>
                  <td><span :class="batchRowConflict(row) ? 'basedata-batch-conflict' : 'basedata-batch-ok'">{{ batchRowConflict(row) || '可保存' }}</span></td>
                  <td>
                    <n-button size="small" type="error" ghost :title="'删除候选行'" :aria-label="'删除候选行'" @click="removeBatchRow(row.row_id)">
                      <template #icon><Trash2 :size="14" aria-hidden="true" /></template>
                    </n-button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="basedata-modal-actions">
            <n-button quaternary :disabled="batchSaving" @click="closeBatch">
              <template #icon><X :size="15" aria-hidden="true" /></template>
              {{ '取消' }}
            </n-button>
            <n-button type="primary" :loading="batchSaving" :disabled="!batchReady" data-testid="class-batch-save" @click="saveBatch">
              <template #icon><Save :size="15" aria-hidden="true" /></template>
              {{ '确认保存' }}
            </n-button>
          </div>
        </template>
      </div>
    </n-modal>
  </div>
</template>
