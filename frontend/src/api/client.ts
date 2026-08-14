// 简易 API client。所有请求带 cookie(credentials: include)以保持 session。

export interface ApiError extends Error {
  status: number
  detail?: unknown
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  const value = error as Partial<ApiError> & { message?: unknown; detail?: unknown } | null
  if (typeof value?.detail === 'string' && value.detail) return value.detail
  if (value?.detail && typeof value.detail === 'object' && 'message' in value.detail) {
    const detailMessage = (value.detail as { message?: unknown }).message
    if (typeof detailMessage === 'string' && detailMessage) return detailMessage
  }
  return typeof value?.message === 'string' && value.message ? value.message : fallback
}

// 全域 401 处理器(由 main.ts 注册):session 过期/被撤销时清除登录状态并导回登录页。
// 认证管理端点(/auth/*)的 401 由调用方自行处理,不触发全域导向,避免重导循环。
let unauthorizedHandler: (() => void) | null = null
export function setUnauthorizedHandler(fn: () => void): void {
  unauthorizedHandler = fn
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!resp.ok) {
    let detail: unknown
    try {
      detail = (await resp.json())?.detail
    } catch {
      detail = undefined
    }
    if (resp.status === 401 && !path.startsWith('/auth/')) {
      unauthorizedHandler?.()
    }
    const detailMessage = typeof detail === 'string'
      ? detail
      : detail && typeof detail === 'object' && 'message' in detail
        ? String((detail as { message?: unknown }).message ?? '')
        : ''
    const err = new Error(detailMessage || `API 错误 ${resp.status}`) as ApiError
    err.status = resp.status
    err.detail = detail
    throw err
  }
  if (resp.status === 204) return undefined as T
  return resp.json() as Promise<T>
}

export const apiGet = <T>(path: string): Promise<T> => request<T>('GET', path)
export const apiPost = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>('POST', path, body)
export const apiPut = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>('PUT', path, body)
export const apiDelete = <T>(path: string): Promise<T> => request<T>('DELETE', path)
