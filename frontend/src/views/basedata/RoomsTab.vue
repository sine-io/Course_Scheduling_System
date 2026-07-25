<script setup lang="ts">
import {
  NButton, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSpace, NTag, NText, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import type { ApiError } from '@/api/client'
import {
  ROOM_TYPE_LABELS, createRoom, deleteRoom, listRooms, listSubjects, updateRoom,
} from '@/api/basedata'
import type { Room, RoomType, Subject } from '@/api/basedata'
import { useProfileText } from '@/composables/useProfileText'

const props = defineProps<{ semesterId: number }>()
const message = useMessage()
const { isMainland, tr } = useProfileText()

const items = ref<Room[]>([])
const subjects = ref<Subject[]>([])
const search = ref('')

const mainlandRoomTypeLabels: Record<RoomType, string> = {
  normal: '普通教室', special: '专用教室', workshop: '实训场地', outdoor: '户外',
}
function roomTypeLabel(type: RoomType) {
  return isMainland.value ? mainlandRoomTypeLabels[type] : ROOM_TYPE_LABELS[type]
}
const roomTypeOptions = computed(() => (Object.keys(ROOM_TYPE_LABELS) as RoomType[]).map((type) => ({
  label: roomTypeLabel(type), value: type,
})))
const subjectOptions = computed(() => subjects.value.map((s) => ({ label: s.name, value: s.id })))

async function reload() {
  items.value = await listRooms(props.semesterId, search.value || undefined)
}
onMounted(async () => {
  subjects.value = await listSubjects(props.semesterId)
  await reload()
})

const show = ref(false)
const editingId = ref<number | null>(null)
const form = ref<{ name: string; room_type: RoomType; capacity: number | null; subject_ids: number[] }>({
  name: '', room_type: 'normal', capacity: null, subject_ids: [],
})

function openCreate() {
  editingId.value = null
  form.value = { name: '', room_type: 'normal', capacity: null, subject_ids: [] }
  show.value = true
}
function openEdit(r: Room) {
  editingId.value = r.id
  form.value = {
    name: r.name, room_type: r.room_type, capacity: r.capacity,
    subject_ids: r.subjects.map((s) => s.id),
  }
  show.value = true
}

async function save() {
  if (!form.value.name) {
    message.warning(tr('請輸入場地名稱', '请输入场地名称'))
    return
  }
  try {
    if (editingId.value) await updateRoom(editingId.value, form.value)
    else await createRoom(props.semesterId, form.value)
    show.value = false
    message.success(tr('已儲存', '已保存'))
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail || tr('儲存失敗', '保存失败'))
  }
}

async function remove(r: Room) {
  try {
    await deleteRoom(r.id)
    message.success(tr('已刪除', '已删除'))
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail || tr('刪除失敗', '删除失败'))
  }
}
</script>

<template>
  <n-space vertical>
    <n-space>
      <n-input v-model:value="search" :placeholder="tr('搜尋場地名稱', '搜索场地名称')" clearable style="width: 200px" @input="reload" />
      <n-button type="primary" @click="openCreate">{{ tr('新增場地', '新增场地') }}</n-button>
    </n-space>

    <table class="data-table">
      <thead>
        <tr><th>{{ tr('名稱', '名称') }}</th><th>{{ tr('類型', '类型') }}</th><th>{{ tr('容量', '容量') }}</th><th>{{ tr('適用科目', '适用科目') }}</th><th>{{ tr('操作', '操作') }}</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in items" :key="r.id">
          <td>{{ r.name }}</td>
          <td>{{ roomTypeLabel(r.room_type) }}</td>
          <td>{{ r.capacity ?? '—' }}</td>
          <td>
            <n-space size="small">
              <n-tag v-for="s in r.subjects" :key="s.id" size="small">{{ s.name }}</n-tag>
              <n-text v-if="r.subjects.length === 0" depth="3">—</n-text>
            </n-space>
          </td>
          <td>
            <n-space>
              <n-button size="tiny" @click="openEdit(r)">{{ tr('編輯', '编辑') }}</n-button>
              <n-popconfirm @positive-click="remove(r)">
                <template #trigger><n-button size="tiny" type="error" ghost>{{ tr('刪除', '删除') }}</n-button></template>
                {{ tr('確定刪除此場地?', '确定删除此场地吗？') }}
              </n-popconfirm>
            </n-space>
          </td>
        </tr>
        <tr v-if="items.length === 0"><td colspan="5"><n-text depth="3">{{ tr('尚無場地', '暂无场地') }}</n-text></td></tr>
      </tbody>
    </table>

    <n-modal v-model:show="show" preset="card" :title="editingId ? tr('編輯場地', '编辑场地') : tr('新增場地', '新增场地')" style="max-width: 440px">
      <n-space vertical>
        <n-text>{{ tr('名稱', '名称') }}</n-text>
        <n-input v-model:value="form.name" :placeholder="tr('如:機械實習工場', '如：物理实验室')" />
        <n-text>{{ tr('類型', '类型') }}</n-text>
        <n-select v-model:value="form.room_type" :options="roomTypeOptions" />
        <n-text>{{ tr('容量(選填)', '容量（可选）') }}</n-text>
        <n-input-number v-model:value="form.capacity" :min="0" />
        <n-text>{{ tr('適用科目(選填)', '适用科目（可选）') }}</n-text>
        <n-select v-model:value="form.subject_ids" multiple :options="subjectOptions" :placeholder="tr('可多選', '可多选')" />
        <n-button type="primary" @click="save">{{ tr('儲存', '保存') }}</n-button>
      </n-space>
    </n-modal>
  </n-space>
</template>

<style scoped>
.data-table { border-collapse: collapse; width: 100%; }
.data-table th, .data-table td { border: 1px solid var(--n-border-color, #e0e0e0); padding: 8px 10px; text-align: left; }
.data-table th { background: rgba(128,128,128,0.08); font-weight: 600; }
</style>
