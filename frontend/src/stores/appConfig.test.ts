import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useAppConfigStore } from './appConfig'

const serverConfig = {
  school_name: '示范学校',
  timezone: 'Asia/Shanghai',
  role_display_names: {
    admin: '系统管理员', director: '教务主任', scheduler: '排课管理员', teacher: '教师',
  },
  academic_year: {
    storage: 'start_year', min: 1900, max: 2100,
    label_format: '{year}-{next_year}学年{term_label}',
    term_labels: { '1': '第一学期', '2': '第二学期' },
  },
}

afterEach(() => vi.unstubAllGlobals())

describe('应用配置启动加载', () => {
  it('加载精简后的公开配置', async () => {
    setActivePinia(createPinia())
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(serverConfig),
    })))

    const store = useAppConfigStore()
    await store.load()

    expect(store.loaded).toBe(true)
    expect(store.config).toEqual(serverConfig)
    expect(store.config.role_display_names.scheduler).toBe('排课管理员')
  })

  it('配置接口不可用时仍使用简体中文和上海时区', async () => {
    setActivePinia(createPinia())
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))))

    const store = useAppConfigStore()
    await store.load()

    expect(store.loaded).toBe(true)
    expect(store.config.school_name).toBe('示范学校')
    expect(store.config.timezone).toBe('Asia/Shanghai')
    expect(store.config.academic_year.min).toBe(1900)
  })
})
