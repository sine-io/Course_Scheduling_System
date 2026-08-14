<script setup lang="ts">
import {
  BookOpen, CheckCircle2, ChevronDown, ChevronUp, CircleAlert, Clock3, Inbox,
  RefreshCw, RotateCcw, Shuffle, UserRoundCheck, UsersRound, XCircle,
} from '@lucide/vue'
import {
  NAlert, NButton, NSelect, NSpin, NSwitch, NTag, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import { listLeaves } from '@/api/leaves'
import type { AffectedPeriod, LeaveRequest } from '@/api/leaves'
import { listSemesters } from '@/api/semesters'
import {
  assignSubstitution, clearSubstitution, getRecommendations, listSubstitutionTypes,
} from '@/api/substitutions'
import type { Candidate, Recommendation } from '@/api/substitutions'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import { useSemesterContextStore } from '@/stores/semesterContext'
import './operations-workspace.css'

const message = useMessage()
const semesterContext = useSemesterContextStore()

const semesters = ref<{ id: number; label: string }[]>([])
const sid = ref<number | null>(null)
const leaves = ref<LeaveRequest[]>([])
const types = ref<Record<string, string>>({})
const loading = ref(true)
const loadError = ref<string | null>(null)

const openId = ref<number | null>(null)
const rec = ref<Recommendation | null>(null)
const loadingRec = ref(false)
const recError = ref<string | null>(null)
const recommendationRequest = ref(0)
const countsHours = ref(true)

const actingKey = ref<string | null>(null)
const actionError = ref<{ periodId: number; message: string } | null>(null)
const canEdit = computed(() => (
  !semesterContext.authoritative || semesterContext.isCurrent(sid.value)
))

const WEEKDAYS = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

function withWeekday(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number)
  return `${iso}（${WEEKDAYS[new Date(year, month - 1, day).getDay()]}）`
}

const semesterOptions = computed(() => semesters.value.map((semester) => ({
  label: semester.label,
  value: semester.id,
})))

// 保留已处理节次，调度人员需要从同一队列撤回处理方式。
const activeLeaves = computed(() =>
  leaves.value.filter((leave) => leave.status === 'registered' && leave.affected_count > 0))
const pendingCount = computed(() => activeLeaves.value.reduce(
  (count, leave) => count + leave.affected_periods.filter((period) => period.status === 'pending').length,
  0,
))
const resolvedCount = computed(() => activeLeaves.value.reduce(
  (count, leave) => count + leave.affected_periods.filter((period) => period.status === 'resolved').length,
  0,
))

async function refreshLeaves() {
  if (!sid.value) return
  leaves.value = await listLeaves(sid.value)
}

function closeRecommendation() {
  recommendationRequest.value += 1
  openId.value = null
  rec.value = null
  recError.value = null
  loadingRec.value = false
}

async function onSemesterChange(id: number) {
  sid.value = id
  closeRecommendation()
  actionError.value = null
  loading.value = true
  loadError.value = null
  try {
    await refreshLeaves()
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取待处理请假，请重试。')
  } finally {
    loading.value = false
  }
}

async function loadPage() {
  loading.value = true
  loadError.value = null
  try {
    await semesterContext.load()
    // 保持既有请求顺序：学期和处理类型并发读取，随后读取首个学期的请假单。
    ;[semesters.value, types.value] = await Promise.all([
      listSemesters(),
      listSubstitutionTypes(),
    ])
    if (semesters.value.length) {
      sid.value = semesters.value.find((semester) => semester.id === semesterContext.currentSemesterId)?.id
        ?? semesters.value[0].id
      await refreshLeaves()
    } else {
      sid.value = null
      leaves.value = []
    }
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取调课与代课队列，请重试。')
  } finally {
    loading.value = false
  }
}

async function retryLoad() {
  if (sid.value) await onSemesterChange(sid.value)
  else await loadPage()
}

onMounted(loadPage)

async function loadRecommendation(period: AffectedPeriod) {
  const requestId = recommendationRequest.value + 1
  recommendationRequest.value = requestId
  rec.value = null
  recError.value = null
  loadingRec.value = true
  try {
    const result = await getRecommendations(period.id)
    if (recommendationRequest.value === requestId && openId.value === period.id) {
      rec.value = result
    }
  } catch (error) {
    if (recommendationRequest.value === requestId && openId.value === period.id) {
      recError.value = apiErrorMessage(error, '暂时无法计算候选教师，请重试。')
    }
  } finally {
    if (recommendationRequest.value === requestId && openId.value === period.id) {
      loadingRec.value = false
    }
  }
}

