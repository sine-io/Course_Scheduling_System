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
import { useProfileText } from '@/composables/useProfileText'

const message = useMessage()
const { isMainland, tr } = useProfileText()

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
const mainlandRoomTypeLabels: Record<string, string> = {
  normal: '普通教室', special: '专用教室', workshop: '实训场地', outdoor: '户外',
}
function roomTypeLabel(type: string) {
  return isMainland.value ? (mainlandRoomTypeLabels[type] ?? type) : ROOM_TYPE_LABELS[type as keyof typeof ROOM_TYPE_LABELS]
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
function loadTagType(d: number): 'success' | 'error' | 'warning' {
  if (d > 0) return 'error'
  if (d < 0) return 'warning'
  return 'success'
}

// ── 配課 modal ──
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
  if (f.target === 'single' && !f.class_id) return message.warning(tr('請選擇班級', '请选择班级'))
  if (f.target === 'group' && !f.scheduling_unit_id) return message.warning(tr('請選擇跑班群組', '请选择走班分组'))
  if (!f.subject_id) return message.warning(tr('請選擇科目', '请选择科目'))
  if (f.teacher_ids.length === 0) return message.warning(tr('請至少指定一位教師', '请至少指定一位教师'))
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
    message.success(tr('已儲存配課', '配课已保存'))
    await reloadAll(sid.value!)
  } catch (e) {
    message.error((e as ApiError).detail || tr('儲存失敗', '保存失败'))
  }
}
async function removeAssignment(a: Assignment) {
  await deleteAssignment(a.id)
  message.success(tr('已刪除', '已删除'))
  await reloadAll(sid.value!)
}

// ── 跑班群組 modal ──
const groupShow = ref(false)
const groupForm = ref<{ name: string; class_ids: number[] }>({ name: '', class_ids: [] })
function openGroup() {
  groupForm.value = { name: '', class_ids: [] }
  groupShow.value = true
}
async function saveGroup() {
  if (!groupForm.value.name) return message.warning(tr('請輸入群組名稱', '请输入分组名称'))
  if (groupForm.value.class_ids.length < 2) return message.warning(tr('跑班群組至少需 2 個班級', '走班分组至少需要 2 个班级'))
  try {
    await createGroup(sid.value!, groupForm.value)
    groupShow.value = false
    message.success(tr('已建立跑班群組', '走班分组已建立'))
    await reloadAll(sid.value!)
  } catch (e) {
    message.error((e as ApiError).detail || tr('建立失敗', '创建失败'))
  }
}
async function removeGroup(g: SchedulingUnit) {
  try {
    await deleteGroup(g.id)
    message.success(tr('已刪除群組', '分组已删除'))
    await reloadAll(sid.value!)
  } catch (e) {
    message.error((e as ApiError).detail || tr('刪除失敗(群組可能仍有配課)', '删除失败（分组可能仍有配课）'))
  }
}

function unitLabel(a: Assignment): string {
  const u = a.scheduling_unit
  if (u.unit_type === 'group') return tr(`${u.name}(跑班)`, `${u.name}（走班）`)
  const c = u.classes[0]
  return c ? `${c.grade}年${c.name}` : u.name
}
function blockLabel(a: Assignment): string {
  if (a.block_rules.length === 0) return '—'
  return a.block_rules.map((b) => tr(`${b.block_size}連堂×${b.count_per_week}`, `${b.block_size}连堂×${b.count_per_week}`)).join('、')
}
</script>

