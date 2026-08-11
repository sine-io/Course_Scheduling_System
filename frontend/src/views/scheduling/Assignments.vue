<script setup lang="ts">
import {
  AlertTriangle, CheckCircle2, ClipboardList, Clock3, Layers3, Pencil, Plus, RefreshCw,
  Save, ShieldCheck, Trash2, UsersRound,
} from '@lucide/vue'
import {
  NAlert, NButton, NCard, NCheckbox, NDivider, NEmpty, NInputNumber, NModal, NPopconfirm,
  NRadioButton, NRadioGroup, NSelect, NSpin, NTag, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
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
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import { useAuthStore } from '@/stores/auth'
import './scheduling-workspace.css'

const message = useMessage()
const auth = useAuthStore()
const router = useRouter()
const canEdit = computed(() => auth.hasRole('admin') || auth.hasRole('scheduler'))

const semesters = ref<SemesterListItem[]>([])
const sid = ref<number | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
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
  loading.value = true
  loadError.value = null
  sid.value = id
  try {
    await Promise.all([loadBase(id), reloadAll(id)])
  } catch (error) {
    loadError.value = errorMessage(error, '暂时无法读取教学任务，请重试。')
  } finally {
    loading.value = false
  }
}

function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as Partial<ApiError> | null)?.detail
  return typeof detail === 'string' && detail ? detail : fallback
}

async function loadPage() {
  loading.value = true
  loadError.value = null
  try {
    semesters.value = await listSemesters()
    if (semesters.value.length) {
      sid.value = semesters.value[0].id
      await Promise.all([loadBase(sid.value), reloadAll(sid.value)])
    } else {
      sid.value = null
    }
  } catch (error) {
    loadError.value = errorMessage(error, '暂时无法读取教学任务，请重试。')
  } finally {
    loading.value = false
  }
}

async function retryLoad() {
  if (sid.value) await onSemesterChange(sid.value)
  else await loadPage()
}

onMounted(loadPage)

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
const saving = ref(false)
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
  if (!canEdit.value) return
  editingId.value = null
  form.value = emptyForm()
  show.value = true
}
function openEdit(a: Assignment) {
  if (!canEdit.value) return
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
  if (!canEdit.value || saving.value) return
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
  saving.value = true
  try {
    if (editingId.value) await updateAssignment(editingId.value, payload)
    else await createAssignment(sid.value!, payload)
    show.value = false
    message.success('教学任务已保存')
    await reloadAll(sid.value!)
  } catch (e) {
    message.error((e as ApiError).detail || '保存失败')
  } finally {
    saving.value = false
  }
}
const deletingAssignmentId = ref<number | null>(null)
async function removeAssignment(a: Assignment) {
  if (!canEdit.value || deletingAssignmentId.value !== null) return
  deletingAssignmentId.value = a.id
  try {
    await deleteAssignment(a.id)
    message.success('已删除')
    await reloadAll(sid.value!)
  } catch (error) {
    message.error(errorMessage(error, '删除教学任务失败'))
  } finally {
    deletingAssignmentId.value = null
  }
}

