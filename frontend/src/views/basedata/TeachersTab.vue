<script setup lang="ts">
import {
  AlertTriangle, CalendarClock, Pencil, Plus, RefreshCw, Save, Trash2, X,
} from '@lucide/vue'
import {
  NAlert, NButton, NDivider, NEmpty, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSpin,
  NSwitch, NTag, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import {
  createTeacher, deleteTeacher, listBindableAccounts, listSubjects, listTeachers, updateTeacher,
} from '@/api/basedata'
import type { BindableAccount, Subject, Teacher } from '@/api/basedata'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import TeacherTimeRules from './TeacherTimeRules.vue'
import './basedata-workspace.css'

const props = withDefaults(defineProps<{ semesterId: number; canEdit?: boolean }>(), { canEdit: true })
const message = useMessage()

const items = ref<Teacher[]>([])
const subjects = ref<Subject[]>([])
const accounts = ref<BindableAccount[]>([])
const search = ref('')
const loading = ref(true)
const loadError = ref<string | null>(null)
const saving = ref(false)
const loadingAccounts = ref(false)
const deletingId = ref<number | null>(null)
const subjectOptions = computed(() => subjects.value.map((subject) => ({ label: subject.name, value: subject.id })))
const accountOptions = computed(() =>
  accounts.value.map((account) => ({
    label: `${account.display_name}（${account.username}）`,
    value: account.id,
  })),
)

async function reload() {
  loading.value = true
  loadError.value = null
  try {
    items.value = await listTeachers(props.semesterId, search.value || undefined)
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取教师，请重试。')
  } finally {
    loading.value = false
  }
}

async function loadInitialData() {
  loading.value = true
  loadError.value = null
  try {
    const [teacherItems, subjectItems] = await Promise.all([
      listTeachers(props.semesterId, search.value || undefined),
      listSubjects(props.semesterId),
    ])
    items.value = teacherItems
    subjects.value = subjectItems
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取教师，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(loadInitialData)

const show = ref(false)
const editingId = ref<number | null>(null)
interface TeacherForm {
  name: string
  base_periods: number
  admin_title: string
  admin_reduction: number
  is_external: boolean
  is_active: boolean
  subject_ids: number[]
  email: string
  phone: string
  line_id: string
  user_id: number | null
}
function emptyForm(): TeacherForm {
  return {
    name: '',
    base_periods: 0,
    admin_title: '',
    admin_reduction: 0,
    is_external: false,
    is_active: true,
    subject_ids: [],
    email: '',
    phone: '',
    line_id: '',
    user_id: null,
  }
}
const form = ref<TeacherForm>(emptyForm())

async function loadAccounts(currentTeacherId?: number) {
  loadingAccounts.value = true
  try {
    accounts.value = await listBindableAccounts(props.semesterId, currentTeacherId)
  } catch (error) {
    message.error(apiErrorMessage(error, '账号列表加载失败'))
    throw error
  } finally {
    loadingAccounts.value = false
  }
}

async function openCreate() {
  editingId.value = null
  form.value = emptyForm()
  show.value = true
  try {
    await loadAccounts()
  } catch {
    show.value = false
  }
}
async function openEdit(teacher: Teacher) {
  editingId.value = teacher.id
  form.value = {
    name: teacher.name,
    base_periods: teacher.base_periods,
    admin_title: teacher.admin_title ?? '',
    admin_reduction: teacher.admin_reduction,
    is_external: teacher.is_external,
    is_active: teacher.is_active,
    subject_ids: teacher.subjects.map((subject) => subject.id),
    email: teacher.email ?? '',
    phone: teacher.phone ?? '',
    line_id: teacher.line_id ?? '',
    user_id: teacher.user_id,
  }
  show.value = true
  try {
    await loadAccounts(teacher.id)
  } catch {
    show.value = false
  }
}
function closeModal() {
  if (!saving.value) show.value = false
}

async function save() {
  if (saving.value) return
  if (!form.value.name) {
    message.warning('请输入教师姓名')
    return
  }
  saving.value = true
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
  } catch (error) {
    message.error(apiErrorMessage(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function remove(teacher: Teacher) {
  if (deletingId.value !== null) return
  deletingId.value = teacher.id
  try {
    await deleteTeacher(teacher.id)
    message.success('已删除')
    await reload()
  } catch (error) {
    message.error(apiErrorMessage(error, '删除失败'))
  } finally {
    deletingId.value = null
  }
}

const rulesShow = ref(false)
const rulesTeacher = ref<Teacher | null>(null)
function openRules(teacher: Teacher) {
  rulesTeacher.value = teacher
  rulesShow.value = true
}
</script>

<template>
  <div class="basedata-tab-content" :aria-busy="loading">
    <div class="basedata-toolbar">
      <div class="basedata-toolbar-main">
        <n-input
          v-model:value="search"
          class="basedata-search"
          :placeholder="'搜索教师姓名'"
          clearable
          aria-label="搜索教师姓名"
          @input="reload"
        />
      </div>
      <div v-if="canEdit" class="basedata-toolbar-actions">
        <n-button type="primary" data-testid="teacher-add" @click="openCreate">
          <template #icon><Plus :size="16" aria-hidden="true" /></template>
          {{ '新增教师' }}
        </n-button>
      </div>
    </div>

    <n-alert v-if="!canEdit" class="basedata-readonly" type="info" data-testid="teachers-readonly">
      {{ '仅可查看教师，当前角色没有新增、编辑或删除权限；时段规则可查看但不能修改。' }}
    </n-alert>

    <section v-if="loading && !items.length" class="basedata-state" data-testid="teachers-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取教师' }}</strong>
      <span>{{ '教师列表加载完成后会显示在这里。' }}</span>
    </section>
    <section v-else-if="loadError" class="basedata-state basedata-state-error" data-testid="teachers-error" role="alert">
      <AlertTriangle :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '当前列表未更新。' }}</span>
      <n-button type="primary" data-testid="teachers-retry" @click="loadInitialData">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>
    <section v-else-if="!items.length" class="basedata-state" data-testid="teachers-empty" role="status">
      <n-empty :description="'暂无教师'" />
    </section>
    <div v-else class="basedata-table-scroll" data-testid="teachers-table-scroll" tabindex="0" aria-label="教师列表，可横向滚动">
      <table class="basedata-data-table basedata-data-table--teachers" data-testid="teachers-table">
        <thead>
          <tr>
            <th>{{ '姓名' }}</th>
            <th>{{ '任教科目' }}</th>
            <th>{{ '基本课时' }}</th>
            <th>{{ '行政' }}</th>
            <th>{{ '账号' }}</th>
            <th>{{ '状态' }}</th>
            <th>{{ '操作' }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="teacher in items" :key="teacher.id">
            <td>
              {{ teacher.name }}
              <n-tag v-if="teacher.is_external" size="tiny" type="warning">{{ '外聘' }}</n-tag>
            </td>
            <td>
              <div class="basedata-command-group">
                <n-tag v-for="subject in teacher.subjects" :key="subject.id" size="small">{{ subject.name }}</n-tag>
                <span v-if="teacher.subjects.length === 0">—</span>
              </div>
            </td>
            <td>{{ teacher.base_periods }}</td>
            <td>{{ teacher.admin_title ? `${teacher.admin_title}（减 ${teacher.admin_reduction}）` : '—' }}</td>
            <td>
              <n-tag v-if="teacher.user_id" size="small" type="info">{{ '已绑定' }}</n-tag>
              <span v-else>—</span>
            </td>
            <td>
              <n-tag :type="teacher.is_active ? 'success' : 'default'" size="small">
                {{ teacher.is_active ? '在职' : '离职' }}
              </n-tag>
            </td>
            <td>
              <div class="basedata-command-group">
                <n-button v-if="canEdit" size="small" :data-testid="`teacher-edit-${teacher.id}`" @click="openEdit(teacher)">
                  <template #icon><Pencil :size="14" aria-hidden="true" /></template>
                  {{ '编辑' }}
                </n-button>
                <n-button size="small" :data-testid="`teacher-rules-${teacher.id}`" @click="openRules(teacher)">
                  <template #icon><CalendarClock :size="14" aria-hidden="true" /></template>
                  {{ '时段规则' }}
                </n-button>
                <n-popconfirm v-if="canEdit" :disabled="deletingId !== null" @positive-click="remove(teacher)">
                  <template #trigger>
                    <n-button
                      size="small"
                      type="error"
                      ghost
                      :data-testid="`teacher-delete-${teacher.id}`"
                      :loading="deletingId === teacher.id"
                      :disabled="deletingId !== null"
                    >
                      <template #icon><Trash2 :size="14" aria-hidden="true" /></template>
                      {{ '删除' }}
                    </n-button>
                  </template>
                  {{ '确定删除此教师吗？' }}
                </n-popconfirm>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <n-modal v-model:show="show" preset="card" class="basedata-modal basedata-modal--wide" :title="editingId ? '编辑教师' : '新增教师'">
      <div class="basedata-form">
        <div class="basedata-field">
          <label for="teacher-name">{{ '姓名' }}</label>
          <n-input
            id="teacher-name"
            v-model:value="form.name"
            data-testid="teacher-name"
            :placeholder="'如：王小明'"
            :input-props="{ 'aria-label': '姓名' }"
          />
        </div>
        <div class="basedata-field">
          <span class="basedata-field-label">{{ '任教科目' }}</span>
          <n-select
            v-model:value="form.subject_ids"
            v-accessible-select="'任教科目'"
            multiple
            :options="subjectOptions"
            :placeholder="'可多选'"
          />
        </div>
        <div class="basedata-form-row">
          <div class="basedata-field">
            <span class="basedata-field-label">{{ '基本课时' }}</span>
            <n-input-number
              v-model:value="form.base_periods"
              :min="0"
              :input-props="{ 'aria-label': '基本课时' }"
            />
          </div>
          <div class="basedata-field">
            <span class="basedata-field-label">{{ '行政减课' }}</span>
            <n-input-number
              v-model:value="form.admin_reduction"
              :min="0"
              :input-props="{ 'aria-label': '行政减课' }"
            />
          </div>
        </div>
        <div class="basedata-field">
          <label for="teacher-admin-title">{{ '行政职务（可选）' }}</label>
          <n-input
            id="teacher-admin-title"
            v-model:value="form.admin_title"
            :placeholder="'如：教务排课管理员'"
            :input-props="{ 'aria-label': '行政职务' }"
          />
        </div>
        <div class="basedata-switch-row">
          <label><span>{{ '外聘教师' }}</span><n-switch v-model:value="form.is_external" aria-label="外聘教师" /></label>
          <label><span>{{ '在职' }}</span><n-switch v-model:value="form.is_active" aria-label="在职" /></label>
        </div>

        <n-divider class="basedata-divider" title-placement="left">
          {{ '联系信息（可选，用于调课与代课通知）' }}
        </n-divider>
        <div class="basedata-form-row">
          <div class="basedata-field">
            <label for="teacher-email">{{ '电子邮箱' }}</label>
            <n-input
              id="teacher-email"
              v-model:value="form.email"
              data-testid="teacher-email"
              :placeholder="'用于发送通知'"
              :input-props="{ 'aria-label': '电子邮箱' }"
            />
          </div>
          <div class="basedata-field">
            <label for="teacher-phone">{{ '手机' }}</label>
            <n-input
              id="teacher-phone"
              v-model:value="form.phone"
              :placeholder="'用于人工联系'"
              :input-props="{ 'aria-label': '手机' }"
            />
          </div>
        </div>
        <div class="basedata-field">
          <label for="teacher-line-id">{{ '即时通讯账号（可选，用于人工联系）' }}</label>
          <n-input
            id="teacher-line-id"
            v-model:value="form.line_id"
            :placeholder="'即时通讯账号'"
            :input-props="{ 'aria-label': '即时通讯账号' }"
          />
        </div>
        <div class="basedata-field">
          <span class="basedata-field-label">{{ '绑定登录账号（可选）' }}</span>
          <n-select
            v-model:value="form.user_id"
            v-accessible-select="'绑定登录账号'"
            data-testid="teacher-account"
            :options="accountOptions"
            :loading="loadingAccounts"
            clearable
            :placeholder="'绑定后该教师可使用此账号登录查询课表或请假'"
          />
        </div>
        <div class="basedata-modal-actions">
          <n-button quaternary :disabled="saving" @click="closeModal">
            <template #icon><X :size="15" aria-hidden="true" /></template>
            {{ '取消' }}
          </n-button>
          <n-button type="primary" data-testid="teacher-save" :loading="saving" :disabled="saving" @click="save">
            <template #icon><Save :size="15" aria-hidden="true" /></template>
            {{ '保存' }}
          </n-button>
        </div>
      </div>
    </n-modal>

    <n-modal
      v-model:show="rulesShow"
      preset="card"
      class="basedata-modal basedata-modal--rules"
      :title="`${'时段规则'}：${rulesTeacher?.name}`"
    >
      <TeacherTimeRules
        v-if="rulesTeacher"
        :teacher-id="rulesTeacher.id"
        :semester-id="semesterId"
        :can-edit="canEdit"
        @saved="rulesShow = false"
      />
    </n-modal>
  </div>
</template>
