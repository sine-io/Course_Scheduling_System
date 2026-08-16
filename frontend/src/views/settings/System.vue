<script setup lang="ts">
import {
  AlertTriangle, ClipboardList, DatabaseBackup, Download, Pencil, Plus, RefreshCw,
  RotateCcw, Save, Trash2, Upload, UserCog,
} from '@lucide/vue'
import {
  NAlert, NButton, NCheckbox, NInput, NInputNumber, NModal, NPopconfirm, NSwitch, NTag,
  NUpload,
  useDialog, useMessage,
} from 'naive-ui'
import type { UploadCustomRequestOptions, UploadSettledFileInfo } from 'naive-ui'
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ACCOUNT_ROLES, createAccount, listAccounts, updateAccount } from '@/api/accounts'
import type { Account, AccountRole } from '@/api/accounts'
import { listAuditLogs } from '@/api/audit'
import type { AuditLog } from '@/api/audit'
import {
  createBackup, deleteBackup, downloadBackup, listBackups, restoreBackup, restoreUpload,
} from '@/api/backups'
import type { Backup, RestoreResult } from '@/api/backups'
import {
  demoDataStatus, getSchedulingSettings, getSchoolSettings, loadDemoData,
  saveSchedulingSettings, saveSchoolSettings,
} from '@/api/assignments'
import { apiErrorMessage } from '@/api/client'
import { highRiskConfirmation } from '@/api/highRisk'
import type { HighRiskConfirmation } from '@/api/highRisk'
import { chooseOnboardingRoute } from '@/api/onboarding'
import { getSmtp, saveSmtp } from '@/api/notifications'
import { resetWizard } from '@/api/wizard'
import { useAuthStore } from '@/stores/auth'
import { useWizardStore } from '@/stores/wizard'
import './settings-workspace.css'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const wizard = useWizardStore()
const auth = useAuthStore()

const isAdmin = computed(() => auth.hasRole('admin'))
const adminLoading = ref(isAdmin.value)
const adminError = ref<string | null>(null)

const backups = ref<Backup[]>([])
const accounts = ref<Account[]>([])
const auditLogs = ref<AuditLog[]>([])
const auditQuery = ref('')
const filteredAuditLogs = computed(() => {
  const query = auditQuery.value.trim().toLowerCase()
  if (!query) return auditLogs.value
  return auditLogs.value.filter((log) => [
    log.username,
    ...log.actor_roles.map((role) => auth.roleLabel(role)),
    log.action,
    auditActionLabel(log.action),
    auditTargetLabel(log.target_type),
    log.target_version,
    log.result,
    auditResultLabel(log.result),
    log.reason,
    log.detail,
  ].some((value) => value.toLowerCase().includes(query)))
})
const creatingBackup = ref(false)
const restoringBackup = ref<string | null>(null)
const confirmingUploadRestore = ref(false)
const confirmedUploadRestoreId = ref<string | null>(null)
const uploadRestoreConfirmation = ref<HighRiskConfirmation | null>(null)
const uploadingRestore = ref(false)
const deletingBackup = ref<string | null>(null)
const downloadingBackup = ref<string | null>(null)
const backupBusy = computed(() => (
  creatingBackup.value
  || restoringBackup.value !== null
  || confirmingUploadRestore.value
  || confirmedUploadRestoreId.value !== null
  || uploadingRestore.value
  || deletingBackup.value !== null
))

const smtp = ref({ host: '', port: 25, user: '', password: '', sender: '', use_tls: false })
const configured = ref(false)
const hasPassword = ref(false)
const savingSmtp = ref(false)
const maxOvertime = ref(8)
const savingScheduling = ref(false)
const schoolName = ref('')
const savingSchool = ref(false)
const demoAvailable = ref(false)
const demoSchool = ref('')
const loadingDemo = ref(false)
const resettingWizard = ref(false)
let redirectingAfterRestore = false

interface AccountForm {
  username: string
  display_name: string
  temporary_password: string
  roles: AccountRole[]
  is_active: boolean
}

const accountShow = ref(false)
const accountSaving = ref(false)
const accountTarget = ref<Account | null>(null)
const accountForm = ref<AccountForm>({
  username: '',
  display_name: '',
  temporary_password: '',
  roles: ['teacher'],
  is_active: true,
})
const roleOptions = ACCOUNT_ROLES.map((role) => ({
  value: role,
  label: {
    admin: '系统管理员',
    director: '教务主任',
    scheduler: '排课管理员',
    teacher: '教师',
  }[role],
}))

function humanSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

