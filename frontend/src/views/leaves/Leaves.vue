<script setup lang="ts">
import {
  Ban, CalendarDays, CheckCircle2, ClipboardClock, Clock3, Info, RefreshCw, UserRound,
} from '@lucide/vue'
import {
  NAlert, NButton, NDatePicker, NEmpty, NInput, NPopconfirm, NSelect, NSpin, NSwitch,
  NTag, NTimePicker, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import { listTeachers } from '@/api/basedata'
import { cancelLeave, createLeave, listLeaveTypes, listLeaves } from '@/api/leaves'
import type { AffectedPeriod, LeaveRequest } from '@/api/leaves'
import { listSemesters } from '@/api/semesters'
import { publishedSemesters } from '@/api/timetables'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import { useAuthStore } from '@/stores/auth'
import { useSemesterContextStore } from '@/stores/semesterContext'
import '../substitution/operations-workspace.css'

const auth = useAuthStore()
const semesterContext = useSemesterContextStore()
const message = useMessage()

// 排课管理员/主任可代登、可看全校;教师只登记自己的假、只看自己的假单。
const canManage = computed(() =>
  auth.hasRole('admin') || auth.hasRole('scheduler') || auth.hasRole('director'))

const semesters = ref<{ id: number; label: string }[]>([])
const sid = ref<number | null>(null)
const leaveTypes = ref<Record<string, string>>({})
const teachers = ref<{ id: number; name: string }[]>([])
const leaves = ref<LeaveRequest[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
const saving = ref(false)
const cancellingId = ref<number | null>(null)

// 后端的保护性上限(leaves.MAX_LEAVE_ROWS)。刚好取到条数上限,几乎必然是被截断了。
const MAX_LEAVE_ROWS = 1000
const truncated = computed(() => leaves.value.length >= MAX_LEAVE_ROWS)

const form = ref({
  teacherId: null as number | null,
  leaveType: 'sick',
  // NDatePicker 返回 timestamp,提交前再转成 YYYY-MM-DD。
  startDate: null as number | null,
  endDate: null as number | null,
  halfDay: false,
  startTime: null as number | null,
  endTime: null as number | null,
  reason: '',
})

const semesterOptions = computed(() => semesters.value.map((semester) => ({
  label: semester.label,
  value: semester.id,
})))
const teacherOptions = computed(() => teachers.value.map((teacher) => ({
  label: teacher.name,
  value: teacher.id,
})))
const typeOptions = computed(() =>
  Object.entries(leaveTypes.value).map(([value, label]) => ({ label, value })))

/** 本机日期，不使用 toISOString，避免 UTC 换算导致日期变化。 */
function toDate(ts: number | null): string | null {
  if (ts === null) return null
  const date = new Date(ts)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function toTime(ts: number | null): string | null {
  if (ts === null) return null
  const date = new Date(ts)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

// 保持既有读取顺序：先请假单，再按权限读取教师选项。
async function refreshRecords() {
  if (!sid.value) return
  const nextLeaves = await listLeaves(sid.value)
  const nextTeachers = canManage.value ? await listTeachers(sid.value) : []
  leaves.value = nextLeaves
  teachers.value = nextTeachers
}

async function onSemesterChange(id: number) {
  sid.value = id
  loading.value = true
  loadError.value = null
  try {
    await refreshRecords()
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取请假记录，请重试。')
  } finally {
    loading.value = false
  }
}

async function loadPage() {
  loading.value = true
  loadError.value = null
  try {
    // 保持既有初始化顺序：类型 -> 学期 -> 请假单 -> 可代登记教师。
    leaveTypes.value = await listLeaveTypes()
    await semesterContext.load()
    semesters.value = canManage.value ? await listSemesters() : await publishedSemesters()
    if (semesters.value.length) {
      sid.value = canManage.value
        ? (semesters.value.find((semester) => semester.id === semesterContext.currentSemesterId)?.id
          ?? semesters.value[0].id)
        : (semesterContext.currentSemesterId ?? semesters.value[0].id)
      await refreshRecords()
    } else {
      sid.value = null
      leaves.value = []
      teachers.value = []
    }
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取请假登记，请重试。')
  } finally {
    loading.value = false
  }
}

async function retryLoad() {
  if (sid.value) await onSemesterChange(sid.value)
  else await loadPage()
}

onMounted(loadPage)

const canSubmit = computed(() =>
  !!sid.value && !!form.value.startDate && !!form.value.endDate
  && (!semesterContext.authoritative || semesterContext.isCurrent(sid.value))
  && (!canManage.value || !!form.value.teacherId))
const canWriteSelectedSemester = computed(() =>
  !!sid.value && (!semesterContext.authoritative || semesterContext.isCurrent(sid.value)))

async function onSubmit() {
  if (!sid.value || !canSubmit.value || saving.value) return
  saving.value = true
  let created: LeaveRequest
  try {
    created = await createLeave(sid.value, {
      teacher_id: canManage.value ? form.value.teacherId : null,
      leave_type: form.value.leaveType,
      start_date: toDate(form.value.startDate)!,
      end_date: toDate(form.value.endDate)!,
      start_time: form.value.halfDay ? toTime(form.value.startTime) : null,
      end_time: form.value.halfDay ? toTime(form.value.endTime) : null,
      reason: form.value.reason,
    })
  } catch (error) {
    message.error(apiErrorMessage(error, '登记失败'))
    saving.value = false
    return
  }

  message.success(
    created.affected_count
      ? `已登记，共 ${created.affected_count} 节课受影响`
      : '已登记（这段期间没有课）',
  )
  form.value.reason = ''
  try {
    await refreshRecords()
  } catch (error) {
    loadError.value = apiErrorMessage(error, '请假已登记，但暂时无法刷新记录。')
  } finally {
    saving.value = false
  }
}

async function onCancel(leave: LeaveRequest) {
  if (!canWriteSelectedSemester.value || cancellingId.value !== null) return
  cancellingId.value = leave.id
  try {
    const result = await cancelLeave(leave.id)
    if (result.notified_teachers.length) {
      message.success(`已销假，已通知 ${result.notified_teachers.join('、')} 取消代课`)
    } else {
      message.success('已销假')
    }
    try {
      await refreshRecords()
    } catch (error) {
      loadError.value = apiErrorMessage(error, '请假已销假，但暂时无法刷新记录。')
    }
  } catch (error) {
    message.error(apiErrorMessage(error, '销假失败'))
  } finally {
    cancellingId.value = null
  }
}

const STATUS_TAG = computed<Record<AffectedPeriod['status'], {
  type: 'warning' | 'success' | 'info' | 'default'
  label: string
}>>(() => ({
  pending: { type: 'warning', label: '待处理' },
  resolved: { type: 'success', label: '已处理' },
  completed: { type: 'info', label: '已完成' },
  cancelled: { type: 'default', label: '已取消' },
}))

const WEEKDAYS = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

/** “2026-11-11（星期三）”便于排课管理员快速核对日期。 */
function withWeekday(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number)
  return `${iso}（${WEEKDAYS[new Date(year, month - 1, day).getDay()]}）`
}

function rangeText(leave: LeaveRequest): string {
  if (leave.start_date !== leave.end_date) {
    return `${withWeekday(leave.start_date)} ~ ${withWeekday(leave.end_date)}`
  }
  if (leave.start_time || leave.end_time) {
    const from = leave.start_time?.slice(0, 5) ?? '上课起'
    const to = leave.end_time?.slice(0, 5) ?? '放学'
    return `${withWeekday(leave.start_date)} ${from}~${to}`
  }
  return `${withWeekday(leave.start_date)} 全天`
}
</script>

<template>
  <main class="operations-page" data-testid="leaves-page">
    <header class="operations-page-header">
      <div>
        <p class="operations-eyebrow">{{ '调课与代课' }}</p>
        <h1>{{ '请假登记' }}</h1>
        <p>{{ canManage ? '代教师登记请假，并核对已发布课表中受影响的节次。' : '登记和管理我的请假，查看受影响的已发布课程。' }}</p>
      </div>
      <div class="operations-header-actions">
        <n-select
          v-if="semesters.length"
          v-accessible-select="'选择工作学期'"
          :value="sid"
          :options="semesterOptions"
          :placeholder="'选择学期'"
          data-testid="leaves-semester-select"
          @update:value="onSemesterChange"
        />
      </div>
    </header>

    <section v-if="loading" class="operations-state" data-testid="leaves-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取请假登记' }}</strong>
      <span>{{ '请假类型、学期和记录加载完成后会显示在这里。' }}</span>
    </section>

    <section v-else-if="loadError" class="operations-state operations-state-error" data-testid="leaves-error" role="alert">
      <RefreshCw :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '已填写的请假信息仍保留在当前页面。' }}</span>
      <n-button type="primary" data-testid="leaves-retry" @click="retryLoad">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>

    <section v-else-if="!sid" class="operations-state" data-testid="leaves-no-semester">
      <CalendarDays :size="24" aria-hidden="true" />
      <strong>{{ '暂无可登记请假的学期' }}</strong>
      <span>{{ canManage ? '请先创建学期，再登记教师请假。' : '已发布学期可用后，即可登记我的请假。' }}</span>
    </section>

    <template v-else>
      <section class="operations-panel leave-form-surface" data-testid="leave-form-surface">
        <header class="operations-panel-heading">
          <div>
            <p class="operations-eyebrow">{{ '登记工作面' }}</p>
            <h2>{{ canManage ? '登记请假（可代教师登记）' : '登记我的请假' }}</h2>
            <p>{{ '选择完整日期范围；仅在半日请假时指定起止时间。' }}</p>
          </div>
          <ClipboardClock :size="20" class="operations-heading-icon" aria-hidden="true" />
        </header>

        <div class="leave-form-grid">
          <div v-if="canManage" class="operations-field">
            <label>{{ '教师' }}</label>
            <n-select
              v-model:value="form.teacherId"
              v-accessible-select="'请假教师'"
              :options="teacherOptions"
              filterable
              :placeholder="'选择教师'"
              data-testid="lv-teacher"
            />
          </div>

          <div class="operations-field">
            <label>{{ '请假类型' }}</label>
            <n-select
              v-model:value="form.leaveType"
              v-accessible-select="'请假类型'"
              :options="typeOptions"
              data-testid="lv-type"
            />
          </div>

          <div class="operations-field">
            <label>{{ '开始日期' }}</label>
            <n-date-picker
              v-model:value="form.startDate"
              type="date"
              :input-props="{ 'aria-label': '请假开始日期' }"
              data-testid="lv-start"
            />
          </div>

          <div class="operations-field">
            <label>{{ '结束日期' }}</label>
            <n-date-picker
              v-model:value="form.endDate"
              type="date"
              :input-props="{ 'aria-label': '请假结束日期' }"
              data-testid="lv-end"
            />
          </div>

          <div class="leave-halfday-field">
            <div class="leave-halfday-toggle">
              <n-switch
                v-model:value="form.halfDay"
                aria-label="指定半日时段"
                data-testid="lv-halfday"
              />
              <div>
                <strong>{{ '指定时间（半天假）' }}</strong>
                <span>{{ '关闭时按全天请假处理' }}</span>
              </div>
            </div>
            <div v-if="form.halfDay" class="leave-time-range">
              <n-time-picker
                v-model:value="form.startTime"
                format="HH:mm"
                :input-props="{ 'aria-label': '请假开始时间' }"
                data-testid="lv-start-time"
              />
              <span aria-hidden="true">~</span>
              <n-time-picker
                v-model:value="form.endTime"
                format="HH:mm"
                :input-props="{ 'aria-label': '请假结束时间' }"
                data-testid="lv-end-time"
              />
            </div>
          </div>

          <div class="operations-field leave-reason-field">
            <label>{{ '事由（可选）' }}</label>
            <n-input
              v-model:value="form.reason"
              :placeholder="'填写请假事由'"
              maxlength="200"
              data-testid="lv-reason"
            />
          </div>
        </div>

        <div class="leave-form-footer">
          <p class="operations-hint">
            <Info :size="15" aria-hidden="true" />
            <span>{{ '受影响节次按“已发布课表”自动展开；周末与没有课的日子不会列入。' }}</span>
          </p>
          <n-button
            type="primary"
            :loading="saving"
            :disabled="!canSubmit || saving"
            data-testid="lv-submit"
            @click="onSubmit"
          >
            <template #icon><ClipboardClock :size="15" aria-hidden="true" /></template>
            {{ saving ? '登记中' : '登记请假' }}
          </n-button>
          <span class="sr-only" aria-live="polite">{{ saving ? '正在保存请假登记' : '' }}</span>
        </div>
      </section>

      <section class="operations-panel leave-records" data-testid="leave-records">
        <header class="operations-panel-heading">
          <div>
            <p class="operations-eyebrow">{{ '状态与影响' }}</p>
            <h2>{{ '请假记录' }}</h2>
            <p>{{ leaves.length ? `当前显示 ${leaves.length} 张请假单` : '当前学期还没有请假记录' }}</p>
          </div>
          <span v-if="leaves.length" class="operations-count">{{ leaves.length }}</span>
        </header>

        <n-alert v-if="truncated" type="warning" data-testid="lv-truncated">
          {{ `只显示最新的 ${MAX_LEAVE_ROWS} 张请假单，更早的未列出；要查询更早记录，请到“调课与代课记录”按日期范围查询。` }}
        </n-alert>

        <div v-if="!leaves.length" class="operations-inline-empty">
          <n-empty :description="'暂无请假记录'" />
        </div>

        <div v-else class="leave-record-list">
          <article v-for="leave in leaves" :key="leave.id" class="leave-record" data-testid="lv-card">
            <header class="leave-record-header">
              <div class="leave-record-title">
                <div class="leave-record-person">
                  <span class="operations-icon-box"><UserRound :size="16" aria-hidden="true" /></span>
                  <div>
                    <h3>{{ `${leave.teacher_name} · ${leave.leave_type_label} · ${rangeText(leave)}` }}</h3>
                  </div>
                </div>
                <div class="leave-statuses" aria-label="请假单状态">
                  <n-tag v-if="leave.status === 'cancelled'" type="default" size="small">
                    <template #icon><Ban :size="13" aria-hidden="true" /></template>
                    {{ '已销假' }}
                  </n-tag>
                  <template v-else>
                    <n-tag type="success" size="small">
                      <template #icon><CheckCircle2 :size="13" aria-hidden="true" /></template>
                      {{ '已登记' }}
                    </n-tag>
                    <n-tag type="warning" size="small" data-testid="lv-pending">
                      <template #icon><Clock3 :size="13" aria-hidden="true" /></template>
                      {{ '待处理' }} {{ leave.pending_count }} {{ '节' }}
                    </n-tag>
                  </template>
                </div>
              </div>

              <n-popconfirm v-if="leave.status === 'registered' && canWriteSelectedSemester" @positive-click="onCancel(leave)">
                <template #trigger>
                  <n-button
                    size="small"
                    type="error"
                    ghost
                    :loading="cancellingId === leave.id"
                    :disabled="cancellingId !== null"
                    data-testid="lv-cancel"
                  >
                    <template #icon><Ban :size="14" aria-hidden="true" /></template>
                    {{ '销假' }}
                  </n-button>
                </template>
                {{ '销假将取消所有受影响节次的处理方式，已被指派的代课教师会收到取消通知。确定吗？' }}
              </n-popconfirm>
            </header>

            <p v-if="leave.reason" class="leave-reason"><strong>{{ '事由' }}：</strong>{{ leave.reason }}</p>

            <n-alert v-if="!leave.affected_count" type="info" :bordered="false">
              {{ '这段期间没有课（周末，或课表尚未发布）' }}
            </n-alert>

            <div
              v-else
              class="operations-table-scroll"
              tabindex="0"
              aria-label="受影响节次列表"
            >
              <table class="operations-data-table leave-period-table" data-testid="lv-affected">
                <thead>
                  <tr>
                    <th>{{ '日期' }}</th>
                    <th>{{ '节次' }}</th>
                    <th>{{ '班级' }}</th>
                    <th>{{ '科目' }}</th>
                    <th>{{ '教室/场地' }}</th>
                    <th>{{ '状态' }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="period in leave.affected_periods" :key="period.id">
                    <td data-label="日期">{{ withWeekday(period.date) }}</td>
                    <td data-label="节次">{{ period.period_name }}</td>
                    <td data-label="班级">{{ period.class_names }}</td>
                    <td data-label="科目">{{ period.subject_name }}</td>
                    <td data-label="教室/场地">{{ period.room_name || '—' }}</td>
                    <td data-label="状态">
                      <n-tag
                        size="small"
                        :type="STATUS_TAG[period.status].type"
                        data-testid="lv-status"
                      >
                        <template #icon>
                          <Clock3 v-if="period.status === 'pending'" :size="13" aria-hidden="true" />
                          <Ban v-else-if="period.status === 'cancelled'" :size="13" aria-hidden="true" />
                          <CheckCircle2 v-else :size="13" aria-hidden="true" />
                        </template>
                        {{ STATUS_TAG[period.status].label }}
                      </n-tag>
                      <span v-if="period.handler_name" class="leave-handler">{{ period.handler_name }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <footer class="leave-record-footer">{{ '登记人' }}：{{ leave.created_by_name }}</footer>
          </article>
        </div>
      </section>
    </template>
  </main>
</template>
