<script setup lang="ts">
import {
  NAlert, NButton, NDatePicker, NEmpty, NInput, NInputNumber, NResult, NSelect,
  NSpin, NStatistic, NStep, NSteps, useMessage,
} from 'naive-ui'
import {
  CalendarRange, CheckCircle2, ChevronLeft, ChevronRight, CircleAlert, Clock3, Save,
} from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import { saveSchoolSettings } from '@/api/assignments'
import { createSemester, getSemester, updateSemester } from '@/api/semesters'
import type { Semester } from '@/api/semesters'
import { getSemesterSummary } from '@/api/wizard'
import type { SemesterSummary } from '@/api/wizard'
import { canEditCore as canEditCoreRole } from '@/permissions'
import { useAuthStore } from '@/stores/auth'
import { useWizardStore } from '@/stores/wizard'
import { useAppConfigStore } from '@/stores/appConfig'
import { useSemesterContextStore } from '@/stores/semesterContext'
import ImportTab from '@/views/basedata/ImportTab.vue'

const router = useRouter()
const message = useMessage()
const auth = useAuthStore()
const wizard = useWizardStore()
const appConfig = useAppConfigStore()
const semesterContext = useSemesterContextStore()

const step = ref(0)
const schoolName = ref(appConfig.config.school_name)
const year = ref(new Date().getFullYear())
const term = ref(1)
const startDate = ref<string | null>(null)
const endDate = ref<string | null>(null)
const semesterId = ref<number | null>(null)
const semester = ref<Semester | null>(null)
const summary = ref<SemesterSummary | null>(null)
const busy = ref(false)
const initialLoading = ref(true)
const initialError = ref<string | null>(null)
const actionError = ref<string | null>(null)
const summaryError = ref<string | null>(null)
const summaryLoading = ref(false)

const termOptions = [
  { label: '第一学期', value: 1 },
  { label: '第二学期', value: 2 },
]
const periodTable = computed(() => (
  semester.value?.period_tables.find((table) => table.is_default)
  ?? semester.value?.period_tables[0]
  ?? null
))
const canEditCore = computed(() => (
  // Isolated component tests mount without the router guard; the API remains the final boundary.
  !auth.user || canEditCoreRole(auth.user.roles)
))
const canEditSchool = computed(() => !auth.user || auth.hasRole('admin'))
const canEditSemester = computed(() => (
  canEditCore.value
  && (!semesterContext.authoritative || semesterContext.isCurrent(semesterId.value))
))

function syncFormFromSemester(value: Semester) {
  year.value = value.academic_year
  term.value = value.term
  startDate.value = value.start_date
  endDate.value = value.end_date
}

async function loadSummary(id: number) {
  summaryLoading.value = true
  summaryError.value = null
  summary.value = null
  try {
    summary.value = await getSemesterSummary(id)
  } catch (error) {
    summary.value = null
    summaryError.value = apiErrorMessage(error, '无法读取当前学期的数据摘要')
    throw error
  } finally {
    summaryLoading.value = false
  }
}

async function retrySummary() {
  if (!semesterId.value) return
  try {
    await loadSummary(semesterId.value)
  } catch {
    // loadSummary exposes the API error inline for the next attempt.
  }
}

async function loadSemester(id: number) {
  semester.value = await getSemester(id)
  if (semester.value) syncFormFromSemester(semester.value)
}

async function syncWizardState() {
  step.value = Math.max(0, Math.min(wizard.state?.current_step ?? 0, 3))
  semesterId.value = wizard.state?.semester_id ?? null
  semester.value = null
  summary.value = null
  summaryError.value = null
  if (semesterId.value) {
    await loadSemester(semesterId.value)
    if (step.value === 3) {
      try {
        await loadSummary(semesterId.value)
      } catch {
        // The completion step owns the inline retry state.
      }
    }
  }
}

async function loadWizardData() {
  initialLoading.value = true
  initialError.value = null
  actionError.value = null
  try {
    if (!appConfig.loaded) await appConfig.load()
    schoolName.value = appConfig.config.school_name
    if (!wizard.loaded || wizard.error) await wizard.fetch()
    if (wizard.error && !wizard.state) throw new Error(wizard.error)
    if (canEditCore.value && wizard.state?.paused) await wizard.patch({ paused: false })
    await semesterContext.load()
    await syncWizardState()
  } catch (error) {
    initialError.value = apiErrorMessage(error, '无法读取设置向导，请稍后重试。')
  } finally {
    initialLoading.value = false
  }
}

