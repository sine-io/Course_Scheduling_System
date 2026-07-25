<script setup lang="ts">
import {
  NButton, NCard, NGrid, NGridItem, NInputNumber, NResult, NSelect, NSpace, NStatistic,
  NStep, NSteps, NText, useMessage,
} from 'naive-ui'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import { createSemester, getSemester, listTemplates } from '@/api/semesters'
import { PRIMARY } from '@/theme'
import type { Semester, Template } from '@/api/semesters'
import { getSemesterSummary } from '@/api/wizard'
import type { SemesterSummary } from '@/api/wizard'
import { useWizardStore } from '@/stores/wizard'
import { useAppConfigStore } from '@/stores/appConfig'
import ImportTab from '@/views/basedata/ImportTab.vue'

const router = useRouter()
const message = useMessage()
const wizard = useWizardStore()
const appConfig = useAppConfigStore()

const step = ref(0)
const templates = ref<Template[]>([])
const templateKey = ref<string | null>(null)
const year = ref(new Date().getFullYear())
const term = ref(1)
const semesterId = ref<number | null>(null)
const semester = ref<Semester | null>(null)
const summary = ref<SemesterSummary | null>(null)
const busy = ref(false)

const termOptions = [
  { label: '第一学期', value: 1 },
  { label: '第二学期', value: 2 },
]

onMounted(async () => {
  templates.value = await listTemplates()
  templateKey.value ??= templates.value[0]?.key ?? null
  if (!wizard.loaded) await wizard.fetch()
  if (wizard.state) {
    step.value = wizard.state.current_step
    semesterId.value = wizard.state.semester_id
    if (semesterId.value) await loadSemester(semesterId.value)
  }
})

async function loadSemester(id: number) {
  semester.value = await getSemester(id)
  summary.value = await getSemesterSummary(id)
}

async function persistStep() {
  await wizard.patch({ current_step: step.value })
}

async function goNext() {
  // 第 2 步(学年学期)→ 创建学期
  if (step.value === 1 && !semesterId.value) {
    if (!templateKey.value) {
      message.warning('请先在上一步选择学制模板')
      return
    }
    busy.value = true
    try {
      const sem = await createSemester({
        academic_year: year.value, term: term.value, template_key: templateKey.value,
      })
      semesterId.value = sem.id
      await wizard.patch({ semester_id: sem.id })
      await loadSemester(sem.id)
    } catch (e) {
      message.error((e as ApiError).detail || '创建学期失败')
      busy.value = false
      return
    }
    busy.value = false
  }
  step.value = Math.min(step.value + 1, 4)
  if (step.value === 4 && semesterId.value) await loadSemester(semesterId.value)
  await persistStep()
}

async function goPrev() {
  step.value = Math.max(step.value - 1, 0)
  await persistStep()
}

async function finish() {
  await wizard.patch({ completed: true })
  message.success('初始设置完成')
  router.push({ name: 'basedata' })
}

async function skip() {
  await wizard.patch({ completed: true })
  router.push({ name: 'dashboard' })
}

function openPeriodEditor() {
  const table = semester.value?.period_tables.find((t) => t.is_default)
  if (table) router.push({ name: 'period-table-editor', params: { id: table.id } })
}
</script>

