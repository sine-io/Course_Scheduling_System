<script setup lang="ts">
import {
  NButton, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSpace, NText, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import type { ApiError } from '@/api/client'
import {
  TRACK_LABELS, createClassUnit, deleteClassUnit, listClassUnits, listTeachers, updateClassUnit,
} from '@/api/basedata'
import type { ClassTrack, ClassUnit, Teacher } from '@/api/basedata'
import { getSemester } from '@/api/semesters'
import type { PeriodTable } from '@/api/semesters'
import { useProfileText } from '@/composables/useProfileText'

const props = defineProps<{ semesterId: number }>()
const message = useMessage()
const { isMainland, tr } = useProfileText()

const items = ref<ClassUnit[]>([])
const teachers = ref<Teacher[]>([])
const periodTables = ref<PeriodTable[]>([])
const search = ref('')

const mainlandTrackLabels: Record<ClassTrack, string> = {
  elementary: '小学', junior_high: '初中', senior_high: '普通高中',
  comprehensive: '综合高中', vocational: '中等职业学校',
}
function trackLabel(track: ClassTrack) {
  return isMainland.value ? mainlandTrackLabels[track] : TRACK_LABELS[track]
}
const trackOptions = computed(() => (Object.keys(TRACK_LABELS) as ClassTrack[]).map((track) => ({
  label: trackLabel(track), value: track,
})))
const teacherOptions = computed(() => teachers.value.map((t) => ({ label: t.name, value: t.id })))
// 僅當該學期有 ≥2 套節次表時才需要讓使用者為班級指定(混合學制)
const showPeriodTable = computed(() => periodTables.value.length >= 2)
const periodTableOptions = computed(() =>
  periodTables.value.map((t) => ({ label: t.name + (t.is_default ? tr('(預設)', '（默认）') : ''), value: t.id })),
)
function tableName(id: number | null): string {
  if (id === null) return tr('預設', '默认')
  return periodTables.value.find((t) => t.id === id)?.name ?? '—'
}

async function reload() {
  items.value = await listClassUnits(props.semesterId, search.value || undefined)
}
onMounted(async () => {
  teachers.value = await listTeachers(props.semesterId)
  periodTables.value = (await getSemester(props.semesterId)).period_tables
  await reload()
})

const show = ref(false)
const editingId = ref<number | null>(null)
const form = ref<{
  grade: number; name: string; track: ClassTrack; department: string
  student_count: number | null; homeroom_teacher_id: number | null; period_table_id: number | null
}>({
  grade: 1, name: '', track: 'elementary', department: '',
  student_count: null, homeroom_teacher_id: null, period_table_id: null,
})

// 技高才顯示群科欄位
const showDepartment = computed(() => form.value.track === 'vocational')

function openCreate() {
  editingId.value = null
  form.value = {
    grade: 1, name: '', track: 'elementary', department: '',
    student_count: null, homeroom_teacher_id: null, period_table_id: null,
  }
  show.value = true
}
function openEdit(c: ClassUnit) {
  editingId.value = c.id
  form.value = {
    grade: c.grade, name: c.name, track: c.track, department: c.department ?? '',
    student_count: c.student_count, homeroom_teacher_id: c.homeroom_teacher_id,
    period_table_id: c.period_table_id ?? null,
  }
  show.value = true
}

async function save() {
  if (!form.value.name) {
    message.warning(tr('請輸入班名', '请输入班级名称'))
    return
  }
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
    message.success(tr('已儲存', '已保存'))
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail || tr('儲存失敗', '保存失败'))
  }
}

async function remove(c: ClassUnit) {
  try {
    await deleteClassUnit(c.id)
    message.success(tr('已刪除', '已删除'))
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail || tr('刪除失敗', '删除失败'))
  }
}
</script>

