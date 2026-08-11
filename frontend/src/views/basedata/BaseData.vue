<script setup lang="ts">
import { Database, RefreshCw, ShieldCheck } from '@lucide/vue'
import { NAlert, NButton, NSelect, NSpin, NTabPane, NTabs } from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import { listSemesters } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'
import { useAuthStore } from '@/stores/auth'
import ClassesTab from './ClassesTab.vue'
import ImportTab from './ImportTab.vue'
import RoomsTab from './RoomsTab.vue'
import SubjectsTab from './SubjectsTab.vue'
import TeachersTab from './TeachersTab.vue'
import './basedata-workspace.css'

const auth = useAuthStore()
const router = useRouter()
const semesters = ref<SemesterListItem[]>([])
const currentId = ref<number | null>(null)
const activeTab = ref('teachers')
const loading = ref(true)
const loadError = ref<string | null>(null)

const canEdit = computed(() => auth.hasRole('admin') || auth.hasRole('scheduler'))

const semesterOptions = computed(() =>
  semesters.value.map((s) => ({ label: s.label, value: s.id })),
)

function errorMessage(error: unknown): string {
  return (error as Partial<ApiError> | null)?.detail || '暂时无法读取基础数据，请重试。'
}

async function loadSemesters() {
  loading.value = true
  loadError.value = null
  try {
    semesters.value = await listSemesters()
    currentId.value = semesters.value[0]?.id ?? null
    if (!canEdit.value && activeTab.value === 'import') activeTab.value = 'teachers'
  } catch (error) {
    loadError.value = errorMessage(error)
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
          :options="semesterOptions"
          data-testid="basedata-semester-select"
          aria-label="选择工作学期"
          :placeholder="'选择学期'"
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
      <span>{{ '请先在“学期与作息时间表”中创建学期，再维护教师、班级、科目和教室/场地。' }}</span>
      <n-button type="primary" @click="router.push({ name: 'semesters' })">{{ '前往学期配置' }}</n-button>
    </section>

    <section v-else class="basedata-panel basedata-tabs-panel" data-testid="basedata-workspace">
      <n-alert v-if="!canEdit" class="basedata-readonly" type="info" data-testid="basedata-readonly">
        <template #icon><ShieldCheck :size="17" aria-hidden="true" /></template>
        {{ '当前角色仅可查看基础数据，写入操作仅对排课管理员开放。' }}
      </n-alert>
      <n-tabs v-model:value="activeTab" type="line" :animated="false">
        <n-tab-pane name="teachers" :tab="'教师'">
          <TeachersTab :key="`t-${currentId}`" :semester-id="currentId" :can-edit="canEdit" />
        </n-tab-pane>
        <n-tab-pane name="classes" :tab="'班级'">
          <ClassesTab :key="`c-${currentId}`" :semester-id="currentId" :can-edit="canEdit" />
        </n-tab-pane>
        <n-tab-pane name="subjects" :tab="'科目'">
          <SubjectsTab :key="`s-${currentId}`" :semester-id="currentId" :can-edit="canEdit" />
        </n-tab-pane>
        <n-tab-pane name="rooms" :tab="'教室/场地'">
          <RoomsTab :key="`r-${currentId}`" :semester-id="currentId" :can-edit="canEdit" />
        </n-tab-pane>
        <n-tab-pane v-if="canEdit" name="import" :tab="'批量导入'">
          <ImportTab :key="`i-${currentId}`" :semester-id="currentId" />
        </n-tab-pane>
      </n-tabs>
    </section>
  </div>
</template>
