<script setup lang="ts">
import {
  NAlert, NButton, NCard, NCheckbox, NCheckboxGroup, NEmpty, NInputNumber, NPopconfirm, NProgress,
  NSelect, NSpace, NTag, NText, useMessage,
} from 'naive-ui'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import { listSemesters } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'
import {
  cancelSolveJob, getSolveJob, listRelaxable, preflight, startAutoSchedule, stopSolveJob,
} from '@/api/solver'
import type {
  PreflightIssue, PreflightReport, RelaxableOption, SolveJob,
} from '@/api/solver'
import { listTimetables } from '@/api/timetables'
import type { TimetableBrief } from '@/api/timetables'
import { useAppConfigStore } from '@/stores/appConfig'

const message = useMessage()
const router = useRouter()
const appConfig = useAppConfigStore()
const mainland = computed(() => appConfig.isMainland)
const tr = (tw: string, cn: string) => mainland.value ? cn : tw

const POLL_MS = 2000

const semesters = ref<SemesterListItem[]>([])
const sid = ref<number | null>(null)
const drafts = ref<TimetableBrief[]>([])
const sourceId = ref<number | null>(null)
const minutes = ref(10) // timeout 預設 10 分鐘

const check = ref<PreflightReport | null>(null)
const job = ref<SolveJob | null>(null)
const blockingIssues = ref<PreflightIssue[]>([])
const starting = ref(false)

const relaxable = ref<RelaxableOption[]>([])
const allowPartial = ref(false)
const relax = ref<string[]>([])

let timer: ReturnType<typeof setInterval> | null = null

const semesterOptions = computed(() => semesters.value.map((s) => ({ label: s.label, value: s.id })))
const draftOptions = computed(() =>
  drafts.value.map((t) => ({ label: `${t.name}(${t.entry_count} 格)`, value: t.id })))

const running = computed(() => job.value?.status === 'queued' || job.value?.status === 'running')
const explaining = computed(() => running.value && job.value?.phase === 'explaining')
const conflict = computed(() => job.value?.conflict ?? null)
const conflictCauses = computed(() => conflict.value?.causes ?? [])
const unscheduled = computed(() => job.value?.unscheduled ?? [])

// 進行中顯示「已用掉多少時間預算」;結束後一律填滿——提前結束時 elapsed 可能只有 1%,
// 進度條停在最左邊卻寫著「已完成」會讓人以為排壞了。
const progressPercent = computed(() => {
  if (!job.value) return 0
  if (!running.value) return 100
  return Math.min(100, Math.round((job.value.elapsed / job.value.max_seconds) * 100))
})

const statusTagType = computed(() => {
  if (running.value) return 'info'
  if (job.value?.status === 'finished') return 'success'
  if (job.value?.status === 'cancelled') return 'warning'
  return 'error'
})

const STATUS_LABELS = computed<Record<string, string>>(() => ({
  queued: tr('排隊中', '排队中'), running: tr('排課中', '排课中'),
  finished: tr('已完成', '已完成'), failed: tr('失敗', '失败'), cancelled: tr('已取消', '已取消'),
}))
const statusLabel = computed(() =>
  (explaining.value ? tr('定位無解原因中', '正在定位无解原因') : STATUS_LABELS.value[job.value?.status ?? ''] ?? ''))

const codeName = (code: string) => relaxable.value.find((o) => o.code === code)?.name ?? code

// 有試解在時限內沒判定出來。each 的每一項仍是驗證過的,只是清單可能不全;
// joint 則連「這組是不是最小」都沒把握。兩者要說不同的話。
const incompleteNote = computed(() => {
  if (conflict.value?.mode === 'joint') {
    return tr('(時間有限,這組未必是最小的組合)', '（时间有限，这组未必是最小组合）')
  }
  return tr('(時間有限,可能還有其他原因未列出)', '（时间有限，可能还有其他原因未列出）')
})

const elapsedText = computed(() => {
  const s = job.value?.elapsed ?? 0
  return s < 1 ? tr('不到 1 秒', '不到 1 秒') : `${Math.round(s)} ${tr('秒', '秒')}`
})
const unplacedPeriods = computed(() => unscheduled.value.reduce((n, u) => n + u.periods, 0))

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}
onUnmounted(stopPolling)

async function reload() {
  if (!sid.value) return
  const all = await listTimetables(sid.value)
  drafts.value = all.filter((t) => t.status === 'draft')
  sourceId.value = drafts.value[0]?.id ?? null
  check.value = await preflight(sid.value)
}

async function onSemesterChange(id: number) {
  sid.value = id
  job.value = null
  blockingIssues.value = []
  stopPolling()
  await reload()
}

