import { flushPromises, mount } from '@vue/test-utils'
import { NDialogProvider, NMessageProvider } from 'naive-ui'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import System from './System.vue'
import { useAuthStore } from '@/stores/auth'

const backupMocks = vi.hoisted(() => ({
  createBackup: vi.fn(),
  deleteBackup: vi.fn(),
  downloadBackup: vi.fn(),
  listBackups: vi.fn(),
  restoreBackup: vi.fn(),
  restoreUpload: vi.fn(),
}))
const assignmentMocks = vi.hoisted(() => ({
  demoDataStatus: vi.fn(),
  getSchedulingSettings: vi.fn(),
  getSchoolSettings: vi.fn(),
  loadDemoData: vi.fn(),
  saveSchedulingSettings: vi.fn(),
  saveSchoolSettings: vi.fn(),
}))
const onboardingMocks = vi.hoisted(() => ({
  chooseOnboardingRoute: vi.fn(),
}))
const notificationMocks = vi.hoisted(() => ({
  getSmtp: vi.fn(),
  saveSmtp: vi.fn(),
}))
const wizardMocks = vi.hoisted(() => ({
  resetWizard: vi.fn(),
  getWizardState: vi.fn(),
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
vi.mock('@/api/onboarding', () => ({ ...onboardingMocks }))
vi.mock('@/api/notifications', () => ({ ...notificationMocks }))
vi.mock('@/api/wizard', () => ({ ...wizardMocks }))
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
  demo: { available: false, reason: '', school_name: '' },
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/settings/system', name: 'system', component: System },
      { path: '/wizard', name: 'wizard', component: { template: '<main />' } },
      { path: '/login', name: 'login', component: { template: '<main />' } },
    ],
  })
}

async function mountSystem(role: string, stubs: Record<string, unknown> = {}) {
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
  await router.push('/settings/system')
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
          template: '<span><slot name="trigger" /><button :data-testid="confirmId || \'confirm-reset-wizard\'" @click="$emit(\'positive-click\')">确认</button></span>',
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
    auditMocks.listAuditLogs.mockResolvedValue([])
    assignmentMocks.demoDataStatus.mockResolvedValue(adminSettings.demo)
    assignmentMocks.getSchedulingSettings.mockResolvedValue(adminSettings.scheduling)
    assignmentMocks.getSchoolSettings.mockResolvedValue(adminSettings.school)
    notificationMocks.getSmtp.mockResolvedValue(adminSettings.smtp)
    wizardMocks.getWizardState.mockResolvedValue({ current_step: 0, completed: true, semester_id: null, total_steps: 4, has_semesters: false })
    backupMocks.createBackup.mockResolvedValue(backup)
    backupMocks.deleteBackup.mockResolvedValue({ deleted: backup.name })
    wizardMocks.resetWizard.mockResolvedValue({ current_step: 0, completed: false, semester_id: null, total_steps: 4, has_semesters: false })
    onboardingMocks.chooseOnboardingRoute.mockResolvedValue({
      route: 'demo', demo_available: false, demo_school_name: '示例初中',
      has_demo_semester: false, has_formal_semester: false, can_reselect: true,
      resume_step: 0, resume_semester_id: null,
    })
  })

  it('非管理员保持原有可见性，只显示设置向导且不读取管理员接口', async () => {
    const wrapper = await mountSystem('scheduler')
    await flushPromises()

    expect(wrapper.find('[data-testid="school-card"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="backup-card"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="wizard-reset-card"]').exists()).toBe(true)
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
  })

  it('审计表以简体中文展示和搜索内部代码', async () => {
    auditMocks.listAuditLogs.mockResolvedValue([{
      id: 1,
      operation_id: 'operation-1',
      username: 'scheduler',
      actor_roles: ['scheduler'],
      action: 'delete_subject',
      target_type: 'subject',
      target_id: 23,
      semester_id: 8,
      target_version: '',
      result: 'rejected',
      reason: '权限不足',
      detail: '',
      created_at: '2042-08-01T00:00:00Z',
    }])

    const wrapper = await mountSystem('admin')
    await flushPromises()

    const row = wrapper.get('[data-testid="audit-row"]')
    expect(row.text()).toContain('排课管理员')
    expect(row.text()).toContain('删除科目')
    expect(row.text()).toContain('科目 #23')
    expect(row.text()).toContain('已拒绝')
    expect(row.text()).not.toContain('delete_subject')

    await wrapper.get('[data-testid="audit-search"] input').setValue('删除科目')
    expect(wrapper.find('[data-testid="audit-row"]').exists()).toBe(true)
  })

  it('管理员加载示例数据前先持久化示例路线', async () => {
    assignmentMocks.demoDataStatus.mockResolvedValue({
      available: true, reason: '', school_name: '示例初中',
    })
    assignmentMocks.loadDemoData.mockResolvedValue({
      semester_id: 12, school_name: '示例初中', classes: 18, teachers: 49,
      subjects: 16, rooms: 26, assignments: 252, total_periods: 594,
      max_overtime_used: 0, under_target: 0,
    })
    const wrapper = await mountSystem('admin')
    await flushPromises()

    await wrapper.get('[data-testid="demo-load"]').trigger('click')
    await flushPromises()

    expect(onboardingMocks.chooseOnboardingRoute).toHaveBeenCalledWith('demo')
    expect(assignmentMocks.loadDemoData).toHaveBeenCalledTimes(1)
  })

  it('重启向导进行中时重复确认只发送一次请求', async () => {
    const reset = (() => {
      let resolve!: (value: unknown) => void
      const promise = new Promise((done) => { resolve = done })
      return { promise, resolve }
    })()
    wizardMocks.resetWizard.mockReturnValue(reset.promise)
    const wrapper = await mountSystem('scheduler')
    await flushPromises()

    const confirm = wrapper.get('[data-testid="confirm-reset-wizard"]')
    await confirm.trigger('click')
    await confirm.trigger('click')

    expect(wizardMocks.resetWizard).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="reset-wizard"]').attributes('disabled')).toBeDefined()
    reset.resolve({ current_step: 0, completed: false, semester_id: null, total_steps: 4, has_semesters: false })
    await flushPromises()
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
    })
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
    })
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
    const wrapper = await mountSystem('admin')
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
