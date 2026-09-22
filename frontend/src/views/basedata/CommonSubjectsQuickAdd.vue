<script setup lang="ts">
import { Plus } from '@lucide/vue'
import { NAlert, NButton, NCheckbox, NInput, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import { createSubject } from '@/api/basedata'
import type { Subject } from '@/api/basedata'
import {
  COMMON_SUBJECTS,
  canonicalCommonSubjectName,
} from './commonSubjects'

const props = withDefaults(
  defineProps<{
    semesterId: number
    subjects?: Subject[]
    canEdit?: boolean
  }>(),
  {
    subjects: () => [],
    canEdit: true,
  },
)
const emit = defineEmits<{ changed: [] }>()
const message = useMessage()

const selectedQuick = ref<string[]>([])
const quickSearch = ref('')
const quickBusy = ref(false)
const quickError = ref<string | null>(null)

const subjectNames = computed(() => new Set(
  props.subjects.map((item) => canonicalCommonSubjectName(item.name)),
))
function isCommonSubjectExisting(name: string): boolean {
  return subjectNames.value.has(canonicalCommonSubjectName(name))
}

const filteredCommonSubjects = computed(() => {
  const query = quickSearch.value.trim()
  return COMMON_SUBJECTS.filter((item) => !query || item.name.includes(query))
})
const selectedCommonSubjects = computed(() => COMMON_SUBJECTS.filter(
  (item) => selectedQuick.value.includes(item.name),
))

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
      const canonicalName = canonicalCommonSubjectName(subject.name)
      if (isCommonSubjectExisting(subject.name)) continue
      try {
        await createSubject(props.semesterId, {
          name: canonicalName,
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
</script>

<template>
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
        :disabled="isCommonSubjectExisting(subject.name) || !canEdit"
        :data-testid="`manual-common-${subject.name}`"
        @update:checked="toggleQuick(subject.name, $event)"
      >
        {{ subject.name }}
        <span v-if="isCommonSubjectExisting(subject.name)" class="manual-common-existing">{{ '已存在' }}</span>
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
</template>

<style scoped>
.manual-common-subjects { display: grid; gap: 14px; padding: 16px; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); background: var(--app-surface-muted); }
.manual-pane-heading { display: flex; min-width: 0; align-items: center; flex-wrap: wrap; justify-content: space-between; gap: 10px; }
.manual-pane-heading h3 { margin: 0; font-size: 15px; }
.manual-pane-heading p { margin: 5px 0 0; color: var(--app-text-muted); font-size: 12px; line-height: 1.55; }
.manual-pane-heading :deep(.n-input) { width: min(220px, 100%); }
.manual-common-subject-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px 14px; }
.manual-common-existing { color: var(--app-text-faint); font-size: 11px; }
</style>
