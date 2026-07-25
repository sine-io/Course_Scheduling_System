<script setup lang="ts">
import {
  NButton, NCard, NCheckbox, NInput, NInputNumber, NPopconfirm, NSpace, NTag, NText, NUpload,
  useDialog, useMessage,
} from 'naive-ui'
import type { UploadCustomRequestOptions } from 'naive-ui'
import { h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '@/api/client'
import {
  createBackup, deleteBackup, downloadBackup, listBackups, restoreBackup, restoreUpload,
} from '@/api/backups'
import type { Backup, RestoreResult } from '@/api/backups'
import { getSmtp, saveSmtp } from '@/api/notifications'
import { resetWizard } from '@/api/wizard'
import { useProfileText } from '@/composables/useProfileText'
import { useAuthStore } from '@/stores/auth'
import { useWizardStore } from '@/stores/wizard'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const wizard = useWizardStore()
const auth = useAuthStore()
const { isMainland, tr } = useProfileText()

const isAdmin = () => auth.hasRole('admin')

// ── 備份與還原 ──
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
    message.success(tr('已建立備份', '备份已创建'))
    await reloadBackups()
  } catch (e) {
    message.error((e as ApiError).message || tr('備份失敗', '备份失败'))
  } finally {
    busy.value = false
  }
}

async function onDeleteBackup(name: string) {
  await deleteBackup(name)
  message.success(tr('已刪除備份', '备份已删除'))
  await reloadBackups()
}

async function redirectToLogin() {
  await auth.logout().catch(() => {})
  router.push({ name: 'login' })
}

async function afterRestore(r: RestoreResult) {
  // 還原後所有 session 已失效,需重新登入。若有可忽略的警告,先以對話框讓管理員看見
  // (訊息在導向登入頁後會消失,警告不能只用一閃即逝的 toast)。
  if (r.warnings.length > 0) {
    dialog.warning({
      title: tr('還原完成,但有可忽略的警告', '恢复完成，但存在可忽略的警告'),
      content: () => h('div', [
        h('p', tr(
          `現狀已備份為 ${r.presafe_backup}。以下警告不影響資料,通常為跨版本的設定參數:`,
          `当前状态已备份为 ${r.presafe_backup}。以下警告不影响资料，通常来自跨版本设置参数：`,
        )),
        ...r.warnings.map((w) => h('p', { style: 'font-size:12px;color:#999;margin:4px 0' }, w)),
      ]),
      positiveText: tr('知道了,重新登入', '知道了，重新登录'),
      maskClosable: false,
      onPositiveClick: redirectToLogin,
      onClose: redirectToLogin,
    })
    return
  }
  message.success(tr(
    `還原完成(現狀已備份為 ${r.presafe_backup}),請重新登入`,
    `恢复完成（当前状态已备份为 ${r.presafe_backup}），请重新登录`,
  ))
  await redirectToLogin()
}