async function openPeriod(period: AffectedPeriod) {
  if (openId.value === period.id) {
    closeRecommendation()
    return
  }
  recommendationRequest.value += 1
  openId.value = period.id
  countsHours.value = true
  actionError.value = null
  await loadRecommendation(period)
}

async function assign(period: AffectedPeriod, type: string, candidate?: Candidate) {
  if (!canEdit.value || actingKey.value !== null) return
  const key = `${period.id}:${type}:${candidate?.teacher_id ?? 'none'}`
  actingKey.value = key
  actionError.value = null
  try {
    await assignSubstitution(period.id, {
      type,
      handler_teacher_id: candidate?.teacher_id ?? null,
      counts_toward_hours: type === 'substitute' ? countsHours.value : null,
    })
    message.success(candidate
      ? `已指派 ${candidate.teacher_name} ${types.value[type] ?? type}`
      : `已设为${types.value[type] ?? type}`)
    closeRecommendation()
  } catch (error) {
    const detail = apiErrorMessage(error, '指派失败')
    actionError.value = { periodId: period.id, message: detail }
    message.error(detail)
    actingKey.value = null
    return
  }

  try {
    await refreshLeaves()
  } catch (error) {
    loadError.value = apiErrorMessage(error, '处理已保存，但暂时无法刷新队列。')
  } finally {
    actingKey.value = null
  }
}

async function undo(period: AffectedPeriod) {
  if (!canEdit.value || actingKey.value !== null) return
  const key = `${period.id}:undo`
  actingKey.value = key
  actionError.value = null
  try {
    await clearSubstitution(period.id)
    message.info('已撤回处理方式，退回待处理')
  } catch (error) {
    const detail = apiErrorMessage(error, '撤回失败')
    actionError.value = { periodId: period.id, message: detail }
    message.error(detail)
    actingKey.value = null
    return
  }

  try {
    await refreshLeaves()
  } catch (error) {
    loadError.value = apiErrorMessage(error, '处理已撤回，但暂时无法刷新队列。')
  } finally {
    actingKey.value = null
  }
}

const STATUS = computed<Record<AffectedPeriod['status'], {
  type: 'warning' | 'success' | 'info' | 'default'
  label: string
}>>(() => ({
  pending: { type: 'warning', label: '待处理' },
  resolved: { type: 'success', label: '已处理' },
  completed: { type: 'info', label: '已完成' },
  cancelled: { type: 'default', label: '已取消' },
}))

function candidateTagType(candidate: Candidate): 'success' | 'info' | 'default' {
  if (candidate.same_subject) return 'success'
  if (candidate.at_school_that_day) return 'info'
  return 'default'
}

function isActing(period: AffectedPeriod, type: string, candidate?: Candidate): boolean {
  return actingKey.value === `${period.id}:${type}:${candidate?.teacher_id ?? 'none'}`
}
</script>