async function persistStep(nextStep: number): Promise<boolean> {
  try {
    await wizard.patch({ current_step: nextStep })
    return true
  } catch (error) {
    actionError.value = apiErrorMessage(error, '无法保存向导进度，请重试。')
    return false
  }
}

function validateFirstStep(): boolean {
  const minYear = appConfig.config.academic_year.min
  const maxYear = appConfig.config.academic_year.max
  if (!Number.isInteger(year.value) || year.value < minYear || year.value > maxYear) {
    actionError.value = `学年起始年须在 ${minYear} 至 ${maxYear} 之间。`
    return false
  }
  if (![1, 2].includes(term.value)) {
    actionError.value = '请选择有效的学期。'
    return false
  }
  if (!startDate.value) {
    actionError.value = '请填写开始日期。'
    return false
  }
  if (!endDate.value) {
    actionError.value = '请填写结束日期。'
    return false
  }
  if (endDate.value < startDate.value) {
    actionError.value = '结束日期不可早于开始日期。'
    return false
  }
  return true
}

async function persistSchoolName(): Promise<void> {
  if (!canEditSchool.value) return
  const value = schoolName.value.trim()
  if (!value) throw new Error('学校名称不能为空。')
  if (value === appConfig.config.school_name) return
  const saved = await saveSchoolSettings({ school_name: value })
  appConfig.config.school_name = saved.school_name
  schoolName.value = saved.school_name
}

async function goNext() {
  if (!canEditCore.value || busy.value) return
  actionError.value = null
  if (step.value === 0 && !validateFirstStep()) return

  const previousStep = step.value
  busy.value = true
  try {
    if (step.value === 0) {
      await persistSchoolName()
      if (!semesterId.value) {
        const previousSemesterId = semesterContext.currentSemesterId
        const sem = await createSemester({
          academic_year: year.value,
          term: term.value,
          start_date: startDate.value,
          end_date: endDate.value,
        })
        semesterId.value = sem.id
        semester.value = sem
        if (previousSemesterId !== null && previousSemesterId !== sem.id) {
          await semesterContext.switchTo(sem.id)
        } else {
          await semesterContext.load()
        }
      } else if (semester.value) {
        await updateSemester(semesterId.value, {
          start_date: startDate.value,
          end_date: endDate.value,
        })
      }
      if (wizard.state?.semester_id !== semesterId.value) {
        await wizard.patch({ semester_id: semesterId.value })
      }
      if (semester.value?.id !== semesterId.value) await loadSemester(semesterId.value)
      await semesterContext.load()
    }

    const nextStep = Math.min(step.value + 1, 3)
    step.value = nextStep
    if (!await persistStep(nextStep)) {
      step.value = previousStep
      return
    }
    if (nextStep === 3 && semesterId.value) {
      try {
        await loadSummary(semesterId.value)
      } catch {
        // The completion step owns the inline retry state.
      }
    }
  } catch (error) {
    step.value = previousStep
    if (!actionError.value) {
      actionError.value = apiErrorMessage(error, previousStep === 0 ? '创建学期失败，请检查输入后重试。' : '无法进入下一步，请稍后重试。')
    }
  } finally {
    busy.value = false
  }
}

async function goPrev() {
  if (!canEditCore.value || busy.value || step.value === 0) return
  actionError.value = null
  const previousStep = step.value
  const nextStep = Math.max(step.value - 1, 0)
  step.value = nextStep
  busy.value = true
  if (!await persistStep(nextStep)) step.value = previousStep
  busy.value = false
}

async function saveAndExit() {
  if (!canEditCore.value || busy.value) return
  busy.value = true
  actionError.value = null
  try {
    await wizard.patch({ current_step: step.value, semester_id: semesterId.value, paused: true })
    await router.push({ name: 'dashboard' })
  } catch (error) {
    actionError.value = apiErrorMessage(error, '无法保存当前进度，请重试。')
  } finally {
    busy.value = false
  }
}

async function finish() {
  if (!canEditCore.value || busy.value) return
  busy.value = true
  actionError.value = null
  try {
    await wizard.patch({ completed: true })
    message.success('基础设置已完成')
    await router.push({ name: 'assignments' })
  } catch (error) {
    actionError.value = apiErrorMessage(error, '无法完成设置，请稍后重试。')
  } finally {
    busy.value = false
  }
}

function openPeriodEditor() {
  if (!canEditCore.value || !periodTable.value) {
    actionError.value = '当前学期还没有作息时间表，请在此步骤创建后再编辑。'
    return
  }
  void router.push({ name: 'period-table-editor', params: { id: periodTable.value.id } })
}

onMounted(loadWizardData)
</script>