// ── 走班群组 modal ──
const groupShow = ref(false)
const groupForm = ref<{ name: string; class_ids: number[] }>({ name: '', class_ids: [] })
const groupSaving = ref(false)
const deletingGroupId = ref<number | null>(null)
function openGroup() {
  if (!canEdit.value) return
  groupForm.value = { name: '', class_ids: [] }
  groupShow.value = true
}
async function saveGroup() {
  if (!canEdit.value || groupSaving.value) return
  if (!groupForm.value.name) return message.warning('请输入分组名称')
  if (groupForm.value.class_ids.length < 2) return message.warning('走班分组至少需要 2 个班级')
  groupSaving.value = true
  try {
    await createGroup(sid.value!, groupForm.value)
    groupShow.value = false
    message.success('走班分组已创建')
    await reloadAll(sid.value!)
  } catch (e) {
    message.error((e as ApiError).detail || '创建失败')
  } finally {
    groupSaving.value = false
  }
}
async function removeGroup(g: SchedulingUnit) {
  if (!canEdit.value || deletingGroupId.value !== null) return
  deletingGroupId.value = g.id
  try {
    await deleteGroup(g.id)
    message.success('分组已删除')
    await reloadAll(sid.value!)
  } catch (e) {
    message.error((e as ApiError).detail || '删除失败（分组可能仍有教学任务）')
  } finally {
    deletingGroupId.value = null
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
  <div class="scheduling-page" data-testid="assignments-page">
    <header class="scheduling-page-header">
      <div>
        <p class="scheduling-eyebrow">{{ '排课准备' }}</p>
        <h1>{{ '教学任务管理' }}</h1>
        <p>{{ '维护班级、科目、教师与每周课时，并同步核对教师和班级负载。' }}</p>
      </div>
      <div class="scheduling-header-actions">
        <n-select
          v-if="semesters.length"
          v-accessible-select="'选择工作学期'"
          :value="sid"
          :options="semesterOptions"
          :placeholder="'选择学期'"
          data-testid="assignments-semester-select"
          @update:value="onSemesterChange"
        />
      </div>
    </header>

    <section v-if="loading" class="scheduling-state" data-testid="assignments-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取教学任务' }}</strong>
      <span>{{ '教学任务和课时负载加载完成后会显示在这里。' }}</span>
    </section>

    <section v-else-if="loadError" class="scheduling-state scheduling-state-error" data-testid="assignments-error" role="alert">
      <RefreshCw :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '当前工作面没有写入任何更改。' }}</span>
      <n-button type="primary" data-testid="assignments-retry" @click="retryLoad">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>

    <section v-else-if="!sid" class="scheduling-state" data-testid="assignments-empty">
      <ClipboardList :size="24" aria-hidden="true" />
      <strong>{{ '尚未创建可用学期' }}</strong>
      <span>{{ '先创建学期并维护班级、科目和教师，再建立教学任务。' }}</span>
      <n-button type="primary" @click="router.push({ name: 'semesters' })">{{ '前往学期配置' }}</n-button>
    </section>

    <template v-else>
      <n-alert v-if="!canEdit" type="info" data-testid="assignments-readonly">
        <template #icon><ShieldCheck :size="17" aria-hidden="true" /></template>
        {{ '当前角色仅可查看教学任务和课时负载，写入操作仅对排课管理员开放。' }}
      </n-alert>

      <div class="assignments-layout" data-testid="assignments-workspace">
        <div class="assignments-main-column">
          <section class="scheduling-panel assignment-list-panel">
            <header class="scheduling-panel-heading">
              <div>
                <p class="scheduling-eyebrow">{{ '任务总览' }}</p>
                <h2>{{ '教学任务' }}</h2>
                <p>{{ assignments.length ? `当前共 ${assignments.length} 项教学任务` : '当前学期还没有教学任务' }}</p>
              </div>
              <div v-if="canEdit" class="scheduling-actions">
                <n-button type="primary" data-testid="assignment-add" @click="openCreate">
                  <template #icon><Plus :size="15" aria-hidden="true" /></template>
                  {{ '新增教学任务' }}
                </n-button>
                <n-button data-testid="group-add" @click="openGroup">
                  <template #icon><Layers3 :size="15" aria-hidden="true" /></template>
                  {{ '新增走班分组' }}
                </n-button>
              </div>
            </header>

            <div v-if="assignments.length === 0" class="scheduling-inline-empty" data-testid="assignment-list-empty">
              <n-empty :description="'暂无教学任务'" />
            </div>
            <div
              v-else
              class="scheduling-table-scroll"
              data-testid="assignment-table-scroll"
              tabindex="0"
              aria-label="教学任务列表，可横向滚动"
            >
              <table class="scheduling-data-table assignment-data-table" data-testid="assignment-table">
                <thead>
                  <tr>
                    <th>{{ '排课单元' }}</th>
                    <th>{{ '科目' }}</th>
                    <th>{{ '教师' }}</th>
                    <th>{{ '周课时' }}</th>
                    <th>{{ '连堂' }}</th>
                    <th>{{ '教室/场地' }}</th>
                    <th v-if="canEdit">{{ '操作' }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="a in assignments" :key="a.id">
                    <td><strong>{{ unitLabel(a) }}</strong></td>
                    <td>{{ a.subject.name }}</td>
                    <td>
                      <div class="assignment-teachers">
                        <n-tag
                          v-for="teacher in a.teachers"
                          :key="teacher.teacher_id"
                          size="small"
                          :type="teacher.is_lead ? 'success' : 'default'"
                        >
                          {{ teacher.name }}{{ teacher.is_lead ? '（主讲）' : '' }}
                        </n-tag>
                      </div>
                    </td>
                    <td>{{ a.periods_per_week }}</td>
                    <td>{{ blockLabel(a) }}</td>
                    <td>{{ a.required_room_type ? roomTypeLabel(a.required_room_type) : '—' }}</td>
                    <td v-if="canEdit">
                      <div class="scheduling-row-actions">
                        <n-button size="tiny" :aria-label="'编辑本行教学任务'" @click="openEdit(a)">
                          <template #icon><Pencil :size="13" aria-hidden="true" /></template>
                          {{ '编辑' }}
                        </n-button>
                        <n-popconfirm @positive-click="removeAssignment(a)">
                          <template #trigger>
                            <n-button
                              size="tiny"
                              type="error"
                              ghost
                              :loading="deletingAssignmentId === a.id"
                              :disabled="deletingAssignmentId !== null"
                            >
                              <template #icon><Trash2 :size="13" aria-hidden="true" /></template>
                              {{ '删除' }}
                            </n-button>
                          </template>
                          {{ '确定删除此教学任务吗？' }}
                        </n-popconfirm>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <n-card v-if="groups.length" class="assignment-group-panel" size="small">
            <template #header>
              <div class="scheduling-panel-heading compact-heading">
                <div>
                  <p class="scheduling-eyebrow">{{ '共享排课单元' }}</p>
                  <h2>{{ '走班分组' }}</h2>
                </div>
                <Layers3 :size="19" class="scheduling-heading-icon" aria-hidden="true" />
              </div>
            </template>
            <div class="assignment-group-list">
              <div v-for="group in groups" :key="group.id" class="assignment-group-row">
                <div>
                  <strong>{{ group.name }}</strong>
                  <span>{{ group.classes.map((c) => `${c.grade}年${c.name}`).join('、') }}</span>
                </div>
                <n-popconfirm v-if="canEdit" @positive-click="removeGroup(group)">
                  <template #trigger>
                    <n-button
                      size="tiny"
                      type="error"
                      ghost
                      :loading="deletingGroupId === group.id"
                      :disabled="deletingGroupId !== null"
                    >
                      {{ '删除分组' }}
                    </n-button>
                  </template>
                  {{ '删除分组将同时移除其教学任务，确定吗？' }}
                </n-popconfirm>
              </div>
            </div>
          </n-card>
        </div>

        <aside class="assignment-insights" aria-label="课时负载">
          <section class="scheduling-panel assignment-insight-panel" data-testid="teacher-load">
            <header class="scheduling-panel-heading compact-heading">
              <div>
                <p class="scheduling-eyebrow">{{ '负载核对' }}</p>
                <h2>{{ '教师课时' }}</h2>
              </div>
              <Clock3 :size="19" class="scheduling-heading-icon" aria-hidden="true" />
            </header>
            <n-empty v-if="loads.length === 0" :description="'暂无教师'" size="small" />
            <div v-else class="assignment-load-list">
              <div v-for="load in loads" :key="load.teacher_id" class="assignment-load-row">
                <div>
                  <strong>{{ load.name }}</strong>
                  <span>{{ load.assigned }} / {{ load.target }} {{ '节' }}</span>
                </div>
                <n-tag size="small" :type="loadTagType(load)">{{ loadTagText(load) }}</n-tag>
              </div>
            </div>
          </section>

          <section class="scheduling-panel assignment-insight-panel">
            <header class="scheduling-panel-heading compact-heading">
              <div>
                <p class="scheduling-eyebrow">{{ '容量核对' }}</p>
                <h2>{{ '班级课时' }}</h2>
              </div>
              <UsersRound :size="19" class="scheduling-heading-icon" aria-hidden="true" />
            </header>
            <div v-if="overCapacity.length === 0" class="assignment-check-ok">
              <CheckCircle2 :size="17" aria-hidden="true" />
              <span>{{ '各班教学任务均未超出可排节次' }}</span>
            </div>
            <div v-else class="assignment-warning-list" data-testid="class-warning">
              <n-alert v-for="classItem in overCapacity" :key="classItem.class_id" type="warning" :show-icon="false">
                <span class="assignment-warning-line">
                  <AlertTriangle :size="14" aria-hidden="true" />
                  {{ classItem.grade }}{{ '年级' }}{{ classItem.name }}：{{ '教学任务' }} {{ classItem.assigned }} {{ '节' }} &gt; {{ '可排' }} {{ classItem.capacity }} {{ '节' }}
                </span>
              </n-alert>
            </div>
          </section>
        </aside>
      </div>
    </template>

    <n-modal v-model:show="show" preset="card" :title="editingId ? '编辑教学任务' : '新增教学任务'" class="scheduling-modal assignment-modal">
      <div class="scheduling-form">
        <div class="scheduling-field">
          <label>{{ '排课对象' }}</label>
          <div role="radiogroup" aria-label="排课对象">
            <n-radio-group v-model:value="form.target">
              <n-radio-button value="single">{{ '单个班级' }}</n-radio-button>
              <n-radio-button value="group">{{ '走班分组' }}</n-radio-button>
            </n-radio-group>
          </div>
          <n-select
            v-if="form.target === 'single'"
            v-model:value="form.class_id"
            v-accessible-select="'选择排课班级'"
            data-testid="a-class"
            :options="classOptions"
            :placeholder="'选择班级'"
            filterable
          />
          <n-select
            v-else
            v-model:value="form.scheduling_unit_id"
            v-accessible-select="'选择走班分组'"
            :options="groupOptions"
            :placeholder="'选择走班分组（需先创建）'"
          />
        </div>

        <div class="scheduling-field">
          <label>{{ '科目' }}</label>
          <n-select v-model:value="form.subject_id" v-accessible-select="'选择科目'" data-testid="a-subject" :options="subjectOptions" filterable :placeholder="'选择科目'" />
        </div>

        <div class="scheduling-field">
          <label>{{ '授课教师（可多人协同，第一位默认为主讲）' }}</label>
          <n-select v-model:value="form.teacher_ids" v-accessible-select="'选择授课教师'" data-testid="a-teachers" multiple :options="teacherOptions" filterable :placeholder="'选择教师'" />
          <n-select
            v-if="form.teacher_ids.length > 1"
            v-model:value="form.lead_teacher_id"
            v-accessible-select="'指定主讲教师'"
            :options="leadOptions"
            :placeholder="'指定主讲教师'"
          />
        </div>

        <div class="scheduling-field scheduling-field-narrow">
          <label>{{ '每周课时' }}</label>
          <n-input-number v-model:value="form.periods_per_week" data-testid="a-periods" :min="1" :max="40" :input-props="{ 'aria-label': '每周课时' }" />
        </div>

        <div class="assignment-block-heading">
          <label>{{ '连堂规则' }}</label>
          <n-button size="tiny" dashed data-testid="a-add-block" @click="addBlock">
            <template #icon><Plus :size="13" aria-hidden="true" /></template>
            {{ '新增连堂' }}
          </n-button>
        </div>
        <div v-for="(block, index) in form.block_rules" :key="index" class="assignment-block-row">
          <n-input-number v-model:value="block.block_size" :data-testid="`a-block-size-${index}`" :min="2" :max="4" :input-props="{ 'aria-label': `第${index + 1}条连堂规则的连堂节数` }" />
          <span>{{ '连堂 ×' }}</span>
          <n-input-number v-model:value="block.count_per_week" :data-testid="`a-block-count-${index}`" :min="1" :input-props="{ 'aria-label': `第${index + 1}条连堂规则的每周次数` }" />
          <span>{{ '次/周' }}</span>
          <n-button size="tiny" type="error" ghost :aria-label="`移除第${index + 1}条连堂规则`" @click="removeBlock(index)">
            <template #icon><Trash2 :size="13" aria-hidden="true" /></template>
          </n-button>
        </div>

        <n-divider class="scheduling-divider" />
        <div class="scheduling-form-grid">
          <div class="scheduling-field">
            <label>{{ '教室/场地类型（可选）' }}</label>
            <n-select v-model:value="form.required_room_type" v-accessible-select="'选择教室/场地类型'" :options="roomTypeOptions" clearable :placeholder="'教室/场地类型'" />
          </div>
          <div class="scheduling-field">
            <label>{{ '指定教室/场地（可选）' }}</label>
            <n-select v-model:value="form.room_id" v-accessible-select="'指定教室/场地'" :options="roomOptions" clearable :placeholder="'指定教室/场地'" />
          </div>
        </div>
        <n-checkbox v-model:checked="form.lock_room">{{ '锁定教室/场地（排课时不得变更）' }}</n-checkbox>

        <div class="scheduling-modal-actions">
          <n-button :disabled="saving" @click="show = false">{{ '取消' }}</n-button>
          <n-button type="primary" data-testid="a-save" :loading="saving" @click="save">
            <template #icon><Save :size="15" aria-hidden="true" /></template>
            {{ '保存' }}
          </n-button>
        </div>
      </div>
    </n-modal>

    <n-modal v-model:show="groupShow" preset="card" :title="'新增走班分组'" class="scheduling-modal assignment-group-modal">
      <div class="scheduling-form">
        <div class="scheduling-field">
          <label>{{ '分组名称' }}</label>
          <n-select
            v-model:value="groupForm.name"
            v-accessible-select="'分组名称'"
            data-testid="group-name"
            filterable
            tag
            :options="[
              { label: '八年级选修走班', value: '八年级选修走班' },
              { label: '综合实践走班', value: '综合实践走班' },
            ]"
            :placeholder="'输入或选择分组名称'"
          />
        </div>
        <div class="scheduling-field">
          <label>{{ '成员班级（至少 2 个班，须使用同一作息时间表）' }}</label>
          <n-select v-model:value="groupForm.class_ids" v-accessible-select="'选择分组成员班级'" data-testid="group-classes" multiple :options="classOptions" filterable :placeholder="'选择班级'" />
        </div>
        <div class="scheduling-modal-actions">
          <n-button :disabled="groupSaving" @click="groupShow = false">{{ '取消' }}</n-button>
          <n-button type="primary" data-testid="group-save" :loading="groupSaving" @click="saveGroup">
            <template #icon><Layers3 :size="15" aria-hidden="true" /></template>
            {{ '创建' }}
          </n-button>
        </div>
      </div>
    </n-modal>
  </div>
</template>