<template>
  <n-space vertical size="large">
    <n-space align="center">
      <h1 style="margin: 0">{{ tr('配課管理', '配课管理') }}</h1>
      <n-select
        :value="sid" :options="semesterOptions" :placeholder="tr('選擇學期', '选择学期')"
        style="width: 240px" @update:value="onSemesterChange"
      />
    </n-space>

    <n-alert v-if="!sid" type="info">{{ tr('請先建立學期並於基礎資料建立班級、科目、教師。', '请先建立学期，并在基础资料中建立班级、科目和教师。') }}</n-alert>

    <div v-else class="layout">
      <!-- 主區:配課清單 -->
      <n-space vertical size="large" style="flex: 1; min-width: 0">
        <n-space>
          <n-button type="primary" data-testid="assignment-add" @click="openCreate">{{ tr('新增配課', '新增配课') }}</n-button>
          <n-button data-testid="group-add" @click="openGroup">{{ tr('新增跑班群組', '新增走班分组') }}</n-button>
        </n-space>

        <n-card :title="tr('配課清單', '配课清单')" size="small">
          <n-empty v-if="assignments.length === 0" :description="tr('尚無配課', '暂无配课')" />
          <table v-else class="data-table">
            <thead>
              <tr><th>{{ tr('排課單位', '排课单元') }}</th><th>{{ tr('科目', '科目') }}</th><th>{{ tr('教師', '教师') }}</th><th>{{ tr('週節數', '周课时') }}</th><th>{{ tr('連堂', '连堂') }}</th><th>{{ tr('場地', '场地') }}</th><th>{{ tr('操作', '操作') }}</th></tr>
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
                      {{ t.name }}{{ t.is_lead ? tr('(主教)', '（主讲）') : '' }}
                    </n-tag>
                  </n-space>
                </td>
                <td>{{ a.periods_per_week }}</td>
                <td>{{ blockLabel(a) }}</td>
                <td>{{ a.required_room_type ? roomTypeLabel(a.required_room_type) : '—' }}</td>
                <td>
                  <n-space>
                    <n-button size="tiny" @click="openEdit(a)">{{ tr('編輯', '编辑') }}</n-button>
                    <n-popconfirm @positive-click="removeAssignment(a)">
                      <template #trigger><n-button size="tiny" type="error" ghost>{{ tr('刪除', '删除') }}</n-button></template>
                      {{ tr('確定刪除此配課?', '确定删除此配课吗？') }}
                    </n-popconfirm>
                  </n-space>
                </td>
              </tr>
            </tbody>
          </table>
        </n-card>

        <n-card v-if="groups.length" :title="tr('跑班群組', '走班分组')" size="small">
          <n-space vertical size="small">
            <n-space v-for="g in groups" :key="g.id" align="center" justify="space-between">
              <n-text>
                <strong>{{ g.name }}</strong>
                <n-text depth="3" style="margin-left: 8px">
                  {{ g.classes.map((c) => `${c.grade}年${c.name}`).join('、') }}
                </n-text>
              </n-text>
              <n-popconfirm @positive-click="removeGroup(g)">
                <template #trigger><n-button size="tiny" type="error" ghost>{{ tr('刪除群組', '删除分组') }}</n-button></template>
                {{ tr('刪除群組將一併移除其配課,確定?', '删除分组将同时移除其配课，确定吗？') }}
              </n-popconfirm>
            </n-space>
          </n-space>
        </n-card>
      </n-space>

      <!-- 側欄:鐘點統計 -->
      <div class="sidebar">
        <n-card :title="tr('教師鐘點', '教师课时')" size="small" data-testid="teacher-load">
          <n-empty v-if="loads.length === 0" :description="tr('尚無教師', '暂无教师')" size="small" />
          <table v-else class="data-table compact">
            <thead><tr><th>{{ tr('教師', '教师') }}</th><th>{{ tr('已配/應授', '已配/应授') }}</th><th>{{ tr('狀態', '状态') }}</th></tr></thead>
            <tbody>
              <tr v-for="l in loads" :key="l.teacher_id">
                <td>{{ l.name }}</td>
                <td>{{ l.assigned }} / {{ l.target }}</td>
                <td>
                  <n-tag size="tiny" :type="loadTagType(l.delta)">
                    {{ l.delta > 0 ? tr(`+${l.delta} 超鐘點`, `+${l.delta} 超课时`) : l.delta < 0 ? tr(`${l.delta} 不足`, `${l.delta} 不足`) : tr('剛好', '刚好') }}
                  </n-tag>
                </td>
              </tr>
            </tbody>
          </table>
        </n-card>

        <n-card :title="tr('班級節數警告', '班级课时警告')" size="small" style="margin-top: 16px">
          <n-empty v-if="overCapacity.length === 0" :description="tr('各班配課未超出可排節次', '各班配课均未超出可排节次')" size="small" />
          <n-space v-else vertical size="small" data-testid="class-warning">
            <n-alert v-for="c in overCapacity" :key="c.class_id" type="warning" :show-icon="false">
              {{ c.grade }}{{ tr('年', '年级') }}{{ c.name }}:{{ tr('配課', '配课') }} {{ c.assigned }} {{ tr('節', '节') }} &gt; {{ tr('可排', '可排') }} {{ c.capacity }} {{ tr('節', '节') }}
            </n-alert>
          </n-space>
        </n-card>
      </div>
    </div>

    <!-- 配課 modal -->
    <n-modal v-model:show="show" preset="card" :title="editingId ? tr('編輯配課', '编辑配课') : tr('新增配課', '新增配课')" style="max-width: 520px">
      <n-space vertical>
        <n-text>{{ tr('排課對象', '排课对象') }}</n-text>
        <n-radio-group v-model:value="form.target">
          <n-radio-button value="single">{{ tr('單一班級', '单个班级') }}</n-radio-button>
          <n-radio-button value="group">{{ tr('跑班群組', '走班分组') }}</n-radio-button>
        </n-radio-group>
        <n-select
          v-if="form.target === 'single'" v-model:value="form.class_id"
          data-testid="a-class" :options="classOptions" :placeholder="tr('選擇班級', '选择班级')" filterable
        />
        <n-select
          v-else v-model:value="form.scheduling_unit_id"
          :options="groupOptions" :placeholder="tr('選擇跑班群組(需先建立)', '选择走班分组（需先建立）')"
        />

        <n-text>{{ tr('科目', '科目') }}</n-text>
        <n-select v-model:value="form.subject_id" data-testid="a-subject" :options="subjectOptions" filterable :placeholder="tr('選擇科目', '选择科目')" />

        <n-text>{{ tr('授課教師(可多位協同,第一位預設主教)', '授课教师（可多人协同，第一位默认为主讲）') }}</n-text>
        <n-select v-model:value="form.teacher_ids" data-testid="a-teachers" multiple :options="teacherOptions" filterable :placeholder="tr('選擇教師', '选择教师')" />
        <n-select
          v-if="form.teacher_ids.length > 1" v-model:value="form.lead_teacher_id"
          :options="leadOptions" :placeholder="tr('指定主教教師', '指定主讲教师')"
        />

        <n-space>
          <n-space vertical style="flex: 1">
            <n-text>{{ tr('每週節數', '每周课时') }}</n-text>
            <n-input-number v-model:value="form.periods_per_week" data-testid="a-periods" :min="1" :max="40" />
          </n-space>
        </n-space>

        <n-space align="center" justify="space-between">
          <n-text>{{ tr('連堂規則', '连堂规则') }}</n-text>
          <n-button size="tiny" dashed data-testid="a-add-block" @click="addBlock">+ {{ tr('新增連堂', '新增连堂') }}</n-button>
        </n-space>
        <n-space v-for="(b, i) in form.block_rules" :key="i" align="center">
          <n-input-number
            v-model:value="b.block_size" :data-testid="`a-block-size-${i}`"
            :min="2" :max="4" style="width: 110px"
          />
          <n-text>{{ tr('連堂 ×', '连堂 ×') }}</n-text>
          <n-input-number
            v-model:value="b.count_per_week" :data-testid="`a-block-count-${i}`"
            :min="1" style="width: 110px"
          />
          <n-text>{{ tr('次/週', '次/周') }}</n-text>
          <n-button size="tiny" type="error" ghost @click="removeBlock(i)">{{ tr('移除', '移除') }}</n-button>
        </n-space>

        <n-divider style="margin: 4px 0" />
        <n-text>{{ tr('場地需求(選填)', '场地要求（可选）') }}</n-text>
        <n-space>
          <n-select v-model:value="form.required_room_type" :options="roomTypeOptions" clearable :placeholder="tr('場地類型', '场地类型')" style="flex: 1" />
          <n-select v-model:value="form.room_id" :options="roomOptions" clearable :placeholder="tr('指定場地', '指定场地')" style="flex: 1" />
        </n-space>
        <n-checkbox v-model:checked="form.lock_room">{{ tr('鎖定場地(排課不得更動)', '锁定场地（排课时不得变更）') }}</n-checkbox>

        <n-button type="primary" data-testid="a-save" @click="save">{{ tr('儲存', '保存') }}</n-button>
      </n-space>
    </n-modal>

    <!-- 跑班群組 modal -->
    <n-modal v-model:show="groupShow" preset="card" :title="tr('新增跑班群組', '新增走班分组')" style="max-width: 460px">
      <n-space vertical>
        <n-text>{{ tr('群組名稱', '分组名称') }}</n-text>
        <n-select
          v-model:value="groupForm.name" data-testid="group-name" filterable tag
          :options="isMainland
            ? [{ label: '八年级选修走班', value: '八年级选修走班' }, { label: '综合实践走班', value: '综合实践走班' }]
            : [{ label: '高二多元選修', value: '高二多元選修' }, { label: '綜高學程', value: '綜高學程' }]"
          :placeholder="tr('輸入或選擇群組名稱', '输入或选择分组名称')"
        />
        <n-text>{{ tr('成員班級(至少 2 班,須使用同一節次表)', '成员班级（至少 2 个班，须使用同一节次表）') }}</n-text>
        <n-select v-model:value="groupForm.class_ids" data-testid="group-classes" multiple :options="classOptions" filterable :placeholder="tr('選擇班級', '选择班级')" />
        <n-button type="primary" data-testid="group-save" @click="saveGroup">{{ tr('建立', '创建') }}</n-button>
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
