import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { apiErrorMessage, type ApiError } from '@/api/client'
import {
  getSemesterContext,
  listSemesters,
  switchSemesterContext,
} from '@/api/semesters'
import type { SemesterContext, SemesterListItem } from '@/api/semesters'

/**
 * The server owns the current semester.  This store is deliberately small:
 * it keeps the toolbar and mounted workspaces on the same revision, while
 * historical semesters remain available as read-only query targets.
 */
export const useSemesterContextStore = defineStore('semesterContext', () => {
  const currentSemester = ref<SemesterListItem | null>(null)
  const semesters = ref<SemesterListItem[]>([])
  const revision = ref(0)
  const canSwitch = ref(false)
  const loaded = ref(false)
  const authoritative = ref(false)
  const loading = ref(false)
  const switching = ref(false)
  const error = ref<string | null>(null)
  let loadPromise: Promise<void> | null = null

  const currentSemesterId = computed(() => currentSemester.value?.id ?? null)

  function applyContext(context: SemesterContext): void {
    currentSemester.value = context.current_semester
    revision.value = context.revision
    canSwitch.value = context.can_switch
    if (!context.can_switch) {
      semesters.value = context.current_semester ? [context.current_semester] : []
    }
  }

  function applyLegacyFallback(items: SemesterListItem[]): void {
    semesters.value = items
    const current = items.find((item) => item.is_current)
      ?? items.find((item) => item.status === 'active')
      ?? items[0]
    currentSemester.value = current ?? null
    revision.value = 0
    // A backend without /semester-context also has no authoritative switch API.
    // Keep the compatibility view readable without presenting a write control.
    canSwitch.value = false
    authoritative.value = false
  }

  async function load(): Promise<void> {
    if (loadPromise) return loadPromise
    loading.value = true
    error.value = null
    loadPromise = (async () => {
      try {
        const context = await getSemesterContext()
        if (!context || typeof context.revision !== 'number' || !('current_semester' in context)) {
          throw new Error('semester-context-unavailable')
        }
        applyContext(context)
        authoritative.value = true
        if (context.can_switch) {
          semesters.value = await listSemesters()
        }
        loaded.value = true
      } catch (cause) {
        authoritative.value = false
        try {
          // Keep older frontend deployments usable during a rolling backend upgrade.
          applyLegacyFallback(await listSemesters())
          error.value = null
        } catch {
          error.value = apiErrorMessage(cause, '无法读取当前学期，请刷新后重试。')
        }
        loaded.value = true
      } finally {
        loading.value = false
      }
    })()
    try {
      await loadPromise
    } finally {
      loadPromise = null
    }
  }

  async function switchTo(semesterId: number): Promise<void> {
    if (!canSwitch.value || semesterId === currentSemesterId.value || switching.value) return
    switching.value = true
    error.value = null
    try {
      const context = await switchSemesterContext(semesterId, revision.value)
      applyContext(context)
      if (context.can_switch) semesters.value = await listSemesters()
    } catch (cause) {
      // A stale browser must not keep presenting an old writable context.
      const apiCause = cause as Partial<ApiError>
      if (apiCause.status === 409) await load()
      error.value = apiErrorMessage(cause, '当前学期切换失败，请刷新后重试。')
      throw cause
    } finally {
      switching.value = false
    }
  }

  function isCurrent(semesterId: number | null | undefined): boolean {
    return semesterId !== null && semesterId !== undefined && semesterId === currentSemesterId.value
  }

  return {
    currentSemester,
    currentSemesterId,
    semesters,
    revision,
    canSwitch,
    loaded,
    authoritative,
    loading,
    switching,
    error,
    load,
    switchTo,
    isCurrent,
  }
})