<template>
  <div class="wizard-page">
    <header class="wizard-header">
      <div>
        <h1>{{ '设置向导' }}</h1>
        <p>{{ '先建立当前学期，再补齐基础数据和学校实际作息。' }}</p>
      </div>
      <div class="wizard-header-actions">
        <n-button
          v-if="canEditCore"
          quaternary
          class="wizard-skip"
          :disabled="initialLoading || busy"
          data-testid="wizard-save-exit"
          @click="saveAndExit"
        >
          <template #icon><Save :size="16" aria-hidden="true" /></template>
          {{ '保存并退出' }}
        </n-button>
      </div>
    </header>

    <section v-if="initialLoading" class="wizard-state" data-testid="wizard-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取设置向导' }}</strong>
      <span>{{ '正在检查当前学期和已保存的进度。' }}</span>
    </section>

    <section v-else-if="initialError" class="wizard-state wizard-error" data-testid="wizard-load-error" role="alert">
      <CircleAlert :size="22" aria-hidden="true" />
      <strong>{{ initialError }}</strong>
      <n-button data-testid="wizard-retry" type="primary" @click="loadWizardData">
        {{ '重新加载' }}
      </n-button>
    </section>

    <template v-else>
      <n-alert v-if="!canEditCore" type="info" data-testid="wizard-readonly">
        当前角色只能查看设置向导，创建、导入和保存操作仅对系统管理员和排课管理员开放。
      </n-alert>

      <nav class="wizard-progress" aria-label="设置步骤">
        <n-steps :current="step + 1" size="small">
          <n-step :title="'学校与学期'" />
          <n-step :title="'基础数据'" />
          <n-step :title="'作息安排'" />
          <n-step :title="'完成检查'" />
        </n-steps>
      </nav>

      <section class="wizard-panel" aria-labelledby="wizard-step-title">
        <div class="wizard-panel-heading">
          <span class="wizard-panel-icon" aria-hidden="true">
            <CalendarRange v-if="step === 0" :size="20" />
            <CheckCircle2 v-else-if="step === 1" :size="20" />
            <Clock3 v-else-if="step === 2" :size="20" />
            <CheckCircle2 v-else :size="20" />
          </span>
          <div>
            <p class="wizard-step-count">{{ `第 ${step + 1} 步 / 4` }}</p>
            <h2 id="wizard-step-title" data-testid="wizard-step-title">
              {{ ['学校与学期', '基础数据', '作息安排', '完成检查'][step] }}
            </h2>
          </div>
        </div>

        <div v-if="actionError" class="wizard-inline-error" data-testid="wizard-error" role="alert" aria-live="assertive">
          <CircleAlert :size="17" aria-hidden="true" />
          <span>{{ actionError }}</span>
        </div>

        <!-- 步骤 0：学校与学期 -->
        <div v-if="step === 0" class="wizard-step-content">
          <p class="wizard-step-intro">{{ '确认学校名称，并填写当前学期的真实起止日期。' }}</p>
          <div class="wizard-semester-fields wizard-semester-fields-wide">
            <label class="wizard-field wizard-field-wide">
              <span>{{ '学校名称' }}</span>
              <n-input
                v-model:value="schoolName"
                data-testid="wizard-school-name"
                :disabled="!canEditSchool || !!semesterId"
                maxlength="64"
              />
              <small v-if="!canEditSchool">{{ '仅系统管理员可以修改学校名称。' }}</small>
            </label>
            <label class="wizard-field">
              <span>{{ '学年起始年' }}</span>
              <n-input-number
                v-model:value="year"
                data-testid="wizard-year"
                :min="appConfig.config.academic_year.min"
                :max="appConfig.config.academic_year.max"
                :disabled="!!semesterId || !canEditCore"
                button-placement="both"
              />
            </label>
            <label class="wizard-field">
              <span>{{ '学期' }}</span>
              <n-select v-model:value="term" :options="termOptions" :disabled="!!semesterId || !canEditCore" />
            </label>
            <label class="wizard-field">
              <span>{{ '开始日期' }}</span>
              <n-date-picker
                v-model:formatted-value="startDate"
                data-testid="wizard-start-date"
                value-format="yyyy-MM-dd"
                type="date"
                :disabled="!canEditCore"
              />
            </label>
            <label class="wizard-field">
              <span>{{ '结束日期' }}</span>
              <n-date-picker
                v-model:formatted-value="endDate"
                data-testid="wizard-end-date"
                value-format="yyyy-MM-dd"
                type="date"
                :disabled="!canEditCore"
              />
            </label>
          </div>
          <n-alert type="info" class="wizard-neutral-note">
            继续后只创建学期本身，不会自动生成科目、教师、班级或作息。
          </n-alert>
          <p v-if="semesterId" class="wizard-success-note">
            <CheckCircle2 :size="16" aria-hidden="true" />
            <span>{{ '已创建：' }}{{ semester?.label }}</span>
          </p>
        </div>

        <!-- 步骤 1：基础数据 -->
        <div v-else-if="step === 1" class="wizard-step-content">
          <p class="wizard-step-intro">{{ '录入排课需要的科目、教师、班级和教室；下一阶段将提供组合导入与向导内手工模式。' }}</p>
          <ImportTab
            v-if="semesterId"
            :semester-id="semesterId"
            :can-edit="canEditSemester"
          />
          <n-empty v-else :description="'请先完成学期创建'" data-testid="wizard-import-empty" />
        </div>

        <!-- 步骤 2：作息安排 -->
        <div v-else-if="step === 2" class="wizard-step-content">
          <p class="wizard-step-intro">{{ '按学校实际情况设置每周上课日、节次类型和可选钟点时间。' }}</p>
          <div v-if="periodTable" class="wizard-period-summary">
            <strong>{{ periodTable.name }}</strong>
            <span>
              {{ '（共' }} {{ periodTable.periods.length }} {{ '格，每周' }}
              {{ periodTable.num_weekdays }} {{ '天）' }}
            </span>
          </div>
          <n-empty v-else :description="'当前学期还没有作息时间表'" data-testid="wizard-period-empty" />
          <n-button
            class="wizard-secondary-action"
            data-testid="wizard-period-edit"
            :disabled="!periodTable"
            @click="openPeriodEditor"
          >
            <template #icon><Clock3 :size="16" aria-hidden="true" /></template>
            {{ '打开作息时间表编辑器' }}
          </n-button>
          <p class="wizard-help">{{ '离开编辑器后返回本向导时会自动回到此步骤。' }}</p>
        </div>

        <!-- 步骤 3：完成检查 -->
        <div v-else class="wizard-step-content wizard-finish-content">
          <section v-if="summaryLoading" class="wizard-state" data-testid="wizard-summary-loading" role="status" aria-live="polite">
            <n-spin size="small" />
            <strong>{{ '正在读取当前学期的数据摘要' }}</strong>
          </section>
          <section v-else-if="summaryError" class="wizard-state wizard-error" data-testid="wizard-summary-error" role="alert">
            <CircleAlert :size="21" aria-hidden="true" />
            <strong>{{ summaryError }}</strong>
            <n-button type="primary" @click="retrySummary">{{ '重新读取摘要' }}</n-button>
          </section>
          <n-result v-else status="success" :title="'基础设置即将完成'" :description="'以下是目前已创建的数据摘要'">
            <template #footer>
              <div class="wizard-summary-grid">
                <n-statistic :label="'科目'" :value="summary?.subjects ?? 0" />
                <n-statistic :label="'教师'" :value="summary?.teachers ?? 0" />
                <n-statistic :label="'班级'" :value="summary?.classes ?? 0" />
                <n-statistic :label="'教室/场地'" :value="summary?.rooms ?? 0" />
              </div>
            </template>
          </n-result>
        </div>
      </section>

      <footer class="wizard-actions">
        <n-button data-testid="wizard-prev" :disabled="step === 0 || busy || !canEditCore" @click="goPrev">
          <template #icon><ChevronLeft :size="16" aria-hidden="true" /></template>
          {{ '上一步' }}
        </n-button>
        <n-button
          v-if="step < 3"
          data-testid="wizard-next"
          type="primary"
          :loading="busy"
          :disabled="busy || !canEditCore"
          @click="goNext"
        >
          {{ '下一步' }}
          <template #icon><ChevronRight :size="16" aria-hidden="true" /></template>
        </n-button>
        <n-button
          v-else data-testid="wizard-finish" type="primary" :loading="busy"
          :disabled="busy || !!summaryError || !summary || !canEditCore" @click="finish"
        >
          {{ '完成，前往教学任务管理' }}
          <template #icon><ChevronRight :size="16" aria-hidden="true" /></template>
        </n-button>
      </footer>
    </template>
  </div>
