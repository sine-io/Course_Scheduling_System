<script setup lang="ts">
import {
  NButton, NCheckbox, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSpace, NTag, NText,
  useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import type { ApiError } from '@/api/client'
import {
  ROOM_TYPE_LABELS, createSubject, deleteSubject, listSubjects, updateSubject,
} from '@/api/basedata'
import type { RoomType, Subject } from '@/api/basedata'
import { useProfileText } from '@/composables/useProfileText'

const props = defineProps<{ semesterId: number }>()
const message = useMessage()
const { isMainland, tr } = useProfileText()

const items = ref<Subject[]>([])
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

async function reload() {
  items.value = await listSubjects(props.semesterId, search.value || undefined)
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
  editingId.value = null
  form.value = { name: '', domain: '', required_room_type: null, default_block_size: 1, is_major: false }
  show.value = true
}
function openEdit(s: Subject) {
  editingId.value = s.id
  form.value = {
    name: s.name, domain: s.domain ?? '',
    required_room_type: s.required_room_type, default_block_size: s.default_block_size,
    is_major: s.is_major,
  }
  show.value = true
}

async function save() {
  if (!form.value.name) {
    message.warning(tr('請輸入科目名稱', '请输入科目名称'))
    return
  }
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
    message.success(tr('已儲存', '已保存'))
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail || tr('儲存失敗', '保存失败'))
  }
}

async function remove(s: Subject) {
  try {
    await deleteSubject(s.id)
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
      <n-input v-model:value="search" :placeholder="tr('搜尋科目名稱', '搜索科目名称')" clearable style="width: 200px" @input="reload" />
      <n-button type="primary" @click="openCreate">{{ tr('新增科目', '新增科目') }}</n-button>
    </n-space>

    <table class="data-table">
      <thead>
        <tr><th>{{ tr('名稱', '名称') }}</th><th>{{ tr('領域/群別', '领域/类别') }}</th><th>{{ tr('需要場地', '所需场地') }}</th><th>{{ tr('預設連堂', '默认连堂') }}</th><th>{{ tr('主科', '主科') }}</th><th>{{ tr('操作', '操作') }}</th></tr>
      </thead>
      <tbody>
        <tr v-for="s in items" :key="s.id">
          <td>{{ s.name }}</td>
          <td>{{ s.domain || '—' }}</td>
          <td>{{ s.required_room_type ? roomTypeLabel(s.required_room_type) : tr('不限', '不限') }}</td>
          <td>{{ s.default_block_size > 1 ? tr(`${s.default_block_size} 連堂`, `${s.default_block_size} 连堂`) : tr('一般', '普通') }}</td>
          <td>
            <n-tag v-if="s.is_major" size="small" type="info" :data-testid="`sub-major-${s.name}`">{{ tr('主科', '主科') }}</n-tag>
            <span v-else>—</span>
          </td>
          <td>
            <n-space>
              <n-button size="tiny" @click="openEdit(s)">{{ tr('編輯', '编辑') }}</n-button>
              <n-popconfirm @positive-click="remove(s)">
                <template #trigger><n-button size="tiny" type="error" ghost>{{ tr('刪除', '删除') }}</n-button></template>
                {{ tr('確定刪除此科目?', '确定删除此科目吗？') }}
              </n-popconfirm>
            </n-space>
          </td>
        </tr>
        <tr v-if="items.length === 0"><td colspan="6"><n-text depth="3">{{ tr('尚無科目', '暂无科目') }}</n-text></td></tr>
      </tbody>
    </table>

    <n-modal v-model:show="show" preset="card" :title="editingId ? tr('編輯科目', '编辑科目') : tr('新增科目', '新增科目')" style="max-width: 420px">
      <n-space vertical>
        <n-text>{{ tr('名稱', '名称') }}</n-text>
        <n-input v-model:value="form.name" data-testid="sub-name" :placeholder="tr('如:數學', '如：数学')" />
        <n-text>{{ tr('領域/群別(選填)', '领域/类别（可选）') }}</n-text>
        <n-input v-model:value="form.domain" :placeholder="tr('如:數學領域', '如：数学领域')" />
        <n-text>{{ tr('需要場地類型(選填)', '所需场地类型（可选）') }}</n-text>
        <n-select v-model:value="form.required_room_type" :options="roomTypeOptions" clearable :placeholder="tr('不限', '不限')" />
        <n-text>{{ tr('預設連堂長度', '默认连堂长度') }}</n-text>
        <n-input-number v-model:value="form.default_block_size" :min="1" :max="8" />
        <n-checkbox v-model:checked="form.is_major" data-testid="sub-is-major">
          {{ tr('主科(自動排課會盡量排在上午)', '主科（自动排课会尽量安排在上午）') }}
        </n-checkbox>
        <n-button type="primary" data-testid="sub-save" @click="save">{{ tr('儲存', '保存') }}</n-button>
      </n-space>
    </n-modal>
  </n-space>
</template>

<style scoped>
.data-table { border-collapse: collapse; width: 100%; }
.data-table th, .data-table td { border: 1px solid var(--n-border-color, #e0e0e0); padding: 8px 10px; text-align: left; }
.data-table th { background: rgba(128,128,128,0.08); font-weight: 600; }
</style>
