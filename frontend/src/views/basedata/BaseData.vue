<script setup lang="ts">
import { Database, FileUp, RefreshCw, ShieldCheck } from '@lucide/vue'
import { NAlert, NButton, NSelect, NSpin } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import { listSemesters } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import { useAuthStore } from '@/stores/auth'
import { useSemesterContextStore } from '@/stores/semesterContext'
import ManualEntry from './ManualEntry.vue'
import ReferenceImport from './ReferenceImport.vue'
import './basedata-workspace.css'

const auth = useAuthStore()
const semesterContext = useSemesterContextStore()
const route = useRoute()
const router = useRouter()
const semesters = ref<SemesterListItem[]>([])
const currentId = ref<number | null>(null)
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
const initialSection = computed(() => {
  const value = String(route.query.tab ?? '')
  return ['subjects', 'teachers', 'classes', 'rooms', 'reference'].includes(value)
    ? value as 'subjects' | 'teachers' | 'classes' | 'rooms' | 'reference'
    : 'subjects'
})

async function loadSemesters() {
  loading.value = true
  loadError.value = null
  try {
    await semesterContext.load()
    semesters.value = await listSemesters()
    const querySemesterId = Number(route.query.semester)
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
    <header class="basedata-page-header">
      <div>
        <p class="basedata-eyebrow">{{ '基础档案' }}</p>
        <h1>{{ '基础数据' }}</h1>
        <p>{{ '按学期维护教师、班级、科目与教室/场地，保持排课所需的基础信息一致。' }}</p>
      </div>
      <div class="basedata-header-actions">
        <n-select
          v-if="semesters.length"
          v-model:value="currentId"
          v-accessible-select="'选择工作学期'"
          :options="semesterOptions"
          data-testid="basedata-semester-select"
          :placeholder="'选择学期'"
        />
        <n-button secondary data-testid="basedata-reference-import" @click="router.push({ query: { ...route.query, tab: 'reference' } })">
          <template #icon><FileUp :size="16" aria-hidden="true" /></template>
          {{ '参考文件导入' }}
        </n-button>
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
      <span>{{ '请先在“学期与作息时间表”中创建学期，再维护教师、班级、科目和教室/场地。' }}</span>
      <n-button type="primary" @click="router.push({ name: 'semesters' })">{{ '前往学期配置' }}</n-button>
    </section>

    <section v-else class="basedata-panel basedata-manual-panel" data-testid="basedata-workspace">
      <n-alert v-if="!canEdit" class="basedata-readonly" type="info" data-testid="basedata-readonly">
        <template #icon><ShieldCheck :size="17" aria-hidden="true" /></template>
        {{ '当前角色仅可查看基础数据，写入操作仅对教务主任开放。' }}
      </n-alert>
      <ReferenceImport
        v-if="initialSection === 'reference'"
        :key="`reference-${currentId}`"
        :semester-id="currentId"
        :can-edit="canEdit"
      />
      <ManualEntry
        v-else
        :key="`manual-${currentId}-${initialSection}`"
        :semester-id="currentId"
        :initial-section="initialSection"
        :can-edit="canEdit"
        :can-delete="canAdminHighRisk"
        :can-manage-accounts="canAdminHighRisk"
        :show-readonly-notice="false"
      />
    </section>
  </div>
</template>
