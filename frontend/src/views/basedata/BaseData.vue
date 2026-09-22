<script setup lang="ts">
import { Database, RefreshCw, ShieldCheck } from '@lucide/vue'
import { NAlert, NButton, NRadioButton, NRadioGroup, NSelect, NSpin } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import { listSemesters } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import { useAuthStore } from '@/stores/auth'
import { useSemesterContextStore } from '@/stores/semesterContext'
import ReferenceImport from './ReferenceImport.vue'
import RoomsTab from './RoomsTab.vue'
import TemplateImport from './TemplateImport.vue'
import TeacherAccountBindings from './TeacherAccountBindings.vue'
import './basedata-workspace.css'

export type BaseDataSection = 'rooms' | 'template' | 'reference' | 'teacher-accounts'
const props = withDefaults(defineProps<{
  embedded?: boolean
  embeddedSemesterId?: number
  embeddedSection?: BaseDataSection
}>(), {
  embedded: false,
  embeddedSemesterId: undefined,
  embeddedSection: 'rooms',
})
const emit = defineEmits<{ changed: [] }>()
const auth = useAuthStore()
const semesterContext = useSemesterContextStore()
const route = useRoute()
const router = useRouter()
const semesters = ref<SemesterListItem[]>([])
const currentId = ref<number | null>(null)
const embeddedSection = ref<BaseDataSection>(props.embeddedSection)
const loading = ref(true)
const loadError = ref<string | null>(null)

const canEdit = computed(() => (
  (auth.hasRole('admin') || auth.hasRole('director'))
  && (!semesterContext.authoritative || semesterContext.isCurrent(currentId.value))
))
const canAdminHighRisk = computed(() => (
  auth.hasRole('admin')
  && (!semesterContext.authoritative || semesterContext.isCurrent(currentId.value))
))

const semesterOptions = computed(() =>
  semesters.value.map((s) => ({ label: s.label, value: s.id })),
)
const currentSemester = computed(() => (
  semesters.value.find(semester => semester.id === currentId.value) ?? null
))
const activeSection = computed<BaseDataSection>(() => {
  if (props.embedded) {
    const allowed = auth.hasRole('admin')
      ? ['rooms', 'template', 'reference', 'teacher-accounts']
      : ['rooms', 'template', 'reference']
    return allowed.includes(embeddedSection.value)
      ? embeddedSection.value
      : 'rooms'
  }
  const value = String(route.query.tab ?? '')
  const allowed = auth.hasRole('admin')
    ? ['rooms', 'template', 'reference', 'teacher-accounts']
    : ['rooms', 'template', 'reference']
  return allowed.includes(value)
    ? value as BaseDataSection
    : 'rooms'
})

async function selectSection(value: BaseDataSection) {
  if (props.embedded) {
    embeddedSection.value = value
    return
  }
  await router.replace({ query: { ...route.query, tab: value } })
}

async function selectSemester(value: number | null) {
  currentId.value = value
  if (!value) return
  await router.replace({ query: { ...route.query, semester: String(value) } })
}

async function loadSemesters() {
  loading.value = true
  loadError.value = null
  try {
    await semesterContext.load()
    semesters.value = await listSemesters()
    const querySemesterId = props.embeddedSemesterId ?? Number(route.query.semester)
    currentId.value = semesters.value.find((semester) => semester.id === querySemesterId)?.id
      ?? semesters.value.find((semester) => semester.is_current)?.id
      ?? semesterContext.currentSemesterId
      ?? semesters.value[0]?.id
      ?? null
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取基础数据，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(loadSemesters)
</script>

<template>
  <div class="basedata-page">
    <header v-if="!props.embedded" class="basedata-page-header">
      <div>
        <p class="basedata-eyebrow">{{ '基础档案' }}</p>
        <h1>{{ '基础数据' }}</h1>
        <p>{{ '维护教室/场地、批量导入和教师登录账号绑定。班级、科目与教师档案统一在“排课工作台”中维护。' }}</p>
      </div>
      <div class="basedata-header-actions">
        <n-select
          v-if="semesters.length"
          v-accessible-select="'选择工作学期'"
          :value="currentId"
          :options="semesterOptions"
          data-testid="basedata-semester-select"
          :placeholder="'选择学期'"
          @update:value="selectSemester"
        />
      </div>
    </header>

    <section v-if="loading" class="basedata-state" data-testid="basedata-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取基础数据' }}</strong>
      <span>{{ '学期列表加载完成后会显示可维护的基础档案。' }}</span>
    </section>

    <section v-else-if="loadError" class="basedata-state basedata-state-error" data-testid="basedata-error" role="alert">
      <RefreshCw :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '基础数据未更新。' }}</span>
      <n-button type="primary" data-testid="basedata-retry" @click="loadSemesters">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>

    <section v-else-if="!currentId" class="basedata-state" data-testid="basedata-empty">
      <Database :size="24" aria-hidden="true" />
      <strong>{{ '尚未创建任何学期' }}</strong>
      <span>{{ '请先在“排课工作台”中创建学期，再维护教室/场地、导入数据或绑定教师账号。' }}</span>
      <n-button type="primary" data-testid="basedata-start-scheduling" @click="router.push({ name: 'scheduling-workbench' })">{{ '前往排课工作台' }}</n-button>
    </section>

    <section v-else class="basedata-panel basedata-manual-panel" data-testid="basedata-workspace">
      <n-radio-group
        :value="activeSection"
        size="small"
        data-testid="basedata-section-switcher"
        aria-label="选择基础数据功能"
        @update:value="selectSection"
      >
        <n-radio-button value="rooms" data-testid="basedata-section-rooms">{{ '教室/场地' }}</n-radio-button>
        <n-radio-button value="template" data-testid="basedata-section-template">{{ '模板导入' }}</n-radio-button>
        <n-radio-button value="reference" data-testid="basedata-section-reference">{{ '参考文件导入' }}</n-radio-button>
        <n-radio-button v-if="auth.hasRole('admin')" value="teacher-accounts" data-testid="basedata-section-teacher-accounts">
          {{ '教师账号绑定' }}
        </n-radio-button>
      </n-radio-group>

      <n-alert
        v-if="activeSection === 'teacher-accounts' ? !canAdminHighRisk : !canEdit"
        class="basedata-readonly"
        type="info"
        data-testid="basedata-readonly"
      >
        <template #icon><ShieldCheck :size="17" aria-hidden="true" /></template>
        {{ '当前学期仅可查看，无法执行写入操作。' }}
      </n-alert>
      <RoomsTab
        v-if="activeSection === 'rooms'"
        :key="`rooms-${currentId}`"
        :semester-id="currentId"
        :can-edit="canEdit"
        :can-delete="canAdminHighRisk"
        @changed="emit('changed')"
      />
      <TemplateImport
        v-else-if="activeSection === 'template' && currentSemester"
        :key="`template-${currentId}`"
        :semester="currentSemester"
        :can-edit="canEdit"
        @changed="emit('changed')"
      />
      <ReferenceImport
        v-else-if="activeSection === 'reference'"
        :key="`reference-${currentId}`"
        :semester-id="currentId"
        :can-edit="canEdit"
        @changed="emit('changed')"
      />
      <TeacherAccountBindings
        v-else
        :key="`teacher-accounts-${currentId}`"
        :semester-id="currentId"
        :can-edit="canAdminHighRisk"
        @changed="emit('changed')"
      />
    </section>
  </div>
</template>
