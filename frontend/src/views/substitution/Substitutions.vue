<script setup lang="ts">
import {
  NAlert, NButton, NCard, NEmpty, NSelect, NSpace, NSwitch, NTag, NText, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import type { ApiError } from '@/api/client'
import { listLeaves } from '@/api/leaves'
import type { AffectedPeriod, LeaveRequest } from '@/api/leaves'
import { listSemesters } from '@/api/semesters'
import {
  assignSubstitution, clearSubstitution, getRecommendations, listSubstitutionTypes,
} from '@/api/substitutions'
import type { Candidate, Recommendation } from '@/api/substitutions'

const message = useMessage()

const semesters = ref<{ id: number; label: string }[]>([])
const sid = ref<number | null>(null)
const leaves = ref<LeaveRequest[]>([])
const types = ref<Record<string, string>>({})
const openId = ref<number | null>(null) // 展开中的受影响节次
const rec = ref<Recommendation | null>(null)
const loadingRec = ref(false)
const countsHours = ref(true)

const WEEKDAYS = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
function withWeekday(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return `${iso}（${WEEKDAYS[new Date(y, m - 1, d).getDay()]}）`
}

const semesterOptions = computed(() => semesters.value.map((s) => ({ label: s.label, value: s.id })))

// 只显示还有待处理节次的假单(已全部处理或已销假的收起来)
const activeLeaves = computed(() =>
  leaves.value.filter((l) => l.status === 'registered' && l.affected_count > 0))

async function reload() {
  if (!sid.value) return
  leaves.value = await listLeaves(sid.value)
}

async function onSemesterChange(id: number) {
  sid.value = id
  openId.value = null
  rec.value = null
  await reload()
}

onMounted(async () => {
  ;[semesters.value, types.value] = await Promise.all([listSemesters(), listSubstitutionTypes()])
  if (semesters.value.length) await onSemesterChange(semesters.value[0].id)
})

async function openPeriod(p: AffectedPeriod) {
  if (openId.value === p.id) {
    openId.value = null
    return
  }
  openId.value = p.id
  rec.value = null
  countsHours.value = true
  loadingRec.value = true
  try {
    rec.value = await getRecommendations(p.id)
  } finally {
    loadingRec.value = false
  }
}

async function assign(p: AffectedPeriod, type: string, candidate?: Candidate) {
  try {
    await assignSubstitution(p.id, {
      type,
      handler_teacher_id: candidate?.teacher_id ?? null,
      counts_toward_hours: type === 'substitute' ? countsHours.value : null,
    })
    message.success(candidate
      ? `已指派 ${candidate.teacher_name} ${types.value[type]}`
      : `已设为${types.value[type]}`)
    openId.value = null
    await reload()
  } catch (e) {
    message.error((e as ApiError).message || '指派失败')
  }
}

async function undo(p: AffectedPeriod) {
  await clearSubstitution(p.id)
  message.info('已撤回处理方式，退回待处理')
  await reload()
}

const STATUS = computed<Record<AffectedPeriod['status'], { type: string; label: string }>>(() => ({
  pending: { type: 'warning', label: '待处理' },
  resolved: { type: 'success', label: '已处理' },
  completed: { type: 'info', label: '已完成' },
  cancelled: { type: 'default', label: '已取消' },
}))

function candidateTagType(c: Candidate): string {
  if (c.same_subject) return 'success'
  if (c.at_school_that_day) return 'info'
  return 'default'
}
</script>

<template>
  <n-space vertical size="large">
    <n-space align="center">
      <h2 style="margin: 0">{{ '调课与代课处理' }}</h2>
      <n-select
        :value="sid" :options="semesterOptions" style="width: 220px"
        :placeholder="'选择学期'" @update:value="onSemesterChange"
      />
    </n-space>

    <n-empty v-if="!sid" :description="'请先创建学期'" />
    <n-empty v-else-if="!activeLeaves.length" :description="'当前没有待处理的请假'" />

    <template v-else>
      <n-card
        v-for="l in activeLeaves" :key="l.id" size="small" data-testid="sub-leave"
        :title="`${l.teacher_name} · ${l.leave_type_label} · ${'待处理'} ${l.pending_count} ${'节'}`"
      >
        <n-space vertical size="small">
          <div v-for="p in l.affected_periods" :key="p.id" data-testid="sub-period">
            <n-space align="center" :wrap="false">
              <n-tag size="small" :type="STATUS[p.status].type as never">
                {{ STATUS[p.status].label }}
              </n-tag>
              <n-text style="min-width: 260px">
                {{ withWeekday(p.date) }} {{ p.period_name }} ·
                {{ p.class_names }} {{ p.subject_name }}
                <n-text v-if="p.room_name" depth="3">@{{ p.room_name }}</n-text>
              </n-text>
              <n-text v-if="p.handler_name" type="success" data-testid="sub-handler">
                → {{ p.handler_name }}
              </n-text>
              <n-button
                v-if="p.status === 'pending'" size="small" type="primary"
                data-testid="sub-handle" @click="openPeriod(p)"
              >
                {{ openId === p.id ? '收起' : '处理' }}
              </n-button>
              <n-button
                v-else-if="p.status === 'resolved'" size="small" tertiary
                data-testid="sub-undo" @click="undo(p)"
              >
                {{ '撤回' }}
              </n-button>
            </n-space>

            <!-- 展开:代课推荐 + 其他处理方式 -->
            <n-card
              v-if="openId === p.id" size="small" embedded style="margin: 8px 0 8px 40px"
              data-testid="sub-panel"
            >
              <n-space vertical size="small">
                <n-text v-if="loadingRec" depth="3">{{ '正在计算可代课教师…' }}</n-text>

                <template v-else-if="rec">
                  <n-alert
                    v-if="!rec.candidates.length" type="warning" :bordered="false"
                    data-testid="sub-nocandidate"
                  >
                    {{ rec.no_candidate_hint }}
                  </n-alert>

                  <template v-else>
                    <n-space align="center">
                      <n-text depth="3">{{ '代课课时' }}</n-text>
                      <n-switch v-model:value="countsHours" size="small" />
                      <n-text depth="3">{{ countsHours ? '计入' : '不计' }}</n-text>
                    </n-space>
                    <div
                      v-for="c in rec.candidates" :key="c.teacher_id"
                      data-testid="sub-candidate"
                    >
                      <n-space align="center" :wrap="false">
                        <n-button
                          size="small" type="primary" ghost
                          data-testid="sub-pick" @click="assign(p, 'substitute', c)"
                        >
                          {{ '指派' }} {{ c.teacher_name }}
                        </n-button>
                        <n-tag size="small" :type="candidateTagType(c) as never">
                          {{ c.reasons.join(' · ') }}
                        </n-tag>
                      </n-space>
                    </div>
                  </template>
                </template>

                <n-space size="small" style="margin-top: 8px">
                  <n-text depth="3">{{ '或改为' }}：</n-text>
                  <n-button size="tiny" data-testid="sub-merge" @click="assign(p, 'merge')">
                    {{ '合班' }}
                  </n-button>
                  <n-button
                    size="tiny" data-testid="sub-selfstudy" @click="assign(p, 'self_study')"
                  >
                    {{ '自习' }}
                  </n-button>
                  <n-button size="tiny" data-testid="sub-cancel" @click="assign(p, 'cancel')">
                    {{ '不处理' }}
                  </n-button>
                </n-space>
              </n-space>
            </n-card>
          </div>
        </n-space>
      </n-card>
    </template>
  </n-space>
</template>
