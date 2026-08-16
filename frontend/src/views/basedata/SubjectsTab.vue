<script setup lang="ts">
import { AlertTriangle, Pencil, Plus, RefreshCw, Save, Trash2, X } from '@lucide/vue'
import {
  NAlert, NButton, NCheckbox, NEmpty, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSpin,
  NTag, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import {
  ROOM_TYPE_LABELS, createSubject, deleteSubject, listSubjects, updateSubject,
} from '@/api/basedata'
import type { RoomType, Subject } from '@/api/basedata'
import { highRiskConfirmation } from '@/api/highRisk'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import './basedata-workspace.css'

const props = withDefaults(
  defineProps<{ semesterId: number; canEdit?: boolean; canDelete?: boolean }>(),
  { canEdit: true, canDelete: false },
)
const message = useMessage()

const items = ref<Subject[]>([])
const search = ref('')
const loading = ref(true)
const loadError = ref<string | null>(null)
const saving = ref(false)
const deletingId = ref<number | null>(null)

const roomTypeLabels: Record<RoomType, string> = {
  normal: '普通教室', special: '专用教室', workshop: '实训场地', outdoor: '户外',
}
function roomTypeLabel(type: RoomType) {
  return roomTypeLabels[type]
}
const roomTypeOptions = computed(() => (Object.keys(ROOM_TYPE_LABELS) as RoomType[]).map((type) => ({
  label: roomTypeLabel(type), value: type,
})))

async function reload() {
  loading.value = true
  loadError.value = null
  try {
    items.value = await listSubjects(props.semesterId, search.value || undefined)
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取科目，请重试。')
  } finally {
    loading.value = false
  }
}
onMounted(reload)

const show = ref(false)
const editingId = ref<number | null>(null)
const form = ref<{
  name: string
  domain: string
  required_room_type: RoomType | null
  default_block_size: number
  is_major: boolean
}>({ name: '', domain: '', required_room_type: null, default_block_size: 1, is_major: false })

function openCreate() {
  if (!props.canEdit) return
  editingId.value = null
  form.value = { name: '', domain: '', required_room_type: null, default_block_size: 1, is_major: false }
  show.value = true
}
function openEdit(subject: Subject) {
  if (!props.canEdit) return
  editingId.value = subject.id
  form.value = {
    name: subject.name,
    domain: subject.domain ?? '',
    required_room_type: subject.required_room_type,
    default_block_size: subject.default_block_size,
    is_major: subject.is_major,
  }
  show.value = true
}
function closeModal() {
  if (!saving.value) show.value = false
}

async function save() {
  if (!props.canEdit || saving.value) return
  if (!form.value.name) {
    message.warning('请输入科目名称')
    return
  }
  saving.value = true
  const body = {
    name: form.value.name,
    domain: form.value.domain || null,
    required_room_type: form.value.required_room_type,
    default_block_size: form.value.default_block_size,
    is_major: form.value.is_major,
  }
  try {
    if (editingId.value) await updateSubject(editingId.value, body)
    else await createSubject(props.semesterId, body)
    show.value = false
    message.success('已保存')
    await reload()
  } catch (error) {
    message.error(apiErrorMessage(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function remove(subject: Subject) {
  if (!props.canDelete || deletingId.value !== null) return
  deletingId.value = subject.id
  try {
    await deleteSubject(subject.id, highRiskConfirmation(`subject:${subject.id}`))
    message.success('已删除')
    await reload()
  } catch (error) {
    message.error(apiErrorMessage(error, '删除失败'))
  } finally {
    deletingId.value = null
  }
}
</script>

<template>
  <div class="basedata-tab-content" :aria-busy="loading">
    <div class="basedata-toolbar">
      <div class="basedata-toolbar-main">
        <n-input
          v-model:value="search"
          class="basedata-search"
          :placeholder="'搜索科目名称'"
          clearable
          aria-label="搜索科目名称"
          @input="reload"
        />
      </div>
      <div v-if="canEdit" class="basedata-toolbar-actions">
        <n-button type="primary" data-testid="subject-add" @click="openCreate">
          <template #icon><Plus :size="16" aria-hidden="true" /></template>
          {{ '新增科目' }}
        </n-button>
      </div>
    </div>

    <n-alert v-if="!canEdit" class="basedata-readonly" type="info" data-testid="subjects-readonly">
      {{ '仅可查看科目，当前角色没有新增、编辑或删除权限。' }}
    </n-alert>

    <section v-if="loading && !items.length" class="basedata-state" data-testid="subjects-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取科目' }}</strong>
      <span>{{ '科目列表加载完成后会显示在这里。' }}</span>
    </section>
    <section v-else-if="loadError" class="basedata-state basedata-state-error" data-testid="subjects-error" role="alert">
      <AlertTriangle :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '当前列表未更新。' }}</span>
      <n-button type="primary" data-testid="subjects-retry" @click="reload">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>
    <section v-else-if="!items.length" class="basedata-state" data-testid="subjects-empty" role="status">
      <n-empty :description="'暂无科目'" />
    </section>
    <div v-else class="basedata-table-scroll" data-testid="subjects-table-scroll" tabindex="0" aria-label="科目列表，可横向滚动">
      <table class="basedata-data-table" data-testid="subjects-table">
        <thead>
          <tr>
            <th>{{ '名称' }}</th>
            <th>{{ '领域/类别' }}</th>
            <th>{{ '所需教室/场地' }}</th>
            <th>{{ '默认连堂' }}</th>
            <th>{{ '主科' }}</th>
            <th v-if="canEdit">{{ '操作' }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="subject in items" :key="subject.id">
            <td>{{ subject.name }}</td>
            <td>{{ subject.domain || '—' }}</td>
            <td>{{ subject.required_room_type ? roomTypeLabel(subject.required_room_type) : '不限' }}</td>
            <td>{{ subject.default_block_size > 1 ? `${subject.default_block_size} 连堂` : '普通' }}</td>
            <td>
              <n-tag v-if="subject.is_major" size="small" type="info" :data-testid="`sub-major-${subject.name}`">
                {{ '主科' }}
              </n-tag>
              <span v-else>—</span>
            </td>
            <td v-if="canEdit">
              <div class="basedata-command-group">
                <n-button size="small" :data-testid="`subject-edit-${subject.id}`" @click="openEdit(subject)">
                  <template #icon><Pencil :size="14" aria-hidden="true" /></template>
                  {{ '编辑' }}
                </n-button>
                <n-popconfirm v-if="canDelete" :disabled="deletingId !== null" @positive-click="remove(subject)">
                  <template #trigger>
                    <n-button
                      size="small"
                      type="error"
                      ghost
                      :data-testid="`subject-delete-${subject.id}`"
                      :loading="deletingId === subject.id"
                      :disabled="deletingId !== null"
                    >
                      <template #icon><Trash2 :size="14" aria-hidden="true" /></template>
                      {{ '删除' }}
                    </n-button>
                  </template>
                  {{ `将永久删除科目“${subject.name}”及其相关排课数据。确定继续吗？` }}
                </n-popconfirm>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <n-modal v-if="canEdit" v-model:show="show" preset="card" class="basedata-modal" :title="editingId ? '编辑科目' : '新增科目'">
      <div class="basedata-form">
        <div class="basedata-field">
          <label for="subject-name">{{ '名称' }}</label>
          <n-input
            id="subject-name"
            v-model:value="form.name"
            data-testid="sub-name"
            :placeholder="'如：数学'"
            :input-props="{ 'aria-label': '名称' }"
          />
        </div>
        <div class="basedata-field">
          <label for="subject-domain">{{ '领域/类别（可选）' }}</label>
          <n-input
            id="subject-domain"
            v-model:value="form.domain"
            :placeholder="'如：数学领域'"
            :input-props="{ 'aria-label': '领域/类别' }"
          />
        </div>
        <div class="basedata-field">
          <span class="basedata-field-label">{{ '所需教室/场地类型（可选）' }}</span>
          <n-select
            v-model:value="form.required_room_type"
            v-accessible-select="'所需教室/场地类型'"
            :options="roomTypeOptions"
            clearable
            :placeholder="'不限'"
          />
        </div>
        <div class="basedata-field">
          <span class="basedata-field-label">{{ '默认连堂长度' }}</span>
          <n-input-number
            v-model:value="form.default_block_size"
            :min="1"
            :max="8"
            :input-props="{ 'aria-label': '默认连堂长度' }"
          />
        </div>
        <n-checkbox v-model:checked="form.is_major" data-testid="sub-is-major">
          {{ '主科（自动排课会尽量安排在上午）' }}
        </n-checkbox>
        <div class="basedata-modal-actions">
          <n-button quaternary :disabled="!canEdit || saving" @click="closeModal">
            <template #icon><X :size="15" aria-hidden="true" /></template>
            {{ '取消' }}
          </n-button>
          <n-button type="primary" data-testid="sub-save" :loading="saving" :disabled="!canEdit || saving" @click="save">
            <template #icon><Save :size="15" aria-hidden="true" /></template>
            {{ '保存' }}
          </n-button>
        </div>
      </div>
    </n-modal>
  </div>
</template>
