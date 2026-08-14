<script setup lang="ts">
import {
  NAlert, NButton, NEmpty, NInputNumber, NResult, NSelect, NSpace,
  NSpin, NStatistic, NStep, NSteps, NText, useMessage,
} from 'naive-ui'
import {
  CalendarRange, CheckCircle2, ChevronLeft, ChevronRight, CircleAlert, Clock3,
  LayoutTemplate, SkipForward, Upload,
} from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import { demoDataStatus, loadDemoData } from '@/api/assignments'
import { createSemester, getSemester, listTemplates } from '@/api/semesters'
import type { Semester, Template } from '@/api/semesters'
import { getSemesterSummary } from '@/api/wizard'
import type { SemesterSummary } from '@/api/wizard'
import { useWizardStore } from '@/stores/wizard'
import { useAppConfigStore } from '@/stores/appConfig'
import { useSemesterContextStore } from '@/stores/semesterContext'
import ImportTab from '@/views/basedata/ImportTab.vue'

const router = useRouter()
const message = useMessage()
const wizard = useWizardStore()
const appConfig = useAppConfigStore()
const semesterContext = useSemesterContextStore()

const step = ref(0)
const templates = ref<Template[]>([])
const templateKey = ref<string | null>(null)
const year = ref(new Date().getFullYear())
const term = ref(1)
const semesterId = ref<number | null>(null)
const semester = ref<Semester | null>(null)
const summary = ref<SemesterSummary | null>(null)
const busy = ref(false)
const initialLoading = ref(true)
const initialError = ref<string | null>(null)
const actionError = ref<string | null>(null)
const summaryError = ref<string | null>(null)
const summaryLoading = ref(false)
const demoAvailable = ref(false)
const demoSchool = ref('')
const loadingDemo = ref(false)

const termOptions = [
  { label: '第一学期', value: 1 },
  { label: '第二学期', value: 2 },
]
const periodTable = computed(() => (
  semester.value?.period_tables.find((table) => table.is_default)
  ?? semester.value?.period_tables[0]
  ?? null
))
const canEditSemester = computed(() => (
  !semesterContext.authoritative || semesterContext.isCurrent(semesterId.value)
))

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
}

