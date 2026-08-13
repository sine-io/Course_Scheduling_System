<script setup lang="ts">
import { AlertTriangle, Pencil, Plus, RefreshCw, Save, Trash2, X } from '@lucide/vue'
import {
  NAlert, NButton, NEmpty, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSpin, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import {
  TRACK_LABELS, createClassUnit, deleteClassUnit, listClassUnits, listTeachers, updateClassUnit,
} from '@/api/basedata'
import type { ClassTrack, ClassUnit, Teacher } from '@/api/basedata'
import { getSemester } from '@/api/semesters'
import type { PeriodTable } from '@/api/semesters'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import './basedata-workspace.css'

const props = withDefaults(defineProps<{ semesterId: number; canEdit?: boolean }>(), { canEdit: true })
const message = useMessage()

const items = ref<ClassUnit[]>([])
const teachers = ref<Teacher[]>([])
const periodTables = ref<PeriodTable[]>([])
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
const showPeriodTable = computed(() => periodTables.value.length >= 2)
const periodTableOptions = computed(() =>
  periodTables.value.map((table) => ({
    label: table.name + (table.is_default ? '（默认）' : ''),
    value: table.id,
  })),
)
function tableName(id: number | null): string {
  if (id === null) return '默认'
  return periodTables.value.find((table) => table.id === id)?.name ?? '—'
}
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
    const [classItems, teacherItems, semester] = await Promise.all([
      listClassUnits(props.semesterId, search.value || undefined),
      listTeachers(props.semesterId),
      getSemester(props.semesterId),
    ])
    items.value = classItems
    teachers.value = teacherItems
    periodTables.value = semester.period_tables
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

function openCreate() {
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
  editingId.value = classUnit.id
  form.value = {
    grade: classUnit.grade,
    name: classUnit.name,
    track: classUnit.track,
    department: classUnit.department ?? '',
    student_count: classUnit.student_count,
    homeroom_teacher_id: classUnit.homeroom_teacher_id,
    period_table_id: classUnit.period_table_id ?? null,
  }
  show.value = true
}
function closeModal() {
  if (!saving.value) show.value = false
}

async function save() {
  if (saving.value) return
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
    period_table_id: showPeriodTable.value ? form.value.period_table_id : null,
  }
  try {
    if (editingId.value) await updateClassUnit(editingId.value, body)
    else await createClassUnit(props.semesterId, body)
    show.value = false
    message.success('已保存')
    await reload()
  } catch (error) {
    message.error(apiErrorMessage(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function remove(classUnit: ClassUnit) {
  if (deletingId.value !== null) return
  deletingId.value = classUnit.id
  try {
    await deleteClassUnit(classUnit.id)
    message.success('已删除')
    await reload()
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
            <th v-if="showPeriodTable">{{ '作息时间表' }}</th>
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
            <td v-if="showPeriodTable">{{ tableName(classUnit.period_table_id) }}</td>
            <td>{{ classUnit.student_count ?? '—' }}</td>
            <td v-if="canEdit">
              <div class="basedata-command-group">
                <n-button size="small" :data-testid="`class-edit-${classUnit.id}`" @click="openEdit(classUnit)">
                  <template #icon><Pencil :size="14" aria-hidden="true" /></template>
                  {{ '编辑' }}
                </n-button>
                <n-popconfirm :disabled="deletingId !== null" @positive-click="remove(classUnit)">
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
                  {{ '确定删除此班级吗？' }}
                </n-popconfirm>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <n-modal v-model:show="show" preset="card" class="basedata-modal" :title="editingId ? '编辑班级' : '新增班级'">
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
        <div v-if="showPeriodTable" class="basedata-field">
          <span class="basedata-field-label">{{ '作息时间表' }}</span>
          <n-select
            v-model:value="form.period_table_id"
            v-accessible-select="'作息时间表'"
            data-testid="class-period-table"
            :options="periodTableOptions"
            clearable
            :placeholder="'使用学期默认设置'"
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
          <n-button quaternary :disabled="saving" @click="closeModal">
            <template #icon><X :size="15" aria-hidden="true" /></template>
            {{ '取消' }}
          </n-button>
          <n-button type="primary" data-testid="class-save" :loading="saving" :disabled="saving" @click="save">
            <template #icon><Save :size="15" aria-hidden="true" /></template>
            {{ '保存' }}
          </n-button>
        </div>
      </div>
    </n-modal>
  </div>
</template>
