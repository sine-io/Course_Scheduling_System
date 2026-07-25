import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export interface AcademicYearDisplay {
  storage: string
  min: number
  max: number
  label_format: string
  term_labels: Record<string, string>
}

export interface AppConfig {
  profile: 'tw_k12' | 'cn_mainland' | string
  school_profile: string
  locale: string
  language: string
  school_name: string
  timezone: string
  tz: string
  role_display_names: Record<string, string>
  roles: Record<string, string>
  terms: Record<string, string>
  academic_year: AcademicYearDisplay
}

const TW_FALLBACK: AppConfig = {
  profile: 'tw_k12', school_profile: 'tw_k12', locale: 'zh-TW', language: '繁體中文',
  school_name: '示範學校', timezone: 'Asia/Taipei', tz: 'Asia/Taipei',
  role_display_names: {
    admin: '系統管理員', director: '教務主任', scheduler: '教學組長', teacher: '教師',
  },
  roles: {
    admin: '系統管理員', director: '教務主任', scheduler: '教學組長', teacher: '教師',
  },
  terms: {
    system_name: '排課與調代課系統', school_calendar: '校曆',
    substitute: '代課', swap: '調課', leave: '請假',
  },
  academic_year: {
    storage: 'start_year', min: 100, max: 200,
    label_format: '民國{year}學年度第{term}學期', term_labels: { '1': '第 1 學期', '2': '第 2 學期' },
  },
}

export const useAppConfigStore = defineStore('appConfig', () => {
  const config = ref<AppConfig>(TW_FALLBACK)
  const loaded = ref(false)
  const isMainland = computed(() => config.value.profile === 'cn_mainland')

  async function load(): Promise<void> {
    try {
      const response = await fetch('/api/app-config', { credentials: 'include' })
      if (response.ok) config.value = await response.json() as AppConfig
    } catch {
      // The app remains usable with the historical Taiwan defaults when the API is unavailable.
    } finally {
      loaded.value = true
    }
  }

  return { config, loaded, isMainland, load }
})
