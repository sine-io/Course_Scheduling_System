<script setup lang="ts">
import { ArrowRight, CheckCircle2, CircleAlert, Plus, RefreshCw } from '@lucide/vue'
import {
  NAlert, NButton, NCheckbox, NInput, NSpin, NTabPane, NTabs, NTag, useMessage,
} from 'naive-ui'
import { computed, onMounted, reactive, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import {
  createSubject, listClassUnits, listRooms, listSubjects, listTeachers,
} from '@/api/basedata'
import type { Subject } from '@/api/basedata'
import ClassesTab from './ClassesTab.vue'
import RoomsTab from './RoomsTab.vue'
import SubjectsTab from './SubjectsTab.vue'
import TeachersTab from './TeachersTab.vue'
import './basedata-workspace.css'

const props = withDefaults(
  defineProps<{ semesterId: number; canEdit?: boolean }>(),
  { canEdit: true },
)
const emit = defineEmits<{ changed: [] }>()
const message = useMessage()

type ManualSection = 'subjects' | 'teachers' | 'classes' | 'rooms'
const activeSection = ref<ManualSection>('subjects')
const loading = ref(true)
const loadError = ref<string | null>(null)
const childRevision = ref(0)
const counts = reactive({ subjects: 0, teachers: 0, classes: 0, rooms: 0 })

const subjectList = ref<Subject[]>([])
const selectedQuick = ref<string[]>([])
const quickSearch = ref('')
const quickBusy = ref(false)
const quickError = ref<string | null>(null)

const commonSubjects = [
  { name: '语文', domain: '语言与文学', is_major: true },
  { name: '数学', domain: '数学', is_major: true },
  { name: '英语', domain: '语言与文学', is_major: true },
  { name: '道德与法治', domain: '人文社会', is_major: false },
  { name: '历史', domain: '人文社会', is_major: false },
  { name: '地理', domain: '人文社会', is_major: false },
  { name: '物理', domain: '自然科学', is_major: false },
  { name: '化学', domain: '自然科学', is_major: false },
  { name: '生物', domain: '自然科学', is_major: false },
  { name: '信息技术', domain: '技术', is_major: false },
  { name: '体育', domain: '艺术与健康', is_major: false },
  { name: '音乐', domain: '艺术与健康', is_major: false },
  { name: '美术', domain: '艺术与健康', is_major: false },
  { name: '综合实践', domain: '综合实践', is_major: false },
]

const sectionMeta: Array<{ key: ManualSection; label: string; required: boolean }> = [
  { key: 'subjects', label: '科目', required: true },
  { key: 'teachers', label: '教师', required: true },
  { key: 'classes', label: '班级', required: true },
  { key: 'rooms', label: '教室/场地', required: false },
]

const subjectNames = computed(() => new Set(subjectList.value.map((item) => item.name.trim())))
const filteredCommonSubjects = computed(() => {
  const query = quickSearch.value.trim()
  return commonSubjects.filter((item) => !query || item.name.includes(query))
})
const selectedCommonSubjects = computed(() => commonSubjects.filter((item) => selectedQuick.value.includes(item.name)))

function sectionCount(section: ManualSection): number {
  return counts[section]
}

function sectionComplete(section: ManualSection): boolean {
  return !sectionMeta.find((item) => item.key === section)?.required || sectionCount(section) > 0
}

function sectionStatus(section: ManualSection): string {
  const meta = sectionMeta.find((item) => item.key === section)
  if (meta?.required && sectionCount(section) === 0) return '待补充'
  return '已完成'
}

async function loadCounts() {
  loading.value = true
  loadError.value = null
  try {
    const [subjects, teachers, classes, rooms] = await Promise.all([
      listSubjects(props.semesterId),
      listTeachers(props.semesterId),
      listClassUnits(props.semesterId),
      listRooms(props.semesterId),
    ])
    subjectList.value = subjects
    counts.subjects = subjects.length
    counts.teachers = teachers.length
    counts.classes = classes.length
    counts.rooms = rooms.length
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取手工录入状态，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(loadCounts)

function selectSection(section: ManualSection) {
  activeSection.value = section
}

function toggleQuick(name: string, checked: boolean) {
  selectedQuick.value = checked
    ? [...selectedQuick.value, name]
    : selectedQuick.value.filter((item) => item !== name)
}

async function addSelectedSubjects() {
  if (!props.canEdit || quickBusy.value || !selectedCommonSubjects.value.length) return
  quickBusy.value = true
  quickError.value = null
  let created = 0
  const failures: string[] = []
  try {
    for (const subject of selectedCommonSubjects.value) {
      if (subjectNames.value.has(subject.name)) continue
      try {
        await createSubject(props.semesterId, {
          name: subject.name,
          domain: subject.domain,
          default_block_size: 1,
          is_major: subject.is_major,
          required_room_type: null,
        })
        created += 1
      } catch (error) {
        failures.push(`${subject.name}：${apiErrorMessage(error, '保存失败')}`)
      }
    }
    selectedQuick.value = []
    childRevision.value += 1
    await loadCounts()
    if (failures.length) {
      quickError.value = failures.join('；')
    } else if (created) {
      message.success(`已新增 ${created} 个科目`)
    }
    emit('changed')
  } finally {
    quickBusy.value = false
  }
}

async function handleChildChanged() {
  await loadCounts()
  emit('changed')
}
</script>

<template>
  <section class="manual-entry" data-testid="manual-entry">
    <n-alert v-if="!canEdit" type="info" data-testid="manual-readonly">
      {{ '当前角色只能查看基础数据；手工录入和常用科目确认仅对排课管理员开放。' }}
    </n-alert>
    <n-alert v-if="loadError" type="error" data-testid="manual-load-error" role="alert">
      {{ loadError }}
    </n-alert>
    <n-button v-if="loadError" size="small" data-testid="manual-retry" @click="loadCounts">
      <template #icon><RefreshCw :size="14" aria-hidden="true" /></template>
      {{ '重新读取' }}
    </n-button>

    <section class="manual-entry-guide" aria-labelledby="manual-entry-title">
      <div class="manual-entry-heading">
        <div>
          <p class="manual-entry-eyebrow">{{ '少量数据' }}</p>
          <h2 id="manual-entry-title">{{ '按引用关系逐项录入' }}</h2>
          <p>{{ '先建立科目，再补教师和班级；教室/场地可以最后再补。每一步都会显示当前已完成数量。' }}</p>
        </div>
        <n-tag type="info" size="small">{{ '不会创建教师登录账号' }}</n-tag>
      </div>
      <div class="manual-entry-sequence" aria-label="手工录入顺序">
        <template v-for="(item, index) in sectionMeta" :key="item.key">
          <button
            type="button"
            class="manual-entry-sequence-item"
            :class="{ active: activeSection === item.key }"
            :data-testid="`manual-section-${item.key}`"
            @click="selectSection(item.key)"
          >
            <span class="manual-entry-sequence-number">{{ index + 1 }}</span>
            <span>
              <strong>{{ item.label }}</strong>
              <small>{{ `${sectionCount(item.key)} 条 · ${sectionStatus(item.key)}` }}</small>
            </span>
            <CheckCircle2 v-if="sectionComplete(item.key)" :size="16" aria-label="已完成" />
            <CircleAlert v-else :size="16" aria-label="待补充" />
          </button>
          <ArrowRight v-if="index < sectionMeta.length - 1" class="manual-entry-sequence-arrow" :size="15" aria-hidden="true" />
        </template>
      </div>
    </section>

    <section v-if="loading" class="manual-entry-state" data-testid="manual-loading" role="status">
      <n-spin size="small" />
      <span>{{ '正在读取现有基础数据' }}</span>
    </section>

    <n-tabs v-else v-model:value="activeSection" type="line" animated :tabs-padding="0" class="manual-entry-tabs">
      <n-tab-pane v-for="item in sectionMeta" :key="item.key" :name="item.key">
        <template #tab>
          <span class="manual-entry-tab-label">
            {{ item.label }}
            <n-tag size="small" :type="sectionComplete(item.key) ? 'success' : 'warning'">
              {{ sectionCount(item.key) }}
            </n-tag>
          </span>
        </template>

        <div v-if="item.key === 'subjects'" class="manual-entry-pane">
          <section class="manual-common-subjects" data-testid="manual-common-subjects">
            <div class="manual-pane-heading">
              <div>
                <h3>{{ '常用科目' }}</h3>
                <p>{{ '按名称逐项选择，默认全部未选择；确认前不会写入，也不会按学段成套添加。' }}</p>
              </div>
              <n-input
                v-model:value="quickSearch"
                clearable
                size="small"
                :placeholder="'搜索常用科目'"
                aria-label="搜索常用科目"
              />
            </div>
            <div class="manual-common-subject-list">
              <n-checkbox
                v-for="subject in filteredCommonSubjects"
                :key="subject.name"
                :checked="selectedQuick.includes(subject.name)"
                :disabled="subjectNames.has(subject.name) || !canEdit"
                :data-testid="`manual-common-${subject.name}`"
                @update:checked="toggleQuick(subject.name, $event)"
              >
                {{ subject.name }}
                <span v-if="subjectNames.has(subject.name)" class="manual-common-existing">{{ '已存在' }}</span>
              </n-checkbox>
            </div>
            <n-alert v-if="selectedCommonSubjects.length" type="info" :show-icon="true" data-testid="manual-common-preview">
              {{ `确认后将新增 ${selectedCommonSubjects.length} 个科目：${selectedCommonSubjects.map((item) => item.name).join('、')}` }}
            </n-alert>
            <n-alert v-if="quickError" type="error" data-testid="manual-common-error" role="alert">
              {{ quickError }}
            </n-alert>
            <n-button
              type="primary"
              data-testid="manual-common-confirm"
              :loading="quickBusy"
              :disabled="!canEdit || quickBusy || !selectedCommonSubjects.length"
              @click="addSelectedSubjects"
            >
              <template #icon><Plus :size="15" aria-hidden="true" /></template>
              {{ `确认新增所选科目${selectedCommonSubjects.length ? `（${selectedCommonSubjects.length}）` : ''}` }}
            </n-button>
          </section>
          <SubjectsTab :key="`subjects-${childRevision}`" :semester-id="semesterId" :can-edit="canEdit" @changed="handleChildChanged" />
        </div>

        <div v-else-if="item.key === 'teachers'" class="manual-entry-pane">
          <n-alert v-if="!counts.subjects" type="warning" data-testid="manual-teachers-dependency">
            {{ '建议先添加至少一个科目，录入教师时可以直接选择任教科目。' }}
          </n-alert>
          <n-button v-if="!counts.subjects" size="small" data-testid="manual-go-subjects" @click="selectSection('subjects')">{{ '去添加科目' }}</n-button>
          <TeachersTab :key="`teachers-${childRevision}`" :semester-id="semesterId" :can-edit="canEdit" :can-manage-accounts="false" @changed="handleChildChanged" />
        </div>

        <div v-else-if="item.key === 'classes'" class="manual-entry-pane">
          <n-alert v-if="!counts.teachers" type="warning" data-testid="manual-classes-dependency">
            {{ '班主任可以稍后补充；如果现在已有教师，录入班级时可以直接选择。' }}
          </n-alert>
          <n-button v-if="!counts.teachers" size="small" data-testid="manual-go-teachers" @click="selectSection('teachers')">{{ '去添加教师' }}</n-button>
          <ClassesTab :key="`classes-${childRevision}`" :semester-id="semesterId" :can-edit="canEdit" @changed="handleChildChanged" />
        </div>

        <div v-else class="manual-entry-pane">
          <n-alert type="info" data-testid="manual-rooms-optional">
            {{ '教室/场地是可选数据；没有时仍可先完成基础设置，之后在基础数据页补录。' }}
          </n-alert>
          <RoomsTab :key="`rooms-${childRevision}`" :semester-id="semesterId" :can-edit="canEdit" @changed="handleChildChanged" />
        </div>
      </n-tab-pane>
    </n-tabs>
  </section>
</template>

<style scoped>
.manual-entry { display: grid; min-width: 0; gap: 18px; }
.manual-entry-guide { display: grid; gap: 18px; padding: 18px; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); background: var(--app-surface-muted); }
.manual-entry-heading,
.manual-pane-heading,
.manual-entry-sequence,
.manual-entry-tab-label { display: flex; min-width: 0; align-items: center; flex-wrap: wrap; gap: 10px; }
.manual-entry-heading { justify-content: space-between; align-items: flex-start; }
.manual-entry-eyebrow { margin: 0 0 4px; color: var(--app-primary-strong); font-size: 11px; font-weight: 700; }
.manual-entry-heading h2 { margin: 0; font-size: 18px; }
.manual-entry-heading p:last-child { margin: 6px 0 0; color: var(--app-text-muted); font-size: 13px; line-height: 1.6; }
.manual-entry-sequence { align-items: stretch; }
.manual-entry-sequence-item { display: flex; min-width: 0; flex: 1 1 170px; align-items: center; gap: 9px; padding: 10px; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); background: var(--app-surface); color: var(--app-text-muted); text-align: left; cursor: pointer; }
.manual-entry-sequence-item:hover,
.manual-entry-sequence-item.active { border-color: var(--app-primary); color: var(--app-text); }
.manual-entry-sequence-number { display: grid; width: 24px; height: 24px; flex: 0 0 auto; place-items: center; border-radius: 50%; background: var(--app-primary-soft); color: var(--app-primary-strong); font-size: 12px; font-weight: 700; }
.manual-entry-sequence-item > span:nth-child(2) { display: grid; min-width: 0; gap: 3px; }
.manual-entry-sequence-item small { color: var(--app-text-faint); font-size: 11px; }
.manual-entry-sequence-item svg { margin-left: auto; flex: 0 0 auto; color: var(--app-success); }
.manual-entry-sequence-item:not(.active) svg { color: var(--app-text-faint); }
.manual-entry-sequence-arrow { align-self: center; color: var(--app-text-faint); }
.manual-entry-tabs { min-width: 0; }
.manual-entry-tab-label { gap: 6px; }
.manual-entry-pane { display: grid; min-width: 0; gap: 16px; padding-top: 18px; }
.manual-common-subjects { display: grid; gap: 14px; padding: 16px; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); background: var(--app-surface-muted); }
.manual-pane-heading { justify-content: space-between; align-items: flex-start; }
.manual-pane-heading h3 { margin: 0; font-size: 15px; }
.manual-pane-heading p { margin: 5px 0 0; color: var(--app-text-muted); font-size: 12px; line-height: 1.55; }
.manual-pane-heading :deep(.n-input) { width: min(220px, 100%); }
.manual-common-subject-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px 14px; }
.manual-common-existing { color: var(--app-text-faint); font-size: 11px; }
.manual-entry-state { display: grid; min-height: 180px; place-items: center; align-content: center; gap: 10px; color: var(--app-text-muted); }
@media (max-width: 700px) {
  .manual-entry-sequence-arrow { display: none; }
  .manual-entry-sequence-item { flex-basis: calc(50% - 5px); }
}
@media (max-width: 460px) {
  .manual-entry-guide { padding: 14px; }
  .manual-entry-sequence-item { flex-basis: 100%; }
}
</style>