onMounted(async () => {
  ;[semesters.value, relaxable.value] = await Promise.all([listSemesters(), listRelaxable()])
  if (semesters.value.length) await onSemesterChange(semesters.value[0].id)
})

async function poll() {
  if (!job.value) return
  try {
    job.value = await getSolveJob(job.value.job_id)
  } catch {
    stopPolling()
    return
  }
  if (!running.value) {
    stopPolling()
    if (job.value.status === 'finished') message.success(tr(`已產生「${job.value.result_name}」`, `已生成“${job.value.result_name}”`))
    if (job.value.status === 'cancelled') message.info(tr('已取消排課', '已取消排课'))
    if (job.value.status === 'failed') message.error(job.value.error ?? tr('排課失敗', '排课失败'))
    await reload()
  }
}

async function onStart() {
  if (!sourceId.value) return
  starting.value = true
  blockingIssues.value = []
  try {
    const { job_id } = await startAutoSchedule(sourceId.value, minutes.value * 60, {
      allowPartial: allowPartial.value,
      relax: allowPartial.value ? relax.value : [],
    })
    job.value = await getSolveJob(job_id)
    stopPolling()
    timer = setInterval(poll, POLL_MS)
  } catch (e) {
    const detail = (e as ApiError).detail as unknown
    if (detail && typeof detail === 'object' && 'issues' in detail) {
      blockingIssues.value = (detail as { issues: PreflightIssue[] }).issues
      message.error(tr('資料未通過排課前置檢查', '资料未通过排课前置检查'))
    } else {
      message.error((e as ApiError).message || tr('無法啟動排課', '无法启动排课'))
    }
  } finally {
    starting.value = false
  }
}

/** 照著衝突報告的建議重試:勾好可放寬的項目,直接再排一次。 */
async function onRetryPartial() {
  allowPartial.value = true
  relax.value = conflict.value?.relaxable_codes ?? []
  job.value = null
  await onStart()
}

async function onStop() {
  if (!job.value) return
  await stopSolveJob(job.value.job_id)
  message.info(tr('已要求提前結束,將保留目前最佳解', '已请求提前结束，将保留当前最佳解'))
}
async function onCancel() {
  if (!job.value) return
  await cancelSolveJob(job.value.job_id)
  message.info(tr('已要求取消', '已请求取消'))
}

function openResult() {
  router.push({ name: 'versions' })
}
</script>