const AUDIT_ACTION_LABELS: Readonly<Record<string, string>> = {
  assign_substitution: '安排调课与代课',
  auto_schedule: '自动排课',
  bind_teacher_account: '绑定教师账号',
  bulk_create_accounts: '批量创建教师账号',
  cancel_leave: '撤销请假',
  confirm_semester_readiness: '确认排课准备',
  create_account: '创建账号',
  create_backup: '创建备份',
  create_calendar_exception: '新增特殊日期',
  create_demo_data: '创建示例数据',
  create_leave: '登记请假',
  delete_assignment: '删除教学任务',
  delete_backup: '删除备份',
  delete_calendar_exception: '删除特殊日期',
  delete_class_unit: '删除班级',
  delete_period_table: '删除作息时间表',
  delete_room: '删除教室/场地',
  delete_scheduling_unit: '删除排课单元',
  delete_semester: '删除学期',
  delete_subject: '删除科目',
  delete_teacher: '删除教师',
  delete_timetable: '删除课表版本',
  publish_timetable: '发布课表',
  restore_backup: '恢复备份',
  revoke_semester_readiness: '撤回排课准备确认',
  update_account: '更新账号',
  update_calendar_exception: '修改特殊日期',
  update_school_name: '更新学校名称',
  update_scheduling_settings: '更新排课设置',
  update_smtp: '更新邮件设置',
}

const AUDIT_TARGET_LABELS: Readonly<Record<string, string>> = {
  account: '账号',
  affected_period: '受影响节次',
  app_setting: '系统设置',
  assignment: '教学任务',
  backup: '备份',
  class_unit: '班级',
  leave_request: '请假记录',
  period_table: '作息时间表',
  room: '教室/场地',
  scheduling_unit: '排课单元',
  semester: '学期',
  semester_calendar_exception: '特殊日期',
  subject: '科目',
  teacher: '教师',
  timetable: '课表版本',
}

function auditActionLabel(action: string): string {
  return AUDIT_ACTION_LABELS[action] ?? '其他操作'
}

function auditTargetLabel(targetType: string): string {
  return AUDIT_TARGET_LABELS[targetType] ?? '其他对象'
}

function auditResultLabel(result: string): string {
  return { success: '成功', rejected: '已拒绝', failed: '失败', pending: '处理中' }[result] ?? '其他结果'
}

function auditResultType(result: string): 'success' | 'warning' | 'error' | 'info' | 'default' {
  return {
    success: 'success',
    rejected: 'warning',
    failed: 'error',
    pending: 'info',
  }[result] as 'success' | 'warning' | 'error' | 'info' | undefined ?? 'default'
}

async function loadAdminSettings() {
  if (!isAdmin.value) {
    adminLoading.value = false
    return
  }
  adminLoading.value = true
  adminError.value = null
  try {
    const [smtpSettings, scheduling, school, demo, backupRows, accountRows, auditRows] = await Promise.all([
      getSmtp(),
      getSchedulingSettings(),
      getSchoolSettings(),
      demoDataStatus(),
      listBackups(),
      listAccounts(),
      listAuditLogs(),
    ])
    smtp.value = {
      host: smtpSettings.host,
      port: smtpSettings.port,
      user: smtpSettings.user,
      password: '',
      sender: smtpSettings.sender,
      use_tls: smtpSettings.use_tls,
    }
    configured.value = smtpSettings.configured
    hasPassword.value = smtpSettings.has_password
    maxOvertime.value = scheduling.max_overtime
    schoolName.value = school.school_name
    demoAvailable.value = demo.available
    demoSchool.value = demo.school_name
    backups.value = backupRows
    accounts.value = accountRows
    auditLogs.value = auditRows
  } catch (error) {
    adminError.value = apiErrorMessage(error, '暂时无法读取系统设置，请重试。')
  } finally {
    adminLoading.value = false
  }
}

onMounted(loadAdminSettings)

async function reloadBackups() {
  if (!isAdmin.value) return
  try {
    backups.value = await listBackups()
  } catch (error) {
    message.error(apiErrorMessage(error, '备份列表读取失败，请重试。'))
  }
}

async function reloadAccounts() {
  if (!isAdmin.value) return
  try {
    accounts.value = await listAccounts()
  } catch (error) {
    message.error(apiErrorMessage(error, '账号列表读取失败，请重试。'))
  }
}

async function reloadAudit() {
  if (!isAdmin.value) return
  try {
    auditLogs.value = await listAuditLogs()
  } catch (error) {
    message.error(apiErrorMessage(error, '审计记录读取失败，请重试。'))
  }
}

