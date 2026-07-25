<script setup lang="ts">
import {
  NButton, NCard, NCheckbox, NDatePicker, NDivider, NEmpty, NInputNumber, NModal,
  NPopconfirm, NSelect, NSpace, NSwitch, NTag, NText, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import {
  copySemester, createPeriodTable, createSemester, deletePeriodTable,
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

// 创建学期表单
const currentYear = new Date().getFullYear()
const form = ref({ academic_year: currentYear, term: 1, template_key: 'junior_high_draft' as string | null })
const yearMin = computed(() => appConfig.config.academic_year.min)
const yearMax = computed(() => appConfig.config.academic_year.max)
const templateOptions = computed(() => [
  { label: '不使用模板', value: '' },
  ...templates.value.map((t) => ({
    label: t.name,
    value: t.key,
  })),
])
const termOptions = [
  { label: '第一学期', value: 1 },
  { label: '第二学期', value: 2 },
]

async function reload() {
  loading.value = true
  try {
    const items = await listSemesters()
    // 逐一取回含作息时间表的完整数据
    semesters.value = await Promise.all(items.map((s: SemesterListItem) => getSemester(s.id)))
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
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
    message.success('学期已创建')
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail || ('创建失败'))
  }
}

async function onDeleteSemester(id: number) {
  await deleteSemester(id)
  message.success('学期已删除')
  await reload()
}

// 新增作息时间表弹窗
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
    message.warning('请输入作息时间表名称')
    return
  }
  try {
    await createPeriodTable(addTableTarget.value!, {
      name: addTableForm.value.name,
      template_key: addTableForm.value.template_key || null,
      is_default: addTableForm.value.is_default,
    })
    showAddTable.value = false
    message.success('作息时间表已新增')
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail || '新增失败')
  }
}

async function onDeleteTable(id: number) {
  await deletePeriodTable(id)
  message.success('作息时间表已删除')
  await reload()
}

function editTable(id: number) {
  router.push({ name: 'period-table-editor', params: { id } })
}

// 复制到新学期
const showCopy = ref(false)
const copySource = ref<Semester | null>(null)

/** 来源日期往后推半年,作为新学期的默认值(用户仍须依实际校历确认)。 */
function halfYearLater(day: string | null): string | null {
  if (!day) return null
  const d = new Date(day)
  d.setMonth(d.getMonth() + 6)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const emptyCopyForm = (): CopyOptions => ({
  academic_year: currentYear, term: 1,
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
    // 起止日不可沿用来源(那是上学期的日期);往后推半年带个起点,让排课管理员改而不是从零填
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
    message.success('已复制到新学期')
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail || '复制失败')
  }
}

const statusType: Record<string, 'default' | 'success' | 'warning'> = {
  preparing: 'warning',
  active: 'success',
  archived: 'default',
}
const statusLabel = (value: string) => (
  { preparing: '准备中', active: '进行中', archived: '已归档' }[value] ?? value
)
const readinessLabel = (value: string) => (value === 'ready' ? '已确认' : '待完善')
</script>