</template>

<style scoped>
.wizard-page {
  width: min(100%, 1040px);
  min-height: 100svh;
  margin: 0 auto;
  padding: 32px 24px 44px;
  color: var(--app-text);
}

.wizard-header,
.wizard-actions,
.wizard-panel-heading,
.wizard-success-note,
.wizard-inline-error,
.wizard-period-summary {
  display: flex;
  align-items: center;
}

.wizard-header {
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 26px;
}
.wizard-header-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }

.wizard-header h1 { margin: 0; font-size: 30px; line-height: 1.2; }
.wizard-header p:last-child { margin: 8px 0 0; color: var(--app-text-muted); font-size: 14px; line-height: 1.6; }
.wizard-step-count {
  margin: 0 0 7px;
  color: var(--app-primary-strong);
  font-size: 12px;
  font-weight: 700;
}

.wizard-skip { flex: 0 0 auto; color: var(--app-text-muted); }
.wizard-progress { overflow-x: auto; margin-bottom: 18px; padding: 4px 2px 8px; }
.wizard-progress :deep(.n-steps) { min-width: 560px; }

.wizard-panel {
  min-width: 0;
  padding: clamp(22px, 4vw, 36px);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-md);
}

.wizard-panel-heading { gap: 12px; margin-bottom: 28px; }
.wizard-panel-heading h2 { margin: 0; font-size: 21px; line-height: 1.3; }
.wizard-step-count { margin-bottom: 4px; color: var(--app-text-faint); font-size: 11px; }
.wizard-panel-icon {
  display: grid;
  width: 40px;
  height: 40px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: var(--app-radius-sm);
  background: var(--app-primary-soft);
  color: var(--app-primary-strong);
}

