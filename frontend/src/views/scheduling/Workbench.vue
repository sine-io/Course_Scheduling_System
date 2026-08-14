<script setup lang="ts">
import {
  AlertTriangle, CheckCircle2, Clock3, MousePointer2, RefreshCw, Redo2, Save,
  ShieldCheck, Undo2,
} from '@lucide/vue'
import {
  NAlert, NButton, NRadioButton, NRadioGroup, NSelect, NSpin, NTag,
  useMessage,
} from 'naive-ui'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import TimetableGrid from '@/components/timetable/TimetableGrid.vue'
import type { DragData, DropFeedback, GridEntry, PeriodCell } from '@/components/timetable/types'
import { apiErrorMessage, type ApiError } from '@/api/client'
import { listAssignments } from '@/api/assignments'
import type { Assignment } from '@/api/assignments'
import { listClassUnits, listRooms, listTeachers } from '@/api/basedata'
import type { ClassUnit, Room, Teacher } from '@/api/basedata'
import { getSemester, listSemesters } from '@/api/semesters'
import type { PeriodTable, SemesterListItem } from '@/api/semesters'
import {
  checkConflict, conflictText, createTimetable, deleteEntry, getClassPeriodTable, getTimetable,
  listTimetables, lockEntry, moveEntry, placeEntry,
} from '@/api/timetables'
import type { Timetable, TimetableBrief } from '@/api/timetables'
import { useAuthStore } from '@/stores/auth'
import { useSemesterContextStore } from '@/stores/semesterContext'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import './scheduling-workspace.css'

type ViewKind = 'class' | 'teacher' | 'room'
type SaveState = 'idle' | 'saving' | 'saved' | 'error'

const message = useMessage()
const auth = useAuthStore()
const semesterContext = useSemesterContextStore()
const router = useRouter()

const loading = ref(true)
const loadError = ref<string | null>(null)
const semesters = ref<SemesterListItem[]>([])
const sid = ref<number | null>(null)
const canEdit = computed(() => (
  (auth.hasRole('admin') || auth.hasRole('scheduler'))
  && (!semesterContext.authoritative || semesterContext.isCurrent(sid.value))
))
const drafts = ref<TimetableBrief[]>([])
const ttId = ref<number | null>(null)
const tt = ref<Timetable | null>(null)

const assignments = ref<Assignment[]>([])
const classes = ref<ClassUnit[]>([])
const teachers = ref<Teacher[]>([])
const rooms = ref<Room[]>([])
const defaultTable = ref<PeriodTable | null>(null)
const periods = ref<PeriodCell[]>([])
const numWeekdays = ref(5)

const view = ref<ViewKind>('class')
const classId = ref<number | null>(null)
const teacherId = ref<number | null>(null)
const roomId = ref<number | null>(null)

const semesterOptions = computed(() => semesters.value.map((s) => ({ label: s.label, value: s.id })))
const draftOptions = computed(() => drafts.value.map((d) => ({ label: d.name, value: d.id })))
const classOptions = computed(() =>
  classes.value.map((c) => ({ label: `${c.grade}年${c.name}`, value: c.id })))
const teacherOptions = computed(() => teachers.value.map((t) => ({ label: t.name, value: t.id })))
const roomOptions = computed(() => rooms.value.map((r) => ({ label: r.name, value: r.id })))

const readonly = computed(() => (
  !canEdit.value || view.value !== 'class' || tt.value?.status !== 'draft'
))
const readonlyReason = computed(() => {
  if (
    semesterContext.authoritative
    && sid.value !== null
    && !semesterContext.isCurrent(sid.value)
  ) {
    return '所选学期不是当前工作学期，历史学期只允许查询。'
  }
  if (!canEdit.value) return '当前角色仅可查看课表，排课写入仅对排课管理员开放。'
  if (view.value !== 'class') return '教师与教室/场地视图为只读视图，请在班级视图中调整排课。'
  if (tt.value && tt.value.status !== 'draft') return '当前课表不是草稿，无法在工作台中写入更改。'
  return ''
})