<template>
  <n-space vertical size="large">
    <h1 style="margin: 0">学期与作息时间表</h1>

    <n-card title="创建学期">
      <n-space align="center" :wrap="true">
        <n-text>{{ '学年起始年' }}</n-text>
        <n-input-number v-model:value="form.academic_year" :min="yearMin" :max="yearMax" style="width: 120px" />
        <n-select v-model:value="form.term" :options="termOptions" style="width: 130px" />
        <n-text>学校模板</n-text>
        <n-select
          v-model:value="form.template_key"
          :options="templateOptions"
          placeholder="选择学校模板"
          style="width: 220px"
        />
        <n-button type="primary" @click="onCreateSemester">{{ '创建' }}</n-button>
      </n-space>
    </n-card>

    <n-empty v-if="!loading && semesters.length === 0" :description="'尚未创建任何学期'" />

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
            校历与排课准备
          </n-button>
          <n-button size="tiny" data-testid="copy-semester" @click="openCopy(sem)">
            {{ '复制到新学期' }}
          </n-button>
          <n-popconfirm @positive-click="onDeleteSemester(sem.id)">
            <template #trigger>
              <n-button size="tiny" type="error" ghost>{{ '删除学期' }}</n-button>
            </template>
            确定删除此学期？其作息时间表也会一并删除。
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
            <n-tag v-if="table.is_default" type="success" size="tiny">{{ '默认' }}</n-tag>
            <n-text depth="3">{{ '共' }} {{ table.periods.length }} {{ '格' }}</n-text>
          </n-space>
          <n-space>
            <n-button size="tiny" @click="editTable(table.id)">编辑作息时间表</n-button>
            <n-popconfirm @positive-click="onDeleteTable(table.id)">
              <template #trigger>
                <n-button size="tiny" type="error" ghost>{{ '删除' }}</n-button>
              </template>
              确定删除此作息时间表？
            </n-popconfirm>
          </n-space>
        </n-space>
        <n-button size="small" dashed @click="openAddTable(sem.id)">+ 新增作息时间表</n-button>
      </n-space>
    </n-card>

    <n-modal
      v-model:show="showAddTable"
      preset="card"
      title="新增作息时间表"
      style="max-width: 440px"
    >
      <n-space vertical>
        <n-text>{{ '名称' }}</n-text>
        <n-select
          v-model:value="addTableForm.name"
          filterable
          tag
          :options="[
            { label: '高中作息时间表', value: '高中作息时间表' },
            { label: '初中作息时间表', value: '初中作息时间表' },
          ]"
          :placeholder="'输入或选择名称'"
        />
        <n-text>使用学校模板（可选）</n-text>
        <n-select
          v-model:value="addTableForm.template_key"
          :options="templateOptions"
          placeholder="不使用模板则创建空白作息时间表"
        />
        <n-button type="primary" @click="onAddTable">{{ '创建' }}</n-button>
      </n-space>
    </n-modal>

    <n-modal
      v-model:show="showCopy"
      preset="card"
      :title="`复制“${copySource?.label}”到新学期`"
      style="max-width: 460px"
    >
      <n-space vertical>
        <n-space align="center">
          <n-text>{{ '目标学年起始年' }}</n-text>
          <n-input-number v-model:value="copyForm.academic_year" :min="yearMin" :max="yearMax" style="width: 120px" />
          <n-select v-model:value="copyForm.term" :options="termOptions" style="width: 130px" />
        </n-space>
        <!-- 起止日必填:请假展开、今日看板、代课的「已上过」判定都吃它,漏填不会报错但整个算错 -->
        <n-space align="center">
          <n-text>{{ '学期起止日期' }}</n-text>
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
          {{ '已按来源学期向后推半年带入默认值，请根据实际校历修改。' }}
        </n-text>
        <n-text strong>{{ '复制项目' }}</n-text>
        <n-space>
          <n-checkbox v-model:checked="copyForm.period_tables">作息时间表</n-checkbox>
          <n-checkbox v-model:checked="copyForm.subjects">科目</n-checkbox>
          <n-checkbox v-model:checked="copyForm.teachers">{{ '教师' }}</n-checkbox>
          <n-checkbox v-model:checked="copyForm.rooms">{{ '教室/场地' }}</n-checkbox>
          <n-checkbox v-model:checked="copyForm.classes">{{ '班级' }}</n-checkbox>
          <n-checkbox v-model:checked="copyForm.constraint_config" data-testid="copy-config">
            {{ '排课偏好设置' }}
          </n-checkbox>
        </n-space>
        <n-space align="center">
          <n-switch v-model:value="copyForm.grade_promotion" />
          <n-text>{{ '班级年级自动进位（毕业年级不复制）' }}</n-text>
        </n-space>
        <n-button
          type="primary" data-testid="copy-confirm"
          :disabled="!copyForm.start_date || !copyForm.end_date" @click="onCopy"
        >
          {{ '创建新学期' }}
        </n-button>
      </n-space>
    </n-modal>
  </n-space>
</template>