async function onRestore(name: string) {
  busy.value = true
  try {
    const r = await restoreBackup(name)
    await afterRestore(r)
  } catch (e) {
    message.error((e as ApiError).message || tr('還原失敗', '恢复失败'))
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
    message.error((e as Error).message || tr('上傳還原失敗', '上传恢复失败'))
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

onMounted(async () => {
  if (!isAdmin()) return
  const s = await getSmtp()
  smtp.value = { host: s.host, port: s.port, user: s.user, password: '', sender: s.sender, use_tls: s.use_tls }
  configured.value = s.configured
  hasPassword.value = s.has_password
  await reloadBackups()
})

async function onSaveSmtp() {
  savingSmtp.value = true
  try {
    const s = await saveSmtp(smtp.value)
    configured.value = s.configured
    hasPassword.value = s.has_password
    smtp.value.password = ''
    message.success(tr('已儲存 SMTP 設定', 'SMTP 设置已保存'))
  } catch (e) {
    message.error((e as ApiError).message || tr('儲存失敗', '保存失败'))
  } finally {
    savingSmtp.value = false
  }
}

async function onResetWizard() {
  await resetWizard()
  await wizard.fetch()
  message.success(tr('已重新啟動設定精靈', '设置向导已重新启动'))
  router.push({ name: 'wizard' })
}
</script>

<template>
  <n-space vertical size="large">
    <h1 style="margin: 0">{{ tr('系統管理', '系统管理') }}</h1>

    <n-card v-if="isAdmin()" :title="tr('通知信件(SMTP)', '通知邮件（SMTP）')" data-testid="smtp-card">
      <n-space vertical>
        <n-space align="center">
          <n-text depth="3">
            {{ tr('設定後,調代課通知除站內外會加寄 Email;未設定時系統照常運作,僅站內通知。', '设置后，调代课通知除站内消息外还会发送邮件；未设置时系统仍正常运行，仅发送站内通知。') }}
          </n-text>
          <n-tag :type="configured ? 'success' : 'default'" data-testid="smtp-status">
            {{ configured ? tr('已設定', '已设置') : tr('未設定', '未设置') }}
          </n-tag>
        </n-space>
        <n-space align="center" :wrap="true">
          <n-text style="width: 72px">{{ tr('主機', '主机') }}</n-text>
          <n-input
            v-model:value="smtp.host" placeholder="smtp.example.com" style="width: 220px"
            data-testid="smtp-host"
          />
          <n-text>{{ tr('連接埠', '端口') }}</n-text>
          <n-input-number v-model:value="smtp.port" :min="1" :max="65535" style="width: 110px" />
          <n-checkbox v-model:checked="smtp.use_tls">{{ tr('使用 TLS', '使用 TLS') }}</n-checkbox>
        </n-space>
        <n-space align="center" :wrap="true">
          <n-text style="width: 72px">{{ tr('寄件人', '发件人') }}</n-text>
          <n-input
            v-model:value="smtp.sender" placeholder="noreply@school.edu.tw"
            style="width: 220px" data-testid="smtp-sender"
          />
          <n-text>{{ tr('帳號', '账号') }}</n-text>
          <n-input v-model:value="smtp.user" :placeholder="tr('(選填)', '（可选）')" style="width: 160px" />
          <n-text>{{ tr('密碼', '密码') }}</n-text>
          <n-input
            v-model:value="smtp.password" type="password"
            :placeholder="hasPassword ? tr('(已設定,留空不變更)', '（已设置，留空不变更）') : tr('(選填)', '（可选）')" style="width: 160px"
          />
        </n-space>
        <div>
          <n-button
            type="primary" :loading="savingSmtp" data-testid="smtp-save" @click="onSaveSmtp"
          >
            {{ tr('儲存 SMTP 設定', '保存 SMTP 设置') }}
          </n-button>
        </div>
      </n-space>
    </n-card>

    <n-card v-if="isAdmin()" :title="tr('資料備份與還原', '资料备份与恢复')" data-testid="backup-card">
      <n-space vertical>
        <n-space align="center">
          <n-text depth="3">
            {{ tr('每日凌晨自動備份(保留 30 份);也可立即備份、下載保存,或上傳備份檔還原。還原前系統會自動先備份現狀,還原後所有人需重新登入。', '系统每天凌晨自动备份（保留 30 份）；也可立即备份、下载保存，或上传备份文件恢复。恢复前系统会先自动备份当前状态，恢复后所有人都需重新登录。') }}
          </n-text>
        </n-space>
        <n-space align="center">
          <n-button
            type="primary" :loading="busy" data-testid="backup-now" @click="onCreateBackup"
          >
            {{ tr('立即備份', '立即备份') }}
          </n-button>
          <n-upload
            :custom-request="onUploadRestore" :show-file-list="false" accept=".dump"
            :disabled="busy"
          >
            <n-button :disabled="busy" data-testid="backup-upload">{{ tr('上傳備份檔並還原', '上传备份文件并恢复') }}</n-button>
          </n-upload>
        </n-space>

        <n-text v-if="!backups.length" depth="3">{{ tr('尚無備份。', '暂无备份。') }}</n-text>
        <table v-else class="data-table" data-testid="backup-table">
          <thead>
            <tr><th>{{ tr('時間', '时间') }}</th><th>{{ tr('來源', '来源') }}</th><th>{{ tr('大小', '大小') }}</th><th>{{ tr('操作', '操作') }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="b in backups" :key="b.name" data-testid="backup-row">
              <td>{{ new Date(b.created_at).toLocaleString(isMainland ? 'zh-CN' : 'zh-TW', { hour12: false }) }}</td>
              <td><n-tag size="small">{{ b.reason_label }}</n-tag></td>
              <td>{{ humanSize(b.size_bytes) }}</td>
              <td>
                <n-space size="small">
                  <n-button size="tiny" @click="downloadBackup(b.name)">{{ tr('下載', '下载') }}</n-button>
                  <n-popconfirm @positive-click="() => onRestore(b.name)">
                    <template #trigger>
                      <n-button size="tiny" type="warning" data-testid="backup-restore">
                        {{ tr('還原', '恢复') }}
                      </n-button>
                    </template>
                    {{ tr('還原將覆蓋目前所有資料(現狀會先自動備份),確定?', '恢复将覆盖当前所有资料（系统会先自动备份当前状态），确定吗？') }}
                  </n-popconfirm>
                  <n-popconfirm @positive-click="() => onDeleteBackup(b.name)">
                    <template #trigger>
                      <n-button size="tiny" tertiary>{{ tr('刪除', '删除') }}</n-button>
                    </template>
                    {{ tr('確定刪除此備份?', '确定删除此备份吗？') }}
                  </n-popconfirm>
                </n-space>
              </td>
            </tr>
          </tbody>
        </table>
      </n-space>
    </n-card>

    <n-card :title="tr('設定精靈', '设置向导')">
      <n-space vertical>
        <n-text depth="3">{{ tr('重新執行首次設定的引導流程(不會刪除既有資料)。', '重新执行首次设置向导（不会删除现有资料）。') }}</n-text>
        <n-popconfirm @positive-click="onResetWizard">
          <template #trigger>
            <n-button>{{ tr('重新啟動設定精靈', '重新启动设置向导') }}</n-button>
          </template>
          {{ tr('確定重新啟動設定精靈?', '确定重新启动设置向导吗？') }}
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
