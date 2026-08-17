<script setup lang="ts">
import {
  NAlert, NButton, NCheckbox, NDatePicker, NEmpty, NInput, NInputNumber, NSelect,
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
import { getSetupCheck } from '@/api/wizard'
import type { SetupCheck, SetupCheckItem } from '@/api/wizard'
import { canEditCore as canEditCoreRole } from '@/permissions'
import { useAuthStore } from '@/stores/auth'
import { useWizardStore } from '@/stores/wizard'
import { useAppConfigStore } from '@/stores/appConfig'
import { useSemesterContextStore } from '@/stores/semesterContext'
import ImportTab from '@/views/basedata/ImportTab.vue'
import PeriodSetup from '@/views/wizard/PeriodSetup.vue'

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
const setupCheck = ref<SetupCheck | null>(null)
const busy = ref(false)
const initialLoading = ref(true)
const initialError = ref<string | null>(null)
const actionError = ref<string | null>(null)
const checkError = ref<string | null>(null)
const checkLoading = ref(false)
const warningsAcknowledged = ref(false)
type BaseDataSection = 'subjects' | 'teachers' | 'classes' | 'rooms'
const baseDataTarget = ref<BaseDataSection | null>(null)

const termOptions = [
  { label: '第一学期', value: 1 },
  { label: '第二学期', value: 2 },
]
const stepNames = ['学校与学期', '基础数据', '作息安排', '完成检查']
const baseDataSections: Partial<Record<string, BaseDataSection>> = {
  subjects_missing: 'subjects',
  teachers_missing: 'teachers',
  classes_missing: 'classes',
  rooms_missing: 'rooms',
}
const baseDataActionLabels: Record<BaseDataSection, string> = {
  subjects: '录入科目',
  teachers: '录入教师',
  classes: '录入班级',
  rooms: '录入教室',
}
const canEditCore = computed(() => (
  // Isolated component tests mount without the router guard; the API remains the final boundary.
  !auth.user || canEditCoreRole(auth.user.roles)
))
const canEditSchool = computed(() => !auth.user || auth.hasRole('admin'))
const canEditSemester = computed(() => (
  canEditCore.value
  && (!semesterContext.authoritative || semesterContext.isCurrent(semesterId.value))
))
const finishDisabled = computed(() => (
  busy.value
  || !canEditCore.value
  || !setupCheck.value
  || setupCheck.value.blockers.length > 0
  || (setupCheck.value.warnings.length > 0 && !warningsAcknowledged.value)
))

function stepStatus(index: number): 'wait' | 'process' | 'finish' | 'error' {
  if (index === 3) {
    if (wizard.state?.completed) return 'finish'
    return step.value === index ? 'process' : 'wait'
  }
  if (!semesterId.value || !setupCheck.value) {
    return step.value === index ? 'process' : 'wait'
  }
  if (setupCheck.value.blockers.some((item) => item.step === index)) {
    return step.value === index ? 'process' : 'error'
  }
  return 'finish'
}

function syncFormFromSemester(value: Semester) {
  year.value = value.academic_year
  term.value = value.term
  startDate.value = value.start_date
  endDate.value = value.end_date
}

async function loadCheck(id: number) {
  checkLoading.value = true
  checkError.value = null
  warningsAcknowledged.value = false
  try {
    setupCheck.value = await getSetupCheck(id)
  } catch (error) {
    setupCheck.value = null
    checkError.value = apiErrorMessage(error, '无法读取当前学期的完成检查')
    throw error
  } finally {
    checkLoading.value = false
  }
}

async function retryCheck() {
  if (!semesterId.value) return
  try {
    await loadCheck(semesterId.value)
  } catch {
    // loadCheck exposes the API error inline for the next attempt.
  }
}

async function refreshCheck() {
  if (!semesterId.value) return
  try {
    await loadCheck(semesterId.value)
  } catch {
    // The completion step exposes the retry action.
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
  setupCheck.value = null
  checkError.value = null
  if (semesterId.value) {
    await loadSemester(semesterId.value)
    try {
      await loadCheck(semesterId.value)
    } catch {
      // The completion step owns the inline retry state.
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
    if (canEditCore.value && wizard.state?.paused) {
      await wizard.patch({
        current_step: wizard.state.resume_step,
        paused: false,
      })
    }
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
  if (busy.value) return
  if (!canEditCore.value) {
    step.value = Math.min(step.value + 1, 3)
    return
  }
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
    if (nextStep === 1) baseDataTarget.value = null
    step.value = nextStep
    if (!await persistStep(nextStep)) {
      step.value = previousStep
      return
    }
    await refreshCheck()
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
  if (busy.value || step.value === 0) return
  if (!canEditCore.value) {
    step.value = Math.max(step.value - 1, 0)
    return
  }
  actionError.value = null
  const previousStep = step.value
  const nextStep = Math.max(step.value - 1, 0)
  if (nextStep === 1) baseDataTarget.value = null
  step.value = nextStep
  busy.value = true
  if (!await persistStep(nextStep)) step.value = previousStep
  busy.value = false
}

async function goToStep(targetStep: number, targetSection: BaseDataSection | null = null) {
  const nextStep = Math.max(0, Math.min(targetStep, 2))
  actionError.value = null
  const previousTarget = baseDataTarget.value
  if (nextStep === 1) baseDataTarget.value = targetSection
  if (!canEditCore.value) {
    step.value = nextStep
    return
  }
  if (busy.value) return
  const previousStep = step.value
  step.value = nextStep
  busy.value = true
  if (!await persistStep(nextStep)) {
    step.value = previousStep
    baseDataTarget.value = previousTarget
  }
  busy.value = false
}

function checkActionLabel(item: SetupCheckItem): string {
  const section = baseDataSections[item.code]
  if (section) return baseDataActionLabels[section]
  if (item.code.startsWith('semester_dates_')) return '修改学期日期'
  if (item.code === 'special_dates_missing') return '前往校历设置'
  if (item.code === 'teacher_accounts_missing' && auth.hasRole('admin')) return '前往账号管理'
  if (item.step === 2) return '修改作息安排'
  return `修改${stepNames[item.step]}`
}

function checkActionAvailable(item: SetupCheckItem): boolean {
  return item.code !== 'teacher_accounts_missing' || auth.hasRole('admin')
}

async function openCheckItem(item: SetupCheckItem) {
  const section = baseDataSections[item.code]
  if (section) {
    await goToStep(1, section)
    return
  }
  if (item.code === 'special_dates_missing') {
    await router.push({
      name: 'calendar',
      query: semesterId.value ? { semester: String(semesterId.value) } : undefined,
    })
    return
  }
  if (item.code === 'teacher_accounts_missing' && auth.hasRole('admin')) {
    await router.push({ name: 'account-permissions' })
    return
  }
  await goToStep(item.step)
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
  if (!semesterId.value || finishDisabled.value) return
  busy.value = true
  actionError.value = null
  try {
    await wizard.complete(semesterId.value, warningsAcknowledged.value)
    message.success('基础设置已完成，可以开始创建教学任务')
    await router.push({ name: 'assignments' })
  } catch (error) {
    actionError.value = apiErrorMessage(error, '无法完成设置，请稍后重试。')
    await refreshCheck()
  } finally {
    busy.value = false
  }
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
          <n-step
            v-for="(name, index) in stepNames"
            :key="name"
            :title="name"
            :status="stepStatus(index)"
          />
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
              {{ stepNames[step] }}
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
                :disabled="!canEditSchool"
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
          <p class="wizard-step-intro">{{ '使用组合工作簿或按顺序手工录入科目、教师、班级和教室。' }}</p>
          <ImportTab
            v-if="semesterId"
            :semester-id="semesterId"
            :can-edit="canEditSemester"
            :initial-workspace-mode="baseDataTarget ? 'manual' : 'batch'"
            :initial-manual-section="baseDataTarget ?? 'subjects'"
            @imported="refreshCheck"
          />
          <n-empty v-else :description="'请先完成学期创建'" data-testid="wizard-import-empty" />
        </div>

        <!-- 步骤 2：作息安排 -->
        <div v-else-if="step === 2" class="wizard-step-content">
          <p class="wizard-step-intro">{{ '根据班级生成可调整的作息建议；确认分组、节次和周视图后，一次应用到当前学期。' }}</p>
          <PeriodSetup
            v-if="semesterId"
            :semester-id="semesterId"
            :can-edit="canEditSemester"
            @applied="refreshCheck"
          />
          <n-empty v-else :description="'请先完成学期创建'" data-testid="wizard-period-empty" />
        </div>

        <!-- 步骤 3：完成检查 -->
        <div v-else class="wizard-step-content wizard-finish-content">
          <section v-if="checkLoading" class="wizard-state" data-testid="wizard-check-loading" role="status" aria-live="polite">
            <n-spin size="small" />
            <strong>{{ '正在检查当前学期的基础设置' }}</strong>
          </section>
          <section v-else-if="checkError" class="wizard-state wizard-error" data-testid="wizard-check-error" role="alert">
            <CircleAlert :size="21" aria-hidden="true" />
            <strong>{{ checkError }}</strong>
            <n-button type="primary" @click="retryCheck">{{ '重新检查' }}</n-button>
          </section>
          <div v-else-if="setupCheck" class="wizard-check" data-testid="wizard-check">
            <div
              class="wizard-check-lead"
              :data-status="setupCheck.blockers.length ? 'blocked' : 'ready'"
            >
              <span class="wizard-check-lead-icon" aria-hidden="true">
                <CircleAlert v-if="setupCheck.blockers.length" :size="20" />
                <CheckCircle2 v-else :size="20" />
              </span>
              <div>
                <strong>
                  {{ setupCheck.blockers.length
                    ? `还有 ${setupCheck.blockers.length} 项必须完成`
                    : '已满足基础设置的必要条件' }}
                </strong>
                <p>{{ '完成只表示可以开始创建教学任务，不代表已经通过排课就绪检查。' }}</p>
              </div>
            </div>

            <div class="wizard-summary-grid" aria-label="当前学期数据摘要">
              <n-statistic :label="'科目'" :value="setupCheck.summary.subjects" />
              <n-statistic :label="'教师'" :value="setupCheck.summary.teachers" />
              <n-statistic :label="'班级'" :value="setupCheck.summary.classes" />
              <n-statistic :label="'教室/场地'" :value="setupCheck.summary.rooms" />
            </div>

            <section v-if="setupCheck.blockers.length" class="wizard-check-section" data-testid="wizard-blockers">
              <div class="wizard-check-section-heading">
                <h3>{{ '必须完成' }}</h3>
                <span>{{ '处理后才能完成基础设置' }}</span>
              </div>
              <ul class="wizard-check-list">
                <li v-for="item in setupCheck.blockers" :key="item.code">
                  <span class="wizard-check-marker wizard-check-marker-blocker" aria-hidden="true" />
                  <span>{{ item.message }}</span>
                  <n-button
                    v-if="checkActionAvailable(item)"
                    text
                    type="primary"
                    :data-testid="`wizard-check-action-${item.code}`"
                    @click="openCheckItem(item)"
                  >
                    {{ checkActionLabel(item) }}
                  </n-button>
                  <span v-else class="wizard-check-action-note">{{ '需由系统管理员处理' }}</span>
                </li>
              </ul>
            </section>

            <section v-if="setupCheck.warnings.length" class="wizard-check-section" data-testid="wizard-warnings">
              <div class="wizard-check-section-heading">
                <h3>{{ '建议补充' }}</h3>
                <span>{{ '不阻止创建教学任务' }}</span>
              </div>
              <ul class="wizard-check-list">
                <li v-for="item in setupCheck.warnings" :key="item.code">
                  <span class="wizard-check-marker wizard-check-marker-warning" aria-hidden="true" />
                  <span>{{ item.message }}</span>
                  <n-button
                    v-if="checkActionAvailable(item)"
                    text
                    type="primary"
                    :data-testid="`wizard-check-action-${item.code}`"
                    @click="openCheckItem(item)"
                  >
                    {{ checkActionLabel(item) }}
                  </n-button>
                  <span v-else class="wizard-check-action-note">{{ '需由系统管理员处理' }}</span>
                </li>
              </ul>
              <n-checkbox
                v-if="!setupCheck.blockers.length"
                v-model:checked="warningsAcknowledged"
                data-testid="wizard-warning-ack"
                class="wizard-warning-ack"
                :disabled="!canEditCore"
              >
                {{ '我已了解这些建议项，并选择稍后补充' }}
              </n-checkbox>
            </section>

            <n-alert v-if="!setupCheck.blockers.length && !setupCheck.warnings.length" type="success">
              {{ '基础设置已完整，可以进入教学任务管理。' }}
            </n-alert>
          </div>
        </div>
      </section>

      <footer class="wizard-actions">
        <n-button data-testid="wizard-prev" :disabled="step === 0 || busy" @click="goPrev">
          <template #icon><ChevronLeft :size="16" aria-hidden="true" /></template>
          {{ '上一步' }}
        </n-button>
        <n-button
          v-if="step < 3"
          data-testid="wizard-next"
          type="primary"
          :loading="busy"
          :disabled="busy"
          @click="goNext"
        >
          {{ '下一步' }}
          <template #icon><ChevronRight :size="16" aria-hidden="true" /></template>
        </n-button>
        <n-button
          v-else data-testid="wizard-finish" type="primary" :loading="busy"
          :disabled="finishDisabled" @click="finish"
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
.wizard-check { display: grid; gap: 22px; }
.wizard-check-lead { display: flex; align-items: flex-start; gap: 12px; padding: 14px; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); }
.wizard-check-lead[data-status='blocked'] { border-color: var(--app-danger); background: var(--app-danger-soft); }
.wizard-check-lead[data-status='ready'] { border-color: var(--app-success); background: var(--app-success-soft); }
.wizard-check-lead-icon { display: grid; width: 30px; height: 30px; flex: 0 0 auto; place-items: center; }
.wizard-check-lead[data-status='blocked'] .wizard-check-lead-icon { color: var(--app-danger); }
.wizard-check-lead[data-status='ready'] .wizard-check-lead-icon { color: var(--app-success); }
.wizard-check-lead strong { font-size: 15px; }
.wizard-check-lead p { margin: 4px 0 0; color: var(--app-text-muted); font-size: 12px; line-height: 1.55; }
.wizard-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.wizard-summary-grid :deep(.n-statistic) { min-width: 0; padding: 12px; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); background: var(--app-surface-muted); }
.wizard-summary-grid :deep(.n-statistic-value__content) { font-size: 22px; font-weight: 700; }
.wizard-check-section { display: grid; gap: 10px; }
.wizard-check-section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.wizard-check-section-heading h3 { margin: 0; font-size: 15px; }
.wizard-check-section-heading span { color: var(--app-text-faint); font-size: 12px; }
.wizard-check-list { display: grid; margin: 0; padding: 0; border-top: 1px solid var(--app-border); list-style: none; }
.wizard-check-list li { display: grid; min-width: 0; grid-template-columns: 10px minmax(0, 1fr) auto; align-items: center; gap: 10px; padding: 11px 0; border-bottom: 1px solid var(--app-border); }
.wizard-check-list li > span:nth-child(2) { min-width: 0; overflow-wrap: anywhere; font-size: 13px; line-height: 1.5; }
.wizard-check-action-note { color: var(--app-text-faint); font-size: 12px; }
.wizard-check-marker { width: 8px; height: 8px; border-radius: 50%; }
.wizard-check-marker-blocker { background: var(--app-danger); }
.wizard-check-marker-warning { background: var(--app-warning); }
.wizard-warning-ack { align-items: flex-start; padding: 12px; border: 1px solid var(--app-warning); border-radius: var(--app-radius-sm); background: var(--app-warning-soft); }
.wizard-warning-ack :deep(.n-checkbox__label) { white-space: normal; line-height: 1.5; }
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
  .wizard-check-section-heading { align-items: flex-start; flex-direction: column; gap: 3px; }
  .wizard-check-list li { grid-template-columns: 10px minmax(0, 1fr); }
  .wizard-check-list li :deep(.n-button) { grid-column: 2; justify-self: start; }
  .wizard-actions { align-items: stretch; }
  .wizard-actions :deep(.n-button) { flex: 1; }
}
</style>
