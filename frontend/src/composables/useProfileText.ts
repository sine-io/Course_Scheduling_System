import { computed, getCurrentInstance } from 'vue'
import type { Pinia } from 'pinia'
import { useAppConfigStore } from '@/stores/appConfig'

/**
 * Profile-aware UI text with a Taiwan-compatible fallback.
 *
 * A few presentational components are mounted directly in unit tests without
 * Pinia.  Falling back here preserves the historical zh-TW rendering in that
 * situation while the real application follows the deployment profile loaded
 * before mount.
 */
export function useProfileText() {
  const pinia = getCurrentInstance()?.appContext.config.globalProperties.$pinia as Pinia | undefined
  const appConfig = pinia ? useAppConfigStore(pinia) : null
  const isMainland = computed(() => appConfig?.isMainland ?? false)
  const tr = (tw: string, mainland: string) => isMainland.value ? mainland : tw

  return { appConfig, isMainland, tr }
}