async function refreshTimetable() {
  tt.value = ttId.value ? await getTimetable(ttId.value) : null
}

async function loadPeriods() {
  let table: PeriodTable | null = defaultTable.value
  if (view.value === 'class' && classId.value) {
    try {
      table = await getClassPeriodTable(classId.value)
    } catch {
      table = defaultTable.value
    }
  }
  periods.value = (table?.periods ?? []) as PeriodCell[]
  numWeekdays.value = table?.num_weekdays ?? 5
}

async function loadSemesterData(id: number) {
  sid.value = id
  resetWorkspaceHistory()
  const [semester, listedAssignments, listedClasses, listedTeachers, listedRooms, listedDrafts] = await Promise.all([
    getSemester(id), listAssignments(id), listClassUnits(id), listTeachers(id), listRooms(id),
    listTimetables(id),
  ])
  assignments.value = listedAssignments
  classes.value = listedClasses
  teachers.value = listedTeachers
  rooms.value = listedRooms
  defaultTable.value = semester.period_tables.find((table) => table.is_default)
    ?? semester.period_tables[0]
    ?? null
  drafts.value = listedDrafts

  if (drafts.value.length === 0 && canEdit.value) {
    const created = await createTimetable(id, '草稿A')
    drafts.value = await listTimetables(id)
    ttId.value = created.id
  } else {
    ttId.value = drafts.value[0]?.id ?? null
  }

  classId.value = listedClasses[0]?.id ?? null
  teacherId.value = listedTeachers[0]?.id ?? null
  roomId.value = listedRooms[0]?.id ?? null
  await Promise.all([refreshTimetable(), loadPeriods()])
}

async function loadSemester(id: number) {
  loading.value = true
  loadError.value = null
  try {
    await loadSemesterData(id)
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取排课工作台，请重试。')
  } finally {
    loading.value = false
  }
}

async function loadPage() {
  loading.value = true
  loadError.value = null
  try {
    await semesterContext.load()
    semesters.value = await listSemesters()
    const currentId = semesters.value.find((semester) => semester.is_current)?.id
      ?? semesterContext.currentSemesterId
      ?? semesters.value[0]?.id
    if (currentId) await loadSemesterData(currentId)
    else sid.value = null
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取排课工作台，请重试。')
  } finally {
    loading.value = false
  }
}

async function retryLoad() {
  if (sid.value) await loadSemester(sid.value)
  else await loadPage()
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  void loadPage()
})
onUnmounted(() => window.removeEventListener('keydown', onKey))

async function onViewChange(next: ViewKind) {
  view.value = next
  clearPlacement()
  await loadPeriods()
}

async function onClassChange(id: number) {
  classId.value = id
  clearPlacement()
  await loadPeriods()
}

async function onDraftChange(id: number) {
  loading.value = true
  loadError.value = null
  ttId.value = id
  resetWorkspaceHistory()
  try {
    await refreshTimetable()
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取所选课表草稿，请重试。')
  } finally {
    loading.value = false
  }
}

const visibleEntries = computed<GridEntry[]>(() => {
  const all = tt.value?.entries ?? []
  let entries = all
  if (view.value === 'class') {
    entries = classId.value ? all.filter((entry) => entry.class_ids.includes(classId.value!)) : []
  } else if (view.value === 'teacher') {
    entries = teacherId.value ? all.filter((entry) => entry.teacher_ids.includes(teacherId.value!)) : []
  } else {
    entries = roomId.value ? all.filter((entry) => entry.room_id === roomId.value) : []
  }
  return entries.map((entry) => ({
    id: entry.id,
    weekday: entry.weekday,
    period_no: entry.period_no,
    span: entry.span,
    locked: entry.locked,
    subject: entry.subject,
    teacher: view.value === 'class' ? entry.teachers.join('、') : entry.classes.join('、'),
    room: entry.room ?? undefined,
  }))
})