async function onCreateBackup() {
  if (backupBusy.value) return
  creatingBackup.value = true
  try {
    await createBackup(highRiskConfirmation('backup:create'))
    message.success('备份已创建')
    await reloadBackups()
  } catch (error) {
    message.error(apiErrorMessage(error, '备份失败，请重试。'))
  } finally {
    creatingBackup.value = false
    void reloadAudit()
  }
}

async function onDeleteBackup(name: string) {
  if (backupBusy.value) return
  deletingBackup.value = name
  try {
    await deleteBackup(name, highRiskConfirmation(`backup:${name}`))
    message.success('备份已删除')
    await reloadBackups()
  } catch (error) {
    message.error(apiErrorMessage(error, '备份删除失败，请重试。'))
  } finally {
    deletingBackup.value = null
    void reloadAudit()
  }
}

async function onDownloadBackup(name: string) {
  if (downloadingBackup.value !== null) return
  downloadingBackup.value = name
  try {
    await downloadBackup(name)
  } catch (error) {
    message.error(apiErrorMessage(error, '备份下载失败，请重试。'))
  } finally {
    downloadingBackup.value = null
  }
}

async function redirectToLogin() {
  if (redirectingAfterRestore) return
  redirectingAfterRestore = true
  await auth.logout().catch(() => {})
  await router.push({ name: 'login' })
}

async function afterRestore(result: RestoreResult) {
  if (result.warnings.length > 0) {
    dialog.warning({
      title: '恢复完成，但存在可忽略的警告',
      content: () => h('div', [
        h('p', `当前状态已备份为 ${result.presafe_backup}。以下警告不影响数据：`),
        ...result.warnings.map((warning) => h('p', { style: 'font-size:12px;margin:4px 0' }, warning)),
      ]),
      positiveText: '知道了，重新登录',
      maskClosable: false,
      onPositiveClick: redirectToLogin,
      onClose: redirectToLogin,
    })
    return
  }
  message.success(`恢复完成（当前状态已备份为 ${result.presafe_backup}），请重新登录`)
  await redirectToLogin()
}

async function onRestore(name: string) {
  if (backupBusy.value) return
  restoringBackup.value = name
  try {
    const result = await restoreBackup(name, highRiskConfirmation(`backup:${name}`))
    await afterRestore(result)
  } catch (error) {
    message.error(apiErrorMessage(error, '恢复失败，请重试。'))
  } finally {
    restoringBackup.value = null
    if (!redirectingAfterRestore) void reloadAudit()
  }
}

function onBeforeUploadRestore({ file }: { file: UploadSettledFileInfo }): Promise<boolean> {
  if (backupBusy.value) return Promise.resolve(false)
  if (!file.file) {
    message.error('无法读取所选备份文件，请重新选择。')
    return Promise.resolve(false)
  }

  confirmingUploadRestore.value = true
  return new Promise((resolve) => {
    let settled = false
    const finishConfirmation = (confirmed: boolean) => {
      if (settled) return
      settled = true
      confirmingUploadRestore.value = false
      confirmedUploadRestoreId.value = confirmed ? file.id : null
      uploadRestoreConfirmation.value = confirmed
        ? highRiskConfirmation(`upload:${file.name}`)
        : null
      resolve(confirmed)
    }

    dialog.warning({
      title: '确认上传并恢复备份',
      content: `将使用“${file.name}”覆盖当前所有数据。系统会先自动备份当前状态，恢复后所有用户需要重新登录。`,
      positiveText: '确认恢复',
      negativeText: '取消',
      maskClosable: false,
      onPositiveClick: () => finishConfirmation(true),
      onNegativeClick: () => finishConfirmation(false),
      onClose: () => finishConfirmation(false),
    })
  })
}

async function onUploadRestore({ file, onFinish, onError }: UploadCustomRequestOptions) {
  const confirmation = uploadRestoreConfirmation.value
  if (confirmedUploadRestoreId.value !== file.id || !confirmation || uploadingRestore.value) {
    onError()
    return
  }
  const uploadFile = file.file
  confirmedUploadRestoreId.value = null
  uploadRestoreConfirmation.value = null
  if (!uploadFile) {
    onError()
    message.error('无法读取所选备份文件，请重新选择。')
    return
  }
  uploadingRestore.value = true
  try {
    const result = await restoreUpload(uploadFile, confirmation)
    onFinish()
    await afterRestore(result)
  } catch (error) {
    onError()
    message.error(apiErrorMessage(error, '上传恢复失败，请重试。'))
  } finally {
    uploadingRestore.value = false
    if (!redirectingAfterRestore) void reloadAudit()
  }
}

function openCreateAccount() {
  accountTarget.value = null
  accountForm.value = {
    username: '',
    display_name: '',
    temporary_password: '',
    roles: ['teacher'],
    is_active: true,
  }
  accountShow.value = true
}

