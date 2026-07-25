<script setup lang="ts">
import {
  NButton, NCard, NCheckbox, NDatePicker, NDivider, NEmpty, NInputNumber, NModal,
  NPopconfirm, NSelect, NSpace, NSwitch, NTag, NText, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import {
  STATUS_LABELS, copySemester, createPeriodTable, createSemester, deletePeriodTable,
  deleteSemester, listSemesters, listTemplates,
} from '@/api/semesters'
import type { CopyOptions, SemesterListItem, Semester, Template } from '@/api/semesters'
import { getSemester } from '@/api/semesters'
import { useAppConfigStore } from '@/stores/appConfig'

const message = useMessage()
const router = useRouter()
const appConfig = useAppConfigStore()

const semesters = ref<Semester[]>([])
const templates = ref<Template[]>([])
const loading = ref(false)

// 建立學期表單
const form = ref({ academic_year: 115, term: 1, template_key: null as string | null })
const yearMin = computed(() => appConfig.config.academic_year.min)
const yearMax = computed(() => appConfig.config.academic_year.max)
const templateOptions = computed(() => [
  { label: appConfig.isMainland ? '空白（不带入节次表）' : '空白(不帶入節次表)', value: '' },
  ...templates.value.map((t) => ({
    label: `${t.name}(${t.minutes_per_period == null
      ? (appConfig.isMainland ? '待编辑节次' : '待編輯節次')
      : `${t.minutes_per_period} ${appConfig.isMainland ? '分/节' : '分/節'}`})`,
    value: t.key,
  })),
])
const termOptions = computed(() => appConfig.isMainland
  ? [{ label: '第一学期', value: 1 }, { label: '第二学期', value: 2 }]
  : [{ label: '第 1 學期', value: 1 }, { label: '第 2 學期', value: 2 }])

async function reload() {
  loading.value = true
  try {
    const items = await listSemesters()
    // 逐一取回含節次表的完整資料
    semesters.value = await Promise.all(items.map((s: SemesterListItem) => getSemester(s.id)))
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (appConfig.isMainland) form.value.academic_year = 2026
  templates.value = await listTemplates()
  await reload()
})

async function onCreateSemester() {
  try {
    await createSemester({
      academic_year: form.value.academic_year,
      term: form.value.term,
      template_key: form.value.template_key || null,
    })
    message.success(appConfig.isMainland ? '学期已创建' : '學期已建立')
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail || (appConfig.isMainland ? '创建失败' : '建立失敗'))
  }
}

async function onDeleteSemester(id: number) {
  await deleteSemester(id)
  message.success(appConfig.isMainland ? '学期已删除' : '學期已刪除')
  await reload()
}

// 新增節次表 modal
const showAddTable = ref(false)
const addTableTarget = ref<number | null>(null)
const addTableForm = ref({ name: '', template_key: null as string | null, is_default: false })

function openAddTable(semesterId: number) {
  addTableTarget.value = semesterId
  addTableForm.value = { name: '', template_key: null, is_default: false }
  showAddTable.value = true
}

async function onAddTable() {
  if (!addTableForm.value.name) {
    message.warning(appConfig.isMainland ? '请输入节次表名称' : '請輸入節次表名稱')
    return
  }
  try {
    await createPeriodTable(addTableTarget.value!, {
      name: addTableForm.value.name,
      template_key: addTableForm.value.template_key || null,
      is_default: addTableForm.value.is_default,
    })
    showAddTable.value = false
    message.success(appConfig.isMainland ? '节次表已新增' : '節次表已新增')
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail || '新增失敗')
  }
}

async function onDeleteTable(id: number) {
  await deletePeriodTable(id)
    message.success(appConfig.isMainland ? '节次表已删除' : '節次表已刪除')
  await reload()
}

function editTable(id: number) {
  router.push({ name: 'period-table-editor', params: { id } })
}

// 複製到新學期
const showCopy = ref(false)
const copySource = ref<Semester | null>(null)

/** 來源日期往後推半年,作為新學期的預設值(使用者仍須依實際校曆確認)。 */
function halfYearLater(day: string | null): string | null {
  if (!day) return null
  const d = new Date(day)
  d.setMonth(d.getMonth() + 6)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const emptyCopyForm = (): CopyOptions => ({
  academic_year: 115, term: 1,
  start_date: null, end_date: null,
  period_tables: true, subjects: true, teachers: true, rooms: true, classes: true,
  grade_promotion: true, constraint_config: true,
})
const copyForm = ref<CopyOptions>(emptyCopyForm())

function openCopy(sem: Semester) {
  copySource.value = sem
  copyForm.value = {
    ...emptyCopyForm(),
    academic_year: sem.academic_year + 1,
    term: sem.term,
    // 起訖日不可沿用來源(那是上學期的日期);往後推半年帶個起點,讓組長改而不是從零填
    start_date: halfYearLater(sem.start_date),
    end_date: halfYearLater(sem.end_date),
  }
  showCopy.value = true
}

async function onCopy() {
  if (!copySource.value) return
  try {
    await copySemester(copySource.value.id, copyForm.value)
    showCopy.value = false
    message.success(appConfig.isMainland ? '已复制到新学期' : '已複製到新學期')
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail || '複製失敗')
  }
}

