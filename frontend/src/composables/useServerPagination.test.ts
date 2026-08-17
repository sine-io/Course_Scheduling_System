import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, onMounted } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'
import type { Page } from '@/api/pagination'
import { useServerPagination } from './useServerPagination'


interface Row {
  id: number
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

async function mountPager(
  fetchPage: (request: { page: number, pageSize: number }) => Promise<Page<Row>>,
  path = '/list',
  enabledPath?: string,
) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/list', component: { render: () => h('main') } },
      { path: '/other', component: { render: () => h('main') } },
    ],
  })
  await router.push(path)
  await router.isReady()
  let pager!: ReturnType<typeof useServerPagination<Row>>
  const Harness = defineComponent({
    setup() {
      pager = useServerPagination<Row>({
        fetchPage,
        errorMessage: (error) => String(error),
        enabled: enabledPath ? () => router.currentRoute.value.path === enabledPath : undefined,
        queryPrefix: 'test',
        additionalRouteKeys: ['test_q'],
      })
      onMounted(() => void pager.initialize())
      return () => h('main')
    },
  })
  const wrapper = mount(Harness, { global: { plugins: [router] } })
  await flushPromises()
  return { pager, router, wrapper }
}

describe('useServerPagination', () => {
  it('规范化 URL，并区分翻页 push 与筛选、页容量 replace', async () => {
    const fetchPage = vi.fn(async ({ page, pageSize }) => ({
      items: [{ id: page }], total: 80, page, page_size: pageSize,
    }))
    const { pager, router } = await mountPager(
      fetchPage,
      '/list?test_page=bad&test_page_size=50',
    )
    const push = vi.spyOn(router, 'push')
    const replace = vi.spyOn(router, 'replace')

    expect(router.currentRoute.value.query).toMatchObject({
      test_page: '1',
      test_page_size: '50',
    })
    expect(fetchPage).toHaveBeenLastCalledWith({ page: 1, pageSize: 50 })

    await pager.setPage(2)
    await flushPromises()
    expect(push).toHaveBeenCalled()
    expect(router.currentRoute.value.query.test_page).toBe('2')
    expect(fetchPage).toHaveBeenLastCalledWith({ page: 2, pageSize: 50 })

    await pager.setPageSize(20)
    await flushPromises()
    expect(replace).toHaveBeenCalled()
    expect(router.currentRoute.value.query).toMatchObject({
      test_page: '1',
      test_page_size: '20',
    })

    await pager.replaceQuery({ test_q: '删除科目' })
    await flushPromises()
    expect(router.currentRoute.value.query).toMatchObject({
      test_page: '1',
      test_q: '删除科目',
    })
  })

  it('越界时跳到最后一页并重新读取', async () => {
    const fetchPage = vi.fn(async ({ page, pageSize }) => ({
      items: page === 2 ? [{ id: 21 }] : [],
      total: 21,
      page,
      page_size: pageSize,
    }))
    const { pager, router } = await mountPager(
      fetchPage,
      '/list?test_page=99&test_page_size=20',
    )
    await flushPromises()

    expect(router.currentRoute.value.query.test_page).toBe('2')
    expect(fetchPage).toHaveBeenLastCalledWith({ page: 2, pageSize: 20 })
    expect(pager.items.value).toEqual([{ id: 21 }])
  })

  it('空结果的越界页回到第一页', async () => {
    const fetchPage = vi.fn(async ({ page, pageSize }) => ({
      items: [], total: 0, page, page_size: pageSize,
    }))
    const { router } = await mountPager(
      fetchPage,
      '/list?test_page=99&test_page_size=20',
    )
    await flushPromises()

    expect(router.currentRoute.value.query.test_page).toBe('1')
    expect(fetchPage).toHaveBeenLastCalledWith({ page: 1, pageSize: 20 })
  })

  it('丢弃迟到响应，失败时保留最后一次成功结果', async () => {
    const first = deferred<Page<Row>>()
    const second = deferred<Page<Row>>()
    const fetchPage = vi.fn()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
      .mockRejectedValueOnce(new Error('暂时不可用'))
    const { pager } = await mountPager(fetchPage)

    await pager.setPage(2)
    await flushPromises()
    second.resolve({ items: [{ id: 2 }], total: 40, page: 2, page_size: 20 })
    await flushPromises()
    first.resolve({ items: [{ id: 1 }], total: 40, page: 1, page_size: 20 })
    await flushPromises()

    expect(pager.items.value).toEqual([{ id: 2 }])
    await pager.reload()
    expect(pager.items.value).toEqual([{ id: 2 }])
    expect(pager.error.value).toContain('暂时不可用')
  })

  it('停用后不把分页参数带到其他页面，并丢弃在途响应', async () => {
    const pending = deferred<Page<Row>>()
    const fetchPage = vi.fn(() => pending.promise)
    const { pager, router } = await mountPager(fetchPage, '/list', '/list')

    expect(router.currentRoute.value.query).toMatchObject({
      test_page: '1',
      test_page_size: '20',
    })
    await router.push('/other')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({})
    expect(pager.loading.value).toBe(false)

    pending.resolve({ items: [{ id: 1 }], total: 1, page: 1, page_size: 20 })
    await flushPromises()
    expect(pager.items.value).toEqual([])
    expect(fetchPage).toHaveBeenCalledTimes(1)
  })
})
