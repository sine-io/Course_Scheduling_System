// 简易 API client。所有请求带 cookie(credentials: include)以保持 session。

export interface ApiError extends Error {
  status: number
  detail?: unknown
}

function apiDetailMessage(detail: unknown): string {
  if (typeof detail === 'string' && detail) return detail
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const message = (detail as { message?: unknown }).message
    if (typeof message === 'string' && message) return message
  }
  return ''
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  const value = error as Partial<ApiError> & { message?: unknown; detail?: unknown } | null
  const detailMessage = apiDetailMessage(value?.detail)
  if (detailMessage) return detailMessage
  return typeof value?.message === 'string' && value.message ? value.message : fallback
}

export async function apiErrorFromResponse(
  response: Response,
  fallback: string,
): Promise<ApiError> {
  let detail: unknown
  try {
    detail = (await response.json())?.detail
  } catch {
    detail = undefined
  }
  const error = new Error(apiDetailMessage(detail) || fallback) as ApiError
  error.status = response.status
  error.detail = detail
  return error
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
    if (resp.status === 401 && !path.startsWith('/auth/')) {
      unauthorizedHandler?.()
    }
    throw await apiErrorFromResponse(resp, `API 错误 ${resp.status}`)
  }
  if (resp.status === 204) return undefined as T
  return resp.json() as Promise<T>
}

export const apiGet = <T>(path: string): Promise<T> => request<T>('GET', path)
export const apiPost = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>('POST', path, body)
export const apiPut = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>('PUT', path, body)
export const apiDelete = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>('DELETE', path, body)
