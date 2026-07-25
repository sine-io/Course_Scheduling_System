<script setup lang="ts">
import {
  NButton, NDivider, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSpace, NSwitch, NTag, NText, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import type { ApiError } from '@/api/client'
import {
  createTeacher, deleteTeacher, listBindableAccounts, listSubjects, listTeachers, updateTeacher,
} from '@/api/basedata'
import type { BindableAccount, Subject, Teacher } from '@/api/basedata'
import TeacherTimeRules from './TeacherTimeRules.vue'

const props = defineProps<{ semesterId: number }>()
const message = useMessage()

const items = ref<Teacher[]>([])
const subjects = ref<Subject[]>([])
const accounts = ref<BindableAccount[]>([])
const search = ref('')
const subjectOptions = computed(() => subjects.value.map((s) => ({ label: s.name, value: s.id })))
const accountOptions = computed(() =>
  accounts.value.map((a) => ({ label: `${a.display_name}(${a.username})`, value: a.id })),
)

async function reload() {
  items.value = await listTeachers(props.semesterId, search.value || undefined)
}
onMounted(async () => {
  subjects.value = await listSubjects(props.semesterId)
  await reload()
})

const show = ref(false)
const editingId = ref<number | null>(null)
interface TeacherForm {
  name: string; base_periods: number; admin_title: string; admin_reduction: number
  is_external: boolean; is_active: boolean; subject_ids: number[]
  email: string; phone: string; line_id: string; user_id: number | null
}
function emptyForm(): TeacherForm {
  return {
    name: '', base_periods: 0, admin_title: '', admin_reduction: 0,
    is_external: false, is_active: true, subject_ids: [],
    email: '', phone: '', line_id: '', user_id: null,
  }
}
const form = ref<TeacherForm>(emptyForm())

async function loadAccounts(currentTeacherId?: number) {
  accounts.value = await listBindableAccounts(props.semesterId, currentTeacherId)
}

async function openCreate() {
  editingId.value = null
  form.value = emptyForm()
  await loadAccounts()
  show.value = true
}
async function openEdit(t: Teacher) {
  editingId.value = t.id
  form.value = {
    name: t.name, base_periods: t.base_periods, admin_title: t.admin_title ?? '',
    admin_reduction: t.admin_reduction, is_external: t.is_external, is_active: t.is_active,
    subject_ids: t.subjects.map((s) => s.id),
    email: t.email ?? '', phone: t.phone ?? '', line_id: t.line_id ?? '', user_id: t.user_id,
  }
  await loadAccounts(t.id)
  show.value = true
}

async function save() {
  if (!form.value.name) {
    message.warning('请输入教师姓名')
    return
  }
  const body = {
    ...form.value,
    admin_title: form.value.admin_title || null,
    email: form.value.email || null,
    phone: form.value.phone || null,
    line_id: form.value.line_id || null,
  }
  try {
    if (editingId.value) await updateTeacher(editingId.value, body)
    else await createTeacher(props.semesterId, body)
    show.value = false
    message.success('已保存')
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail || '保存失败')
  }
}

async function remove(t: Teacher) {
  try {
    await deleteTeacher(t.id)
    message.success('已删除')
    await reload()
  } catch (e) {
    message.error((e as ApiError).detail || '删除失败')
  }
}

// 时段规则
const rulesShow = ref(false)
const rulesTeacher = ref<Teacher | null>(null)
function openRules(t: Teacher) {
  rulesTeacher.value = t
  rulesShow.value = true
}
</script>