<template>
  <div style="max-width: 860px; margin: 24px auto; padding: 0 16px">
    <n-space vertical size="large">
      <n-space justify="space-between" align="center">
        <h1 style="margin: 0">{{ '设置向导' }}</h1>
        <n-button quaternary @click="skip">{{ '跳过，稍后设置' }}</n-button>
      </n-space>

      <n-steps :current="step + 1" size="small">
        <n-step :title="'学制模板'" />
        <n-step :title="'学年学期'" />
        <n-step :title="'作息时间表'" />
        <n-step :title="'导入数据'" />
        <n-step :title="'完成'" />
      </n-steps>

      <n-card>
        <!-- 步骤 0：学校模板 -->
        <template v-if="step === 0">
          <n-text>选择初中空白模板，系统会带入可编辑的科目参考项和空白作息时间表。</n-text>
          <n-grid :cols="2" :x-gap="12" :y-gap="12" style="margin-top: 16px">
            <n-grid-item v-for="t in templates" :key="t.key">
              <n-card
                hoverable
                :data-testid="`tpl-${t.key}`"
                :style="{
                  cursor: 'pointer',
                  borderColor: templateKey === t.key ? 'var(--n-color-target)' : undefined,
                  outline: templateKey === t.key ? `2px solid ${PRIMARY}` : 'none',
                }"
                @click="templateKey = t.key"
              >
                <strong>{{ t.name }}</strong>
                <div><n-text depth="3">空白作息时间表 · {{ t.subject_count }} 个科目参考项</n-text></div>
              </n-card>
            </n-grid-item>
          </n-grid>
        </template>

        <!-- 步骤 1：学年学期 -->
        <template v-else-if="step === 1">
          <n-space vertical>
            <n-text>{{ '设置本学期的学年起始年和学期。' }}</n-text>
            <n-space align="center">
              <n-text>{{ '学年起始年' }}</n-text>
              <n-input-number v-model:value="year" data-testid="wizard-year" :min="appConfig.config.academic_year.min" :max="appConfig.config.academic_year.max" :disabled="!!semesterId" style="width: 120px" />
              <n-select v-model:value="term" :options="termOptions" :disabled="!!semesterId" style="width: 140px" />
            </n-space>
            <n-text v-if="semesterId" type="success">{{ '已创建：' }}{{ semester?.label }}</n-text>
          </n-space>
        </template>

        <!-- 步骤 2：作息时间表 -->
        <template v-else-if="step === 2">
          <n-space vertical>
            <n-text>模板不会默认铃声和上课时段，请按学校实际作息填写。</n-text>
            <div v-if="semester">
              <n-text strong>{{ semester.period_tables[0]?.name }}</n-text>
              <n-text depth="3">
                {{ '（共' }} {{ semester.period_tables[0]?.periods.length ?? 0 }} {{ '格，每周' }}
                {{ semester.period_tables[0]?.num_weekdays ?? 5 }} {{ '天）' }}
              </n-text>
            </div>
            <n-button @click="openPeriodEditor">打开作息时间表编辑器</n-button>
            <n-text depth="3">{{ '提示：离开编辑器后返回本向导时会自动回到此步骤。' }}</n-text>
          </n-space>
        </template>

        <!-- 步骤 3：导入数据 -->
        <template v-else-if="step === 3">
          <n-space vertical>
            <n-text>下载模板填写后上传，批量创建教师、班级和科目（可跳过，稍后在基础数据中补充）。</n-text>
            <ImportTab v-if="semesterId" :semester-id="semesterId" />
          </n-space>
        </template>

        <!-- 步骤 4：完成 -->
        <template v-else>
          <n-result status="success" :title="'初始设置即将完成'" :description="'以下是目前已创建的数据摘要'">
            <template #footer>
              <n-space justify="center" size="large">
                <n-statistic :label="'科目'" :value="summary?.subjects ?? 0" />
                <n-statistic :label="'教师'" :value="summary?.teachers ?? 0" />
                <n-statistic :label="'班级'" :value="summary?.classes ?? 0" />
                <n-statistic :label="'教室/场地'" :value="summary?.rooms ?? 0" />
              </n-space>
            </template>
          </n-result>
        </template>
      </n-card>

      <n-space justify="space-between">
        <n-button data-testid="wizard-prev" :disabled="step === 0" @click="goPrev">{{ '上一步' }}</n-button>
        <n-button v-if="step < 4" data-testid="wizard-next" type="primary" :loading="busy" @click="goNext">
          {{ '下一步' }}
        </n-button>
        <n-button v-else data-testid="wizard-finish" type="primary" @click="finish">
          {{ '完成，前往基础数据' }}
        </n-button>
      </n-space>
    </n-space>
  </div>
</template>
