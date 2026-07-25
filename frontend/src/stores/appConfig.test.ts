import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useAppConfigStore } from './appConfig'

const mainlandConfig = {
  profile: 'cn_mainland',
  school_profile: 'cn_mainland',
  locale: 'zh-CN',
  language: '简体中文',
  school_name: '天津示范学校',
  timezone: 'Asia/Shanghai',
  tz: 'Asia/Shanghai',
  role_display_names: { admin: '系统管理员', director: '教务主任', scheduler: '教务员', teacher: '教师' },
  roles: { admin: '系统管理员', director: '教务主任', scheduler: '教务员', teacher: '教师' },
  terms: { system_name: '排课与调代课系统', school_calendar: '校历', substitute: '代课', swap: '调课', leave: '请假' },
  academic_year: {
    storage: 'start_year', min: 1900, max: 2100,
    label_format: '{year}-{next_year}学年{term_label}', term_labels: { '1': '第一学期', '2': '第二学期' },
  },
}

afterEach(() => vi.unstubAllGlobals())

describe('app configuration bootstrap', () => {
  it('uses the mainland profile before components mount', async () => {
    setActivePinia(createPinia())
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(mainlandConfig),
    })))

    const store = useAppConfigStore()
    await store.load()

    expect(store.loaded).toBe(true)
    expect(store.isMainland).toBe(true)
    expect(store.config.locale).toBe('zh-CN')
    expect(store.config.academic_year.max).toBe(2100)
  })

  it('keeps the compatible Taiwan fallback when config cannot be loaded', async () => {
    setActivePinia(createPinia())
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))))

    const store = useAppConfigStore()
    await store.load()

    expect(store.loaded).toBe(true)
    expect(store.isMainland).toBe(false)
    expect(store.config.locale).toBe('zh-TW')
  })
})
