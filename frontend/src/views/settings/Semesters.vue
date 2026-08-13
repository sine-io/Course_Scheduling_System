<script setup lang="ts">
import {
  CalendarDays, Clock3, Copy, Pencil, Plus, RefreshCw, Trash2,
} from '@lucide/vue'
import {
  NButton, NCheckbox, NDatePicker, NEmpty, NInput, NInputNumber, NModal,
  NPopconfirm, NSelect, NSpace, NSpin, NSwitch, NTag, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import {
  copySemester, createPeriodTable, createSemester, deletePeriodTable,
  deleteSemester, getSemester, listSemesters, listTemplates,
} from '@/api/semesters'
import type { CopyOptions, SemesterListItem, Semester, Template } from '@/api/semesters'
import { useAppConfigStore } from '@/stores/appConfig'
import './settings-workspace.css'

const message = useMessage()
const route = useRoute()
const router = useRouter()
const appConfig = useAppConfigStore()

const semesters = ref<Semester[]>([])
const templates = ref<Template[]>([])
const initialLoading = ref(true)
const refreshing = ref(false)
const loadError = ref<string | null>(null)
const selectedSemesterId = ref<number | null>(null)

const creating = ref(false)
const deletingSemesterId = ref<number | null>(null)
const deletingTableId = ref<number | null>(null)
const addingTable = ref(false)
const copying = ref(false)

const currentYear = new Date().getFullYear()
const form = ref({
  academic_year: currentYear,
  term: 1,
  template_key: 'junior_high_draft' as string | null,
})
const yearMin = computed(() => appConfig.config.academic_year.min)
const yearMax = computed(() => appConfig.config.academic_year.max)
const templateOptions = computed(() => [
  { label: '不使用模板', value: '' },
  ...templates.value.map((template) => ({ label: template.name, value: template.key })),
])
const termOptions = [
  { label: '第一学期', value: 1 },
  { label: '第二学期', value: 2 },
]
const semesterOptions = computed(() => semesters.value.map((semester) => ({
  label: semester.label,
  value: semester.id,
})))

async function fetchSemesters() {
  const items = await listSemesters()
  semesters.value = await Promise.all(items.map((item: SemesterListItem) => getSemester(item.id)))
  const queryId = Number(route.query.semester)
  const currentId = selectedSemesterId.value
  selectedSemesterId.value = semesters.value.some((semester) => semester.id === currentId)
    ? currentId
    : (semesters.value.some((semester) => semester.id === queryId)
      ? queryId
      : (semesters.value[0]?.id ?? null))
}

async function loadPage() {
  initialLoading.value = true
  loadError.value = null
  try {
    templates.value = await listTemplates()
    await fetchSemesters()
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取学期与作息数据，请重试。')
  } finally {
    initialLoading.value = false
  }
}

async function refreshData() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await fetchSemesters()
  } catch (error) {
    message.error(apiErrorMessage(error, '暂时无法读取学期与作息数据，请重试。'))
  } finally {
    refreshing.value = false
  }
}

onMounted(loadPage)

async function onCreateSemester() {
  if (creating.value) return
  creating.value = true
  try {
    await createSemester({
      academic_year: form.value.academic_year,
      term: form.value.term,
      template_key: form.value.template_key || null,
    })
    message.success('学期已创建')
    await refreshData()
  } catch (error) {
    message.error(apiErrorMessage(error, '暂时无法读取学期与作息数据，请重试。').replace('学期与作息数据', '学期'))
  } finally {
    creating.value = false
  }
}

async function onDeleteSemester(id: number) {
  if (deletingSemesterId.value !== null) return
  deletingSemesterId.value = id
  try {
    await deleteSemester(id)
    message.success('学期已删除')
    await refreshData()
  } catch (error) {
    message.error(apiErrorMessage(error, '暂时无法读取学期与作息数据，请重试。').replace('学期与作息数据', '学期'))
  } finally {
    deletingSemesterId.value = null
  }
}

const showAddTable = ref(false)
const addTableTarget = ref<number | null>(null)
const addTableForm = ref({ name: '', template_key: null as string | null, is_default: false })

function openAddTable(semesterId: number) {
  addTableTarget.value = semesterId
  addTableForm.value = { name: '', template_key: null, is_default: false }
  showAddTable.value = true
}

async function onAddTable() {
  if (addingTable.value) return
  if (!addTableTarget.value || !addTableForm.value.name.trim()) {
    message.warning('请输入作息时间表名称')
    return
  }
  addingTable.value = true
  try {
    await createPeriodTable(addTableTarget.value, {
      name: addTableForm.value.name.trim(),
      template_key: addTableForm.value.template_key || null,
      is_default: addTableForm.value.is_default,
    })
    showAddTable.value = false
    message.success('作息时间表已新增')
    await refreshData()
  } catch (error) {
    message.error(apiErrorMessage(error, '暂时无法读取学期与作息数据，请重试。').replace('学期与作息数据', '作息时间表'))
  } finally {
    addingTable.value = false
  }
}