const statusType: Record<string, 'default' | 'success' | 'warning'> = {
  preparing: 'warning',
  active: 'success',
  archived: 'default',
}
const statusLabel = (value: string) => appConfig.isMainland
  ? ({ preparing: '准备中', active: '进行中', archived: '已归档' }[value] ?? value)
  : STATUS_LABELS[value as keyof typeof STATUS_LABELS]
const readinessLabel = (value: string) => appConfig.isMainland
  ? (value === 'ready' ? '已就绪' : '草稿')
  : (value === 'ready' ? '已就緒' : '草稿')
</script>

<template>
  <n-space vertical size="large">
    <h1 style="margin: 0">{{ appConfig.isMainland ? '学期与节次表' : '學期與節次表' }}</h1>

    <n-card :title="appConfig.isMainland ? '建立学期' : '建立學期'">
      <n-space align="center" :wrap="true">
        <n-text>{{ appConfig.isMainland ? '学年起始年' : '學年度' }}</n-text>
        <n-input-number v-model:value="form.academic_year" :min="yearMin" :max="yearMax" style="width: 120px" />
        <n-select v-model:value="form.term" :options="termOptions" style="width: 130px" />
        <n-text>{{ appConfig.isMainland ? '学制模板' : '學制範本' }}</n-text>
        <n-select
          v-model:value="form.template_key"
          :options="templateOptions"
          :placeholder="appConfig.isMainland ? '选择学制模板' : '選擇學制範本'"
          style="width: 220px"
        />
        <n-button type="primary" @click="onCreateSemester">{{ appConfig.isMainland ? '创建' : '建立' }}</n-button>
      </n-space>
    </n-card>

    <n-empty v-if="!loading && semesters.length === 0" :description="appConfig.isMainland ? '尚未创建任何学期' : '尚未建立任何學期'" />

    <n-card v-for="sem in semesters" :key="sem.id">
      <n-space justify="space-between" align="center">
        <n-space align="center">
          <strong>{{ sem.label }}</strong>
          <n-tag :type="statusType[sem.status]" size="small">
            {{ statusLabel(sem.status) }}
          </n-tag>
          <n-tag :type="sem.readiness === 'ready' ? 'success' : 'warning'" size="small">
            {{ readinessLabel(sem.readiness) }}
          </n-tag>
        </n-space>
        <n-space>
          <n-button size="tiny" @click="router.push({ name: 'calendar' })">
            {{ appConfig.isMainland ? '校历与就绪' : '校曆與就緒' }}
          </n-button>
          <n-button size="tiny" data-testid="copy-semester" @click="openCopy(sem)">
            {{ appConfig.isMainland ? '复制到新学期' : '複製到新學期' }}
          </n-button>
          <n-popconfirm @positive-click="onDeleteSemester(sem.id)">
            <template #trigger>
              <n-button size="tiny" type="error" ghost>{{ appConfig.isMainland ? '删除学期' : '刪除學期' }}</n-button>
            </template>
            {{ appConfig.isMainland ? '确定删除此学期？其节次表将一并移除。' : '確定刪除此學期?其節次表將一併移除。' }}
          </n-popconfirm>
        </n-space>
      </n-space>

      <n-divider style="margin: 12px 0" />

      <n-space vertical size="small">
        <n-space
          v-for="table in sem.period_tables"
          :key="table.id"
          align="center"
          justify="space-between"
        >
          <n-space align="center">
            <n-text>{{ table.name }}</n-text>
            <n-tag v-if="table.is_default" type="success" size="tiny">{{ appConfig.isMainland ? '默认' : '預設' }}</n-tag>
            <n-text depth="3">{{ appConfig.isMainland ? '共' : '共' }} {{ table.periods.length }} {{ appConfig.isMainland ? '格' : '格' }}</n-text>
          </n-space>
          <n-space>
            <n-button size="tiny" @click="editTable(table.id)">{{ appConfig.isMainland ? '编辑节次表' : '編輯節次表' }}</n-button>
            <n-popconfirm @positive-click="onDeleteTable(table.id)">
              <template #trigger>
                <n-button size="tiny" type="error" ghost>{{ appConfig.isMainland ? '删除' : '刪除' }}</n-button>
              </template>
              {{ appConfig.isMainland ? '确定删除此节次表？' : '確定刪除此節次表?' }}
            </n-popconfirm>
          </n-space>
        </n-space>
        <n-button size="small" dashed @click="openAddTable(sem.id)">+ {{ appConfig.isMainland ? '新增节次表' : '新增節次表' }}</n-button>
      </n-space>
    </n-card>

    <n-modal
      v-model:show="showAddTable"
      preset="card"
      :title="appConfig.isMainland ? '新增节次表' : '新增節次表'"
      style="max-width: 440px"
    >
      <n-space vertical>
        <n-text>{{ appConfig.isMainland ? '名称' : '名稱' }}</n-text>
        <n-select
          v-model:value="addTableForm.name"
          filterable
          tag
          :options="[
            { label: '高中部節次表', value: '高中部節次表' },
            { label: appConfig.isMainland ? '初中节次表' : '國中部節次表', value: appConfig.isMainland ? '初中节次表' : '國中部節次表' },
          ]"
          :placeholder="appConfig.isMainland ? '输入或选择名称' : '輸入或選擇名稱'"
        />
        <n-text>{{ appConfig.isMainland ? '带入学制模板（可选）' : '帶入學制範本(選填)' }}</n-text>
        <n-select
          v-model:value="addTableForm.template_key"
          :options="templateOptions"
          :placeholder="appConfig.isMainland ? '不带入则建立空表' : '不帶入則建立空表'"
        />
        <n-button type="primary" @click="onAddTable">{{ appConfig.isMainland ? '创建' : '建立' }}</n-button>
      </n-space>
    </n-modal>

    <n-modal
      v-model:show="showCopy"
      preset="card"
      :title="appConfig.isMainland
        ? `复制“${copySource?.label}”到新学期`
        : `複製「${copySource?.label}」到新學期`"
      style="max-width: 460px"
    >
      <n-space vertical>
        <n-space align="center">
          <n-text>{{ appConfig.isMainland ? '目标学年起始年' : '目標學年度' }}</n-text>
          <n-input-number v-model:value="copyForm.academic_year" :min="yearMin" :max="yearMax" style="width: 120px" />
          <n-select v-model:value="copyForm.term" :options="termOptions" style="width: 130px" />
        </n-space>
        <!-- 起訖日必填:請假展開、今日看板、代課的「已上過」判定都吃它,漏填不會報錯但整個算錯 -->
        <n-space align="center">
          <n-text>{{ appConfig.isMainland ? '学期起止日期' : '學期起訖' }}</n-text>
          <n-date-picker
            v-model:formatted-value="copyForm.start_date" value-format="yyyy-MM-dd"
            type="date" data-testid="copy-start" style="width: 150px"
          />
          <n-text>~</n-text>
          <n-date-picker
            v-model:formatted-value="copyForm.end_date" value-format="yyyy-MM-dd"
            type="date" data-testid="copy-end" style="width: 150px"
          />
        </n-space>
        <n-text depth="3" style="font-size: 12px">
          {{ appConfig.isMainland
            ? '已按来源学期向后推半年带入默认值，请根据实际校历修改。'
            : '已依來源學期往後推半年帶入預設值,請確認實際校曆後修改。' }}
        </n-text>
        <n-text strong>{{ appConfig.isMainland ? '复制项目' : '複製項目' }}</n-text>
        <n-space>
          <n-checkbox v-model:checked="copyForm.period_tables">{{ appConfig.isMainland ? '节次表' : '節次表' }}</n-checkbox>
          <n-checkbox v-model:checked="copyForm.subjects">科目</n-checkbox>
          <n-checkbox v-model:checked="copyForm.teachers">{{ appConfig.isMainland ? '教师' : '教師' }}</n-checkbox>
          <n-checkbox v-model:checked="copyForm.rooms">{{ appConfig.isMainland ? '场地' : '場地' }}</n-checkbox>
          <n-checkbox v-model:checked="copyForm.classes">{{ appConfig.isMainland ? '班级' : '班級' }}</n-checkbox>
          <n-checkbox v-model:checked="copyForm.constraint_config" data-testid="copy-config">
            {{ appConfig.isMainland ? '排课偏好设置' : '排課偏好設定' }}
          </n-checkbox>
        </n-space>
        <n-space align="center">
          <n-switch v-model:value="copyForm.grade_promotion" />
          <n-text>{{ appConfig.isMainland ? '班级年级自动进位（毕业年级不复制）' : '班級年級自動進位(畢業年級不複製)' }}</n-text>
        </n-space>
        <n-button
          type="primary" data-testid="copy-confirm"
          :disabled="!copyForm.start_date || !copyForm.end_date" @click="onCopy"
        >
          {{ appConfig.isMainland ? '创建新学期' : '建立新學期' }}
        </n-button>
      </n-space>
    </n-modal>
  </n-space>
</template>