<template>
  <n-space vertical>
    <n-space>
      <n-input v-model:value="search" :placeholder="'搜索教师姓名'" clearable style="width: 200px" @input="reload" />
      <n-button type="primary" data-testid="teacher-add" @click="openCreate">{{ '新增教师' }}</n-button>
    </n-space>

    <table class="data-table">
      <thead>
        <tr><th>{{ '姓名' }}</th><th>{{ '任教科目' }}</th><th>{{ '基本课时' }}</th><th>{{ '行政' }}</th><th>{{ '账号' }}</th><th>{{ '状态' }}</th><th>{{ '操作' }}</th></tr>
      </thead>
      <tbody>
        <tr v-for="t in items" :key="t.id">
          <td>
            {{ t.name }}
            <n-tag v-if="t.is_external" size="tiny" type="warning" style="margin-left: 4px">{{ '外聘' }}</n-tag>
          </td>
          <td>
            <n-space size="small">
              <n-tag v-for="s in t.subjects" :key="s.id" size="small">{{ s.name }}</n-tag>
              <n-text v-if="t.subjects.length === 0" depth="3">—</n-text>
            </n-space>
          </td>
          <td>{{ t.base_periods }}</td>
          <td>{{ t.admin_title ? `${t.admin_title}（减 ${t.admin_reduction}）` : '—' }}</td>
          <td>
            <n-tag v-if="t.user_id" size="small" type="info">{{ '已绑定' }}</n-tag>
            <n-text v-else depth="3">—</n-text>
          </td>
          <td>
            <n-tag :type="t.is_active ? 'success' : 'default'" size="small">
              {{ t.is_active ? '在职' : '离职' }}
            </n-tag>
          </td>
          <td>
            <n-space>
              <n-button size="tiny" @click="openEdit(t)">{{ '编辑' }}</n-button>
              <n-button size="tiny" @click="openRules(t)">{{ '时段规则' }}</n-button>
              <n-popconfirm @positive-click="remove(t)">
                <template #trigger><n-button size="tiny" type="error" ghost>{{ '删除' }}</n-button></template>
                {{ '确定删除此教师吗？' }}
              </n-popconfirm>
            </n-space>
          </td>
        </tr>
        <tr v-if="items.length === 0"><td colspan="7"><n-text depth="3">{{ '暂无教师' }}</n-text></td></tr>
      </tbody>
    </table>

    <n-modal v-model:show="show" preset="card" :title="editingId ? '编辑教师' : '新增教师'" style="max-width: 460px">
      <n-space vertical>
        <n-text>{{ '姓名' }}</n-text>
        <n-input v-model:value="form.name" data-testid="teacher-name" :placeholder="'如：王小明'" />
        <n-text>{{ '任教科目' }}</n-text>
        <n-select v-model:value="form.subject_ids" multiple :options="subjectOptions" :placeholder="'可多选'" />
        <n-space>
          <n-space vertical style="flex: 1">
            <n-text>{{ '基本课时' }}</n-text>
            <n-input-number v-model:value="form.base_periods" :min="0" />
          </n-space>
          <n-space vertical style="flex: 1">
            <n-text>{{ '行政减课' }}</n-text>
            <n-input-number v-model:value="form.admin_reduction" :min="0" />
          </n-space>
        </n-space>
        <n-text>{{ '行政职务（可选）' }}</n-text>
        <n-input v-model:value="form.admin_title" :placeholder="'如：教务排课管理员'" />
        <n-space align="center">
          <n-text>{{ '外聘教师' }}</n-text>
          <n-switch v-model:value="form.is_external" />
          <n-text style="margin-left: 16px">{{ '在职' }}</n-text>
          <n-switch v-model:value="form.is_active" />
        </n-space>

        <n-divider style="margin: 4px 0" title-placement="left">
          <n-text depth="3" style="font-size: 12px">{{ '联系信息（可选，用于调课与代课通知）' }}</n-text>
        </n-divider>
        <n-space>
          <n-space vertical style="flex: 1">
            <n-text>Email</n-text>
            <n-input v-model:value="form.email" data-testid="teacher-email" :placeholder="'用于发送通知'" />
          </n-space>
          <n-space vertical style="flex: 1">
            <n-text>{{ '手机' }}</n-text>
            <n-input v-model:value="form.phone" :placeholder="'用于人工联系'" />
          </n-space>
        </n-space>
        <n-text>{{ '即时通讯账号（可选，用于人工联系）' }}</n-text>
        <n-input v-model:value="form.line_id" :placeholder="'即时通讯账号'" />
        <n-text>{{ '绑定登录账号（可选）' }}</n-text>
        <n-select
          v-model:value="form.user_id"
          data-testid="teacher-account"
          :options="accountOptions"
          clearable
          :placeholder="'绑定后该教师可使用此账号登录查询课表或请假'"
        />

        <n-button type="primary" data-testid="teacher-save" @click="save">{{ '保存' }}</n-button>
      </n-space>
    </n-modal>

    <n-modal
      v-model:show="rulesShow"
      preset="card"
      :title="`${'时段规则'}:${rulesTeacher?.name}`"
      style="max-width: 640px"
    >
      <TeacherTimeRules
        v-if="rulesTeacher"
        :teacher-id="rulesTeacher.id"
        :semester-id="semesterId"
        @saved="rulesShow = false"
      />
    </n-modal>
  </n-space>
</template>

<style scoped>
.data-table { border-collapse: collapse; width: 100%; }
.data-table th, .data-table td { border: 1px solid var(--n-border-color, #e0e0e0); padding: 8px 10px; text-align: left; }
.data-table th { background: rgba(128,128,128,0.08); font-weight: 600; }
</style>