async function onDeleteTable(id: number) {
  if (deletingTableId.value !== null) return
  deletingTableId.value = id
  try {
    await deletePeriodTable(id)
    message.success('作息时间表已删除')
    await refreshData()
  } catch (error) {
    message.error(apiErrorMessage(error, '暂时无法读取学期与作息数据，请重试。').replace('学期与作息数据', '作息时间表'))
  } finally {
    deletingTableId.value = null
  }
}

function editTable(id: number) {
  router.push({ name: 'period-table-editor', params: { id } })
}

async function selectSemester(id: number | null) {
  if (!id) return
  selectedSemesterId.value = id
  await router.replace({ query: { ...route.query, semester: String(id) } })
}

const showCopy = ref(false)
const copySource = ref<Semester | null>(null)

function halfYearLater(day: string | null): string | null {
  if (!day) return null
  const date = new Date(day)
  date.setMonth(date.getMonth() + 6)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

const emptyCopyForm = (): CopyOptions => ({
  academic_year: currentYear,
  term: 1,
  start_date: null,
  end_date: null,
  period_tables: true,
  subjects: true,
  teachers: true,
  rooms: true,
  classes: true,
  grade_promotion: true,
  constraint_config: true,
})
const copyForm = ref<CopyOptions>(emptyCopyForm())

function openCopy(semester: Semester) {
  copySource.value = semester
  copyForm.value = {
    ...emptyCopyForm(),
    academic_year: semester.academic_year + 1,
    term: semester.term,
    start_date: halfYearLater(semester.start_date),
    end_date: halfYearLater(semester.end_date),
  }
  showCopy.value = true
}

async function onCopy() {
  if (copying.value || !copySource.value) return
  if (!copyForm.value.start_date || !copyForm.value.end_date) {
    message.warning('请选择目标学期的起止日期')
    return
  }
  copying.value = true
  try {
    await copySemester(copySource.value.id, copyForm.value)
    showCopy.value = false
    message.success('已复制到新学期')
    await refreshData()
  } catch (error) {
    message.error(apiErrorMessage(error, '暂时无法读取学期与作息数据，请重试。').replace('学期与作息数据', '学期'))
  } finally {
    copying.value = false
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
  <div class="settings-page">
    <header class="settings-page-header">
      <div>
        <p class="settings-eyebrow">{{ '学期配置' }}</p>
        <h1>{{ '学期与作息时间表' }}</h1>
        <p>{{ '管理学期生命周期、作息表和排课准备状态。每个危险操作都会在提交前明确确认。' }}</p>
      </div>
      <div class="settings-header-actions">
        <n-select
          v-if="semesters.length"
          :value="selectedSemesterId"
          :options="semesterOptions"
          data-testid="semester-select"
          aria-label="选择工作学期"
          @update:value="selectSemester"
        />
        <n-button text type="primary" @click="router.push({ name: 'calendar' })">
          <template #icon><CalendarDays :size="16" aria-hidden="true" /></template>
          {{ '查看校历' }}
        </n-button>
      </div>
    </header>

    <section v-if="initialLoading" class="settings-state" data-testid="semesters-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取学期与作息时间表' }}</strong>
      <span>{{ '学期和作息表加载完成后会显示在这里。' }}</span>
    </section>

    <section v-else-if="loadError" class="settings-state settings-error" data-testid="semesters-error" role="alert">
      <RefreshCw :size="21" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '设置数据未更新，已保留当前页面。' }}</span>
      <n-button type="primary" data-testid="semesters-retry" @click="loadPage">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>

    <template v-else>
      <section class="settings-panel" data-testid="semester-create-panel">
        <div class="settings-panel-heading">
          <div>
            <p class="settings-eyebrow">{{ '新建工作面' }}</p>
            <h2>{{ '创建学期' }}</h2>
            <p>{{ '选择学年、学期和可选模板，创建后仍可继续调整日期与作息。' }}</p>
          </div>
          <Clock3 :size="20" class="settings-heading-icon" aria-hidden="true" />
        </div>
        <div class="settings-form-grid">
          <div class="settings-field">
            <label for="semester-academic-year">{{ '学年起始年' }}</label>
            <n-input-number id="semester-academic-year" v-model:value="form.academic_year" :min="yearMin" :max="yearMax" />
          </div>
          <div class="settings-field">
            <span class="settings-field-label">{{ '学期' }}</span>
            <n-select v-model:value="form.term" :options="termOptions" />
          </div>
          <div class="settings-field">
            <span class="settings-field-label">{{ '学校模板' }}</span>
            <n-select v-model:value="form.template_key" :options="templateOptions" placeholder="选择学校模板" />
          </div>
        </div>
        <div class="settings-actions">
          <n-button type="primary" data-testid="semester-create" :loading="creating" :disabled="creating" @click="onCreateSemester">
            <template #icon><Plus :size="16" aria-hidden="true" /></template>
            {{ '创建学期' }}
          </n-button>
          <n-button quaternary :loading="refreshing" :disabled="refreshing" @click="refreshData">
            <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
            {{ '刷新列表' }}
          </n-button>
        </div>
      </section>

      <section v-if="!refreshing && !semesters.length" class="settings-panel settings-empty" data-testid="semesters-empty">
        <n-empty :description="'尚未创建任何学期'" />
      </section>

      <section v-else class="settings-list" data-testid="semester-list" :aria-busy="refreshing">
        <div v-if="refreshing" class="settings-state settings-inline-state" data-testid="semesters-refreshing" role="status">
          <n-spin size="small" />
          <strong>{{ '正在更新学期列表' }}</strong>
        </div>
        <article
          v-for="semester in semesters" v-else :key="semester.id"
          class="settings-item"
          :data-testid="`semester-${semester.id}`"
          :data-selected="selectedSemesterId === semester.id"
          :aria-current="selectedSemesterId === semester.id ? 'true' : undefined"
        >
          <header class="settings-item-header">
            <div>
              <div class="settings-meta">
                <h2>{{ semester.label }}</h2>
                <n-tag :type="statusType[semester.status]" size="small">{{ statusLabel(semester.status) }}</n-tag>
                <n-tag :type="semester.readiness === 'ready' ? 'success' : 'warning'" size="small">
                  {{ readinessLabel(semester.readiness) }}
                </n-tag>
                <n-tag v-if="selectedSemesterId === semester.id" type="info" size="small">{{ '当前选择' }}</n-tag>
              </div>
              <p>{{ semester.start_date || '未设置开始日期' }} - {{ semester.end_date || '未设置结束日期' }}</p>
            </div>
            <div class="settings-command-group">
              <n-button size="small" @click="router.push({ name: 'calendar', query: { semester: String(semester.id) } })">
                <template #icon><CalendarDays :size="14" aria-hidden="true" /></template>
                {{ '校历与排课准备' }}
              </n-button>
              <n-button size="small" data-testid="copy-semester" :disabled="copying || deletingSemesterId !== null" @click="openCopy(semester)">
                <template #icon><Copy :size="14" aria-hidden="true" /></template>
                {{ '复制到新学期' }}
              </n-button>
              <n-popconfirm :disabled="deletingSemesterId !== null" @positive-click="onDeleteSemester(semester.id)">
                <template #trigger>
                  <n-button
                    :data-testid="`semester-delete-${semester.id}`"
                    size="small" type="error" ghost
                    :loading="deletingSemesterId === semester.id"
                    :disabled="deletingSemesterId !== null"
                  >
                    <template #icon><Trash2 :size="14" aria-hidden="true" /></template>
                    {{ '删除学期' }}
                  </n-button>
                </template>
                {{ `确定删除“${semester.label}”吗？其中的作息时间表也会一并删除。` }}
              </n-popconfirm>
            </div>
          </header>

          <div class="settings-subsection">
            <div class="settings-subsection-header">
              <div>
                <h3>{{ '作息时间表' }}</h3>
                <p>{{ '维护排课使用的节次和时段；编辑会进入独立的宽表工作面。' }}</p>
              </div>
              <n-button size="small" dashed :disabled="addingTable || deletingTableId !== null" @click="openAddTable(semester.id)">
                <template #icon><Plus :size="14" aria-hidden="true" /></template>
                {{ '新增作息表' }}
              </n-button>
            </div>
            <div v-if="!semester.period_tables.length" class="settings-empty">
              <n-empty size="small" :description="'此学期还没有作息时间表'" />
            </div>
            <div v-else class="settings-rows">
              <div v-for="table in semester.period_tables" :key="table.id" class="settings-row">
                <div class="settings-row-main">
                  <strong>{{ table.name }}</strong>
                  <span>{{ `共 ${table.periods.length} 格` }}<template v-if="table.is_default"> · {{ '默认作息表' }}</template></span>
                </div>
                <div class="settings-command-group">
                  <n-button size="small" @click="editTable(table.id)">
                    <template #icon><Pencil :size="14" aria-hidden="true" /></template>
                    {{ '编辑' }}
                  </n-button>
                  <n-popconfirm :disabled="deletingTableId !== null" @positive-click="onDeleteTable(table.id)">
                    <template #trigger>
                      <n-button
                        :data-testid="`period-table-delete-${table.id}`"
                        size="small" type="error" ghost
                        :loading="deletingTableId === table.id"
                        :disabled="deletingTableId !== null"
                      >
                        <template #icon><Trash2 :size="14" aria-hidden="true" /></template>
                        {{ '删除' }}
                      </n-button>
                    </template>
                    {{ `确定删除“${table.name}”吗？` }}
                  </n-popconfirm>
                </div>
              </div>
            </div>
          </div>
        </article>
      </section>

      <n-modal v-model:show="showAddTable" preset="card" title="新增作息时间表" style="max-width: 440px">
        <div class="settings-modal-form">
          <div class="settings-field">
            <label for="period-table-name">{{ '名称' }}</label>
            <n-input id="period-table-name" v-model:value="addTableForm.name" placeholder="例如：初中作息时间表" />
          </div>
          <div class="settings-field">
            <span class="settings-field-label">{{ '使用学校模板（可选）' }}</span>
            <n-select v-model:value="addTableForm.template_key" :options="templateOptions" placeholder="不使用模板则创建空白表" />
          </div>
          <n-checkbox v-model:checked="addTableForm.is_default">{{ '设为该学期默认作息表' }}</n-checkbox>
          <div class="settings-modal-actions">
            <n-button @click="showAddTable = false">{{ '取消' }}</n-button>
            <n-button type="primary" :loading="addingTable" :disabled="addingTable" @click="onAddTable">
              <template #icon><Plus :size="15" aria-hidden="true" /></template>
              {{ '创建' }}
            </n-button>
          </div>
        </div>
      </n-modal>

      <n-modal v-model:show="showCopy" preset="card" :title="`复制“${copySource?.label}”到新学期`" style="max-width: 520px">
        <div class="settings-modal-form">
          <div class="settings-form-grid settings-form-grid-two">
            <div class="settings-field">
              <label for="copy-academic-year">{{ '目标学年起始年' }}</label>
              <n-input-number id="copy-academic-year" v-model:value="copyForm.academic_year" :min="yearMin" :max="yearMax" />
            </div>
            <div class="settings-field">
              <span class="settings-field-label">{{ '目标学期' }}</span>
              <n-select v-model:value="copyForm.term" :options="termOptions" />
            </div>
          </div>
          <div class="settings-form-grid settings-form-grid-two">
            <div class="settings-field">
              <label for="copy-start">{{ '开始日期' }}</label>
              <n-date-picker id="copy-start" v-model:formatted-value="copyForm.start_date" data-testid="copy-start" value-format="yyyy-MM-dd" type="date" />
            </div>
            <div class="settings-field">
              <label for="copy-end">{{ '结束日期' }}</label>
              <n-date-picker id="copy-end" v-model:formatted-value="copyForm.end_date" data-testid="copy-end" value-format="yyyy-MM-dd" type="date" />
            </div>
          </div>
          <span class="settings-field-hint">{{ '日期已按来源学期向后推半年带入默认值，请根据实际校历修改。' }}</span>
          <div class="settings-field">
            <span class="settings-field-label">{{ '复制项目' }}</span>
            <n-space :wrap="true">
              <n-checkbox v-model:checked="copyForm.period_tables">{{ '作息时间表' }}</n-checkbox>
              <n-checkbox v-model:checked="copyForm.subjects">{{ '科目' }}</n-checkbox>
              <n-checkbox v-model:checked="copyForm.teachers">{{ '教师' }}</n-checkbox>
              <n-checkbox v-model:checked="copyForm.rooms">{{ '教室/场地' }}</n-checkbox>
              <n-checkbox v-model:checked="copyForm.classes">{{ '班级' }}</n-checkbox>
              <n-checkbox v-model:checked="copyForm.constraint_config" data-testid="copy-config">
                {{ '排课偏好设置' }}
              </n-checkbox>
            </n-space>
          </div>
          <n-switch v-model:value="copyForm.grade_promotion">
            <template #checked>{{ '班级年级自动进位' }}</template>
            <template #unchecked>{{ '班级年级不进位' }}</template>
          </n-switch>
          <div class="settings-modal-actions">
            <n-button @click="showCopy = false">{{ '取消' }}</n-button>
            <n-button type="primary" data-testid="copy-confirm" :loading="copying" :disabled="copying || !copyForm.start_date || !copyForm.end_date" @click="onCopy">
              <template #icon><Copy :size="15" aria-hidden="true" /></template>
              {{ '创建新学期' }}
            </n-button>
          </div>
        </div>
      </n-modal>
    </template>
  </div>
</template>