<template>
  <n-space vertical size="large">
    <n-space align="center">
      <h2 style="margin: 0">{{ tr('自動排課', '自动排课') }}</h2>
      <n-select
        :value="sid" :options="semesterOptions" style="width: 220px"
        :placeholder="tr('選擇學期', '选择学期')" @update:value="onSemesterChange"
      />
    </n-space>

    <n-empty v-if="!sid" :description="tr('請先建立學期', '请先建立学期')" />

    <template v-else>
      <!-- 排課前置檢查 -->
      <n-card v-if="check" :title="tr('排課前置檢查', '排课前置检查')" size="small">
        <n-space vertical>
          <n-text depth="3">
            {{ check.class_count }} {{ tr('班', '班') }} · {{ check.teacher_count }} {{ tr('位教師', '位教师') }} ·
            {{ check.assignment_count }} {{ tr('筆配課', '条配课') }} · {{ tr('共', '共') }} {{ check.total_periods }} {{ tr('節', '节') }}
          </n-text>
          <n-alert v-if="check.ok && check.warning_count === 0" type="success" :bordered="false">
            {{ tr('資料檢查通過,可以開始排課', '资料检查通过，可以开始排课') }}
          </n-alert>
          <n-alert v-else :type="check.ok ? 'warning' : 'error'" :bordered="false">
            {{ check.error_count }} {{ tr('項錯誤', '项错误') }}、{{ check.warning_count }} {{ tr('項提醒', '项提醒') }}
          </n-alert>
          <div v-for="i in check.issues" :key="i.code + i.subject_id" data-testid="pf-issue">
            <n-tag size="small" :type="i.level === 'error' ? 'error' : 'warning'">
              {{ i.level === 'error' ? tr('錯誤', '错误') : tr('提醒', '提醒') }}
            </n-tag>
            <n-text style="margin-left: 8px">{{ i.message }}</n-text>
          </div>
        </n-space>
      </n-card>

      <!-- 啟動 -->
      <n-card :title="tr('開始排課', '开始排课')" size="small">
        <n-space vertical>
          <n-space align="center">
            <n-text>{{ tr('來源草稿', '来源草稿') }}</n-text>
            <n-select
              v-model:value="sourceId" :options="draftOptions" style="width: 260px"
              :placeholder="tr('選擇草稿', '选择草稿')" data-testid="as-source" :disabled="running"
            />
            <n-text>{{ tr('排課時間上限', '排课时间上限') }}</n-text>
            <n-input-number
              v-model:value="minutes" :min="1" :max="60" style="width: 120px"
              :disabled="running" data-testid="as-minutes"
            >
              <template #suffix>{{ tr('分鐘', '分钟') }}</template>
            </n-input-number>
            <n-button
              type="primary" :loading="starting" :disabled="!sourceId || running"
              data-testid="as-start" @click="onStart"
            >
              {{ tr('開始排課', '开始排课') }}
            </n-button>
          </n-space>
          <n-text depth="3">
            {{ tr('鎖定的格位會維持原位;其餘已排的課會作為求解起點,結果寫成新草稿,來源草稿不動。', '锁定的格位会维持原位；其余已排课程作为求解起点，结果写成新草稿，来源草稿不变。') }}
          </n-text>

          <n-checkbox v-model:checked="allowPartial" :disabled="running" data-testid="as-partial">
            {{ tr('允許部分排課(排不下的課列成清單,不要整個失敗)', '允许部分排课（排不下的课程列成清单，不让整个任务失败）') }}
          </n-checkbox>
          <n-space v-if="allowPartial" align="center" style="padding-left: 24px">
            <n-text depth="3">{{ tr('可放寬', '可放宽') }}：</n-text>
            <n-checkbox-group v-model:value="relax" :disabled="running">
              <n-checkbox
                v-for="o in relaxable" :key="o.code" :value="o.code"
                :label="o.name" :data-testid="`as-relax-${o.code}`"
              />
            </n-checkbox-group>
          </n-space>
          <n-text v-if="allowPartial" depth="3" style="padding-left: 24px">
            {{ tr('班級、教師、場地的「同時段只能有一門課」不可放寬——那是物理限制,不是政策。', '班级、教师、场地的“同一时段只能有一门课”不可放宽，这是物理限制，不是政策。') }}
          </n-text>

          <n-alert v-if="blockingIssues.length" type="error" :title="tr('請先修正這些問題', '请先修正这些问题')">
            <div v-for="i in blockingIssues" :key="i.code + i.subject_id" data-testid="as-blocking">
              {{ i.message }}
            </div>
          </n-alert>
        </n-space>
      </n-card>

      <!-- 進度 -->
      <n-card v-if="job" :title="tr('排課進度', '排课进度')" size="small" data-testid="as-job">
        <n-space vertical>
          <n-space align="center">
            <n-tag :type="statusTagType" data-testid="as-status">{{ statusLabel }}</n-tag>
            <n-text>{{ tr('已耗時', '已耗时') }} {{ elapsedText }} / {{ tr('上限', '上限') }} {{ job.max_seconds }} {{ tr('秒', '秒') }}</n-text>
            <n-text v-if="running || job.solutions" data-testid="as-solutions">
              {{ tr('已找到', '已找到') }} {{ job.solutions }} {{ tr('個解', '个解') }}
            </n-text>
            <!-- 部分排課的目標值被「未排入」的高額懲罰灌爆(一節 = 10000),
                 拿給人看只會以為排壞了;真正該看的是未排幾節。 -->
            <n-text v-if="job.partial && !running">{{ tr('未排', '未排') }} {{ unplacedPeriods }} {{ tr('節', '节') }}</n-text>
            <n-text v-else-if="job.objective !== null">{{ tr('目前目標值', '当前目标值') }} {{ Math.round(job.objective) }}</n-text>
          </n-space>

          <n-progress
            type="line" :percentage="progressPercent"
            :status="job.status === 'failed' ? 'error'
              : job.status === 'cancelled' ? 'warning'
                : running ? 'default' : 'success'"
            :processing="running"
          />

          <n-space v-if="running && !explaining">
            <n-button
              type="primary" ghost :disabled="job.solutions === 0"
              data-testid="as-stop" @click="onStop"
            >
              {{ tr('提前結束(取目前最佳解)', '提前结束（取当前最佳解）') }}
            </n-button>
            <n-popconfirm @positive-click="onCancel">
              <template #trigger>
                <n-button type="error" ghost data-testid="as-cancel">{{ tr('取消排課', '取消排课') }}</n-button>
              </template>
              {{ tr('取消後不會產生結果草稿,確定?', '取消后不会生成结果草稿，确定吗？') }}
            </n-popconfirm>
          </n-space>

          <n-text v-if="explaining" depth="3" data-testid="as-explaining">
            {{ tr('排不出來。正在逐項試解,找出是哪幾件事湊在一起造成的……', '无法排出。正在逐项试解，找出是哪几项组合造成的……') }}
          </n-text>

          <!-- 定位不出具體原因時(例如硬約束其實可解、只是軟約束最佳化太慢),仍要給一句人話 -->
          <n-alert
            v-if="job.status === 'failed' && !conflictCauses.length"
            type="error" data-testid="as-error"
          >
            {{ job.error }}
          </n-alert>

          <!-- 無解衝突定位:不只說「排不出來」,說是誰、差幾節、鬆開哪一個就好 -->
          <n-alert
            v-if="conflict && conflictCauses.length" type="error"
            :title="conflict.headline" data-testid="as-conflict"
          >
            <n-space vertical size="small">
              <div v-for="(c, k) in conflictCauses" :key="k" data-testid="as-cause">
                <n-tag size="small" :bordered="false" :type="c.relaxable ? 'warning' : 'error'">
                  {{ c.scope_name }}
                </n-tag>
                <n-text style="margin-left: 8px">{{ c.message }}</n-text>
                <div style="padding-left: 8px">
                  <n-text depth="3">{{ tr('建議', '建议') }}：{{ c.suggestion }}</n-text>
                </div>
              </div>
              <n-text v-if="!conflict.complete" depth="3">{{ incompleteNote }}</n-text>
              <n-button
                v-if="conflict.relaxable_codes.length" type="primary" ghost size="small"
                data-testid="as-retry-partial" @click="onRetryPartial"
              >
                {{ tr('改用部分排課', '改用部分排课') }}（{{ tr('放寬', '放宽') }} {{ conflict.relaxable_codes.map(codeName).join('、') }}）
              </n-button>
            </n-space>
          </n-alert>

          <n-alert v-if="job.status === 'finished'" type="success" data-testid="as-done">
            {{ tr('已產生新草稿', '已生成新草稿') }}「{{ job.result_name }}」
            <n-button text type="primary" style="margin-left: 8px" @click="openResult">
              {{ tr('前往版本與發布', '前往版本与发布') }}
            </n-button>
          </n-alert>

          <!-- 未排清單:部分排課的另一半交付物 -->
          <n-alert
            v-if="unscheduled.length" type="warning" :title="tr('以下課務未能排入,請人工處理', '以下课务未能排入，请人工处理')"
            data-testid="as-unscheduled"
          >
            <table class="data-table">
              <thead>
                <tr><th>{{ tr('科目', '科目') }}</th><th>{{ tr('班級', '班级') }}</th><th>{{ tr('未排節數', '未排节数') }}</th><th>{{ tr('原因', '原因') }}</th></tr>
              </thead>
              <tbody>
                <tr v-for="u in unscheduled" :key="u.assignment_ids.join('-')">
                  <td>{{ u.subject_name }}</td>
                  <td>{{ u.class_names.join('、') }}</td>
                  <td>{{ u.periods }} {{ tr('節', '节') }}</td>
                  <!-- 完全排不下的課會說明原因;其餘是 solver 權衡後的取捨 -->
                  <td>{{ u.reason || tr('排課時權衡取捨', '排课时权衡取舍') }}</td>
                </tr>
              </tbody>
            </table>
          </n-alert>

          <!-- 軟約束達成度 -->
          <table v-if="job.report" class="data-table" data-testid="as-report">
            <thead>
              <tr><th>{{ tr('軟約束', '软约束') }}</th><th>{{ tr('權重', '权重') }}</th><th>{{ tr('達成', '达成') }}</th><th>{{ tr('未達成明細', '未达成明细') }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="i in job.report.items" :key="i.code">
                <td>{{ i.code }} {{ i.name }}</td>
                <td>{{ i.weight === 0 ? tr('關閉', '关闭') : i.weight }}</td>
                <td>
                  {{ i.satisfied }} / {{ i.opportunities }}
                  <n-text :depth="3">({{ Math.round(i.rate * 100) }}%)</n-text>
                </td>
                <td>
                  <n-text v-if="!i.details.length" depth="3">—</n-text>
                  <div v-for="(d, k) in i.details.slice(0, 3)" v-else :key="k">{{ d }}</div>
                  <n-text v-if="i.details.length > 3" depth="3">
                    …{{ tr('等', '等') }} {{ i.violations }} {{ tr('項', '项') }}
                  </n-text>
                </td>
              </tr>
            </tbody>
          </table>
        </n-space>
      </n-card>
    </template>
  </n-space>
</template>

<style scoped>
.data-table { border-collapse: collapse; width: 100%; }
.data-table th, .data-table td {
  border: 1px solid var(--n-border-color, #e0e0e0); padding: 6px 10px; text-align: left;
  vertical-align: top;
}
.data-table th { background: rgba(128, 128, 128, 0.08); font-weight: 600; }
</style>