async function loadWizardData() {
  initialLoading.value = true
  initialError.value = null
  actionError.value = null
  try {
    await semesterContext.load()
    templates.value = await listTemplates()
    templateKey.value ??= templates.value[0]?.key ?? null

    if (!wizard.loaded || wizard.error) await wizard.fetch()
    if (wizard.error && !wizard.state) throw new Error(wizard.error)
    if (wizard.state) {
      step.value = wizard.state.current_step
      semesterId.value = wizard.state.semester_id
      if (semesterId.value) {
        await loadSemester(semesterId.value)
        if (step.value === 4) {
          try {
            await loadSummary(semesterId.value)
          } catch {
            // The completion step owns the inline retry state.
          }
        }
      }
    }

    // 查询接口仅对管理员开放，其他角色进入向导时忽略 403 即可。
    try {
      const demo = await demoDataStatus()
      demoAvailable.value = demo.available
      demoSchool.value = demo.school_name
    } catch {
      demoAvailable.value = false
    }
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

async function goNext() {
  if (busy.value) return
  actionError.value = null

  if (step.value === 0 && !templateKey.value) {
    actionError.value = '当前没有可用的学制模板，请重新加载。'
    return
  }
  if (step.value === 1) {
    const minYear = appConfig.config.academic_year.min
    const maxYear = appConfig.config.academic_year.max
    if (!Number.isInteger(year.value) || year.value < minYear || year.value > maxYear) {
      actionError.value = `学年起始年须在 ${minYear} 至 ${maxYear} 之间。`
      return
    }
    if (![1, 2].includes(term.value)) {
      actionError.value = '请选择有效的学期。'
      return
    }
  }

  const previousStep = step.value
  busy.value = true
  try {
    // 每项都独立检查，以便从创建、保存或读取任一失败点继续重试。
    if (step.value === 1) {
      if (!semesterId.value) {
        const sem = await createSemester({
          academic_year: year.value, term: term.value, template_key: templateKey.value,
        })
        semesterId.value = sem.id
      }
      if (wizard.state?.semester_id !== semesterId.value) {
        await wizard.patch({ semester_id: semesterId.value })
      }
      if (semester.value?.id !== semesterId.value) {
        await loadSemester(semesterId.value)
      }
    }

    const nextStep = Math.min(step.value + 1, 4)
    step.value = nextStep
    if (!await persistStep(nextStep)) {
      step.value = previousStep
      return
    }
    if (nextStep === 4 && semesterId.value) {
      try {
        await loadSummary(semesterId.value)
      } catch {
        // The completion step owns the inline retry state.
      }
    }
  } catch (error) {
    step.value = previousStep
    if (!actionError.value) {
      actionError.value = apiErrorMessage(error, step.value === 1 ? '创建学期失败，请检查输入后重试。' : '无法进入下一步，请稍后重试。')
    }
  } finally {
    busy.value = false
  }
}

async function goPrev() {
  if (busy.value || step.value === 0) return
  actionError.value = null
  const previousStep = step.value
  const nextStep = Math.max(step.value - 1, 0)
  step.value = nextStep
  busy.value = true
  if (!await persistStep(nextStep)) step.value = previousStep
  busy.value = false
}

async function finish() {
  if (busy.value) return
  busy.value = true
  actionError.value = null
  try {
    await wizard.patch({ completed: true })
    message.success('初始设置完成')
    await router.push({ name: 'assignments' })
  } catch (error) {
    actionError.value = apiErrorMessage(error, '无法完成设置，请稍后重试。')
  } finally {
    busy.value = false
  }
}

async function onLoadDemo() {
  if (loadingDemo.value) return
  actionError.value = null
  loadingDemo.value = true
  try {
    const r = await loadDemoData()
    await wizard.fetch()
    message.success(
      `已创建 ${r.classes} 个班级、${r.teachers} 名教师和 ${r.assignments} 条教学任务，`
      + '现在可以直接试用自动排课。',
      { duration: 8000 },
    )
    router.push({ name: 'dashboard' })
  } catch (e) {
    actionError.value = apiErrorMessage(e, '示例数据加载失败，请稍后重试。')
  } finally {
    loadingDemo.value = false
  }
}

async function skip() {
  if (busy.value) return
  busy.value = true
  actionError.value = null
  try {
    await wizard.patch({ completed: true })
    await router.push({ name: 'dashboard' })
  } catch (error) {
    actionError.value = apiErrorMessage(error, '无法跳过设置，请稍后重试。')
  } finally {
    busy.value = false
  }
}

function openPeriodEditor() {
  if (!periodTable.value) {
    actionError.value = '当前学期没有可编辑的作息时间表，请返回上一步重试。'
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
        <p class="wizard-eyebrow">{{ '首次设置' }}</p>
        <h1>{{ '设置向导' }}</h1>
        <p>{{ '按顺序准备学期、作息时间表和基础数据，之后即可开始排课。' }}</p>
      </div>
      <n-button
        quaternary
        class="wizard-skip"
        :disabled="initialLoading || busy"
        data-testid="wizard-skip"
        @click="skip"
      >
        <template #icon><SkipForward :size="16" aria-hidden="true" /></template>
        {{ '跳过，稍后设置' }}
      </n-button>
    </header>

    <section v-if="initialLoading" class="wizard-state" data-testid="wizard-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取设置向导' }}</strong>
      <span>{{ '正在检查模板和已保存的进度。' }}</span>
    </section>

    <section v-else-if="initialError" class="wizard-state wizard-error" data-testid="wizard-load-error" role="alert">
      <CircleAlert :size="22" aria-hidden="true" />
      <strong>{{ initialError }}</strong>
      <n-button data-testid="wizard-retry" type="primary" @click="loadWizardData">
        {{ '重新加载' }}
      </n-button>
    </section>

    <template v-else>
      <nav class="wizard-progress" aria-label="设置步骤">
        <n-steps :current="step + 1" size="small">
          <n-step :title="'学制模板'" />
          <n-step :title="'学年学期'" />
          <n-step :title="'作息时间表'" />
          <n-step :title="'导入数据'" />
          <n-step :title="'完成'" />
        </n-steps>
      </nav>

      <section class="wizard-panel" aria-labelledby="wizard-step-title">
        <div class="wizard-panel-heading">
          <span class="wizard-panel-icon" aria-hidden="true">
            <LayoutTemplate v-if="step === 0" :size="20" />
            <CalendarRange v-else-if="step === 1" :size="20" />
            <Clock3 v-else-if="step === 2" :size="20" />
            <Upload v-else-if="step === 3" :size="20" />
            <CheckCircle2 v-else :size="20" />
          </span>
          <div>
            <p class="wizard-step-count">{{ `第 ${step + 1} 步 / 5` }}</p>
            <h2 id="wizard-step-title" data-testid="wizard-step-title">
              {{ ['学制模板', '学年学期', '作息时间表', '导入数据', '完成'][step] }}
            </h2>
          </div>
        </div>

        <div v-if="actionError" class="wizard-inline-error" data-testid="wizard-error" role="alert" aria-live="assertive">
          <CircleAlert :size="17" aria-hidden="true" />
          <span>{{ actionError }}</span>
        </div>

        <!-- 步骤 0：学校模板 -->
        <div v-if="step === 0" class="wizard-step-content">
          <n-alert
            v-if="demoAvailable" type="info" title="先体验完整排课流程"
            class="wizard-demo-alert"
          >
            <n-space vertical size="small">
              <n-text>
                可加载虚构的初中示例学校“{{ demoSchool || '示例初中' }}”，系统会自动创建
                班级、教师、科目、教学任务和教室，随后即可运行自动排课。
              </n-text>
              <n-text depth="3" style="font-size: 12px">
                示例数据仅可在尚未创建任何学期的全新系统中加载，不适用于正式环境。
              </n-text>
              <div>
                <n-button
                  type="primary" size="small" :loading="loadingDemo" :disabled="busy"
                  data-testid="wizard-demo-load" @click="onLoadDemo"
                >
                  加载示例数据
                </n-button>
              </div>
            </n-space>
          </n-alert>

          <p class="wizard-step-intro">{{ '选择初中空白模板，系统会带入可编辑的科目参考项和空白作息时间表。' }}</p>
          <div v-if="!templates.length" class="wizard-empty" data-testid="wizard-empty" role="status">
            <n-empty :description="'暂无可用的学制模板'">
              <template #extra>
                <n-button @click="loadWizardData">{{ '重新读取模板' }}</n-button>
              </template>
            </n-empty>
          </div>
          <div v-else class="wizard-template-grid" role="radiogroup" aria-label="学制模板">
            <label
              v-for="t in templates"
              :key="t.key"
              class="wizard-template"
              :class="{ 'is-selected': templateKey === t.key }"
            >
              <input
                v-model="templateKey"
                class="wizard-template-input"
                type="radio"
                name="wizard-template"
                :value="t.key"
                :data-testid="`tpl-${t.key}`"
              >
              <span class="wizard-template-mark" aria-hidden="true"><LayoutTemplate :size="19" /></span>
              <span class="wizard-template-copy">
                <strong>{{ t.name }}</strong>
                <span>{{ `空白作息时间表 · ${t.subject_count} 个科目参考项` }}</span>
              </span>
              <CheckCircle2 v-if="templateKey === t.key" class="wizard-template-check" :size="18" aria-hidden="true" />
            </label>
          </div>
        </div>

        <!-- 步骤 1：学年学期 -->
        <div v-else-if="step === 1" class="wizard-step-content">
          <p class="wizard-step-intro">{{ '设置本学期的学年起始年和学期。' }}</p>
          <div class="wizard-semester-fields">
            <label class="wizard-field">
              <span>{{ '学年起始年' }}</span>
              <n-input-number
                v-model:value="year"
                data-testid="wizard-year"
                :min="appConfig.config.academic_year.min"
                :max="appConfig.config.academic_year.max"
                :disabled="!!semesterId"
                button-placement="both"
              />
            </label>
            <label class="wizard-field">
              <span>{{ '学期' }}</span>
              <n-select v-model:value="term" :options="termOptions" :disabled="!!semesterId" />
            </label>
          </div>
          <p v-if="semesterId" class="wizard-success-note">
            <CheckCircle2 :size="16" aria-hidden="true" />
            <span>{{ '已创建：' }}{{ semester?.label }}</span>
          </p>
        </div>

        <!-- 步骤 2：作息时间表 -->
        <div v-else-if="step === 2" class="wizard-step-content">
          <p class="wizard-step-intro">{{ '模板不会默认铃声和上课时段，请按学校实际作息填写。' }}</p>
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

        <!-- 步骤 3：导入数据 -->
        <div v-else-if="step === 3" class="wizard-step-content">
          <p class="wizard-step-intro">{{ '下载模板填写后上传，批量创建教师、班级和科目（可跳过，稍后在基础数据中补充）。' }}</p>
          <ImportTab v-if="semesterId" :semester-id="semesterId" :can-edit="canEditSemester" />
          <n-empty v-else :description="'请先完成学期创建'" data-testid="wizard-import-empty" />
        </div>

        <!-- 步骤 4：完成 -->
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
          <n-result v-else status="success" :title="'初始设置即将完成'" :description="'以下是目前已创建的数据摘要'">
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
        <n-button data-testid="wizard-prev" :disabled="step === 0 || busy" @click="goPrev">
          <template #icon><ChevronLeft :size="16" aria-hidden="true" /></template>
          {{ '上一步' }}
        </n-button>
        <n-button
          v-if="step < 4"
          data-testid="wizard-next"
          type="primary"
          :loading="busy"
          :disabled="!templates.length && step === 0"
          @click="goNext"
        >
          {{ '下一步' }}
          <template #icon><ChevronRight :size="16" aria-hidden="true" /></template>
        </n-button>
        <n-button
          v-else data-testid="wizard-finish" type="primary" :loading="busy"
          :disabled="busy || !!summaryError || !summary" @click="finish"
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

.wizard-header h1 { margin: 0; font-size: 30px; line-height: 1.2; }
.wizard-header p:last-child { margin: 8px 0 0; color: var(--app-text-muted); font-size: 14px; line-height: 1.6; }
.wizard-eyebrow,
.wizard-step-count {
  margin: 0 0 7px;
  color: var(--app-primary-strong);
  font-size: 12px;
  font-weight: 700;
}

.wizard-skip { flex: 0 0 auto; color: var(--app-text-muted); }
.wizard-progress { overflow-x: auto; margin-bottom: 18px; padding: 4px 2px 8px; }
.wizard-progress :deep(.n-steps) { min-width: 620px; }

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
.wizard-demo-alert { margin-bottom: 20px; }
.wizard-template-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }

.wizard-template {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: 92px;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  color: var(--app-text);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--app-motion-duration) var(--app-motion-ease), background var(--app-motion-duration) var(--app-motion-ease);
}

.wizard-template-input {
  position: absolute;
  z-index: 1;
  inset: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  opacity: 0;
  cursor: pointer;
}

.wizard-template:hover { border-color: var(--app-primary-border); background: var(--app-primary-soft); }
.wizard-template.is-selected { border-color: var(--app-primary); background: var(--app-primary-soft); box-shadow: inset 0 0 0 1px var(--app-primary); }
.wizard-template-mark { display: grid; width: 34px; height: 34px; flex: 0 0 auto; place-items: center; border-radius: var(--app-radius-sm); background: var(--app-surface-muted); color: var(--app-primary-strong); }
.wizard-template-copy { display: grid; min-width: 0; gap: 4px; }
.wizard-template-copy strong { overflow-wrap: anywhere; font-size: 14px; }
.wizard-template-copy span { color: var(--app-text-muted); font-size: 12px; line-height: 1.45; }
.wizard-template-check { margin-left: auto; flex: 0 0 auto; color: var(--app-primary); }

.wizard-empty { display: grid; min-height: 180px; place-items: center; border: 1px dashed var(--app-border-strong); border-radius: var(--app-radius-sm); }
.wizard-semester-fields { display: grid; max-width: 480px; grid-template-columns: minmax(0, 1fr) minmax(140px, 0.7fr); gap: 14px; }
.wizard-field { display: grid; gap: 7px; color: var(--app-text-muted); font-size: 13px; font-weight: 650; }
.wizard-field :deep(.n-input-number),
.wizard-field :deep(.n-select) { width: 100%; }
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
  .wizard-skip { align-self: flex-start; }
  .wizard-template-grid { grid-template-columns: 1fr; }
  .wizard-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
}

@media (max-width: 420px) {
  .wizard-page { padding: 18px 12px 28px; }
  .wizard-header h1 { font-size: 26px; }
  .wizard-header p:last-child { font-size: 13px; }
  .wizard-panel { padding: 20px 16px; }
  .wizard-panel-heading { margin-bottom: 22px; }
  .wizard-semester-fields { grid-template-columns: 1fr; }
  .wizard-actions { align-items: stretch; }
  .wizard-actions :deep(.n-button) { flex: 1; }
}
</style>
