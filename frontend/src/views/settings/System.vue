<script setup lang="ts">
import {
  AlertTriangle, DatabaseBackup, Download, RefreshCw, RotateCcw, Save, Trash2, Upload,
} from '@lucide/vue'
import {
  NAlert, NButton, NCheckbox, NInput, NInputNumber, NPopconfirm, NTag, NUpload,
  useDialog, useMessage,
} from 'naive-ui'
import type { UploadCustomRequestOptions } from 'naive-ui'
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import {
  createBackup, deleteBackup, downloadBackup, listBackups, restoreBackup, restoreUpload,
} from '@/api/backups'
import type { Backup, RestoreResult } from '@/api/backups'
import {
  demoDataStatus, getSchedulingSettings, getSchoolSettings, loadDemoData,
  saveSchedulingSettings, saveSchoolSettings,
} from '@/api/assignments'
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
const creatingBackup = ref(false)
const restoringBackup = ref<string | null>(null)
const uploadingRestore = ref(false)
const deletingBackup = ref<string | null>(null)
const downloadingBackup = ref<string | null>(null)
const backupBusy = computed(() => (
  creatingBackup.value || restoringBackup.value !== null || uploadingRestore.value || deletingBackup.value !== null
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

function errorMessage(error: unknown, fallback: string): string {
  const value = error as Partial<ApiError> & { message?: string }
  return value?.detail || value?.message || fallback
}

function humanSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

async function loadAdminSettings() {
  if (!isAdmin.value) {
    adminLoading.value = false
    return
  }
  adminLoading.value = true
  adminError.value = null
  try {
    const [smtpSettings, scheduling, school, demo, backupRows] = await Promise.all([
      getSmtp(),
      getSchedulingSettings(),
      getSchoolSettings(),
      demoDataStatus(),
      listBackups(),
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
  } catch (error) {
    adminError.value = errorMessage(error, '暂时无法读取系统设置，请重试。')
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
    message.error(errorMessage(error, '备份列表读取失败，请重试。'))
  }
}

async function onCreateBackup() {
  if (backupBusy.value) return
  creatingBackup.value = true
  try {
    await createBackup()
    message.success('备份已创建')
    await reloadBackups()
  } catch (error) {
    message.error(errorMessage(error, '备份失败，请重试。'))
  } finally {
    creatingBackup.value = false
  }
}

async function onDeleteBackup(name: string) {
  if (backupBusy.value) return
  deletingBackup.value = name
  try {
    await deleteBackup(name)
    message.success('备份已删除')
    await reloadBackups()
  } catch (error) {
    message.error(errorMessage(error, '备份删除失败，请重试。'))
  } finally {
    deletingBackup.value = null
  }
}

async function onDownloadBackup(name: string) {
  if (downloadingBackup.value !== null) return
  downloadingBackup.value = name
  try {
    await downloadBackup(name)
  } catch (error) {
    message.error(errorMessage(error, '备份下载失败，请重试。'))
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
    const result = await restoreBackup(name)
    await afterRestore(result)
  } catch (error) {
    message.error(errorMessage(error, '恢复失败，请重试。'))
  } finally {
    restoringBackup.value = null
  }
}

async function onUploadRestore({ file, onFinish, onError }: UploadCustomRequestOptions) {
  if (backupBusy.value) return
  uploadingRestore.value = true
  try {
    const result = await restoreUpload(file.file as File)
    onFinish()
    await afterRestore(result)
  } catch (error) {
    onError()
    message.error(errorMessage(error, '上传恢复失败，请重试。'))
  } finally {
    uploadingRestore.value = false
  }
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
    message.error(errorMessage(error, '学校名称保存失败，请重试。'))
  } finally {
    savingSchool.value = false
  }
}

async function onLoadDemo() {
  if (loadingDemo.value) return
  loadingDemo.value = true
  try {
    const result = await loadDemoData()
    schoolName.value = result.school_name
    demoAvailable.value = false
    message.success(
      `已创建 ${result.classes} 个班级、${result.teachers} 名教师和 ${result.assignments} 条教学任务`
      + `（共 ${result.total_periods} 课时），现在可以试用自动排课。`,
      { duration: 8000 },
    )
  } catch (error) {
    message.error(errorMessage(error, '示例数据加载失败，请重试。'))
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
    message.error(errorMessage(error, '排课设置保存失败，请重试。'))
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
    message.error(errorMessage(error, 'SMTP 设置保存失败，请重试。'))
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
    message.error(errorMessage(error, '设置向导重启失败，请重试。'))
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
          <n-button type="primary" :loading="creatingBackup" :disabled="backupBusy" data-testid="backup-now" @click="onCreateBackup">
            <template #icon><DatabaseBackup :size="15" aria-hidden="true" /></template>
            {{ '立即备份' }}
          </n-button>
          <n-upload :custom-request="onUploadRestore" :show-file-list="false" accept=".dump" :disabled="backupBusy">
            <n-button :disabled="backupBusy" data-testid="backup-upload">
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
                      {{ '恢复将覆盖当前所有数据，系统会先自动备份当前状态。确定继续吗？' }}
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
    </template>

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