const placedByAssignment = computed(() => {
  const placed = new Map<number, number>()
  for (const entry of tt.value?.entries ?? []) {
    placed.set(entry.course_assignment_id, (placed.get(entry.course_assignment_id) ?? 0) + entry.span)
  }
  return placed
})

interface TrayItem { a: Assignment; remaining: number; span: number }
const selectedClassAssignments = computed(() => {
  if (view.value !== 'class' || !classId.value) return []
  return assignments.value.filter((assignment) => (
    assignment.scheduling_unit.classes.some((item) => item.id === classId.value)
  ))
})
const trayItems = computed<TrayItem[]>(() => {
  return selectedClassAssignments.value
    .map((assignment) => {
      const remaining = assignment.periods_per_week - (placedByAssignment.value.get(assignment.id) ?? 0)
      const block = assignment.block_rules[0]
      const span = block && remaining >= block.block_size ? block.block_size : 1
      return { a: assignment, remaining, span }
    })
    .filter((item) => item.remaining > 0)
})
const totalRemaining = computed(() => trayItems.value.reduce((total, item) => total + item.remaining, 0))
const lockedCount = computed(() => visibleEntries.value.filter((entry) => entry.locked).length)

interface WbDrag extends DragData { assignmentId: number; span: number }
const dragging = ref<WbDrag | null>(null)
const selectedAssignmentId = ref<number | null>(null)
const selectedEntryId = ref<number | null>(null)
const feedback = ref<DropFeedback | null>(null)
let lastKey = ''
let checkToken = 0

const selectedTrayItem = computed(() => (
  trayItems.value.find((item) => item.a.id === selectedAssignmentId.value) ?? null
))
const selectedEntry = computed(() => (
  tt.value?.entries.find((entry) => entry.id === selectedEntryId.value) ?? null
))
const keyboardPlacement = computed<WbDrag | null>(() => {
  const item = selectedTrayItem.value
  if (item) return { source: 'tray', assignmentId: item.a.id, span: item.span }
  const entry = selectedEntry.value
  if (!entry || entry.locked) return null
  return {
    source: 'grid',
    entryId: entry.id,
    assignmentId: entry.course_assignment_id,
    span: entry.span,
  }
})
const activeInteraction = computed(() => dragging.value ?? keyboardPlacement.value)
const placementLabel = computed(() => (
  selectedTrayItem.value?.a.subject.name ?? selectedEntry.value?.subject ?? '所选课程'
))

function clearFeedback() {
  feedback.value = null
  lastKey = ''
  checkToken += 1
}

function clearDrag() {
  dragging.value = null
  clearFeedback()
}

function clearPlacement() {
  selectedAssignmentId.value = null
  selectedEntryId.value = null
  clearDrag()
}

function togglePlacement(item: TrayItem) {
  if (readonly.value || busy.value) return
  dragging.value = null
  selectedEntryId.value = null
  selectedAssignmentId.value = selectedAssignmentId.value === item.a.id ? null : item.a.id
  clearFeedback()
}

