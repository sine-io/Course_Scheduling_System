import { computed, ref, watch } from 'vue'
import type { LocationQueryRaw } from 'vue-router'
import { useRoute, useRouter } from 'vue-router'
import type { Page, PageRequest } from '@/api/pagination'
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from '@/api/pagination'

interface ServerPaginationOptions<T> {
  fetchPage: (request: PageRequest) => Promise<Page<T>>
  errorMessage: (error: unknown) => string
  enabled?: () => boolean
  queryPrefix?: string
  additionalRouteKeys?: readonly string[]
  defaultPageSize?: number
  pageSizes?: readonly number[]
}

type QueryUpdate = string | number | null | undefined

function queryString(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function positiveInteger(value: unknown): number | null {
  const raw = queryString(value)
  if (raw === null || !/^\d+$/.test(raw)) return null
  const parsed = Number(raw)
  return Number.isSafeInteger(parsed) && parsed >= 1 ? parsed : null
}

export function useServerPagination<T>(options: ServerPaginationOptions<T>) {
  const route = useRoute()
  const router = useRouter()
  const prefix = options.queryPrefix ? `${options.queryPrefix}_` : ''
  const pageKey = `${prefix}page`
  const pageSizeKey = `${prefix}page_size`
  const pageSizes = [...(options.pageSizes ?? PAGE_SIZE_OPTIONS)]
  const defaultPageSize = pageSizes.includes(options.defaultPageSize ?? DEFAULT_PAGE_SIZE)
    ? (options.defaultPageSize ?? DEFAULT_PAGE_SIZE)
    : pageSizes[0]
  const trackedKeys = [pageKey, pageSizeKey, ...(options.additionalRouteKeys ?? [])]
  const enabled = computed(() => options.enabled?.() ?? true)

  const items = ref<T[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(defaultPageSize)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const initialized = ref(false)
  let requestSequence = 0

  const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

  function readRouteState() {
    const routePage = positiveInteger(route.query[pageKey]) ?? 1
    const candidateSize = positiveInteger(route.query[pageSizeKey])
    return {
      page: routePage,
      pageSize: candidateSize !== null && pageSizes.includes(candidateSize)
        ? candidateSize
        : defaultPageSize,
    }
  }

  function fingerprint(): string {
    return JSON.stringify(trackedKeys.map((key) => route.query[key] ?? null))
  }

  async function normalizeRoute(): Promise<void> {
    const next = readRouteState()
    page.value = next.page
    pageSize.value = next.pageSize
    if (
      queryString(route.query[pageKey]) === String(next.page)
      && queryString(route.query[pageSizeKey]) === String(next.pageSize)
    ) return
    await router.replace({
      query: {
        ...route.query,
        [pageKey]: String(next.page),
        [pageSizeKey]: String(next.pageSize),
      },
    })
  }

  async function load(): Promise<void> {
    if (!enabled.value) return
    const requestId = ++requestSequence
    const requestedPage = page.value
    const requestedPageSize = pageSize.value
    loading.value = true
    error.value = null
    try {
      const result = await options.fetchPage({
        page: requestedPage,
        pageSize: requestedPageSize,
      })
      if (requestId !== requestSequence) return

      const lastPage = Math.max(1, Math.ceil(result.total / requestedPageSize))
      if (requestedPage > lastPage) {
        total.value = result.total
        await router.replace({
          query: { ...route.query, [pageKey]: String(lastPage) },
        })
        return
      }

      items.value = result.items
      total.value = result.total
    } catch (loadError) {
      if (requestId === requestSequence) error.value = options.errorMessage(loadError)
    } finally {
      if (requestId === requestSequence) loading.value = false
    }
  }

  async function initialize(): Promise<void> {
    if (!enabled.value) return
    if (initialized.value) {
      await load()
      return
    }
    await normalizeRoute()
    const next = readRouteState()
    page.value = next.page
    pageSize.value = next.pageSize
    initialized.value = true
    await load()
  }

  async function setPage(nextPage: number): Promise<void> {
    if (!enabled.value) return
    if (nextPage === page.value) {
      await load()
      return
    }
    await router.push({ query: { ...route.query, [pageKey]: String(nextPage) } })
  }

  async function setPageSize(nextPageSize: number): Promise<void> {
    if (!enabled.value) return
    if (!pageSizes.includes(nextPageSize)) return
    const before = fingerprint()
    await router.replace({
      query: {
        ...route.query,
        [pageKey]: '1',
        [pageSizeKey]: String(nextPageSize),
      },
    })
    if (before === fingerprint() && initialized.value) await load()
  }

  async function replaceQuery(
    updates: Record<string, QueryUpdate>,
    resetPage = true,
  ): Promise<void> {
    if (!enabled.value) return
    const nextQuery: LocationQueryRaw = { ...route.query }
    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === undefined || value === '') delete nextQuery[key]
      else nextQuery[key] = String(value)
    }
    if (resetPage) nextQuery[pageKey] = '1'

    const before = fingerprint()
    await router.replace({ query: nextQuery })
    if (before === fingerprint() && initialized.value) await load()
  }

  watch(
    () => fingerprint(),
    async () => {
      if (!initialized.value || !enabled.value) return
      const next = readRouteState()
      const needsNormalization = (
        queryString(route.query[pageKey]) !== String(next.page)
        || queryString(route.query[pageSizeKey]) !== String(next.pageSize)
      )
      page.value = next.page
      pageSize.value = next.pageSize
      if (needsNormalization) {
        await normalizeRoute()
        return
      }
      await load()
    },
  )

  watch(enabled, (isEnabled) => {
    if (isEnabled) return
    requestSequence += 1
    loading.value = false
  })

  return {
    items,
    total,
    page,
    pageSize,
    pageCount,
    pageSizes,
    loading,
    error,
    initialized,
    enabled,
    initialize,
    reload: load,
    setPage,
    setPageSize,
    replaceQuery,
  }
}