function openEditAccount(account: Account) {
  accountTarget.value = account
  accountForm.value = {
    username: account.username,
    display_name: account.display_name,
    temporary_password: '',
    roles: [...account.roles],
    is_active: account.is_active,
  }
  accountShow.value = true
}

function toggleAccountRole(role: AccountRole, checked: boolean) {
  const roles = new Set(accountForm.value.roles)
  if (checked) roles.add(role)
  else roles.delete(role)
  accountForm.value.roles = [...roles] as AccountRole[]
}

async function persistAccount() {
  if (accountSaving.value) return
  accountSaving.value = true
  const target = accountTarget.value
    ? `account:${accountTarget.value.id}`
    : `account:${accountForm.value.username.trim()}`
  try {
    if (accountTarget.value) {
      const body: Parameters<typeof updateAccount>[1] = {
        display_name: accountForm.value.display_name.trim(),
        roles: accountForm.value.roles,
        is_active: accountForm.value.is_active,
        confirmation: highRiskConfirmation(target),
      }
      if (accountForm.value.temporary_password) {
        body.temporary_password = accountForm.value.temporary_password
      }
      await updateAccount(accountTarget.value.id, body)
    } else {
      await createAccount({
        username: accountForm.value.username.trim(),
        display_name: accountForm.value.display_name.trim(),
        temporary_password: accountForm.value.temporary_password,
        roles: accountForm.value.roles,
        confirmation: highRiskConfirmation(target),
      })
    }
    accountShow.value = false
    message.success(accountTarget.value ? '账号设置已更新' : '账号已创建')
    await Promise.all([reloadAccounts(), reloadAudit()])
  } catch (error) {
    message.error(apiErrorMessage(error, '账号操作失败，请重试。'))
  } finally {
    accountSaving.value = false
  }
}

function saveAccount() {
  if (accountSaving.value) return
  if (!accountForm.value.display_name.trim() || !accountForm.value.roles.length) {
    message.warning('请填写显示名称并至少选择一个角色')
    return
  }
  if (!accountTarget.value && (!accountForm.value.username.trim() || accountForm.value.temporary_password.length < 8)) {
    message.warning('新账号需要用户名和至少 8 位临时密码')
    return
  }
  const target = accountTarget.value
    ? `账号 #${accountTarget.value.id}（${accountTarget.value.username}）`
    : `新账号 ${accountForm.value.username.trim()}`
  const impact = accountTarget.value
    ? '将立即改变该账号的角色、启用状态或登录凭据。'
    : `将创建账号并授予：${accountForm.value.roles.map((role) => roleOptions.find((item) => item.value === role)?.label).join('、')}。`
  dialog.warning({
    title: '确认账号与角色变更',
    content: `目标：${target}。影响：${impact}`,
    positiveText: '确认提交',
    negativeText: '取消',
    maskClosable: false,
    onPositiveClick: () => persistAccount(),
  })
}

async function onSaveSchool() {
  if (savingSchool.value) return
  if (!schoolName.value.trim()) {
    message.warning('请输入学校名称')
    return
  }
  savingSchool.value = true
  try {
    schoolName.value = (await saveSchoolSettings({ school_name: schoolName.value.trim() })).school_name
    message.success('学校名称已更新')
  } catch (error) {
    message.error(apiErrorMessage(error, '学校名称保存失败，请重试。'))
  } finally {
    savingSchool.value = false
  }
}

async function onLoadDemo() {
  if (loadingDemo.value) return
  loadingDemo.value = true
  try {
    await chooseOnboardingRoute('demo')
    const result = await loadDemoData()
    schoolName.value = result.school_name
    demoAvailable.value = false
    message.success(
      `已创建 ${result.classes} 个班级、${result.teachers} 名教师和 ${result.assignments} 条教学任务`
      + `（共 ${result.total_periods} 课时），现在可以试用自动排课。`,
      { duration: 8000 },
    )
  } catch (error) {
    message.error(apiErrorMessage(error, '示例数据加载失败，请重试。'))
  } finally {
    loadingDemo.value = false
  }
}

async function onSaveScheduling() {
  if (savingScheduling.value) return
  savingScheduling.value = true
  try {
    const result = await saveSchedulingSettings({ max_overtime: maxOvertime.value })
    maxOvertime.value = result.max_overtime
    message.success('排课设置已保存')
  } catch (error) {
    message.error(apiErrorMessage(error, '排课设置保存失败，请重试。'))
  } finally {
    savingScheduling.value = false
  }
}

