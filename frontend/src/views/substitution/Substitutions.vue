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
import { useAppConfigStore } from '@/stores/appConfig'

const message = useMessage()
const appConfig = useAppConfigStore()
const mainland = computed(() => appConfig.isMainland)
const tr = (tw: string, cn: string) => mainland.value ? cn : tw

const semesters = ref<{ id: number; label: string }[]>([])
const sid = ref<number | null>(null)
const leaves = ref<LeaveRequest[]>([])
const types = ref<Record<string, string>>({})
const openId = ref<number | null>(null) // 展開中的受影響節次
const rec = ref<Recommendation | null>(null)
const loadingRec = ref(false)
const countsHours = ref(true)

const WEEKDAYS = computed(() => mainland.value
  ? ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  : ['週日', '週一', '週二', '週三', '週四', '週五', '週六'])
function withWeekday(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return `${iso}(${WEEKDAYS.value[new Date(y, m - 1, d).getDay()]})`
}

const semesterOptions = computed(() => semesters.value.map((s) => ({ label: s.label, value: s.id })))

// 只顯示還有待處理節次的假單(已全部處理或已銷假的收起來)
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
      ? tr(`已指派 ${candidate.teacher_name} ${types.value[type]}`, `已指派 ${candidate.teacher_name} ${types.value[type]}`)
      : tr(`已設為${types.value[type]}`, `已设为${types.value[type]}`))
    openId.value = null
    await reload()
  } catch (e) {
    message.error((e as ApiError).message || tr('指派失敗', '指派失败'))
  }
}

async function undo(p: AffectedPeriod) {
  await clearSubstitution(p.id)
  message.info(tr('已撤回處置,退回待處理', '已撤回处置，退回待处理'))
  await reload()
}

const STATUS = computed<Record<AffectedPeriod['status'], { type: string; label: string }>>(() => ({
  pending: { type: 'warning', label: tr('待處理', '待处理') },
  resolved: { type: 'success', label: tr('已確認', '已确认') },
  completed: { type: 'info', label: tr('已完成', '已完成') },
  cancelled: { type: 'default', label: tr('已取消', '已取消') },
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
      <h2 style="margin: 0">{{ tr('調代課處理', '调代课处理') }}</h2>
      <n-select
        :value="sid" :options="semesterOptions" style="width: 220px"
        :placeholder="tr('選擇學期', '选择学期')" @update:value="onSemesterChange"
      />
    </n-space>

    <n-empty v-if="!sid" :description="tr('請先建立學期', '请先建立学期')" />
    <n-empty v-else-if="!activeLeaves.length" :description="tr('目前沒有待處理的請假', '当前没有待处理的请假')" />

    <template v-else>
      <n-card
        v-for="l in activeLeaves" :key="l.id" size="small" data-testid="sub-leave"
        :title="`${l.teacher_name} · ${l.leave_type_label} · ${tr('待處理', '待处理')} ${l.pending_count} ${tr('節', '节')}`"
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
                {{ openId === p.id ? tr('收合', '收起') : tr('處理', '处理') }}
              </n-button>
              <n-button
                v-else-if="p.status === 'resolved'" size="small" tertiary
                data-testid="sub-undo" @click="undo(p)"
              >
                {{ tr('撤回', '撤回') }}
              </n-button>
            </n-space>

            <!-- 展開:代課推薦 + 其他處置 -->
            <n-card
              v-if="openId === p.id" size="small" embedded style="margin: 8px 0 8px 40px"
              data-testid="sub-panel"
            >
              <n-space vertical size="small">
                <n-text v-if="loadingRec" depth="3">{{ tr('計算可代教師中…', '正在计算可代课教师…') }}</n-text>

                <template v-else-if="rec">
                  <n-alert
                    v-if="!rec.candidates.length" type="warning" :bordered="false"
                    data-testid="sub-nocandidate"
                  >
                    {{ rec.no_candidate_hint }}
                  </n-alert>

                  <template v-else>
                    <n-space align="center">
                      <n-text depth="3">{{ tr('代課鐘點', '代课课时') }}</n-text>
                      <n-switch v-model:value="countsHours" size="small" />
                      <n-text depth="3">{{ countsHours ? tr('計入', '计入') : tr('不計', '不计') }}</n-text>
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
                          {{ tr('指派', '指派') }} {{ c.teacher_name }}
                        </n-button>
                        <n-tag size="small" :type="candidateTagType(c) as never">
                          {{ c.reasons.join(' · ') }}
                        </n-tag>
                      </n-space>
                    </div>
                  </template>
                </template>

                <n-space size="small" style="margin-top: 8px">
                  <n-text depth="3">{{ tr('或改採', '或改为') }}：</n-text>
                  <n-button size="tiny" data-testid="sub-merge" @click="assign(p, 'merge')">
                    {{ tr('併班', '合班') }}
                  </n-button>
                  <n-button
                    size="tiny" data-testid="sub-selfstudy" @click="assign(p, 'self_study')"
                  >
                    {{ tr('自習', '自习') }}
                  </n-button>
                  <n-button size="tiny" data-testid="sub-cancel" @click="assign(p, 'cancel')">
                    {{ tr('不處理', '不处理') }}
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
