import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { NDialogProvider, NMessageProvider } from 'naive-ui'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import System from './System.vue'
import { useAuthStore } from '@/stores/auth'

enableAutoUnmount(afterEach)

const backupMocks = vi.hoisted(() => ({
  createBackup: vi.fn(),
  deleteBackup: vi.fn(),
  downloadBackup: vi.fn(),
  listBackups: vi.fn(),
  restoreBackup: vi.fn(),
  restoreUpload: vi.fn(),
}))
const assignmentMocks = vi.hoisted(() => ({
  getSchedulingSettings: vi.fn(),
  getSchoolSettings: vi.fn(),
  saveSchedulingSettings: vi.fn(),
  saveSchoolSettings: vi.fn(),
}))
const notificationMocks = vi.hoisted(() => ({
  getSmtp: vi.fn(),
  saveSmtp: vi.fn(),
}))
const accountMocks = vi.hoisted(() => ({
  createAccount: vi.fn(),
  listAccounts: vi.fn(),
  updateAccount: vi.fn(),
}))
const auditMocks = vi.hoisted(() => ({
  listAuditLogs: vi.fn(),
}))

vi.mock('@/api/backups', () => ({ ...backupMocks }))
vi.mock('@/api/assignments', () => ({ ...assignmentMocks }))
vi.mock('@/api/notifications', () => ({ ...notificationMocks }))
vi.mock('@/api/accounts', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/api/accounts')>(),
  ...accountMocks,
}))
vi.mock('@/api/audit', () => ({ ...auditMocks }))

const backup = {
  name: 'backup-1.dump',
  size_bytes: 1024,
  created_at: '2042-08-01T00:00:00Z',
  reason: 'manual',
  reason_label: '手动备份',
}
const adminSettings = {
  smtp: { host: '', port: 25, user: '', sender: '', use_tls: false, configured: false, has_password: false },
  scheduling: { max_overtime: 8 },
  school: { school_name: '测试学校' },
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/settings/system', name: 'system', component: System },
      { path: '/settings/backup', name: 'backup', component: System },
      { path: '/settings/accounts', name: 'account-permissions', component: System },
      { path: '/login', name: 'login', component: { template: '<main />' } },
    ],
  })
}

async function mountSystem(role: string, stubs: Record<string, unknown> = {}, path = '/settings/system') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore(pinia)
  auth.user = {
    id: 1,
    username: 'test-user',
    display_name: '测试用户',
    roles: [role],
    must_change_password: false,
  }
  const router = makeRouter()
  await router.push(path)
  await router.isReady()
  const Host = {
    render: () => h(NMessageProvider, null, {
      default: () => h(NDialogProvider, null, { default: () => h(System) }),
    }),
  }
  return mount(Host, {
    global: {
      plugins: [pinia, router],
      stubs: {
        Popconfirm: {
          emits: ['positive-click'],
          props: ['confirmId'],
          template: '<span><slot name="trigger" /><button :data-testid="confirmId || \'confirm-action\'" @click="$emit(\'positive-click\')">确认</button></span>',
        },
        ...stubs,
      },
    },
  })
}

