<script setup lang="ts">
import { AlertTriangle, Pencil, Plus, RefreshCw, Save, Trash2, X } from '@lucide/vue'
import {
  NAlert, NButton, NEmpty, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSpin, NTag,
  useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import {
  ROOM_TYPE_LABELS, createRoom, deleteRoom, listRooms, listSubjects, updateRoom,
} from '@/api/basedata'
import type { Room, RoomType, Subject } from '@/api/basedata'
import { highRiskConfirmation } from '@/api/highRisk'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import './basedata-workspace.css'

const props = withDefaults(
  defineProps<{ semesterId: number; canEdit?: boolean; canDelete?: boolean }>(),
  { canEdit: true, canDelete: false },
)
const emit = defineEmits<{ changed: [] }>()
const message = useMessage()

const items = ref<Room[]>([])
const subjects = ref<Subject[]>([])
const search = ref('')
const loading = ref(true)
const loadError = ref<string | null>(null)
const saving = ref(false)
const deletingId = ref<number | null>(null)

const roomTypeLabels: Record<RoomType, string> = {
  normal: '普通教室',
  special: '专用教室',
  workshop: '实训场地',
  outdoor: '户外',
}
function roomTypeLabel(type: RoomType) {
  return roomTypeLabels[type]
}
const roomTypeOptions = computed(() => (Object.keys(ROOM_TYPE_LABELS) as RoomType[]).map((type) => ({
  label: roomTypeLabel(type),
  value: type,
})))
const subjectOptions = computed(() => subjects.value.map((subject) => ({ label: subject.name, value: subject.id })))

async function reload() {
  loading.value = true
  loadError.value = null
  try {
    items.value = await listRooms(props.semesterId, search.value || undefined)
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取教室/场地，请重试。')
  } finally {
    loading.value = false
  }
}

async function loadInitialData() {
  loading.value = true
  loadError.value = null
  try {
    const [roomItems, subjectItems] = await Promise.all([
      listRooms(props.semesterId, search.value || undefined),
      listSubjects(props.semesterId),
    ])
    items.value = roomItems
    subjects.value = subjectItems
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取教室/场地，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(loadInitialData)

const show = ref(false)
const editingId = ref<number | null>(null)
const form = ref<{ name: string; room_type: RoomType; capacity: number | null; subject_ids: number[] }>({
  name: '',
  room_type: 'normal',
  capacity: null,
  subject_ids: [],
})

function openCreate() {
  if (!props.canEdit) return
  editingId.value = null
  form.value = { name: '', room_type: 'normal', capacity: null, subject_ids: [] }
  show.value = true
}
function openEdit(room: Room) {
  if (!props.canEdit) return
  editingId.value = room.id
  form.value = {
    name: room.name,
    room_type: room.room_type,
    capacity: room.capacity,
    subject_ids: room.subjects.map((subject) => subject.id),
  }
  show.value = true
}
function closeModal() {
  if (!saving.value) show.value = false
}

async function save() {
  if (!props.canEdit || saving.value) return
  if (!form.value.name) {
    message.warning('请输入教室/场地名称')
    return
  }
  saving.value = true
  try {
    if (editingId.value) await updateRoom(editingId.value, form.value)
    else await createRoom(props.semesterId, form.value)
    show.value = false
    message.success('已保存')
    await reload()
    emit('changed')
  } catch (error) {
    message.error(apiErrorMessage(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function remove(room: Room) {
  if (!props.canDelete || deletingId.value !== null) return
  deletingId.value = room.id
  try {
    await deleteRoom(room.id, highRiskConfirmation(`room:${room.id}`))
    message.success('已删除')
    await reload()
    emit('changed')
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
          :placeholder="'搜索教室/场地名称'"
          clearable
          aria-label="搜索教室/场地名称"
          @input="reload"
        />
      </div>
      <div v-if="canEdit" class="basedata-toolbar-actions">
        <n-button type="primary" data-testid="room-add" @click="openCreate">
          <template #icon><Plus :size="16" aria-hidden="true" /></template>
          {{ '新增教室/场地' }}
        </n-button>
      </div>
    </div>

    <n-alert v-if="!canEdit" class="basedata-readonly" type="info" data-testid="rooms-readonly">
      {{ '仅可查看教室/场地，当前角色没有新增、编辑或删除权限。' }}
    </n-alert>

    <section v-if="loading && !items.length" class="basedata-state" data-testid="rooms-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取教室/场地' }}</strong>
      <span>{{ '教室/场地列表加载完成后会显示在这里。' }}</span>
    </section>
    <section v-else-if="loadError" class="basedata-state basedata-state-error" data-testid="rooms-error" role="alert">
      <AlertTriangle :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '当前列表未更新。' }}</span>
      <n-button type="primary" data-testid="rooms-retry" @click="loadInitialData">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>
    <section v-else-if="!items.length" class="basedata-state" data-testid="rooms-empty" role="status">
      <n-empty :description="'暂无教室/场地'" />
    </section>
    <div v-else class="basedata-table-scroll" data-testid="rooms-table-scroll" tabindex="0" aria-label="教室/场地列表，可横向滚动">
      <table class="basedata-data-table basedata-data-table--rooms" data-testid="rooms-table">
        <thead>
          <tr>
            <th>{{ '名称' }}</th>
            <th>{{ '类型' }}</th>
            <th>{{ '容量' }}</th>
            <th>{{ '适用科目' }}</th>
            <th v-if="canEdit">{{ '操作' }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="room in items" :key="room.id">
            <td>{{ room.name }}</td>
            <td>{{ roomTypeLabel(room.room_type) }}</td>
            <td>{{ room.capacity ?? '—' }}</td>
            <td>
              <div class="basedata-command-group">
                <n-tag v-for="subject in room.subjects" :key="subject.id" size="small">{{ subject.name }}</n-tag>
                <span v-if="room.subjects.length === 0">—</span>
              </div>
            </td>
            <td v-if="canEdit">
              <div class="basedata-command-group">
                <n-button size="small" :data-testid="`room-edit-${room.id}`" @click="openEdit(room)">
                  <template #icon><Pencil :size="14" aria-hidden="true" /></template>
                  {{ '编辑' }}
                </n-button>
                <n-popconfirm v-if="canDelete" :disabled="deletingId !== null" @positive-click="remove(room)">
                  <template #trigger>
                    <n-button
                      size="small"
                      type="error"
                      ghost
                      :data-testid="`room-delete-${room.id}`"
                      :loading="deletingId === room.id"
                      :disabled="deletingId !== null"
                    >
                      <template #icon><Trash2 :size="14" aria-hidden="true" /></template>
                      {{ '删除' }}
                    </n-button>
                  </template>
                  {{ `将永久删除教室/场地“${room.name}”并解除相关排课指定。确定继续吗？` }}
                </n-popconfirm>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <n-modal v-if="canEdit" v-model:show="show" preset="card" class="basedata-modal" :title="editingId ? '编辑教室/场地' : '新增教室/场地'">
      <div class="basedata-form">
        <div class="basedata-field">
          <label for="room-name">{{ '名称' }}</label>
          <n-input
            id="room-name"
            v-model:value="form.name"
            data-testid="room-name"
            :placeholder="'如：物理实验室'"
            :input-props="{ 'aria-label': '名称' }"
          />
        </div>
        <div class="basedata-field">
          <span class="basedata-field-label">{{ '类型' }}</span>
          <n-select
            v-model:value="form.room_type"
            v-accessible-select="'教室/场地类型'"
            :options="roomTypeOptions"
          />
        </div>
        <div class="basedata-field">
          <span class="basedata-field-label">{{ '容量（可选）' }}</span>
          <n-input-number
            v-model:value="form.capacity"
            :min="0"
            :input-props="{ 'aria-label': '容量' }"
          />
        </div>
        <div class="basedata-field">
          <span class="basedata-field-label">{{ '适用科目（可选）' }}</span>
          <n-select
            v-model:value="form.subject_ids"
            v-accessible-select="'适用科目'"
            multiple
            :options="subjectOptions"
            :placeholder="'可多选'"
          />
        </div>
        <div class="basedata-modal-actions">
          <n-button quaternary :disabled="!canEdit || saving" @click="closeModal">
            <template #icon><X :size="15" aria-hidden="true" /></template>
            {{ '取消' }}
          </n-button>
          <n-button type="primary" data-testid="room-save" :loading="saving" :disabled="!canEdit || saving" @click="save">
            <template #icon><Save :size="15" aria-hidden="true" /></template>
            {{ '保存' }}
          </n-button>
        </div>
      </div>
    </n-modal>
  </div>
</template>
