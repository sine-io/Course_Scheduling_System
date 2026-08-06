<script setup lang="ts">
import {
  NAlert, NButton, NCard, NCheckbox, NDivider, NEmpty, NInputNumber, NModal, NPopconfirm,
  NRadioButton, NRadioGroup, NSelect, NSpace, NTag, NText, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import type { ApiError } from '@/api/client'
import {
  createAssignment, createGroup, deleteAssignment, deleteGroup, listAssignments, listGroups,
  updateAssignment, teacherLoad, classLoad,
} from '@/api/assignments'
import type { Assignment, AssignmentPayload, ClassLoad, SchedulingUnit, TeacherLoad } from '@/api/assignments'
import { listClassUnits, listRooms, listSubjects, listTeachers, ROOM_TYPE_LABELS } from '@/api/basedata'
import type { ClassUnit, Room, Subject, Teacher } from '@/api/basedata'
import { listSemesters } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'

const message = useMessage()

const semesters = ref<SemesterListItem[]>([])
const sid = ref<number | null>(null)
const semesterOptions = computed(() => semesters.value.map((s) => ({ label: s.label, value: s.id })))

const classes = ref<ClassUnit[]>([])
const subjects = ref<Subject[]>([])
const teachers = ref<Teacher[]>([])
const rooms = ref<Room[]>([])
const groups = ref<SchedulingUnit[]>([])
const assignments = ref<Assignment[]>([])
const loads = ref<TeacherLoad[]>([])
const classLoads = ref<ClassLoad[]>([])

const classOptions = computed(() =>
  classes.value.map((c) => ({ label: `${c.grade}年${c.name}`, value: c.id })))
const subjectOptions = computed(() => subjects.value.map((s) => ({ label: s.name, value: s.id })))
const teacherOptions = computed(() => teachers.value.map((t) => ({ label: t.name, value: t.id })))
const roomOptions = computed(() => rooms.value.map((r) => ({ label: r.name, value: r.id })))
const roomTypeLabels: Record<string, string> = {
  normal: '普通教室', special: '专用教室', workshop: '实训场地', outdoor: '户外',
}
function roomTypeLabel(type: string) {
  return roomTypeLabels[type] ?? type
}
const roomTypeOptions = computed(() => Object.keys(ROOM_TYPE_LABELS).map((value) => ({
  label: roomTypeLabel(value), value,
})))
const groupOptions = computed(() => groups.value.map((g) => ({ label: g.name, value: g.id })))

async function loadBase(id: number) {
  ;[classes.value, subjects.value, teachers.value, rooms.value] = await Promise.all([
    listClassUnits(id), listSubjects(id), listTeachers(id), listRooms(id),
  ])
}
async function reloadAll(id: number) {
  ;[assignments.value, groups.value, loads.value, classLoads.value] = await Promise.all([
    listAssignments(id), listGroups(id), teacherLoad(id), classLoad(id),
  ])
}
async function onSemesterChange(id: number) {
  sid.value = id
  await loadBase(id)
  await reloadAll(id)
}

onMounted(async () => {
  semesters.value = await listSemesters()
  if (semesters.value.length) await onSemesterChange(semesters.value[0].id)
})

const overCapacity = computed(() => classLoads.value.filter((c) => c.over_capacity))
function loadTagType(load: TeacherLoad): 'success' | 'error' | 'warning' | 'info' {
  if (load.over_limit) return 'error'
  if (load.delta > 0) return 'warning'
  if (load.delta < 0) return 'info'
  return 'success'
}

function loadTagText(load: TeacherLoad): string {
  if (load.delta > 0) {
    return load.over_limit
      ? `+${load.delta} 超过上限 ${load.max_overtime}`
      : `+${load.delta} 超课时`
  }
  return load.delta < 0 ? `${load.delta} 不足` : '刚好'
}

// ── 教学任务 modal ──
const show = ref(false)
const editingId = ref<number | null>(null)
interface AForm {
  target: 'single' | 'group'
  class_id: number | null
  scheduling_unit_id: number | null
  subject_id: number | null
  teacher_ids: number[]
  lead_teacher_id: number | null
  periods_per_week: number
  block_rules: { block_size: number; count_per_week: number }[]
  required_room_type: string | null
  room_id: number | null
  lock_room: boolean
}
function emptyForm(): AForm {
  return {
    target: 'single', class_id: null, scheduling_unit_id: null, subject_id: null,
    teacher_ids: [], lead_teacher_id: null, periods_per_week: 1, block_rules: [],
    required_room_type: null, room_id: null, lock_room: false,
  }
}
const form = ref<AForm>(emptyForm())
const leadOptions = computed(() =>
  teachers.value.filter((t) => form.value.teacher_ids.includes(t.id))
    .map((t) => ({ label: t.name, value: t.id })))

function openCreate() {
  editingId.value = null
  form.value = emptyForm()
  show.value = true
}
function openEdit(a: Assignment) {
  editingId.value = a.id
  const isGroup = a.scheduling_unit.unit_type === 'group'
  form.value = {
    target: isGroup ? 'group' : 'single',
    class_id: isGroup ? null : (a.scheduling_unit.classes[0]?.id ?? null),
    scheduling_unit_id: isGroup ? a.scheduling_unit.id : null,
    subject_id: a.subject.id,
    teacher_ids: a.teachers.map((t) => t.teacher_id),
    lead_teacher_id: a.teachers.find((t) => t.is_lead)?.teacher_id ?? null,
    periods_per_week: a.periods_per_week,
    block_rules: a.block_rules.map((b) => ({ block_size: b.block_size, count_per_week: b.count_per_week })),
    required_room_type: a.required_room_type,
    room_id: a.room_id,
    lock_room: a.lock_room,
  }
  show.value = true
}
function addBlock() {
  form.value.block_rules.push({ block_size: 2, count_per_week: 1 })
}
function removeBlock(i: number) {
  form.value.block_rules.splice(i, 1)
}

async function save() {
  const f = form.value
  if (f.target === 'single' && !f.class_id) return message.warning('请选择班级')
  if (f.target === 'group' && !f.scheduling_unit_id) return message.warning('请选择走班分组')
  if (!f.subject_id) return message.warning('请选择科目')
  if (f.teacher_ids.length === 0) return message.warning('请至少指定一位教师')
  const lead = f.lead_teacher_id && f.teacher_ids.includes(f.lead_teacher_id)
    ? f.lead_teacher_id : f.teacher_ids[0]
  const payload: AssignmentPayload = {
    class_id: f.target === 'single' ? f.class_id : null,
    scheduling_unit_id: f.target === 'group' ? f.scheduling_unit_id : null,
    subject_id: f.subject_id,
    periods_per_week: f.periods_per_week,
    teachers: f.teacher_ids.map((id) => ({ teacher_id: id, is_lead: id === lead })),
    block_rules: f.block_rules,
    required_room_type: (f.required_room_type as AssignmentPayload['required_room_type']) || null,
    room_id: f.room_id,
    lock_room: f.lock_room,
  }
  try {
    if (editingId.value) await updateAssignment(editingId.value, payload)
    else await createAssignment(sid.value!, payload)
    show.value = false
    message.success('教学任务已保存')
    await reloadAll(sid.value!)
  } catch (e) {
    message.error((e as ApiError).detail || '保存失败')
  }
}
async function removeAssignment(a: Assignment) {
  await deleteAssignment(a.id)
  message.success('已删除')
  await reloadAll(sid.value!)
}

// ── 走班群组 modal ──
const groupShow = ref(false)
const groupForm = ref<{ name: string; class_ids: number[] }>({ name: '', class_ids: [] })
function openGroup() {
  groupForm.value = { name: '', class_ids: [] }
  groupShow.value = true
}
async function saveGroup() {
  if (!groupForm.value.name) return message.warning('请输入分组名称')
  if (groupForm.value.class_ids.length < 2) return message.warning('走班分组至少需要 2 个班级')
  try {
    await createGroup(sid.value!, groupForm.value)
    groupShow.value = false
    message.success('走班分组已创建')
    await reloadAll(sid.value!)
  } catch (e) {
    message.error((e as ApiError).detail || '创建失败')
  }
}
async function removeGroup(g: SchedulingUnit) {
  try {
    await deleteGroup(g.id)
    message.success('分组已删除')
    await reloadAll(sid.value!)
  } catch (e) {
    message.error((e as ApiError).detail || '删除失败（分组可能仍有教学任务）')
  }
}

function unitLabel(a: Assignment): string {
  const u = a.scheduling_unit
  if (u.unit_type === 'group') return `${u.name}（走班）`
  const c = u.classes[0]
  return c ? `${c.grade}年${c.name}` : u.name
}
function blockLabel(a: Assignment): string {
  if (a.block_rules.length === 0) return '—'
  return a.block_rules.map((b) => `${b.block_size}连堂×${b.count_per_week}`).join('、')
}
</script>

<template>
  <n-space vertical size="large">
    <n-space align="center">
      <h1 style="margin: 0">{{ '教学任务管理' }}</h1>
      <n-select
        :value="sid" :options="semesterOptions" :placeholder="'选择学期'"
        style="width: 240px" @update:value="onSemesterChange"
      />
    </n-space>

    <n-alert v-if="!sid" type="info">{{ '请先创建学期，并在基础数据中创建班级、科目和教师。' }}</n-alert>

    <div v-else class="layout">
      <!-- 主区:教学任务列表 -->
      <n-space vertical size="large" style="flex: 1; min-width: 0">
        <n-space>
          <n-button type="primary" data-testid="assignment-add" @click="openCreate">{{ '新增教学任务' }}</n-button>
          <n-button data-testid="group-add" @click="openGroup">{{ '新增走班分组' }}</n-button>
        </n-space>

        <n-card :title="'教学任务列表'" size="small">
          <n-empty v-if="assignments.length === 0" :description="'暂无教学任务'" />
          <table v-else class="data-table">
            <thead>
              <tr><th>{{ '排课单元' }}</th><th>{{ '科目' }}</th><th>{{ '教师' }}</th><th>{{ '周课时' }}</th><th>{{ '连堂' }}</th><th>{{ '教室/场地' }}</th><th>{{ '操作' }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="a in assignments" :key="a.id">
                <td>{{ unitLabel(a) }}</td>
                <td>{{ a.subject.name }}</td>
                <td>
                  <n-space size="small">
                    <n-tag
                      v-for="t in a.teachers" :key="t.teacher_id" size="small"
                      :type="t.is_lead ? 'success' : 'default'"
                    >
                      {{ t.name }}{{ t.is_lead ? '（主讲）' : '' }}
                    </n-tag>
                  </n-space>
                </td>
                <td>{{ a.periods_per_week }}</td>
                <td>{{ blockLabel(a) }}</td>
                <td>{{ a.required_room_type ? roomTypeLabel(a.required_room_type) : '—' }}</td>
                <td>
                  <n-space>
                    <n-button size="tiny" @click="openEdit(a)">{{ '编辑' }}</n-button>
                    <n-popconfirm @positive-click="removeAssignment(a)">
                      <template #trigger><n-button size="tiny" type="error" ghost>{{ '删除' }}</n-button></template>
                      {{ '确定删除此教学任务吗？' }}
                    </n-popconfirm>
                  </n-space>
                </td>
              </tr>
            </tbody>
          </table>
        </n-card>

        <n-card v-if="groups.length" :title="'走班分组'" size="small">
          <n-space vertical size="small">
            <n-space v-for="g in groups" :key="g.id" align="center" justify="space-between">
              <n-text>
                <strong>{{ g.name }}</strong>
                <n-text depth="3" style="margin-left: 8px">
                  {{ g.classes.map((c) => `${c.grade}年${c.name}`).join('、') }}
                </n-text>
              </n-text>
              <n-popconfirm @positive-click="removeGroup(g)">
                <template #trigger><n-button size="tiny" type="error" ghost>{{ '删除分组' }}</n-button></template>
                {{ '删除分组将同时移除其教学任务，确定吗？' }}
              </n-popconfirm>
            </n-space>
          </n-space>
        </n-card>
      </n-space>

      <!-- 侧栏:课时统计 -->
      <div class="sidebar">
        <n-card :title="'教师课时'" size="small" data-testid="teacher-load">
          <n-empty v-if="loads.length === 0" :description="'暂无教师'" size="small" />
          <table v-else class="data-table compact">
            <thead><tr><th>{{ '教师' }}</th><th>{{ '已配/应授' }}</th><th>{{ '状态' }}</th></tr></thead>
            <tbody>
              <tr v-for="l in loads" :key="l.teacher_id">
                <td>{{ l.name }}</td>
                <td>{{ l.assigned }} / {{ l.target }}</td>
                <td>
                  <n-tag size="tiny" :type="loadTagType(l)">
                    {{ loadTagText(l) }}
                  </n-tag>
                </td>
              </tr>
            </tbody>
          </table>
        </n-card>

        <n-card :title="'班级课时警告'" size="small" style="margin-top: 16px">
          <n-empty v-if="overCapacity.length === 0" :description="'各班教学任务均未超出可排节次'" size="small" />
          <n-space v-else vertical size="small" data-testid="class-warning">
            <n-alert v-for="c in overCapacity" :key="c.class_id" type="warning" :show-icon="false">
              {{ c.grade }}{{ '年级' }}{{ c.name }}:{{ '教学任务' }} {{ c.assigned }} {{ '节' }} &gt; {{ '可排' }} {{ c.capacity }} {{ '节' }}
            </n-alert>
          </n-space>
        </n-card>
      </div>
    </div>

    <!-- 教学任务 modal -->
    <n-modal v-model:show="show" preset="card" :title="editingId ? '编辑教学任务' : '新增教学任务'" style="max-width: 520px">
      <n-space vertical>
        <n-text>{{ '排课对象' }}</n-text>
        <n-radio-group v-model:value="form.target">
          <n-radio-button value="single">{{ '单个班级' }}</n-radio-button>
          <n-radio-button value="group">{{ '走班分组' }}</n-radio-button>
        </n-radio-group>
        <n-select
          v-if="form.target === 'single'" v-model:value="form.class_id"
          data-testid="a-class" :options="classOptions" :placeholder="'选择班级'" filterable
        />
        <n-select
          v-else v-model:value="form.scheduling_unit_id"
          :options="groupOptions" :placeholder="'选择走班分组（需先创建）'"
        />

        <n-text>{{ '科目' }}</n-text>
        <n-select v-model:value="form.subject_id" data-testid="a-subject" :options="subjectOptions" filterable :placeholder="'选择科目'" />

        <n-text>{{ '授课教师（可多人协同，第一位默认为主讲）' }}</n-text>
        <n-select v-model:value="form.teacher_ids" data-testid="a-teachers" multiple :options="teacherOptions" filterable :placeholder="'选择教师'" />
        <n-select
          v-if="form.teacher_ids.length > 1" v-model:value="form.lead_teacher_id"
          :options="leadOptions" :placeholder="'指定主讲教师'"
        />

        <n-space>
          <n-space vertical style="flex: 1">
            <n-text>{{ '每周课时' }}</n-text>
            <n-input-number v-model:value="form.periods_per_week" data-testid="a-periods" :min="1" :max="40" />
          </n-space>
        </n-space>

        <n-space align="center" justify="space-between">
          <n-text>{{ '连堂规则' }}</n-text>
          <n-button size="tiny" dashed data-testid="a-add-block" @click="addBlock">+ {{ '新增连堂' }}</n-button>
        </n-space>
        <n-space v-for="(b, i) in form.block_rules" :key="i" align="center">
          <n-input-number
            v-model:value="b.block_size" :data-testid="`a-block-size-${i}`"
            :min="2" :max="4" style="width: 110px"
          />
          <n-text>{{ '连堂 ×' }}</n-text>
          <n-input-number
            v-model:value="b.count_per_week" :data-testid="`a-block-count-${i}`"
            :min="1" style="width: 110px"
          />
          <n-text>{{ '次/周' }}</n-text>
          <n-button size="tiny" type="error" ghost @click="removeBlock(i)">{{ '移除' }}</n-button>
        </n-space>

        <n-divider style="margin: 4px 0" />
        <n-text>{{ '教室/场地要求（可选）' }}</n-text>
        <n-space>
          <n-select v-model:value="form.required_room_type" :options="roomTypeOptions" clearable :placeholder="'教室/场地类型'" style="flex: 1" />
          <n-select v-model:value="form.room_id" :options="roomOptions" clearable :placeholder="'指定教室/场地'" style="flex: 1" />
        </n-space>
        <n-checkbox v-model:checked="form.lock_room">{{ '锁定教室/场地（排课时不得变更）' }}</n-checkbox>

        <n-button type="primary" data-testid="a-save" @click="save">{{ '保存' }}</n-button>
      </n-space>
    </n-modal>

    <!-- 走班群组 modal -->
    <n-modal v-model:show="groupShow" preset="card" :title="'新增走班分组'" style="max-width: 460px">
      <n-space vertical>
        <n-text>{{ '分组名称' }}</n-text>
        <n-select
          v-model:value="groupForm.name" data-testid="group-name" filterable tag
          :options="[
            { label: '八年级选修走班', value: '八年级选修走班' },
            { label: '综合实践走班', value: '综合实践走班' },
          ]"
          :placeholder="'输入或选择分组名称'"
        />
        <n-text>{{ '成员班级（至少 2 个班，须使用同一作息时间表）' }}</n-text>
        <n-select v-model:value="groupForm.class_ids" data-testid="group-classes" multiple :options="classOptions" filterable :placeholder="'选择班级'" />
        <n-button type="primary" data-testid="group-save" @click="saveGroup">{{ '创建' }}</n-button>
      </n-space>
    </n-modal>
  </n-space>
</template>

<style scoped>
.layout { display: flex; gap: 24px; align-items: flex-start; }
.sidebar { width: 320px; flex-shrink: 0; }
.data-table { border-collapse: collapse; width: 100%; }
.data-table th, .data-table td { border: 1px solid var(--n-border-color, #e0e0e0); padding: 6px 8px; text-align: left; }
.data-table th { background: rgba(128,128,128,0.08); font-weight: 600; }
.data-table.compact th, .data-table.compact td { padding: 4px 6px; font-size: 13px; }
@media (max-width: 900px) { .layout { flex-direction: column; } .sidebar { width: 100%; } }
</style>
