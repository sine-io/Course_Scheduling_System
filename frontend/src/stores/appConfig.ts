import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface AcademicYearDisplay {
  storage: string
  min: number
  max: number
  label_format: string
  term_labels: Record<string, string>
}

export interface AppConfig {
  school_name: string
  timezone: string
  role_display_names: Record<string, string>
  academic_year: AcademicYearDisplay
}

export const DEFAULT_APP_CONFIG: AppConfig = {
  school_name: '示范学校',
  timezone: 'Asia/Shanghai',
  role_display_names: {
    admin: '系统管理员',
    director: '教务主任',
    scheduler: '排课管理员',
    teacher: '教师',
  },
  academic_year: {
    storage: 'start_year',
    min: 1900,
    max: 2100,
    label_format: '{year}-{next_year}学年{term_label}',
    term_labels: { '1': '第一学期', '2': '第二学期' },
  },
}

export const useAppConfigStore = defineStore('appConfig', () => {
  const config = ref<AppConfig>(DEFAULT_APP_CONFIG)
  const loaded = ref(false)

  async function load(): Promise<void> {
    try {
      const response = await fetch('/api/app-config', { credentials: 'include' })
      if (response.ok) config.value = await response.json() as AppConfig
    } catch {
      // 配置接口不可用时继续使用同一套简体中文默认值。
    } finally {
      loaded.value = true
    }
  }

  return { config, loaded, load }
})