function onTrayDragStart(item: TrayItem, event: DragEvent) {
  selectedAssignmentId.value = null
  selectedEntryId.value = null
  clearFeedback()
  const data: WbDrag = { source: 'tray', assignmentId: item.a.id, span: item.span }
  dragging.value = data
  event.dataTransfer?.setData('application/json', JSON.stringify(data))
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

function onGridDragStart(data: DragData) {
  selectedAssignmentId.value = null
  selectedEntryId.value = null
  clearFeedback()
  const entry = tt.value?.entries.find((item) => item.id === data.entryId)
  if (!entry) return
  dragging.value = {
    source: 'grid',
    entryId: entry.id,
    assignmentId: entry.course_assignment_id,
    span: entry.span,
  }
}

async function requestConflict(
  data: WbDrag,
  target: { weekday: number; period_no: number },
  force = false,
) {
  if (!ttId.value) return null
  const key = `${data.source}-${data.assignmentId}-${data.entryId ?? ''}-${target.weekday}-${target.period_no}`
  if (!force && key === lastKey) return null
  lastKey = key
  const token = ++checkToken
  try {
    const result = await checkConflict(ttId.value, {
      course_assignment_id: data.assignmentId,
      weekday: target.weekday,
      period_no: target.period_no,
      span: data.span,
      ...(data.source === 'grid' ? { ignore_entry_id: data.entryId as number } : {}),
    })
    if (token !== checkToken) return null
    feedback.value = {
      weekday: target.weekday,
      period_no: target.period_no,
      ok: result.ok,
      reason: result.conflicts[0]?.message,
    }
    return result
  } catch {
    if (token === checkToken) {
      feedback.value = {
        weekday: target.weekday,
        period_no: target.period_no,
        ok: false,
        reason: '冲突检查失败，请重试',
      }
    }
    return null
  }
}

async function onCheck(target: { weekday: number; period_no: number }) {
  const data = dragging.value ?? keyboardPlacement.value
  if (!data || readonly.value) return
  await requestConflict(data, target)
}

const saveState = ref<SaveState>('idle')
const saveStatusText = computed(() => {
  if (readonly.value) return '只读，不会保存更改'
  return {
    idle: '更改会实时保存',
    saving: '正在保存',
    saved: '已保存',
    error: '保存失败，请重试',
  }[saveState.value]
})

interface Cmd { undo: () => Promise<void>; redo: () => Promise<void> }
const UNDO_LIMIT = 20
const undoStack = ref<Cmd[]>([])
const redoStack = ref<Cmd[]>([])
const busy = ref(false)

function pushUndo(command: Cmd) {
  undoStack.value.push(command)
  if (undoStack.value.length > UNDO_LIMIT) undoStack.value.shift()
  redoStack.value = []
}

function resetWorkspaceHistory() {
  clearPlacement()
  undoStack.value = []
  redoStack.value = []
  saveState.value = 'idle'
}

async function performDrop(data: WbDrag, target: { weekday: number; period_no: number }) {
  if (readonly.value || busy.value || !ttId.value) return
  const id = ttId.value
  const movedEntry = data.source === 'grid'
    ? tt.value?.entries.find((entry) => entry.id === data.entryId)
    : null
  if (data.source === 'grid' && !movedEntry) return

  clearFeedback()
  busy.value = true
  saveState.value = 'saving'
  try {
    if (data.source === 'tray') {
      const before = new Set((tt.value?.entries ?? []).map((entry) => entry.id))
      const updated = await placeEntry(id, {
        course_assignment_id: data.assignmentId,
        weekday: target.weekday,
        period_no: target.period_no,
        span: data.span,
      })
      tt.value = updated
      let createdId = updated.entries.find((entry) => !before.has(entry.id))?.id
      pushUndo({
        undo: async () => {
          if (createdId !== undefined) await deleteEntry(id, createdId)
          await refreshTimetable()
        },
        redo: async () => {
          const ids = new Set((tt.value?.entries ?? []).map((entry) => entry.id))
          const next = await placeEntry(id, {
            course_assignment_id: data.assignmentId,
            weekday: target.weekday,
            period_no: target.period_no,
            span: data.span,
          })
          tt.value = next
          createdId = next.entries.find((entry) => !ids.has(entry.id))?.id
        },
      })
    } else {
      const entry = movedEntry!
      const from = { weekday: entry.weekday, period_no: entry.period_no }
      const to = { weekday: target.weekday, period_no: target.period_no }
      tt.value = await moveEntry(id, entry.id, to)
      pushUndo({
        undo: async () => { tt.value = await moveEntry(id, entry.id, from) },
        redo: async () => { tt.value = await moveEntry(id, entry.id, to) },
      })
    }
    selectedEntryId.value = null
    saveState.value = 'saved'
  } catch (error) {
    saveState.value = 'error'
    message.error(conflictText((error as ApiError).detail))
  } finally {
    busy.value = false
  }
}

async function onDrop(target: { weekday: number; period_no: number }) {
  const data = dragging.value
  clearDrag()
  if (data) await performDrop(data, target)
}

async function onKeyboardActivate(target: { weekday: number; period_no: number }) {
  const data = keyboardPlacement.value
  if (!data || readonly.value || busy.value) return
  const result = await requestConflict(data, target, true)
  if (!result) {
    message.error('冲突检查失败，请重试')
    return
  }
  if (!result.ok) {
    message.warning(result.conflicts[0]?.message ?? '此时段存在冲突')
    return
  }
  await performDrop(data, target)
}

function onGridMove(gridEntry: GridEntry) {
  if (readonly.value || busy.value) return
  const entryId = Number(gridEntry.id)
  const entry = tt.value?.entries.find((item) => item.id === entryId)
  if (!entry) return
  if (entry.locked) {
    message.warning('锁定单元格不可移动，请先解锁')
    return
  }
  dragging.value = null
  selectedAssignmentId.value = null
  selectedEntryId.value = selectedEntryId.value === entry.id ? null : entry.id
  clearFeedback()
}

async function removePlacedEntry(entryId: number) {
  if (readonly.value || busy.value || !ttId.value) return
  const id = ttId.value
  const entry = tt.value?.entries.find((item) => item.id === entryId)
  if (!entry) return
  if (entry.locked) {
    message.warning('锁定单元格不可移除，请先解锁')
    return
  }

  const snapshot = {
    assignmentId: entry.course_assignment_id,
    weekday: entry.weekday,
    periodNo: entry.period_no,
    span: entry.span,
  }
  let currentId = entry.id
  busy.value = true
  saveState.value = 'saving'
  try {
    await deleteEntry(id, currentId)
    await refreshTimetable()
    pushUndo({
      undo: async () => {
        const updated = await placeEntry(id, {
          course_assignment_id: snapshot.assignmentId,
          weekday: snapshot.weekday,
          period_no: snapshot.periodNo,
          span: snapshot.span,
        })
        tt.value = updated
        const restored = updated.entries.find((item) => (
          item.course_assignment_id === snapshot.assignmentId
          && item.weekday === snapshot.weekday
          && item.period_no === snapshot.periodNo
        ))
        if (restored) currentId = restored.id
      },
      redo: async () => {
        await deleteEntry(id, currentId)
        await refreshTimetable()
      },
    })
    saveState.value = 'saved'
  } catch (error) {
    saveState.value = 'error'
    message.error(conflictText((error as ApiError).detail))
  } finally {
    busy.value = false
  }
}

async function onGridRemove(gridEntry: GridEntry) {
  clearPlacement()
  await removePlacedEntry(Number(gridEntry.id))
}

async function onTrayDrop(event: DragEvent) {
  event.preventDefault()
  const data = dragging.value
  clearDrag()
  if (!data || data.source !== 'grid') return
  await removePlacedEntry(data.entryId as number)
}

async function onSelect(gridEntry: GridEntry) {
  if (readonly.value || busy.value || !ttId.value) return
  const id = ttId.value
  const entry = tt.value?.entries.find((item) => item.id === gridEntry.id)
  if (!entry) return
  const next = !entry.locked
  busy.value = true
  saveState.value = 'saving'
  try {
    tt.value = await lockEntry(id, entry.id, next)
    pushUndo({
      undo: async () => { tt.value = await lockEntry(id, entry.id, !next) },
      redo: async () => { tt.value = await lockEntry(id, entry.id, next) },
    })
    saveState.value = 'saved'
    message.info(next ? `已锁定“${entry.subject}”` : `已解锁“${entry.subject}”`)
  } catch (error) {
    saveState.value = 'error'
    message.error(apiErrorMessage(error, '锁定状态保存失败'))
  } finally {
    busy.value = false
  }
}

async function doUndo() {
  if (readonly.value || busy.value) return
  const command = undoStack.value.at(-1)
  if (!command) return
  busy.value = true
  saveState.value = 'saving'
  try {
    await command.undo()
    undoStack.value.pop()
    redoStack.value.push(command)
    saveState.value = 'saved'
  } catch {
    saveState.value = 'error'
    message.error('撤销失败')
  } finally {
    busy.value = false
  }
}

async function doRedo() {
  if (readonly.value || busy.value) return
  const command = redoStack.value.at(-1)
  if (!command) return
  busy.value = true
  saveState.value = 'saving'
  try {
    await command.redo()
    redoStack.value.pop()
    undoStack.value.push(command)
    saveState.value = 'saved'
  } catch {
    saveState.value = 'error'
    message.error('重做失败')
  } finally {
    busy.value = false
  }
}

function onKey(event: KeyboardEvent) {
  if (!(event.ctrlKey || event.metaKey) || readonly.value) return
  const target = event.target as HTMLElement | null
  if (target?.closest('input, textarea, [contenteditable="true"]')) return
  const key = event.key.toLowerCase()
  if (key === 'z' && !event.shiftKey) {
    event.preventDefault()
    void doUndo()
  } else if (key === 'y' || (key === 'z' && event.shiftKey)) {
    event.preventDefault()
    void doRedo()
  }
}
</script>

<template>
  <div class="scheduling-page workbench-page" data-testid="workbench-page">
    <header class="scheduling-page-header">
      <div>
        <p class="scheduling-eyebrow">{{ '排课作业' }}</p>
        <h1>{{ '排课工作台' }}</h1>
        <p>{{ '在班级课表中处理未排课程，并从教师或教室/场地视角核对结果。' }}</p>
      </div>
      <div class="scheduling-header-actions workbench-header-actions">
        <n-select
          v-if="semesters.length"
          v-accessible-select="'选择工作学期'"
          :value="sid"
          :options="semesterOptions"
          :placeholder="'选择学期'"
          data-testid="wb-semester"
          @update:value="loadSemester"
        />
        <n-select
          v-if="drafts.length"
          v-accessible-select="'选择课表草稿'"
          :value="ttId"
          :options="draftOptions"
          data-testid="wb-draft"
          @update:value="onDraftChange"
        />
      </div>
    </header>

    <section v-if="loading" class="scheduling-state" data-testid="workbench-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取排课工作台' }}</strong>
      <span>{{ '课表草稿和教学任务加载完成后会显示在这里。' }}</span>
    </section>

    <section v-else-if="loadError" class="scheduling-state scheduling-state-error" data-testid="workbench-error" role="alert">
      <AlertTriangle :size="23" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '当前工作面没有写入任何更改。' }}</span>
      <n-button type="primary" data-testid="workbench-retry" @click="retryLoad">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>

    <section v-else-if="!sid" class="scheduling-state" data-testid="workbench-empty">
      <Clock3 :size="24" aria-hidden="true" />
      <strong>{{ '尚未创建可用学期' }}</strong>
      <span>{{ '先创建学期和作息时间表，再进入排课工作台。' }}</span>
      <n-button type="primary" @click="router.push({ name: 'semesters' })">{{ '前往学期配置' }}</n-button>
    </section>

    <template v-else>
      <section class="scheduling-panel workbench-toolbar" aria-label="课表筛选与操作">
        <div class="workbench-view-controls">
          <div role="radiogroup" aria-label="课表视角">
            <n-radio-group :value="view" @update:value="onViewChange">
              <n-radio-button value="class" data-testid="wb-view-class">{{ '班级视图' }}</n-radio-button>
              <n-radio-button value="teacher" data-testid="wb-view-teacher">{{ '教师视图' }}</n-radio-button>
              <n-radio-button value="room" data-testid="wb-view-room">{{ '教室/场地视图' }}</n-radio-button>
            </n-radio-group>
          </div>
          <n-select
            v-if="view === 'class'"
            v-accessible-select="'选择班级'"
            :value="classId"
            :options="classOptions"
            :placeholder="'选择班级'"
            data-testid="wb-class"
            filterable
            @update:value="onClassChange"
          />
          <n-select
            v-else-if="view === 'teacher'"
            v-model:value="teacherId"
            v-accessible-select="'选择教师'"
            :options="teacherOptions"
            :placeholder="'选择教师'"
            data-testid="wb-teacher"
            filterable
          />
          <n-select
            v-else
            v-model:value="roomId"
            v-accessible-select="'选择教室/场地'"
            :options="roomOptions"
            :placeholder="'选择教室/场地'"
            data-testid="wb-room"
            filterable
          />
        </div>

        <div class="workbench-command-bar">
          <div
            class="workbench-save-status"
            :data-state="readonly ? 'readonly' : saveState"
            data-testid="workbench-save-status"
            role="status"
            aria-live="polite"
          >
            <ShieldCheck v-if="readonly" :size="14" aria-hidden="true" />
            <Save v-else-if="saveState === 'idle' || saveState === 'saving'" :size="14" aria-hidden="true" />
            <CheckCircle2 v-else-if="saveState === 'saved'" :size="14" aria-hidden="true" />
            <AlertTriangle v-else :size="14" aria-hidden="true" />
            <span>{{ saveStatusText }}</span>
          </div>
          <n-button
            quaternary
            circle
            data-testid="wb-undo"
            :disabled="readonly || busy || !undoStack.length"
            :title="'撤销（Ctrl/Cmd+Z）'"
            :aria-label="'撤销（Ctrl/Cmd+Z）'"
            @click="doUndo"
          >
            <template #icon><Undo2 :size="17" aria-hidden="true" /></template>
          </n-button>
          <n-button
            quaternary
            circle
            data-testid="wb-redo"
            :disabled="readonly || busy || !redoStack.length"
            :title="'重做（Ctrl/Cmd+Shift+Z）'"
            :aria-label="'重做（Ctrl/Cmd+Shift+Z）'"
            @click="doRedo"
          >
            <template #icon><Redo2 :size="17" aria-hidden="true" /></template>
          </n-button>
        </div>
      </section>

      <n-alert v-if="readonlyReason" type="info" data-testid="workbench-readonly">
        <template #icon><ShieldCheck :size="17" aria-hidden="true" /></template>
        {{ readonlyReason }}
      </n-alert>

      <section v-if="!tt" class="scheduling-state workbench-inline-state" data-testid="workbench-no-draft">
        <Save :size="22" aria-hidden="true" />
        <strong>{{ '当前学期还没有课表草稿' }}</strong>
        <span>{{ canEdit ? '重新读取工作台后将创建默认草稿。' : '排课管理员创建草稿后即可在此查看。' }}</span>
        <n-button v-if="canEdit" type="primary" @click="retryLoad">{{ '重新读取' }}</n-button>
      </section>

      <section v-else-if="classes.length === 0" class="scheduling-state workbench-inline-state" data-testid="workbench-no-classes">
        <ShieldCheck :size="22" aria-hidden="true" />
        <strong>{{ '当前学期还没有班级' }}</strong>
        <span>{{ '维护班级和教学任务后，工作台会按班级显示待排课程。' }}</span>
        <n-button type="primary" @click="router.push({ name: 'basedata' })">{{ '前往基础数据' }}</n-button>
      </section>

      <section v-else-if="periods.length === 0" class="scheduling-state workbench-inline-state" data-testid="workbench-no-periods">
        <Clock3 :size="22" aria-hidden="true" />
        <strong>{{ '当前学期还没有作息时间表' }}</strong>
        <span>{{ '配置可排课节次后，课表网格会显示在这里。' }}</span>
        <n-button type="primary" @click="router.push({ name: 'semesters' })">{{ '前往学期配置' }}</n-button>
      </section>

      <div v-else class="workbench-layout" data-testid="workbench-workspace">
        <section class="scheduling-panel workbench-grid-panel">
          <header class="scheduling-panel-heading compact-heading workbench-grid-heading">
            <div>
              <p class="scheduling-eyebrow">{{ view === 'class' ? '可编辑课表' : '核对课表' }}</p>
              <h2>
                {{ view === 'class'
                  ? (classOptions.find((item) => item.value === classId)?.label ?? '班级课表')
                  : view === 'teacher'
                    ? (teacherOptions.find((item) => item.value === teacherId)?.label ?? '教师课表')
                    : (roomOptions.find((item) => item.value === roomId)?.label ?? '教室/场地课表') }}
              </h2>
            </div>
            <div class="workbench-grid-summary">
              <n-tag size="small" :type="lockedCount ? 'warning' : 'default'">{{ '已锁定' }} {{ lockedCount }}</n-tag>
              <n-tag size="small">{{ '已排' }} {{ visibleEntries.length }}</n-tag>
            </div>
          </header>
          <TimetableGrid
            :periods="periods"
            :num-weekdays="numWeekdays"
            :entries="visibleEntries"
            :dragging="activeInteraction"
            :feedback="feedback"
            :readonly="readonly"
            :placement-label="placementLabel"
            @dragstart="onGridDragStart"
            @dragend="clearDrag"
            @check="onCheck"
            @drop="onDrop"
            @activate="onKeyboardActivate"
            @select="onSelect"
            @move="onGridMove"
            @remove="onGridRemove"
          />
        </section>

        <aside
          v-if="view === 'class'"
          class="scheduling-panel workbench-tray"
          :class="{ 'is-readonly': readonly }"
          data-testid="wb-tray"
          :aria-label="readonly ? '未排课程，只读' : '未排课程'"
          @dragover.prevent
          @drop="onTrayDrop"
        >
          <header class="scheduling-panel-heading compact-heading">
            <div>
              <p class="scheduling-eyebrow">{{ '课程池' }}</p>
              <h2>{{ '未排课程' }}</h2>
            </div>
            <n-tag
              size="small"
              :type="totalRemaining === 0 ? 'success' : 'info'"
              data-testid="wb-remaining"
            >
              {{ '剩余' }} {{ totalRemaining }} {{ '节' }}
            </n-tag>
          </header>

          <div
            v-if="selectedClassAssignments.length === 0"
            class="workbench-tray-empty workbench-tray-unconfigured"
            data-testid="wb-tray-unconfigured"
          >
            <AlertTriangle :size="20" aria-hidden="true" />
            <strong>{{ '本班尚未配置教学任务' }}</strong>
          </div>
          <div v-else-if="trayItems.length === 0" class="workbench-tray-empty" data-testid="wb-tray-empty">
            <CheckCircle2 :size="20" aria-hidden="true" />
            <strong>{{ '本班课程已全部排入' }}</strong>
          </div>
          <div v-else class="workbench-tray-list">
            <button
              v-for="item in trayItems"
              :key="item.a.id"
              type="button"
              class="workbench-tray-item"
              :class="{ 'is-selected': selectedAssignmentId === item.a.id }"
              :data-testid="`wb-tray-${item.a.subject.name}`"
              :aria-pressed="selectedAssignmentId === item.a.id"
              :disabled="readonly || busy"
              :draggable="!readonly && !busy"
              @click="togglePlacement(item)"
              @dragstart="onTrayDragStart(item, $event)"
              @dragend="clearDrag"
            >
              <span class="workbench-tray-subject">
                <MousePointer2 v-if="selectedAssignmentId === item.a.id" :size="14" aria-hidden="true" />
                <strong>{{ item.a.subject.name }}</strong>
                <n-tag v-if="item.span > 1" size="tiny" type="warning">{{ item.span }}{{ '连堂' }}</n-tag>
              </span>
              <span class="workbench-tray-meta">
                {{ item.a.teachers.map((teacher) => teacher.name).join('、') }}
                <span>{{ '剩余' }} {{ item.remaining }} {{ '节' }}</span>
              </span>
            </button>
          </div>
        </aside>
      </div>
    </template>
  </div>
</template>
