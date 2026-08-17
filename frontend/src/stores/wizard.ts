import { defineStore } from 'pinia'
import { ref } from 'vue'
import { completeWizard, getWizardState, updateWizardState } from '@/api/wizard'
import type { WizardState } from '@/api/wizard'

export const useWizardStore = defineStore('wizard', () => {
  const state = ref<WizardState | null>(null)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  async function fetch(): Promise<void> {
    error.value = null
    try {
      state.value = await getWizardState()
    } catch {
      state.value = null
      error.value = '无法读取设置向导状态'
    } finally {
      loaded.value = true
    }
  }

  async function patch(body: Parameters<typeof updateWizardState>[0]): Promise<void> {
    error.value = null
    try {
      state.value = await updateWizardState(body)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '无法保存设置向导进度'
      throw e
    }
  }

  async function complete(semesterId: number, acknowledgeWarnings: boolean): Promise<void> {
    error.value = null
    try {
      state.value = await completeWizard(semesterId, acknowledgeWarnings)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '无法完成基础设置'
      throw e
    }
  }

  return { state, loaded, error, fetch, patch, complete }
})