describe('System', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    backupMocks.listBackups.mockResolvedValue([])
    accountMocks.listAccounts.mockResolvedValue([])
    auditMocks.listAuditLogs.mockResolvedValue({
      items: [], total: 0, page: 1, page_size: 20,
    })
    assignmentMocks.getSchedulingSettings.mockResolvedValue(adminSettings.scheduling)
    assignmentMocks.getSchoolSettings.mockResolvedValue(adminSettings.school)
    notificationMocks.getSmtp.mockResolvedValue(adminSettings.smtp)
    backupMocks.createBackup.mockResolvedValue(backup)
    backupMocks.deleteBackup.mockResolvedValue({ deleted: backup.name })
  })

  it('非管理员不显示系统管理内容且不读取管理员接口', async () => {
    const wrapper = await mountSystem('director')
    await flushPromises()

    expect(wrapper.find('[data-testid="school-card"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="backup-card"]').exists()).toBe(false)
    expect(notificationMocks.getSmtp).not.toHaveBeenCalled()
    expect(backupMocks.listBackups).not.toHaveBeenCalled()
  })

  it('管理员设置读取失败时保留页面并提供重试', async () => {
    let attempts = 0
    notificationMocks.getSmtp.mockImplementation(() => {
      attempts += 1
      return attempts === 1 ? Promise.reject({ detail: 'SMTP 服务暂时不可用' }) : Promise.resolve(adminSettings.smtp)
    })

    const wrapper = await mountSystem('admin')
    await flushPromises()
    expect(wrapper.get('[data-testid="system-error"]').text()).toContain('SMTP 服务暂时不可用')

    await wrapper.get('[data-testid="system-retry"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="system-error"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="school-card"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="demo-card"]').exists()).toBe(false)
  })

  it('备份恢复页面只读取备份数据', async () => {
    backupMocks.listBackups.mockResolvedValue([backup])
    const wrapper = await mountSystem('admin', {}, '/settings/backup')
    await flushPromises()

    expect(wrapper.find('[data-testid="backup-card"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="school-card"]').exists()).toBe(false)
    expect(backupMocks.listBackups).toHaveBeenCalledTimes(1)
    expect(accountMocks.listAccounts).not.toHaveBeenCalled()
    expect(notificationMocks.getSmtp).not.toHaveBeenCalled()
    expect(auditMocks.listAuditLogs).not.toHaveBeenCalled()
  })

  it('账号权限页面只读取账号数据', async () => {
    accountMocks.listAccounts.mockResolvedValue([{
      id: 7,
      username: 'operator',
      display_name: '操作员',
      roles: ['director'],
      is_active: true,
      must_change_password: false,
      last_login_at: null,
      auth_provider: 'local',
      is_builtin: false,
    }])
    const wrapper = await mountSystem('admin', {}, '/settings/accounts')
    await flushPromises()

    expect(wrapper.find('[data-testid="accounts-card"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="backup-card"]').exists()).toBe(false)
    expect(accountMocks.listAccounts).toHaveBeenCalledTimes(1)
    expect(backupMocks.listBackups).not.toHaveBeenCalled()
    expect(notificationMocks.getSmtp).not.toHaveBeenCalled()
    expect(auditMocks.listAuditLogs).not.toHaveBeenCalled()
  })

  it('新增账号不提供系统管理员角色', async () => {
    const wrapper = await mountSystem('admin', {}, '/settings/accounts')
    await flushPromises()

    await wrapper.get('[data-testid="account-add"]').trigger('click')
    await flushPromises()

    expect(document.body.querySelector('[data-testid="account-role-admin"]')).toBeNull()
    expect(document.body.querySelector('[data-testid="account-role-teacher"]')).not.toBeNull()
  })

  it('账号列表显示内置系统管理员并禁用编辑', async () => {
    accountMocks.listAccounts.mockResolvedValue([{
      id: 1,
      username: 'admin',
      display_name: '系统管理员',
      roles: ['admin'],
      is_active: true,
      must_change_password: false,
      auth_provider: 'local',
      is_builtin: true,
    }])
    const wrapper = await mountSystem('admin', {}, '/settings/accounts')
    await flushPromises()

    expect(wrapper.get('[data-testid="account-row"]').text()).toContain('内置账号')
    const edit = wrapper.get('[data-testid="account-edit-1"]')
    expect(edit.attributes('disabled')).toBeDefined()
    expect(edit.attributes('title')).toBe('内置账号不可编辑')
  })

  it('确认提交使用蓝色主按钮并在请求期间只允许一次提交', async () => {
    let resolve!: (value: unknown) => void
    const pending = new Promise((done) => { resolve = done })
    accountMocks.createAccount.mockReturnValue(pending)
    const wrapper = await mountSystem('admin', {}, '/settings/accounts')
    await flushPromises()

    await wrapper.get('[data-testid="account-add"]').trigger('click')
    await flushPromises()
    const username = document.body.querySelector('[data-testid="account-username"] input') as HTMLInputElement
    const displayName = document.body.querySelector('[data-testid="account-display-name"] input') as HTMLInputElement
    const password = document.body.querySelector('[data-testid="account-password"] input') as HTMLInputElement
    username.value = 'confirm-account'
    username.dispatchEvent(new Event('input', { bubbles: true }))
    displayName.value = '确认账号'
    displayName.dispatchEvent(new Event('input', { bubbles: true }))
    password.value = 'temporary123'
    password.dispatchEvent(new Event('input', { bubbles: true }))
    await wrapper.vm.$nextTick()
    ;(document.body.querySelector('[data-testid="account-save"]') as HTMLButtonElement).click()
    await flushPromises()

    const dialog = Array.from(document.body.querySelectorAll<HTMLElement>('[role="dialog"]'))
      .filter((item) => item.textContent?.includes('确认账号与角色变更')).at(-1)
    expect(dialog).toBeDefined()
    const positive = Array.from(dialog?.querySelectorAll('button') ?? [])
      .find((item) => item.textContent?.includes('确认提交')) as HTMLButtonElement
    expect(positive.className).toContain('n-button--primary-type')

    positive.click()
    await flushPromises()
    expect(accountMocks.createAccount).toHaveBeenCalledTimes(1)
    expect(positive.disabled).toBe(true)

    positive.click()
    expect(accountMocks.createAccount).toHaveBeenCalledTimes(1)
    resolve({
      id: 9,
      username: 'confirm-account',
      display_name: '确认账号',
      roles: ['teacher'],
      is_active: true,
      must_change_password: true,
      auth_provider: 'local',
      is_builtin: false,
    })
    await flushPromises()
  })

  it('审计表以简体中文展示和搜索内部代码', async () => {
    const auditLog = {
      id: 1,
      operation_id: 'operation-1',
      username: 'director',
      actor_roles: ['director'],
      action: 'delete_subject',
      target_type: 'subject',
      target_id: 23,
      semester_id: 8,
      target_version: '',
      result: 'rejected',
      reason: '权限不足',
      detail: '',
      created_at: '2042-08-01T00:00:00Z',
    }
    auditMocks.listAuditLogs.mockImplementation(({ q = '', page = 1, pageSize = 20 } = {}) => (
      Promise.resolve({
        items: !q || q === '删除科目' ? [auditLog] : [],
        total: !q || q === '删除科目' ? 1 : 0,
        page,
        page_size: pageSize,
      })
    ))

    const wrapper = await mountSystem('admin')
    await flushPromises()

    const row = wrapper.get('[data-testid="audit-row"]')
    expect(row.text()).toContain('教务主任')
    expect(row.text()).toContain('删除科目')
    expect(row.text()).toContain('科目 #23')
    expect(row.text()).toContain('已拒绝')
    expect(row.text()).not.toContain('delete_subject')
    expect(wrapper.get('[data-testid="audit-pagination-total"]').text()).toContain('共 1 条')

    await wrapper.get('[data-testid="audit-search"] input').setValue('删除科目')
    await wrapper.get('[data-testid="audit-search"] input').trigger('keyup.enter')
    await flushPromises()
    expect(auditMocks.listAuditLogs).toHaveBeenLastCalledWith({
      page: 1,
      pageSize: 20,
      q: '删除科目',
    })
    expect(wrapper.find('[data-testid="audit-row"]').exists()).toBe(true)
  })

  it('审计关键词停顿 400ms 后自动查询并回到第一页', async () => {
    auditMocks.listAuditLogs.mockImplementation(({ page = 1, pageSize = 20 } = {}) => (
      Promise.resolve({ items: [], total: 100, page, page_size: pageSize })
    ))
    const wrapper = await mountSystem('admin', {}, '/settings/system?audit_page=3')
    await flushPromises()
    expect(auditMocks.listAuditLogs).toHaveBeenCalledTimes(1)

    vi.useFakeTimers()
    try {
      await wrapper.get('[data-testid="audit-search"] input').setValue('alice')
      await vi.advanceTimersByTimeAsync(399)
      expect(auditMocks.listAuditLogs).toHaveBeenCalledTimes(1)

      await vi.advanceTimersByTimeAsync(1)
      await flushPromises()
      expect(auditMocks.listAuditLogs).toHaveBeenLastCalledWith({
        page: 1,
        pageSize: 20,
        q: 'alice',
      })
    } finally {
      vi.useRealTimers()
    }
  })

  it('审计读取失败不影响其他系统设置，并可在审计区域重试', async () => {
    auditMocks.listAuditLogs
      .mockRejectedValueOnce({ detail: '审计查询暂时不可用' })
      .mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20 })

    const wrapper = await mountSystem('admin')
    await flushPromises()

    expect(wrapper.find('[data-testid="school-card"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="system-error"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="audit-error"]').text()).toContain('审计查询暂时不可用')

    await wrapper.get('[data-testid="audit-retry"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="audit-error"]').exists()).toBe(false)
    expect(auditMocks.listAuditLogs).toHaveBeenCalledTimes(2)
  })

  it('恢复备份进行中时重复确认只发送一次请求', async () => {
    const restore = (() => {
      let resolve!: (value: unknown) => void
      const promise = new Promise((done) => { resolve = done })
      return { promise, resolve }
    })()
    backupMocks.listBackups.mockResolvedValue([backup])
    backupMocks.restoreBackup.mockReturnValue(restore.promise)
    const wrapper = await mountSystem('admin', {
      Popconfirm: {
        emits: ['positive-click'],
        template: '<span><slot name="trigger" /><button data-testid="confirm-backup-action" @click="$emit(\'positive-click\')">确认</button></span>',
      },
    }, '/settings/backup')
    await flushPromises()

    const confirmations = wrapper.findAll('[data-testid="confirm-backup-action"]')
    await confirmations[1].trigger('click')
    await confirmations[1].trigger('click')

    expect(backupMocks.restoreBackup).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="backup-restore"]').attributes('disabled')).toBeDefined()
    restore.resolve({ presafe_backup: 'presafe.dump', warnings: [] })
    await flushPromises()
  })

  it('删除备份失败后解除进行中状态并允许重试', async () => {
    backupMocks.listBackups.mockResolvedValue([backup])
    backupMocks.deleteBackup
      .mockRejectedValueOnce({ detail: '备份删除失败' })
      .mockResolvedValueOnce({ deleted: backup.name })
    const wrapper = await mountSystem('admin', {
      Popconfirm: {
        emits: ['positive-click'],
        template: '<span><slot name="trigger" /><button data-testid="confirm-backup-action" @click="$emit(\'positive-click\')">确认</button></span>',
      },
    }, '/settings/backup')
    await flushPromises()

    const confirmations = wrapper.findAll('[data-testid="confirm-backup-action"]')
    await confirmations[2].trigger('click')
    await flushPromises()
    await confirmations[2].trigger('click')
    await flushPromises()

    expect(backupMocks.deleteBackup).toHaveBeenCalledTimes(2)
  })

  it('上传备份需确认，进行中不重复恢复且失败后可重试', async () => {
    const firstRestore = (() => {
      let reject!: (reason: unknown) => void
      const promise = new Promise((_, fail) => { reject = fail })
      return { promise, reject }
    })()
    backupMocks.restoreUpload
      .mockReturnValueOnce(firstRestore.promise)
      .mockRejectedValueOnce({ detail: '上传恢复失败' })
    const wrapper = await mountSystem('admin', {}, '/settings/backup')
    await flushPromises()

    async function chooseBackup(name: string) {
      const input = wrapper.get('input[type="file"]')
      Object.defineProperty(input.element, 'files', {
        configurable: true,
        value: [new File(['backup'], name, { type: 'application/octet-stream' })],
      })
      await input.trigger('change')
      await flushPromises()
    }

    function confirmationButton(): HTMLButtonElement {
      const dialogs = Array.from(document.body.querySelectorAll<HTMLElement>('[role="dialog"]'))
      const confirmation = dialogs
        .filter((element) => element.textContent?.includes('确认上传并恢复备份'))
        .at(-1)
      const button = Array.from(confirmation?.querySelectorAll('button') ?? [])
        .find((element) => element.textContent?.includes('确认恢复'))
      if (!(button instanceof HTMLButtonElement)) throw new Error('未找到上传恢复确认按钮')
      return button
    }

    await chooseBackup('first.dump')
    expect(backupMocks.restoreUpload).not.toHaveBeenCalled()

    const firstConfirmation = confirmationButton()
    firstConfirmation.click()
    firstConfirmation.click()
    await flushPromises()
    expect(backupMocks.restoreUpload).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="backup-upload"]').attributes('disabled')).toBeDefined()

    firstRestore.reject({ detail: '上传恢复失败' })
    await flushPromises()
    expect(wrapper.get('[data-testid="backup-upload"]').attributes('disabled')).toBeUndefined()

    await chooseBackup('retry.dump')
    confirmationButton().click()
    await flushPromises()
    expect(backupMocks.restoreUpload).toHaveBeenCalledTimes(2)
  })
})