async function onSaveSmtp() {
  if (savingSmtp.value) return
  savingSmtp.value = true
  try {
    const result = await saveSmtp(smtp.value)
    configured.value = result.configured
    hasPassword.value = result.has_password
    smtp.value.password = ''
    message.success('SMTP 设置已保存')
  } catch (error) {
    message.error(apiErrorMessage(error, 'SMTP 设置保存失败，请重试。'))
  } finally {
    savingSmtp.value = false
  }
}

async function onResetWizard() {
  if (resettingWizard.value) return
  resettingWizard.value = true
  try {
    await resetWizard()
    await wizard.fetch()
    message.success('设置向导已重新启动')
    await router.push({ name: 'wizard' })
  } catch (error) {
    message.error(apiErrorMessage(error, '设置向导重启失败，请重试。'))
  } finally {
    resettingWizard.value = false
  }
}
</script>

<template>
  <div class="settings-page">
    <header class="settings-page-header">
      <div>
        <p class="settings-eyebrow">{{ '系统配置' }}</p>
        <h1>{{ '系统管理' }}</h1>
        <p>{{ '维护学校信息、通知、排课参数和可恢复的数据快照。' }}</p>
      </div>
      <DatabaseBackup :size="22" class="settings-heading-icon" aria-hidden="true" />
    </header>

    <section v-if="adminLoading" class="settings-state" data-testid="system-loading" role="status" aria-live="polite">
      <RefreshCw :size="21" aria-hidden="true" />
      <strong>{{ '正在读取系统设置' }}</strong>
      <span>{{ '学校、通知、排课参数和备份列表加载完成后会显示在这里。' }}</span>
    </section>

    <section v-else-if="adminError" class="settings-state settings-error" data-testid="system-error" role="alert">
      <AlertTriangle :size="21" aria-hidden="true" />
      <strong>{{ adminError }}</strong>
      <span>{{ '没有修改现有系统设置。' }}</span>
      <n-button type="primary" data-testid="system-retry" @click="loadAdminSettings">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        {{ '重新读取' }}
      </n-button>
    </section>

    <template v-else-if="isAdmin">
      <section class="settings-panel" data-testid="school-card">
        <div class="settings-panel-heading">
          <div>
            <p class="settings-eyebrow">{{ '基础身份' }}</p>
            <h2>{{ '学校信息' }}</h2>
            <p>{{ '学校名称会显示在系统界面、导出的课表、通知邮件和打印公告中。' }}</p>
          </div>
        </div>
        <div class="settings-form-grid settings-form-grid-two">
          <div class="settings-field">
            <label for="school-name">{{ '学校名称' }}</label>
            <n-input id="school-name" v-model:value="schoolName" placeholder="如：海州市启明实验初级中学" data-testid="school-name" />
          </div>
        </div>
        <div class="settings-actions">
          <n-button type="primary" :loading="savingSchool" :disabled="savingSchool" data-testid="school-save" @click="onSaveSchool">
            <template #icon><Save :size="15" aria-hidden="true" /></template>
            {{ '保存学校信息' }}
          </n-button>
        </div>
      </section>

      <section v-if="demoAvailable" class="settings-panel" data-testid="demo-card">
        <div class="settings-panel-heading">
          <div>
            <p class="settings-eyebrow">{{ '试用数据' }}</p>
            <h2>{{ '示例数据' }}</h2>
            <p>{{ `加载虚构学校“${demoSchool || '示例初中'}”，用于体验自动排课和后续流程。` }}</p>
          </div>
        </div>
        <n-alert type="warning" :show-icon="false">{{ '仅可在尚未创建任何学期的全新系统中加载，请勿在正式系统中使用。' }}</n-alert>
        <div class="settings-actions">
          <n-button type="primary" :loading="loadingDemo" :disabled="loadingDemo" data-testid="demo-load" @click="onLoadDemo">
            {{ '加载示例数据' }}
          </n-button>
        </div>
      </section>

      <section class="settings-panel" data-testid="smtp-card">
        <div class="settings-panel-heading">
          <div>
            <p class="settings-eyebrow">{{ '通知渠道' }}</p>
            <h2>{{ '通知邮件（SMTP）' }}</h2>
            <p>{{ '设置后，调课与代课通知会在站内消息之外发送邮件。' }}</p>
          </div>
          <n-tag :type="configured ? 'success' : 'default'" data-testid="smtp-status">{{ configured ? '已设置' : '未设置' }}</n-tag>
        </div>
        <div class="settings-form-grid">
          <div class="settings-field">
            <label for="smtp-host">{{ '主机' }}</label>
            <n-input id="smtp-host" v-model:value="smtp.host" placeholder="smtp.example.com" data-testid="smtp-host" />
          </div>
          <div class="settings-field">
            <label for="smtp-port">{{ '端口' }}</label>
            <n-input-number id="smtp-port" v-model:value="smtp.port" :min="1" :max="65535" />
          </div>
          <div class="settings-field">
            <label for="smtp-sender">{{ '发件人' }}</label>
            <n-input id="smtp-sender" v-model:value="smtp.sender" placeholder="noreply@school.edu.cn" data-testid="smtp-sender" />
          </div>
          <div class="settings-field">
            <label for="smtp-user">{{ '账号' }}</label>
            <n-input id="smtp-user" v-model:value="smtp.user" placeholder="可选" />
          </div>
          <div class="settings-field">
            <label for="smtp-password">{{ '密码' }}</label>
            <n-input id="smtp-password" v-model:value="smtp.password" type="password" :placeholder="hasPassword ? '已设置，留空不变更' : '可选'" />
          </div>
          <div class="settings-field settings-field-checkbox">
            <n-checkbox v-model:checked="smtp.use_tls">{{ '使用 TLS' }}</n-checkbox>
          </div>
        </div>
        <div class="settings-actions">
          <n-button type="primary" :loading="savingSmtp" :disabled="savingSmtp" data-testid="smtp-save" @click="onSaveSmtp">
            <template #icon><Save :size="15" aria-hidden="true" /></template>
            {{ '保存 SMTP 设置' }}
          </n-button>
        </div>
      </section>

      <section class="settings-panel" data-testid="accounts-card">
        <div class="settings-panel-heading">
          <div>
            <p class="settings-eyebrow">{{ '访问控制' }}</p>
            <h2>{{ '账号与角色' }}</h2>
            <p>{{ '维护固定系统角色、账号状态与临时密码。所有变更均需再次确认并写入审计。' }}</p>
          </div>
          <UserCog :size="20" class="settings-heading-icon" aria-hidden="true" />
        </div>
        <div class="settings-actions">
          <n-button type="primary" data-testid="account-add" @click="openCreateAccount">
            <template #icon><Plus :size="15" aria-hidden="true" /></template>
            {{ '新增账号' }}
          </n-button>
          <n-button quaternary @click="reloadAccounts">
            <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
            {{ '刷新' }}
          </n-button>
        </div>
        <div v-if="!accounts.length" class="settings-empty" data-testid="accounts-empty">
          <span class="settings-field-hint">{{ '暂无账号。' }}</span>
        </div>
        <div v-else class="settings-table-scroll">
          <table class="settings-data-table" data-testid="accounts-table">
            <thead>
              <tr>
                <th>{{ '账号' }}</th>
                <th>{{ '显示名称' }}</th>
                <th>{{ '角色' }}</th>
                <th>{{ '状态' }}</th>
                <th>{{ '操作' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="account in accounts" :key="account.id" data-testid="account-row">
                <td><strong>{{ account.username }}</strong></td>
                <td>{{ account.display_name }}</td>
                <td>
                  <div class="settings-command-group">
                    <n-tag v-for="role in account.roles" :key="role" size="small">
                      {{ auth.roleLabel(role) }}
                    </n-tag>
                  </div>
                </td>
                <td>
                  <n-tag :type="account.is_active ? 'success' : 'default'" size="small">
                    {{ account.is_active ? '启用' : '停用' }}
                  </n-tag>
                </td>
                <td>
                  <n-button size="small" :data-testid="`account-edit-${account.id}`" @click="openEditAccount(account)">
                    <template #icon><Pencil :size="14" aria-hidden="true" /></template>
                    {{ '编辑' }}
                  </n-button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="settings-panel" data-testid="backup-card">
        <div class="settings-panel-heading">
          <div>
            <p class="settings-eyebrow">{{ '数据安全' }}</p>
            <h2>{{ '数据备份与恢复' }}</h2>
            <p>{{ '可手动创建、下载、恢复或删除备份。恢复会先保留当前状态，并要求所有用户重新登录。' }}</p>
          </div>
          <DatabaseBackup :size="20" class="settings-heading-icon" aria-hidden="true" />
        </div>
        <div class="settings-actions">
          <n-popconfirm :disabled="backupBusy" @positive-click="onCreateBackup">
            <template #trigger>
              <n-button type="primary" :loading="creatingBackup" :disabled="backupBusy" data-testid="backup-now">
                <template #icon><DatabaseBackup :size="15" aria-hidden="true" /></template>
                {{ '立即备份' }}
              </n-button>
            </template>
            {{ '将创建一份包含当前全部系统数据的手动备份。确定继续吗？' }}
          </n-popconfirm>
          <n-upload
            :custom-request="onUploadRestore"
            :on-before-upload="onBeforeUploadRestore"
            :show-file-list="false"
            accept=".dump"
            :disabled="backupBusy"
          >
            <n-button :loading="uploadingRestore" :disabled="backupBusy" data-testid="backup-upload">
              <template #icon><Upload :size="15" aria-hidden="true" /></template>
              {{ '上传备份并恢复' }}
            </n-button>
          </n-upload>
        </div>
        <div v-if="!backups.length" class="settings-empty" data-testid="backup-empty">
          <span class="settings-field-hint">{{ '暂无备份。' }}</span>
        </div>
        <div v-else class="settings-table-scroll" data-testid="backup-table-scroll">
          <table class="settings-data-table" data-testid="backup-table">
            <thead><tr><th>{{ '时间' }}</th><th>{{ '来源' }}</th><th>{{ '大小' }}</th><th>{{ '操作' }}</th></tr></thead>
            <tbody>
              <tr v-for="backup in backups" :key="backup.name" data-testid="backup-row">
                <td>{{ new Date(backup.created_at).toLocaleString('zh-CN', { hour12: false }) }}</td>
                <td><n-tag size="small">{{ backup.reason_label }}</n-tag></td>
                <td>{{ humanSize(backup.size_bytes) }}</td>
                <td>
                  <div class="settings-command-group">
                    <n-button size="small" :loading="downloadingBackup === backup.name" :disabled="downloadingBackup !== null || backupBusy" @click="onDownloadBackup(backup.name)">
                      <template #icon><Download :size="14" aria-hidden="true" /></template>
                      {{ '下载' }}
                    </n-button>
                    <n-popconfirm :disabled="backupBusy" @positive-click="onRestore(backup.name)">
                      <template #trigger>
                        <n-button size="small" type="warning" data-testid="backup-restore" :loading="restoringBackup === backup.name" :disabled="backupBusy">
                          <template #icon><RefreshCw :size="14" aria-hidden="true" /></template>
                          {{ '恢复' }}
                        </n-button>
                      </template>
                      {{ `将使用备份“${backup.name}”覆盖当前所有数据，系统会先自动备份当前状态，恢复后所有用户需要重新登录。确定继续吗？` }}
                    </n-popconfirm>
                    <n-popconfirm :disabled="backupBusy" @positive-click="onDeleteBackup(backup.name)">
                      <template #trigger>
                        <n-button size="small" type="error" ghost data-testid="backup-delete" :loading="deletingBackup === backup.name" :disabled="backupBusy">
                          <template #icon><Trash2 :size="14" aria-hidden="true" /></template>
                          {{ '删除' }}
                        </n-button>
                      </template>
                      {{ `确定删除备份“${backup.name}”吗？删除后无法恢复。` }}
                    </n-popconfirm>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="settings-panel" data-testid="scheduling-card">
        <div class="settings-panel-heading">
          <div>
            <p class="settings-eyebrow">{{ '排课规则' }}</p>
            <h2>{{ '排课设置' }}</h2>
            <p>{{ '设置教师教学任务最多可超过应授课时的课时数。0 表示不限制。' }}</p>
          </div>
        </div>
        <div class="settings-form-grid settings-form-grid-two">
          <div class="settings-field">
            <label for="max-overtime">{{ '超课时上限（课时）' }}</label>
            <n-input-number id="max-overtime" v-model:value="maxOvertime" :min="0" :max="20" data-testid="max-overtime" />
          </div>
        </div>
        <div class="settings-actions">
          <n-button type="primary" :loading="savingScheduling" :disabled="savingScheduling" data-testid="scheduling-save" @click="onSaveScheduling">
            <template #icon><Save :size="15" aria-hidden="true" /></template>
            {{ '保存排课设置' }}
          </n-button>
        </div>
      </section>

      <section class="settings-panel" data-testid="audit-card">
        <div class="settings-panel-heading">
          <div>
            <p class="settings-eyebrow">{{ '安全追溯' }}</p>
            <h2>{{ '操作审计' }}</h2>
            <p>{{ '查询危险操作的操作者、角色、目标、结果与发生时间。' }}</p>
          </div>
          <ClipboardList :size="20" class="settings-heading-icon" aria-hidden="true" />
        </div>
        <div class="settings-actions">
          <n-input
            v-model:value="auditQuery"
            clearable
            placeholder="搜索操作者、动作、目标或结果"
            aria-label="搜索审计记录"
            data-testid="audit-search"
          />
          <n-button quaternary data-testid="audit-refresh" @click="reloadAudit">
            <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
            {{ '刷新' }}
          </n-button>
        </div>
        <div v-if="!filteredAuditLogs.length" class="settings-empty" data-testid="audit-empty">
          <span class="settings-field-hint">{{ auditQuery ? '没有符合条件的记录。' : '暂无审计记录。' }}</span>
        </div>
        <div v-else class="settings-table-scroll">
          <table class="settings-data-table" data-testid="audit-table">
            <thead>
              <tr>
                <th>{{ '时间' }}</th>
                <th>{{ '操作者 / 角色' }}</th>
                <th>{{ '动作 / 目标' }}</th>
                <th>{{ '结果' }}</th>
                <th>{{ '说明' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in filteredAuditLogs" :key="log.id" data-testid="audit-row">
                <td>{{ new Date(log.created_at).toLocaleString('zh-CN', { hour12: false }) }}</td>
                <td>
                  <strong>{{ log.username }}</strong>
                  <div class="settings-field-hint">{{ log.actor_roles.map((role) => auth.roleLabel(role)).join('、') }}</div>
                </td>
                <td>
                  <strong>{{ auditActionLabel(log.action) }}</strong>
                  <div class="settings-field-hint">{{ log.target_version || `${auditTargetLabel(log.target_type)} #${log.target_id ?? '—'}` }}</div>
                </td>
                <td><n-tag :type="auditResultType(log.result)" size="small">{{ auditResultLabel(log.result) }}</n-tag></td>
                <td>{{ log.detail || log.reason || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <n-modal v-if="isAdmin" v-model:show="accountShow" preset="card" :title="accountTarget ? '编辑账号' : '新增账号'" style="max-width: 520px">
      <div class="settings-modal-form">
        <div class="settings-form-grid settings-form-grid-two">
          <div class="settings-field">
            <label for="account-username">{{ '登录账号' }}</label>
            <n-input
              id="account-username"
              v-model:value="accountForm.username"
              :disabled="accountTarget !== null"
              placeholder="英文字母、数字、点、横线或下划线"
              data-testid="account-username"
            />
          </div>
          <div class="settings-field">
            <label for="account-display-name">{{ '显示名称' }}</label>
            <n-input id="account-display-name" v-model:value="accountForm.display_name" data-testid="account-display-name" />
          </div>
        </div>
        <div class="settings-field">
          <span class="settings-field-label">{{ '角色' }}</span>
          <div class="settings-command-group">
            <n-checkbox
              v-for="option in roleOptions"
              :key="option.value"
              :checked="accountForm.roles.includes(option.value)"
              :data-testid="`account-role-${option.value}`"
              @update:checked="toggleAccountRole(option.value, $event)"
            >
              {{ option.label }}
            </n-checkbox>
          </div>
        </div>
        <div class="settings-field">
          <label for="account-temporary-password">{{ accountTarget ? '重设临时密码（留空不变）' : '临时密码' }}</label>
          <n-input
            id="account-temporary-password"
            v-model:value="accountForm.temporary_password"
            type="password"
            show-password-on="click"
            placeholder="至少 8 位，用户首次登录必须修改"
            data-testid="account-password"
          />
        </div>
        <div v-if="accountTarget" class="settings-field settings-field-checkbox">
          <label><span>{{ '启用账号' }}</span><n-switch v-model:value="accountForm.is_active" data-testid="account-active" /></label>
        </div>
        <div class="settings-modal-actions">
          <n-button :disabled="accountSaving" @click="accountShow = false">{{ '取消' }}</n-button>
          <n-button type="primary" :loading="accountSaving" :disabled="accountSaving" data-testid="account-save" @click="saveAccount">
            <template #icon><Save :size="15" aria-hidden="true" /></template>
            {{ '提交变更' }}
          </n-button>
        </div>
      </div>
    </n-modal>

    <section class="settings-panel settings-danger-panel" data-testid="wizard-reset-card">
      <div class="settings-panel-heading">
        <div>
          <p class="settings-eyebrow">{{ '重新开始' }}</p>
          <h2>{{ '设置向导' }}</h2>
          <p>{{ '重新执行首次设置向导，不会删除现有数据。' }}</p>
        </div>
        <RotateCcw :size="20" aria-hidden="true" />
      </div>
      <div class="settings-actions">
        <n-popconfirm :disabled="resettingWizard" @positive-click="onResetWizard">
          <template #trigger>
            <n-button type="warning" data-testid="reset-wizard" :loading="resettingWizard" :disabled="resettingWizard">
              <template #icon><RotateCcw :size="15" aria-hidden="true" /></template>
              {{ '重新启动设置向导' }}
            </n-button>
          </template>
          {{ '确定重新启动设置向导吗？当前数据不会被删除。' }}
        </n-popconfirm>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-field-checkbox { align-content: center; }
.settings-danger-panel > .settings-panel-heading > svg { color: var(--app-warning); }
</style>