.wizard-inline-error {
  gap: 8px;
  margin: -8px 0 20px;
  padding: 10px 12px;
  border: 1px solid var(--app-danger);
  border-radius: var(--app-radius-sm);
  background: var(--app-danger-soft);
  color: var(--app-danger);
  font-size: 13px;
  line-height: 1.5;
}

.wizard-step-content { min-width: 0; }
.wizard-step-intro { margin: 0 0 20px; color: var(--app-text-muted); font-size: 14px; line-height: 1.65; }
.wizard-semester-fields { display: grid; max-width: 480px; grid-template-columns: minmax(0, 1fr) minmax(140px, 0.7fr); gap: 14px; }
.wizard-semester-fields-wide { max-width: 720px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.wizard-field-wide { grid-column: 1 / -1; }
.wizard-field { display: grid; gap: 7px; color: var(--app-text-muted); font-size: 13px; font-weight: 650; }
.wizard-field small { color: var(--app-text-faint); font-size: 12px; font-weight: 400; }
.wizard-field :deep(.n-input),
.wizard-field :deep(.n-input-number),
.wizard-field :deep(.n-select),
.wizard-field :deep(.n-date-picker) { width: 100%; }
.wizard-neutral-note { max-width: 720px; margin-top: 18px; }
.wizard-success-note { gap: 7px; margin: 18px 0 0; color: var(--app-success); font-size: 13px; }
.wizard-period-summary { flex-wrap: wrap; gap: 8px; margin-bottom: 20px; padding: 14px; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); background: var(--app-surface-muted); }
.wizard-period-summary span { color: var(--app-text-muted); font-size: 13px; }
.wizard-secondary-action { min-height: 40px; }
.wizard-help { margin: 14px 0 0; color: var(--app-text-faint); font-size: 12px; line-height: 1.55; }
.wizard-finish-content :deep(.n-result) { padding: 8px 0 0; }
.wizard-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 22px; }
.wizard-actions { justify-content: space-between; gap: 14px; margin-top: 18px; }
.wizard-actions :deep(.n-button) { min-height: 40px; font-weight: 650; }

.wizard-state {
  display: grid;
  min-height: 260px;
  place-items: center;
  align-content: center;
  gap: 10px;
  padding: 28px;
  border: 1px dashed var(--app-border-strong);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  color: var(--app-text-muted);
  text-align: center;
}

.wizard-state strong { color: var(--app-text); }
.wizard-state span { font-size: 13px; }
.wizard-state svg { color: var(--app-danger); }
.wizard-error { border-style: solid; }

@media (max-width: 700px) {
  .wizard-page { padding: 24px 16px 36px; }
  .wizard-header { align-items: flex-start; flex-direction: column; gap: 14px; }
  .wizard-header-actions { justify-content: flex-start; }
  .wizard-skip { align-self: flex-start; }
  .wizard-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
}

@media (max-width: 420px) {
  .wizard-page { padding: 18px 12px 28px; }
  .wizard-header h1 { font-size: 26px; }
  .wizard-header p:last-child { font-size: 13px; }
  .wizard-panel { padding: 20px 16px; }
  .wizard-panel-heading { margin-bottom: 22px; }
  .wizard-semester-fields,
  .wizard-semester-fields-wide { grid-template-columns: 1fr; }
  .wizard-field-wide { grid-column: auto; }
  .wizard-actions { align-items: stretch; }
  .wizard-actions :deep(.n-button) { flex: 1; }
}
</style>