<template>
  <n-space vertical>
    <n-space>
      <n-input v-model:value="search" :placeholder="tr('搜尋班名', '搜索班级名称')" clearable style="width: 200px" @input="reload" />
      <n-button type="primary" data-testid="class-add" @click="openCreate">{{ tr('新增班級', '新增班级') }}</n-button>
    </n-space>

    <table class="data-table">
      <thead>
        <tr>
          <th>{{ tr('年級', '年级') }}</th><th>{{ tr('班名', '班级名称') }}</th><th>{{ tr('學制', '学段') }}</th><th>{{ tr('群科', '专业') }}</th><th>{{ tr('導師', '班主任') }}</th>
          <th v-if="showPeriodTable">{{ tr('節次表', '节次表') }}</th><th>{{ tr('人數', '人数') }}</th><th>{{ tr('操作', '操作') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in items" :key="c.id">
          <td>{{ c.grade }}</td>
          <td>{{ c.name }}</td>
          <td>{{ trackLabel(c.track) }}</td>
          <td>{{ c.department || '—' }}</td>
          <td>{{ c.homeroom_teacher?.name || '—' }}</td>
          <td v-if="showPeriodTable">{{ tableName(c.period_table_id) }}</td>
          <td>{{ c.student_count ?? '—' }}</td>
          <td>
            <n-space>
              <n-button size="tiny" @click="openEdit(c)">{{ tr('編輯', '编辑') }}</n-button>
              <n-popconfirm @positive-click="remove(c)">
                <template #trigger><n-button size="tiny" type="error" ghost>{{ tr('刪除', '删除') }}</n-button></template>
                {{ tr('確定刪除此班級?', '确定删除此班级吗？') }}
              </n-popconfirm>
            </n-space>
          </td>
        </tr>
        <tr v-if="items.length === 0">
          <td :colspan="showPeriodTable ? 8 : 7"><n-text depth="3">{{ tr('尚無班級', '暂无班级') }}</n-text></td>
        </tr>
      </tbody>
    </table>

    <n-modal v-model:show="show" preset="card" :title="editingId ? tr('編輯班級', '编辑班级') : tr('新增班級', '新增班级')" style="max-width: 440px">
      <n-space vertical>
        <n-space>
          <n-space vertical>
            <n-text>{{ tr('年級', '年级') }}</n-text>
            <n-input-number v-model:value="form.grade" :min="1" :max="12" style="width: 120px" />
          </n-space>
          <n-space vertical style="flex: 1">
            <n-text>{{ tr('班名', '班级名称') }}</n-text>
            <n-input v-model:value="form.name" data-testid="class-name" :placeholder="tr('如:忠、甲、301', '如：1班、七年级1班')" />
          </n-space>
        </n-space>
        <n-text>{{ tr('學制', '学段') }}</n-text>
        <n-select v-model:value="form.track" :options="trackOptions" />
        <template v-if="showDepartment">
          <n-text>{{ tr('群科(技高)', '专业（中职）') }}</n-text>
          <n-input v-model:value="form.department" :placeholder="tr('如:機械科', '如：机械专业')" />
        </template>
        <n-text>{{ tr('導師(選填)', '班主任（可选）') }}</n-text>
        <n-select
          v-model:value="form.homeroom_teacher_id"
          :options="teacherOptions"
          clearable
          :placeholder="tr('（未指定）', '（未指定）')"
        />
        <template v-if="showPeriodTable">
          <n-text>{{ tr('節次表', '节次表') }}</n-text>
          <n-select
            v-model:value="form.period_table_id"
            data-testid="class-period-table"
            :options="periodTableOptions"
            clearable
            :placeholder="tr('使用學期預設', '使用学期默认设置')"
          />
        </template>
        <n-text>{{ tr('人數(選填)', '人数（可选）') }}</n-text>
        <n-input-number v-model:value="form.student_count" :min="0" />
        <n-button type="primary" data-testid="class-save" @click="save">{{ tr('儲存', '保存') }}</n-button>
      </n-space>
    </n-modal>
  </n-space>
</template>

<style scoped>
.data-table { border-collapse: collapse; width: 100%; }
.data-table th, .data-table td { border: 1px solid var(--n-border-color, #e0e0e0); padding: 8px 10px; text-align: left; }
.data-table th { background: rgba(128,128,128,0.08); font-weight: 600; }
</style>