<template>
  <main class="operations-page" data-testid="substitutions-page">
    <header class="operations-page-header">
      <div>
        <p class="operations-eyebrow">{{ '调课与代课' }}</p>
        <h1>{{ '调课与代课处理' }}</h1>
        <p>{{ '逐节处理请假影响，核对候选教师后指派代课、合班、自习或取消课程。' }}</p>
      </div>
      <div class="operations-header-actions">
        <n-select
          v-if="semesters.length"
          v-accessible-select="'选择工作学期'"
          :value="sid"
          :options="semesterOptions"
          :placeholder="'选择学期'"
          data-testid="substitutions-semester-select"
          @update:value="onSemesterChange"
        />
      </div>
    </header>

    <section v-if="loading" class="operations-state" data-testid="substitutions-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取待处理请假' }}</strong>
      <span>{{ '学期、处理方式和受影响节次加载完成后会显示在这里。' }}</span>
    </section>

    <section v-else-if="loadError" class="operations-state operations-state-error" data-testid="substitutions-error" role="alert">
      <RefreshCw :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '未发送任何处理请求，可以直接重新读取。' }}</span>
      <n-button type="primary" data-testid="substitutions-retry" @click="retryLoad">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>

    <section v-else-if="!sid" class="operations-state" data-testid="substitutions-no-semester">
      <BookOpen :size="24" aria-hidden="true" />
      <strong>{{ '请先创建学期' }}</strong>
      <span>{{ '创建学期并发布课表后，受请假影响的节次会进入处理队列。' }}</span>
    </section>

    <section v-else-if="!activeLeaves.length" class="operations-state" data-testid="substitutions-empty">
      <Inbox :size="24" aria-hidden="true" />
      <strong>{{ '当前没有待处理的请假' }}</strong>
      <span>{{ '新的请假影响节次出现后，会按请假单汇总到这里。' }}</span>
    </section>

    <template v-else>
      <section class="substitution-summary" aria-label="处理队列摘要">
        <div>
          <Clock3 :size="17" aria-hidden="true" />
          <span>{{ '待处理节次' }}</span>
          <strong>{{ pendingCount }}</strong>
        </div>
        <div>
          <CheckCircle2 :size="17" aria-hidden="true" />
          <span>{{ '可撤回处理' }}</span>
          <strong>{{ resolvedCount }}</strong>
        </div>
        <div>
          <Shuffle :size="17" aria-hidden="true" />
          <span>{{ '受影响教师' }}</span>
          <strong>{{ activeLeaves.length }}</strong>
        </div>
      </section>

      <section class="substitution-queue" data-testid="substitution-queue">
        <n-alert v-if="!canEdit" type="info" data-testid="substitution-readonly">
          所选学期不是当前工作学期，历史代课记录只允许查看。
        </n-alert>
        <header class="operations-panel-heading">
          <div>
            <p class="operations-eyebrow">{{ '处理队列' }}</p>
            <h2>{{ '待处理请假' }}</h2>
            <p>{{ '展开单节课程后再选择处理方式；已处理节次可在原位撤回。' }}</p>
          </div>
          <span class="operations-count">{{ activeLeaves.length }}</span>
        </header>

        <article
          v-for="leave in activeLeaves"
          :key="leave.id"
          class="substitution-leave-card"
          data-testid="sub-leave"
        >
          <header class="substitution-leave-header">
            <div class="substitution-leave-title">
              <span class="operations-icon-box"><UserRoundCheck :size="16" aria-hidden="true" /></span>
              <div>
                <h3>{{ leave.teacher_name }} · {{ leave.leave_type_label }}</h3>
                <p>{{ withWeekday(leave.start_date) }}{{ leave.end_date !== leave.start_date ? ` ~ ${withWeekday(leave.end_date)}` : '' }}</p>
              </div>
            </div>
            <n-tag type="warning" size="small">
              <template #icon><Clock3 :size="13" aria-hidden="true" /></template>
              {{ '待处理' }} {{ leave.pending_count }} {{ '节' }}
            </n-tag>
          </header>

          <div class="substitution-period-list">
            <article
              v-for="period in leave.affected_periods"
              :key="period.id"
              class="substitution-period"
              :class="{ 'is-open': openId === period.id }"
              data-testid="sub-period"
            >
              <div class="substitution-period-row">
                <n-tag size="small" :type="STATUS[period.status].type">
                  <template #icon>
                    <Clock3 v-if="period.status === 'pending'" :size="13" aria-hidden="true" />
                    <CheckCircle2 v-else-if="period.status === 'resolved'" :size="13" aria-hidden="true" />
                    <XCircle v-else :size="13" aria-hidden="true" />
                  </template>
                  {{ STATUS[period.status].label }}
                </n-tag>

                <div class="substitution-period-main">
                  <strong>{{ period.period_name }} · {{ period.class_names }} {{ period.subject_name }}</strong>
                  <span>{{ withWeekday(period.date) }}{{ period.room_name ? ` · ${period.room_name}` : '' }}</span>
                </div>

                <div v-if="period.handler_name" class="substitution-handler" data-testid="sub-handler">
                  <UserRoundCheck :size="14" aria-hidden="true" />
                  <span>{{ period.handler_name }}</span>
                </div>

                <n-button
                  v-if="period.status === 'pending'"
                  size="small"
                  type="primary"
                  :disabled="actingKey !== null || !canEdit"
                  :aria-expanded="openId === period.id"
                  :aria-controls="`sub-panel-${period.id}`"
                  data-testid="sub-handle"
                  @click="openPeriod(period)"
                >
                  <template #icon>
                    <ChevronUp v-if="openId === period.id" :size="14" aria-hidden="true" />
                    <ChevronDown v-else :size="14" aria-hidden="true" />
                  </template>
                  {{ openId === period.id ? '收起' : '处理' }}
                </n-button>

                <n-button
                  v-else-if="period.status === 'resolved'"
                  size="small"
                  :loading="actingKey === `${period.id}:undo`"
                  :disabled="actingKey !== null || !canEdit"
                  data-testid="sub-undo"
                  @click="undo(period)"
                >
                  <template #icon><RotateCcw :size="14" aria-hidden="true" /></template>
                  {{ '撤回' }}
                </n-button>
              </div>

              <n-alert
                v-if="actionError?.periodId === period.id"
                type="error"
                data-testid="sub-action-error"
                role="alert"
              >
                {{ actionError.message }}
              </n-alert>

              <section
                v-if="openId === period.id"
                :id="`sub-panel-${period.id}`"
                class="substitution-resolution-panel"
                data-testid="sub-panel"
              >
                <div v-if="loadingRec" class="substitution-rec-state" data-testid="sub-rec-loading" role="status" aria-live="polite">
                  <n-spin size="small" />
                  <div>
                    <strong>{{ '正在计算可代课教师' }}</strong>
                    <span>{{ '正在核对同科目、在校情况和当前节次冲突。' }}</span>
                  </div>
                </div>

                <div v-else-if="recError" class="substitution-rec-state is-error" data-testid="sub-rec-error" role="alert">
                  <CircleAlert :size="20" aria-hidden="true" />
                  <div>
                    <strong>{{ recError }}</strong>
                    <span>{{ '仍可选择不需要候选教师的处理方式。' }}</span>
                  </div>
                  <n-button size="small" data-testid="sub-rec-retry" @click="loadRecommendation(period)">
                    <template #icon><RefreshCw :size="14" aria-hidden="true" /></template>
                    {{ '重试推荐' }}
                  </n-button>
                </div>

                <template v-else-if="rec">
                  <n-alert
                    v-if="!rec.candidates.length"
                    type="warning"
                    :bordered="false"
                    data-testid="sub-nocandidate"
                  >
                    {{ rec.no_candidate_hint }}
                  </n-alert>

                  <template v-else>
                    <div class="substitution-candidate-heading">
                      <div>
                        <h4>{{ '候选教师' }}</h4>
                        <p>{{ '候选已排除当前节次有课或不可用的教师。' }}</p>
                      </div>
                      <label class="substitution-hours-toggle">
                        <n-switch v-model:value="countsHours" size="small" />
                        <span>{{ `代课课时${countsHours ? '计入' : '不计入'}` }}</span>
                      </label>
                    </div>

                    <div class="substitution-candidate-list">
                      <article
                        v-for="candidate in rec.candidates"
                        :key="candidate.teacher_id"
                        class="substitution-candidate"
                        data-testid="sub-candidate"
                      >
                        <div class="substitution-candidate-main">
                          <span class="operations-icon-box"><UsersRound :size="16" aria-hidden="true" /></span>
                          <div>
                            <strong>{{ candidate.teacher_name }}</strong>
                            <span>{{ `本月已处理 ${candidate.sub_periods_this_month} 节` }}</span>
                          </div>
                        </div>
                        <n-tag size="small" :type="candidateTagType(candidate)">
                          {{ candidate.reasons.join(' · ') }}
                        </n-tag>
                        <div class="substitution-candidate-actions">
                          <n-button
                            size="small"
                            type="primary"
                            :loading="isActing(period, 'substitute', candidate)"
                            :disabled="actingKey !== null || !canEdit"
                            data-testid="sub-pick"
                            @click="assign(period, 'substitute', candidate)"
                          >
                            {{ `指派${types.substitute ?? '代课'}` }}
                          </n-button>
                          <n-button
                            size="small"
                            :loading="isActing(period, 'merge', candidate)"
                            :disabled="actingKey !== null || !canEdit"
                            data-testid="sub-merge"
                            @click="assign(period, 'merge', candidate)"
                          >
                            {{ '接收合班' }}
                          </n-button>
                        </div>
                      </article>
                    </div>
                  </template>
                </template>

                <div
                  v-if="!loadingRec"
                  class="substitution-alternatives"
                  data-testid="sub-alternatives"
                >
                  <div>
                    <h4>{{ '其他处理方式' }}</h4>
                    <p>{{ '合班需在候选教师行选择接收教师；以下方式无需指派教师。' }}</p>
                  </div>
                  <div class="substitution-alternative-actions">
                    <n-button
                      v-if="rec && !rec.candidates.length"
                      size="small"
                      disabled
                      data-testid="sub-merge"
                    >
                      <template #icon><UsersRound :size="14" aria-hidden="true" /></template>
                      {{ '合班（暂无接收教师）' }}
                    </n-button>
                    <n-button
                      size="small"
                      :loading="isActing(period, 'self_study')"
                      :disabled="actingKey !== null || !canEdit"
                      data-testid="sub-selfstudy"
                      @click="assign(period, 'self_study')"
                    >
                      <template #icon><BookOpen :size="14" aria-hidden="true" /></template>
                      {{ types.self_study ?? '自习' }}
                    </n-button>
                    <n-button
                      size="small"
                      type="error"
                      ghost
                      :loading="isActing(period, 'cancel')"
                      :disabled="actingKey !== null || !canEdit"
                      data-testid="sub-cancel"
                      @click="assign(period, 'cancel')"
                    >
                      <template #icon><XCircle :size="14" aria-hidden="true" /></template>
                      {{ '取消课程' }}
                    </n-button>
                  </div>
                </div>
              </section>
            </article>
          </div>
        </article>
      </section>
    </template>
  </main>
</template>
