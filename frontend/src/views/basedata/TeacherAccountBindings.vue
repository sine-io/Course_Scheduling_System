<script setup lang="ts">
import { AlertTriangle, Link2, RefreshCw, Save, Search, Unlink, X } from '@lucide/vue'
import {
  NButton, NEmpty, NInput, NModal, NSelect, NSpin, NTag, useDialog, useMessage,
} from 'naive-ui'
import { computed, onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import { listBindableAccounts, listTeachers, updateTeacher } from '@/api/basedata'
import type { BindableAccount, Teacher } from '@/api/basedata'
import { highRiskConfirmation } from '@/api/highRisk'
import { vAccessibleSelect } from '@/directives/accessibleSelect'
import './basedata-workspace.css'

const props = withDefaults(defineProps<{ semesterId: number; canEdit?: boolean }>(), {
  canEdit: true,
})
const emit = defineEmits<{ changed: [] }>()
const dialog = useDialog()
const message = useMessage()

const teachers = ref<Teacher[]>([])
const accounts = ref<BindableAccount[]>([])
const search = ref('')
const loading = ref(true)
const loadingAccounts = ref(false)
const saving = ref(false)
const loadError = ref<string | null>(null)
const show = ref(false)
const selectedTeacher = ref<Teacher | null>(null)
const selectedUserId = ref<number | null>(null)

const accountOptions = computed(() => accounts.value.map((account) => ({
  label: `${account.display_name}（${account.username}）`,
  value: account.id,
})))

async function reload() {
  loading.value = true
  loadError.value = null
  try {
    teachers.value = await listTeachers(props.semesterId, search.value || undefined)
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取教师账号绑定，请重试。')
  } finally {
    loading.value = false
  }
}

onMounted(reload)

async function openBinding(teacher: Teacher) {
  if (!props.canEdit) return
  selectedTeacher.value = teacher
  selectedUserId.value = teacher.user_id
  accounts.value = []
  show.value = true
  loadingAccounts.value = true
  try {
    accounts.value = await listBindableAccounts(props.semesterId, teacher.id)
  } catch (error) {
    message.error(apiErrorMessage(error, '暂时无法读取可绑定账号，请重试。'))
    show.value = false
  } finally {
    loadingAccounts.value = false
  }
}

function closeModal() {
  if (!saving.value) show.value = false
}

async function persistBinding() {
  const teacher = selectedTeacher.value
  if (!teacher || saving.value || selectedUserId.value === teacher.user_id) {
    show.value = false
    return
  }
  const userId = selectedUserId.value
  saving.value = true
  try {
    await updateTeacher(teacher.id, {
      name: teacher.name,
      id_last4: teacher.id_last4 ?? null,
      base_periods: teacher.base_periods,
      admin_title: teacher.admin_title,
      admin_reduction: teacher.admin_reduction,
      is_external: teacher.is_external,
      is_active: teacher.is_active,
      subject_ids: teacher.subjects.map((subject) => subject.id),
      email: teacher.email,
      phone: teacher.phone,
      line_id: teacher.line_id,
      user_id: userId,
      account_confirmation: highRiskConfirmation(
        `teacher:${teacher.id}:account:${userId === null ? 'none' : userId}`,
      ),
    })
    show.value = false
    message.success(userId === null ? '已解除教师账号绑定' : '已更新教师账号绑定')
    await reload()
    emit('changed')
  } catch (error) {
    message.error(apiErrorMessage(error, '教师账号绑定更新失败'))
  } finally {
    saving.value = false
  }
}

function confirmBinding() {
  const teacher = selectedTeacher.value
  if (!teacher || selectedUserId.value === teacher.user_id) {
    show.value = false
    return
  }
  const account = accounts.value.find((item) => item.id === selectedUserId.value)
  const impact = selectedUserId.value === null
    ? '解除绑定后，该登录账号将不能再访问这位教师的本人课表与请假数据。'
    : `绑定后，账号“${account?.display_name ?? `#${selectedUserId.value}`}”将可访问这位教师的本人数据。`
  dialog.warning({
    title: '确认变更教师账号绑定',
    content: `目标：教师“${teacher.name}”。${impact}`,
    positiveText: '确认变更',
    negativeText: '取消',
    maskClosable: false,
    onPositiveClick: persistBinding,
  })
}
</script>

<template>
  <div class="basedata-tab-content" :aria-busy="loading">
    <div class="basedata-toolbar">
      <div class="basedata-toolbar-main">
        <n-input
          v-model:value="search"
          class="basedata-search"
          clearable
          :placeholder="'搜索教师姓名'"
          aria-label="搜索教师姓名"
          @input="reload"
        >
          <template #prefix><Search :size="15" aria-hidden="true" /></template>
        </n-input>
      </div>
      <span class="basedata-field-hint">{{ '教师档案请在排课工作台维护；此处仅管理登录账号关联。' }}</span>
    </div>

    <section v-if="loading && !teachers.length" class="basedata-state" data-testid="teacher-accounts-loading" role="status" aria-live="polite">
      <n-spin size="small" />
      <strong>{{ '正在读取教师账号绑定' }}</strong>
      <span>{{ '教师列表加载完成后会显示在这里。' }}</span>
    </section>
    <section v-else-if="loadError" class="basedata-state basedata-state-error" data-testid="teacher-accounts-error" role="alert">
      <AlertTriangle :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <span>{{ '当前列表未更新。' }}</span>
      <n-button type="primary" data-testid="teacher-accounts-retry" @click="reload">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>
    <section v-else-if="!teachers.length" class="basedata-state" data-testid="teacher-accounts-empty" role="status">
      <n-empty :description="'暂无教师'" />
    </section>
    <div v-else class="basedata-table-scroll" data-testid="teacher-accounts-table-scroll" tabindex="0" aria-label="教师账号绑定列表，可横向滚动">
      <table class="basedata-data-table basedata-data-table--accounts" data-testid="teacher-accounts-table">
        <thead>
          <tr>
            <th>{{ '教师' }}</th>
            <th>{{ '任教科目' }}</th>
            <th>{{ '登录账号' }}</th>
            <th v-if="canEdit">{{ '操作' }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="teacher in teachers" :key="teacher.id">
            <td>{{ teacher.name }}</td>
            <td>{{ teacher.subjects.map((subject) => subject.name).join('、') || '—' }}</td>
            <td>
              <n-tag v-if="teacher.user_id !== null" size="small" type="info">{{ `账号 #${teacher.user_id}` }}</n-tag>
              <span v-else>{{ '未绑定' }}</span>
            </td>
            <td v-if="canEdit">
              <n-button size="small" :data-testid="`teacher-account-bind-${teacher.id}`" @click="openBinding(teacher)">
                <template #icon>
                  <Unlink v-if="teacher.user_id !== null" :size="14" aria-hidden="true" />
                  <Link2 v-else :size="14" aria-hidden="true" />
                </template>
                {{ teacher.user_id === null ? '绑定账号' : '变更绑定' }}
              </n-button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <n-modal v-model:show="show" preset="card" class="basedata-modal" :title="`教师账号绑定 · ${selectedTeacher?.name ?? ''}`">
      <div class="basedata-form">
        <div class="basedata-field">
          <span class="basedata-field-label">{{ '登录账号' }}</span>
          <n-select
            v-model:value="selectedUserId"
            v-accessible-select="'绑定登录账号'"
            data-testid="teacher-account-select"
            :options="accountOptions"
            :loading="loadingAccounts"
            clearable
            :placeholder="'选择账号；清空表示解除绑定'"
          />
          <span class="basedata-field-hint">{{ '列表只包含具有教师角色、当前学期尚未绑定的有效账号。' }}</span>
        </div>
        <div class="basedata-modal-actions">
          <n-button quaternary :disabled="saving" @click="closeModal">
            <template #icon><X :size="15" aria-hidden="true" /></template>
            {{ '取消' }}
          </n-button>
          <n-button
            type="primary"
            data-testid="teacher-account-save"
            :loading="saving"
            :disabled="loadingAccounts || saving || selectedUserId === selectedTeacher?.user_id"
            @click="confirmBinding"
          >
            <template #icon><Save :size="15" aria-hidden="true" /></template>
            {{ '保存绑定' }}
          </n-button>
        </div>
      </div>
    </n-modal>
  </div>
</template>
