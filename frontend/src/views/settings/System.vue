<script setup lang="ts">
import {
  NAlert, NButton, NCard, NCheckbox, NInput, NInputNumber, NPopconfirm, NSpace, NTag, NText,
  NUpload, useDialog, useMessage,
} from 'naive-ui'
import type { UploadCustomRequestOptions } from 'naive-ui'
import { h, onMounted, ref } from 'vue'
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

const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const wizard = useWizardStore()
const auth = useAuthStore()

const isAdmin = () => auth.hasRole('admin')

// ── 备份与恢复 ──
const backups = ref<Backup[]>([])
const busy = ref(false)

function humanSize(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

async function reloadBackups() {
  if (!isAdmin()) return
  backups.value = await listBackups()
}

async function onCreateBackup() {
  busy.value = true
  try {
    await createBackup()
    message.success('备份已创建')
    await reloadBackups()
  } catch (e) {
    message.error((e as ApiError).message || '备份失败')
  } finally {
    busy.value = false
  }
}

async function onDeleteBackup(name: string) {
  await deleteBackup(name)
  message.success('备份已删除')
  await reloadBackups()
}

async function redirectToLogin() {
  await auth.logout().catch(() => {})
  router.push({ name: 'login' })
}

async function afterRestore(r: RestoreResult) {
  // 恢复后所有 session 已失效,需重新登录。若有可忽略的警告,先以对话框让管理员看见
  // (信息在导向登录页后会消失,警告不能只用一闪即逝的 toast)。
  if (r.warnings.length > 0) {
    dialog.warning({
      title: '恢复完成，但存在可忽略的警告',
      content: () => h('div', [
        h('p', `当前状态已备份为 ${r.presafe_backup}。以下警告不影响数据，通常来自跨版本设置参数：`),
        ...r.warnings.map((w) => h('p', { style: 'font-size:12px;color:#999;margin:4px 0' }, w)),
      ]),
      positiveText: '知道了，重新登录',
      maskClosable: false,
      onPositiveClick: redirectToLogin,
      onClose: redirectToLogin,
    })
    return
  }
  message.success(`恢复完成（当前状态已备份为 ${r.presafe_backup}），请重新登录`)
  await redirectToLogin()
}

async function onRestore(name: string) {
  busy.value = true
  try {
    const r = await restoreBackup(name)
    await afterRestore(r)
  } catch (e) {
    message.error((e as ApiError).message || '恢复失败')
  } finally {
    busy.value = false
  }
}

async function onUploadRestore({ file, onFinish, onError }: UploadCustomRequestOptions) {
  busy.value = true
  try {
    const r = await restoreUpload(file.file as File)
    onFinish()
    await afterRestore(r)
  } catch (e) {
    onError()
    message.error((e as Error).message || '上传恢复失败')
  } finally {
    busy.value = false
  }
}

const smtp = ref({
  host: '', port: 25, user: '', password: '', sender: '', use_tls: false,
})
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

async function onSaveSchool() {
  if (!schoolName.value.trim()) {
    message.warning('请输入学校名称')
    return
  }
  savingSchool.value = true
  try {
    schoolName.value = (await saveSchoolSettings({ school_name: schoolName.value })).school_name
    message.success('学校名称已更新')
  } catch (e) {
    message.error((e as ApiError).message || '保存失败')
  } finally {
    savingSchool.value = false
  }
}

onMounted(async () => {
  if (!isAdmin()) return
  const [s, scheduling, school, demo] = await Promise.all([
    getSmtp(), getSchedulingSettings(), getSchoolSettings(), demoDataStatus(),
  ])
  smtp.value = { host: s.host, port: s.port, user: s.user, password: '', sender: s.sender, use_tls: s.use_tls }
  configured.value = s.configured
  hasPassword.value = s.has_password
  maxOvertime.value = scheduling.max_overtime
  schoolName.value = school.school_name
  demoAvailable.value = demo.available
  demoSchool.value = demo.school_name
  await reloadBackups()
})

async function onLoadDemo() {
  loadingDemo.value = true
  try {
    const r = await loadDemoData()
    schoolName.value = r.school_name
    demoAvailable.value = false
    message.success(
      `已创建 ${r.classes} 个班级、${r.teachers} 名教师和 ${r.assignments} 条教学任务`
      + `（共 ${r.total_periods} 课时），现在可以试用自动排课。`,
      { duration: 8000 },
    )
  } catch (e) {
    message.error((e as ApiError).message || '加载失败')
  } finally {
    loadingDemo.value = false
  }
}

async function onSaveScheduling() {
  savingScheduling.value = true
  try {
    const s = await saveSchedulingSettings({ max_overtime: maxOvertime.value })
    maxOvertime.value = s.max_overtime
    message.success('排课设置已保存')
  } catch (e) {
    message.error((e as ApiError).message || '保存失败')
  } finally {
    savingScheduling.value = false
  }
}

async function onSaveSmtp() {
  savingSmtp.value = true
  try {
    const s = await saveSmtp(smtp.value)
    configured.value = s.configured
    hasPassword.value = s.has_password
    smtp.value.password = ''
    message.success('SMTP 设置已保存')
  } catch (e) {
    message.error((e as ApiError).message || '保存失败')
  } finally {
    savingSmtp.value = false
  }
}

async function onResetWizard() {
  await resetWizard()
  await wizard.fetch()
  message.success('设置向导已重新启动')
  router.push({ name: 'wizard' })
}
</script>

<template>
  <n-space vertical size="large">
    <h1 style="margin: 0">{{ '系统管理' }}</h1>

    <n-card v-if="isAdmin()" title="学校信息" data-testid="school-card">
      <n-space vertical>
        <n-text depth="3">
          学校名称会显示在系统界面、导出的课表、代课通知邮件和打印公告中，保存后立即生效。
        </n-text>
        <n-space align="center">
          <n-text style="width: 72px">学校名称</n-text>
          <n-input
            v-model:value="schoolName" placeholder="如：海州市启明实验初级中学"
            style="width: 320px" data-testid="school-name"
          />
          <n-button
            type="primary" :loading="savingSchool" data-testid="school-save"
            @click="onSaveSchool"
          >
            保存
          </n-button>
        </n-space>
      </n-space>
    </n-card>

    <n-card v-if="isAdmin() && demoAvailable" title="示例数据" data-testid="demo-card">
      <n-space vertical>
        <n-text depth="3">
          加载虚构的初中示例学校“{{ demoSchool || '示例初中' }}”，自动创建班级、教师、
          科目、教学任务和专用教室，便于直接体验自动排课及后续流程。
        </n-text>
        <n-alert type="warning" :show-icon="false">
          仅可在尚未创建任何学期的全新系统中加载。请勿在正式使用的系统中加载示例数据。
        </n-alert>
        <div>
          <n-button
            type="primary" :loading="loadingDemo"
            data-testid="demo-load" @click="onLoadDemo"
          >
            加载示例数据
          </n-button>
        </div>
      </n-space>
    </n-card>

    <n-card v-if="isAdmin()" :title="'通知邮件（SMTP）'" data-testid="smtp-card">
      <n-space vertical>
        <n-space align="center">
          <n-text depth="3">
            {{ '设置后，调课与代课通知除站内消息外还会发送邮件；未设置时系统仍正常运行，仅发送站内通知。' }}
          </n-text>
          <n-tag :type="configured ? 'success' : 'default'" data-testid="smtp-status">
            {{ configured ? '已设置' : '未设置' }}
          </n-tag>
        </n-space>
        <n-space align="center" :wrap="true">
          <n-text style="width: 72px">{{ '主机' }}</n-text>
          <n-input
            v-model:value="smtp.host" placeholder="smtp.example.com" style="width: 220px"
            data-testid="smtp-host"
          />
          <n-text>{{ '端口' }}</n-text>
          <n-input-number v-model:value="smtp.port" :min="1" :max="65535" style="width: 110px" />
          <n-checkbox v-model:checked="smtp.use_tls">{{ '使用 TLS' }}</n-checkbox>
        </n-space>
        <n-space align="center" :wrap="true">
          <n-text style="width: 72px">{{ '发件人' }}</n-text>
          <n-input
            v-model:value="smtp.sender" placeholder="noreply@school.edu.cn"
            style="width: 220px" data-testid="smtp-sender"
          />
          <n-text>{{ '账号' }}</n-text>
          <n-input v-model:value="smtp.user" :placeholder="'（可选）'" style="width: 160px" />
          <n-text>{{ '密码' }}</n-text>
          <n-input
            v-model:value="smtp.password" type="password"
            :placeholder="hasPassword ? '（已设置，留空不变更）' : '（可选）'" style="width: 160px"
          />
        </n-space>
        <div>
          <n-button
            type="primary" :loading="savingSmtp" data-testid="smtp-save" @click="onSaveSmtp"
          >
            {{ '保存 SMTP 设置' }}
          </n-button>
        </div>
      </n-space>
    </n-card>

    <n-card v-if="isAdmin()" :title="'数据备份与恢复'" data-testid="backup-card">
      <n-space vertical>
        <n-space align="center">
          <n-text depth="3">
            {{ '系统每天凌晨自动备份（保留 30 份）；也可立即备份、下载保存，或上传备份文件恢复。恢复前系统会先自动备份当前状态，恢复后所有人都需重新登录。' }}
          </n-text>
        </n-space>
        <n-space align="center">
          <n-button
            type="primary" :loading="busy" data-testid="backup-now" @click="onCreateBackup"
          >
            {{ '立即备份' }}
          </n-button>
          <n-upload
            :custom-request="onUploadRestore" :show-file-list="false" accept=".dump"
            :disabled="busy"
          >
            <n-button :disabled="busy" data-testid="backup-upload">{{ '上传备份文件并恢复' }}</n-button>
          </n-upload>
        </n-space>

        <n-text v-if="!backups.length" depth="3">{{ '暂无备份。' }}</n-text>
        <table v-else class="data-table" data-testid="backup-table">
          <thead>
            <tr><th>{{ '时间' }}</th><th>{{ '来源' }}</th><th>{{ '大小' }}</th><th>{{ '操作' }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="b in backups" :key="b.name" data-testid="backup-row">
              <td>{{ new Date(b.created_at).toLocaleString('zh-CN', { hour12: false }) }}</td>
              <td><n-tag size="small">{{ b.reason_label }}</n-tag></td>
              <td>{{ humanSize(b.size_bytes) }}</td>
              <td>
                <n-space size="small">
                  <n-button size="tiny" @click="downloadBackup(b.name)">{{ '下载' }}</n-button>
                  <n-popconfirm @positive-click="() => onRestore(b.name)">
                    <template #trigger>
                      <n-button size="tiny" type="warning" data-testid="backup-restore">
                        {{ '恢复' }}
                      </n-button>
                    </template>
                    {{ '恢复将覆盖当前所有数据（系统会先自动备份当前状态），确定吗？' }}
                  </n-popconfirm>
                  <n-popconfirm @positive-click="() => onDeleteBackup(b.name)">
                    <template #trigger>
                      <n-button size="tiny" tertiary>{{ '删除' }}</n-button>
                    </template>
                    {{ '确定删除此备份吗？' }}
                  </n-popconfirm>
                </n-space>
              </td>
            </tr>
          </tbody>
        </table>
      </n-space>
    </n-card>

    <n-card v-if="isAdmin()" title="排课设置" data-testid="scheduling-card">
      <n-space vertical>
        <n-text depth="3">
          超课时上限按学校实际规则设置，表示教师教学任务最多可超过其应授课时的课时数。
        </n-text>
        <n-space align="center">
          <span>超课时上限</span>
          <n-input-number
            v-model:value="maxOvertime" :min="0" :max="20" style="width: 120px"
            data-testid="max-overtime"
          />
          <n-text depth="3">课时（0 表示不限制）</n-text>
        </n-space>
        <n-text depth="3" style="font-size: 12px">
          超过上限的教学任务将无法保存；尚未填写基本课时的教师暂不参与此项校验。
        </n-text>
        <div>
          <n-button
            type="primary" :loading="savingScheduling" data-testid="scheduling-save"
            @click="onSaveScheduling"
          >
            保存排课设置
          </n-button>
        </div>
      </n-space>
    </n-card>

    <n-card :title="'设置向导'">
      <n-space vertical>
        <n-text depth="3">{{ '重新执行首次设置向导（不会删除现有数据）。' }}</n-text>
        <n-popconfirm @positive-click="onResetWizard">
          <template #trigger>
            <n-button>{{ '重新启动设置向导' }}</n-button>
          </template>
          {{ '确定重新启动设置向导吗？' }}
        </n-popconfirm>
      </n-space>
    </n-card>
  </n-space>
</template>

<style scoped>
.data-table { border-collapse: collapse; width: 100%; }
.data-table th, .data-table td {
  border: 1px solid var(--n-border-color, #e0e0e0); padding: 6px 10px; text-align: left;
}
.data-table th { background: rgba(128, 128, 128, 0.08); font-weight: 600; }
</style>
